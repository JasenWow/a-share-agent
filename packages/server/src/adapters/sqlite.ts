import { Database } from "bun:sqlite"
import type { DatabaseAdapter } from "./types"
import type { TableSchema, QueryResult } from "@aquan/core"

export class SQLiteAdapter implements DatabaseAdapter {
  private db: Database

  constructor(filePath: string) {
    this.db = new Database(filePath, { readonly: true })
    this.db.exec("PRAGMA busy_timeout = 5000")
  }

  async executeQuery(sql: string): Promise<QueryResult> {
    try {
      const stmt = this.db.prepare(sql)
      const isSelect = /^\s*(SELECT|PRAGMA)/i.test(sql)
      let rows: Record<string, unknown>[]
      let rowCount: number

      if (isSelect) {
        rows = stmt.all() as Record<string, unknown>[]
        rowCount = rows.length
      } else {
        const info = stmt.run()
        rows = []
        rowCount = info.changes
      }

      const columns = rows.length > 0 ? Object.keys(rows[0]) : []
      return { columns, rows, rowCount }
    } catch (error) {
      throw new Error(`SQLite query error: ${(error as Error).message}`)
    }
  }

  async getSchema(): Promise<TableSchema[]> {
    const tables = this.db
      .prepare(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
      )
      .all() as { name: string }[]

    return tables.map((table) => {
      // Escape table name for PRAGMA (PRAGMA doesn't support parameters)
      const safeName = /[;"'\\]/.test(table.name)
        ? (() => { throw new Error(`Invalid table name: ${table.name}`) })()
        : `"${table.name.replace(/"/g, '""')}"`
      const columns = this.db
        .prepare(`PRAGMA table_info(${safeName})`)
        .all() as {
        name: string
        type: string
        notnull: number
        dflt_value: unknown
        pk: number
      }[]

      return {
        name: table.name,
        columns: columns.map((col) => ({
          name: col.name,
          type: col.type,
          nullable: col.notnull === 0,
        })),
      }
    })
  }

  async testConnection(): Promise<boolean> {
    try {
      this.db.prepare("SELECT 1").get()
      return true
    } catch {
      return false
    }
  }

  async close(): Promise<void> {
    this.db.close()
  }
}
