import { sqlite } from "../db/connection"
import type { TableSchema } from "@aquan/core"

/**
 * Escape a SQLite identifier (table/column name) for use in PRAGMA statements.
 * PRAGMA does not support parameterized queries, so we validate and escape the name.
 */
export function escapeSqliteIdentifier(name: string): string {
  if (/[;"'\\]/.test(name)) {
    throw new Error(`Invalid table name: ${name}`)
  }
  return `"${name.replace(/"/g, '""')}"`
}

export function getSystemSchema(): TableSchema[] {
  const tables = sqlite
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '__drizzle_%' ORDER BY name")
    .all() as { name: string }[]

  return tables.map((table) => {
    const columns = sqlite
      .prepare(`PRAGMA table_info(${escapeSqliteIdentifier(table.name)})`)
      .all() as { name: string; type: string; notnull: number }[]

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
