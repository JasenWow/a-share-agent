import { tool } from "ai"
import { z } from "zod"
import { poolManager } from "../../adapters/pool-manager"
import { sqlite } from "../../db/connection"

export function createQueryDatabaseTool(databaseId: string | null) {
  return tool({
    description: "Execute a SQL query against the database. Use this to validate queries before presenting them to the user.",
    parameters: z.object({
      sql: z.string().describe("The SQL query to execute"),
    }),
    execute: async ({ sql }) => {
      try {
        if (databaseId) {
          const adapter = await poolManager.getAdapter(databaseId)
          const result = await adapter.executeQuery(sql)
          return { success: true, ...result }
        } else {
          // System database (SQLite) — only allow read-only queries
          const isSelect = /^\s*(SELECT|PRAGMA)/i.test(sql)
          if (!isSelect) {
            return { success: false, error: "Only SELECT and PRAGMA queries are allowed on the system database" }
          }

          const stmt = sqlite.prepare(sql)
          const rows = stmt.all() as Record<string, unknown>[]
          const columns = rows.length > 0 ? Object.keys(rows[0]) : []
          return { success: true, columns, rows, rowCount: rows.length }
        }
      } catch (error) {
        return { success: false, error: (error as Error).message }
      }
    },
  })
}
