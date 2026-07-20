import { DuckDBInstance } from "@duckdb/node-api"
import type { DatabaseAdapter } from "./types"
import type { TableSchema, QueryResult } from "@aquan/core"

/**
 * DuckDB Adapter — connects to the a-share-agents DuckDB warehouse.
 *
 * Read-only by design (BI consumption pattern):
 *   - The DuckDB file is written by a-share-agents ETL (Python side)
 *   - chat-database only reads; concurrent reads are safe in DuckDB
 *   - Avoids write contention with ETL
 *
 * Runtime note (R4 from integration spec):
 *   @duckdb/node-api is a native Node-API addon. Bun's N-API support has
 *   improved through 2025-2026 but database drivers can still be a pain
 *   point. If Bun runtime fails to load the native binding, run the server
 *   under Node.js instead (chat-database server is Bun-first but Node-compatible).
 */

function serializeRow(row: Record<string, unknown>): Record<string, unknown> {
  const serialized: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    if (typeof value === "bigint") {
      serialized[key] = value.toString()
    } else if (value instanceof Date) {
      serialized[key] = value.toISOString()
    } else if (value && typeof value === "object" && "toString" in value) {
      // DuckDB may return decimal/timestamp wrapper objects
      serialized[key] = String(value)
    } else {
      serialized[key] = value
    }
  }
  return serialized
}

export class DuckDBAdapter implements DatabaseAdapter {
  private instance: Awaited<ReturnType<DuckDBInstance["create"]>> | null = null
  private readonly filePath: string
  private readonly readOnly: boolean

  constructor(filePath: string, readOnly = true) {
    if (!filePath) {
      throw new Error("DuckDBAdapter requires a file path")
    }
    this.filePath = filePath
    this.readOnly = readOnly
  }

  private async getConnection() {
    if (!this.instance) {
      // @duckdb/node-api option syntax (verified under Bun 1.3.14):
      //   DuckDBInstance.create(path, { access_mode: "READ_ONLY" })
      // Common wrong guesses that DON'T work: { readOnly: true }, "READ_ONLY",
      // "access_mode=READ_ONLY". See probe in commit history.
      if (this.readOnly) {
        this.instance = await DuckDBInstance.create(this.filePath, { access_mode: "READ_ONLY" })
      } else {
        this.instance = await DuckDBInstance.create(this.filePath)
      }
    }
    const conn = await this.instance.connect()
    return conn
  }

  async executeQuery(sql: string): Promise<QueryResult> {
    let conn: Awaited<ReturnType<typeof this.getConnection>> | null = null
    try {
      conn = await this.getConnection()
      // DuckDB reader: arrow table; we convert to plain objects
      const reader = await conn.runAndReadAll(sql)
      const arrowTable = reader.getRowObjects()
      const rows = (arrowTable as Record<string, unknown>[]).map(serializeRow)
      const columns = rows.length > 0 ? Object.keys(rows[0]) : []
      return { columns, rows, rowCount: rows.length }
    } catch (error) {
      throw new Error(`DuckDB query error: ${(error as Error).message}`)
    } finally {
      if (conn) {
        try {
          conn.closeSync()
        } catch {
          // Swallow close errors
        }
      }
    }
  }

  async getSchema(): Promise<TableSchema[]> {
    /**
     * Use information_schema.columns (DuckDB supports the SQL standard).
     * Filters out internal schemas (pg_catalog, information_schema, system, temp).
     * For dbt-created schemas (dwd/dws/ads), prefix the table name with schema.
     */
    const sql = `
      SELECT
        table_schema AS schema_name,
        table_name,
        column_name,
        data_type,
        is_nullable
      FROM information_schema.columns
      WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'system', 'temp', 'main')
         OR table_schema = 'main'
      ORDER BY table_schema, table_name, ordinal_position
    `
    let conn: Awaited<ReturnType<typeof this.getConnection>> | null = null
    try {
      conn = await this.getConnection()
      const reader = await conn.runAndReadAll(sql)
      const rows = reader.getRowObjects() as Array<{
        schema_name: string
        table_name: string
        column_name: string
        data_type: string
        is_nullable: string
      }>

      const schemaMap = new Map<string, TableSchema>()
      for (const row of rows) {
        const qualifiedName =
          row.schema_name === "main" ? row.table_name : `${row.schema_name}.${row.table_name}`
        if (!schemaMap.has(qualifiedName)) {
          schemaMap.set(qualifiedName, { name: qualifiedName, columns: [] })
        }
        schemaMap.get(qualifiedName)!.columns.push({
          name: row.column_name,
          type: row.data_type,
          nullable: row.is_nullable === "YES",
        })
      }
      return Array.from(schemaMap.values())
    } catch (error) {
      throw new Error(`DuckDB schema introspection error: ${(error as Error).message}`)
    } finally {
      if (conn) {
        try {
          conn.closeSync()
        } catch {
          // Swallow
        }
      }
    }
  }

  async testConnection(): Promise<boolean> {
    let conn: Awaited<ReturnType<typeof this.getConnection>> | null = null
    try {
      conn = await this.getConnection()
      await conn.runAndReadAll("SELECT 1")
      return true
    } catch {
      return false
    } finally {
      if (conn) {
        try {
          conn.closeSync()
        } catch {
          // Swallow
        }
      }
    }
  }

  async close(): Promise<void> {
    // @duckdb/node-api uses closeSync for both instance and connection.
    // We close the instance (which terminates its connections) and clear it.
    if (this.instance) {
      try {
        this.instance.closeSync()
      } catch {
        // Swallow
      }
      this.instance = null
    }
  }
}
