import { Pool } from "pg"
import type { DatabaseAdapter } from "./types"
import type { TableSchema, QueryResult } from "@aquan/core"

interface ConnectionConfig {
  host: string
  port: number
  database: string
  username: string
  password: string
  sslEnabled: boolean
}

function buildConnectionString(config: ConnectionConfig): string {
  const ssl = config.sslEnabled ? "?sslmode=require" : ""
  return `postgresql://${encodeURIComponent(config.username)}:${encodeURIComponent(config.password)}@${config.host}:${config.port}/${encodeURIComponent(config.database)}${ssl}`
}

function serializeRow(row: Record<string, unknown>): Record<string, unknown> {
  const serialized: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    if (typeof value === "bigint") {
      serialized[key] = value.toString()
    } else if (value instanceof Date) {
      serialized[key] = value.toISOString()
    } else {
      serialized[key] = value
    }
  }
  return serialized
}

export class PostgreSQLAdapter implements DatabaseAdapter {
  private pool: Pool

  constructor(config: ConnectionConfig) {
    this.pool = new Pool({
      connectionString: buildConnectionString(config),
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 10000,
    })
  }

  async executeQuery(sql: string): Promise<QueryResult> {
    const result = await this.pool.query(sql)
    const rows = result.rows.map(serializeRow)
    const columns = result.fields.map((f) => f.name)
    return { columns, rows, rowCount: rows.length }
  }

  async getSchema(): Promise<TableSchema[]> {
    const result = await this.pool.query<{
      table_name: string
      column_name: string
      data_type: string
      is_nullable: string
    }>(`
      SELECT
        t.table_name,
        c.column_name,
        c.data_type,
        c.is_nullable
      FROM information_schema.tables t
      JOIN information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
      WHERE t.table_schema = 'public'
        AND t.table_type = 'BASE TABLE'
      ORDER BY t.table_name, c.ordinal_position
    `)

    const schemaMap = new Map<string, TableSchema>()
    for (const row of result.rows) {
      if (!schemaMap.has(row.table_name)) {
        schemaMap.set(row.table_name, { name: row.table_name, columns: [] })
      }
      schemaMap.get(row.table_name)!.columns.push({
        name: row.column_name,
        type: row.data_type,
        nullable: row.is_nullable === "YES",
      })
    }
    return Array.from(schemaMap.values())
  }

  async testConnection(): Promise<boolean> {
    try {
      const client = await this.pool.connect()
      await client.query("SELECT 1")
      client.release()
      return true
    } catch {
      return false
    }
  }

  async close(): Promise<void> {
    await this.pool.end()
  }
}
