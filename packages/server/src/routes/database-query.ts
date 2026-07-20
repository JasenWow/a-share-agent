import { Hono } from "hono"
import { poolManager } from "../adapters/pool-manager"
import { sqlite } from "../db/connection"
import type { TableSchema, QueryResult } from "@aquan/core"
import { getSystemSchema } from "../lib/system-schema"

export const databaseQueryRoutes = new Hono()

// GET /database/schema
databaseQueryRoutes.get("/schema", async (c) => {
  const databaseId = c.req.query("databaseId")

  try {
    let schema: TableSchema[]

    if (databaseId) {
      const adapter = await poolManager.getAdapter(databaseId)
      schema = await adapter.getSchema()
    } else {
      // System database schema introspection (SQLite)
      schema = getSystemSchema()
    }

    return c.json({ schema })
  } catch (error) {
    console.error("Failed to fetch database schema:", error)
    return c.json({ error: "Failed to fetch database schema" }, 500)
  }
})

// POST /database/query
databaseQueryRoutes.post("/query", async (c) => {
  const { sql, databaseId } = await c.req.json()

  if (!sql || typeof sql !== "string") {
    return c.json({ error: "SQL query is required" }, 400)
  }

  try {
    let result: QueryResult

    if (databaseId) {
      const adapter = await poolManager.getAdapter(databaseId)
      result = await adapter.executeQuery(sql)
    } else {
      // System database query (SQLite)
      result = executeSystemQuery(sql)
    }

    return c.json(result)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Failed to execute query"
    return c.json({ error: errorMessage }, 500)
  }
})

// System SQLite helpers
function executeSystemQuery(sql: string): QueryResult {
  const isSelect = /^\s*(SELECT|PRAGMA)/i.test(sql)
  if (!isSelect) {
    throw new Error("Only SELECT and PRAGMA queries are allowed on the system database")
  }

  const stmt = sqlite.prepare(sql)
  const rows = stmt.all() as Record<string, unknown>[]
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []
  // Serialize BigInt values
  const serializedRows = rows.map((row) => {
    const serialized: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(row)) {
      if (typeof value === "bigint") serialized[key] = value.toString()
      else if (value instanceof Date) serialized[key] = value.toISOString()
      else serialized[key] = value
    }
    return serialized
  })
  return { columns, rows: serializedRows, rowCount: serializedRows.length }
}
