import { DuckDBInstance } from "@duckdb/node-api"
import type { DatabaseAdapter } from "./types"
import type { TableSchema, QueryResult } from "@chat-database/shared"

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
      // DuckDBInstance.create(path, options) — options supports READ_ONLY via
      // the second arg as an object: { readOnly: true } in current API,
      // or via "READ_ONLY" string in older API. We use the broader form.
      // See https://duckdb.org/docs/current/clients/node_neo/overview.html
      if (this.readOnly) {
        // Try the official options-object form; fall back to string if needed
        try {
          this.instance = await DuckDBInstance.create(this.filePath, { readOnly: true } as any)
        } catch {
          this.instance = await DuckDBInstance.create(this.filePath, "READ_ONLY" as any)
        }
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
          await conn.close()
        } catch {
          // Swallow close errors
        }
      }
    }
  }

  async getSchema(): Promise<TableSchema[]> {
    /**
     * DuckDB exposes schema via duckdb_tables() + duckdb_columns() system functions.
     * Filters out internal schemas (pg_catalog, information_schema, system).
     */
    const sql = `
      SELECT
        t.schema_name AS schema_name,
        t.table_name AS table_name,
        c.column_name AS column_name,
        c.data_type AS data_type,
        c.is_nullable AS is_nullable
      FROM duckdb_tables() t
      JOIN duckdb_columns() c
        ON t.schema_name = c.schema_name AND t.table_name = c.table_name
      WHERE t.schema_name NOT IN ('pg_catalog', 'information_schema', 'system', 'main')
         OR t.schema_name = 'main'
      ORDER BY t.schema_name, t.table_name, c.column_index
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
        // Include schema prefix when not 'main' to avoid collisions
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
          await conn.close()
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
          await conn.close()
        } catch {
          // Swallow
        }
      }
    }
  }

  async close(): Promise<void> {
    // DuckDBInstance has no explicit close in @duckdb/node-api current API;
    // connections are closed per-query. Instance is GC'd.
    this.instance = null
  }
}
