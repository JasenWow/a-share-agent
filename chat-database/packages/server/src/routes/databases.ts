import { Hono } from "hono"
import { db } from "../db/connection"
import { externalDatabases, customCharts } from "../db/schema"
import { eq, desc } from "drizzle-orm"
import { createAdapter } from "../adapters/factory"
import { poolManager } from "../adapters/pool-manager"
import type { ExternalDbConfig } from "@chat-database/shared"

export const databaseRoutes = new Hono()

// GET /databases
databaseRoutes.get("/", async (c) => {
  const rows = await db.select({
    id: externalDatabases.id,
    name: externalDatabases.name,
    dbType: externalDatabases.dbType,
    host: externalDatabases.host,
    port: externalDatabases.port,
    database: externalDatabases.database,
    username: externalDatabases.username,
    sslEnabled: externalDatabases.sslEnabled,
    filePath: externalDatabases.filePath,
    createdBy: externalDatabases.createdBy,
    createdAt: externalDatabases.createdAt,
    updatedAt: externalDatabases.updatedAt,
  }).from(externalDatabases).orderBy(desc(externalDatabases.updatedAt))

  return c.json({
    databases: rows.map((r) => ({
      id: String(r.id),
      name: r.name,
      dbType: r.dbType,
      host: r.host,
      port: r.port,
      database: r.database,
      username: r.username,
      // Never send password to frontend
      sslEnabled: r.sslEnabled,
      filePath: r.filePath,
      createdBy: r.createdBy ? String(r.createdBy) : null,
      createdAt: r.createdAt,
      updatedAt: r.updatedAt,
    })),
  })
})

// GET /databases/:id
databaseRoutes.get("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const row = await db.select().from(externalDatabases).where(eq(externalDatabases.id, id)).get()

  if (!row) {
    return c.json({ error: "Database not found" }, 404)
  }

  if (row.createdBy && row.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  return c.json({
    database: {
      id: String(row.id),
      name: row.name,
      dbType: row.dbType,
      host: row.host,
      port: row.port,
      database: row.database,
      username: row.username,
      sslEnabled: row.sslEnabled,
      filePath: row.filePath,
      createdBy: row.createdBy ? String(row.createdBy) : null,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
    },
  })
})

// POST /databases
databaseRoutes.post("/", async (c) => {
  const user = c.get("user")
  const body = await c.req.json()
  const { name, dbType, host, port, database, username, password, sslEnabled, filePath } = body

  if (!name || !host) {
    return c.json({ error: "Name and host are required" }, 400)
  }

  const row = await db.insert(externalDatabases).values({
    name,
    dbType: dbType || "postgresql",
    host,
    port: port || 5432,
    database: database || "",
    username: username || "",
    password: password || "",
    sslEnabled: sslEnabled || false,
    filePath: filePath || null,
    createdBy: user.id,
  }).returning().get()

  return c.json({
    database: {
      id: String(row.id),
      name: row.name,
      dbType: row.dbType,
      host: row.host,
      port: row.port,
      database: row.database,
      username: row.username,
      sslEnabled: row.sslEnabled,
      filePath: row.filePath,
      createdBy: row.createdBy ? String(row.createdBy) : null,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
    },
  })
})

// PUT /databases/:id
databaseRoutes.put("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const body = await c.req.json()

  const existing = await db.select().from(externalDatabases).where(eq(externalDatabases.id, id)).get()
  if (!existing) {
    return c.json({ error: "Database not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  const updates: Record<string, unknown> = { updatedAt: new Date().toISOString() }
  if (body.name !== undefined) updates.name = body.name
  if (body.dbType !== undefined) updates.dbType = body.dbType
  if (body.host !== undefined) updates.host = body.host
  if (body.port !== undefined) updates.port = body.port
  if (body.database !== undefined) updates.database = body.database
  if (body.username !== undefined) updates.username = body.username
  if (body.password !== undefined) updates.password = body.password
  if (body.sslEnabled !== undefined) updates.sslEnabled = body.sslEnabled
  if (body.filePath !== undefined) updates.filePath = body.filePath

  const row = await db.update(externalDatabases).set(updates).where(eq(externalDatabases.id, id)).returning().get()

  // Invalidate cached adapter
  await poolManager.invalidate(String(id))

  return c.json({
    database: {
      id: String(row.id),
      name: row.name,
      dbType: row.dbType,
      host: row.host,
      port: row.port,
      database: row.database,
      username: row.username,
      sslEnabled: row.sslEnabled,
      filePath: row.filePath,
      createdBy: row.createdBy ? String(row.createdBy) : null,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
    },
  })
})

// DELETE /databases/:id
databaseRoutes.delete("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))

  const existing = await db.select().from(externalDatabases).where(eq(externalDatabases.id, id)).get()
  if (!existing) {
    return c.json({ error: "Database not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  // Check for associated charts
  const charts = await db.select({ id: customCharts.id }).from(customCharts)
    .where(eq(customCharts.databaseId, id)).all()

  if (charts.length > 0) {
    return c.json({ error: `Cannot delete: ${charts.length} chart(s) are linked to this database` }, 400)
  }

  await db.delete(externalDatabases).where(eq(externalDatabases.id, id))
  await poolManager.invalidate(String(id))

  return c.json({ success: true })
})

// POST /databases/test
databaseRoutes.post("/test", async (c) => {
  const body = await c.req.json()
  const { dbType, host, port, database, username, password, sslEnabled, filePath } = body

  try {
    const config: ExternalDbConfig = {
      type: dbType || "postgresql",
      host, port, database, username, password, sslEnabled, filePath,
    }
    const adapter = createAdapter(config)
    const success = await adapter.testConnection()
    await adapter.close()

    if (success) {
      return c.json({ success: true, message: "Connection successful" })
    } else {
      return c.json({ success: false, error: "Failed to connect to database" }, 400)
    }
  } catch (error) {
    return c.json({ success: false, error: (error as Error).message }, 400)
  }
})

// POST /databases/:id/test
databaseRoutes.post("/:id/test", async (c) => {
  const id = Number(c.req.param("id"))
  const row = await db.select().from(externalDatabases).where(eq(externalDatabases.id, id)).get()

  if (!row) {
    return c.json({ error: "Database not found" }, 404)
  }

  try {
    const adapter = await poolManager.getAdapter(String(id))
    const success = await adapter.testConnection()

    if (success) {
      return c.json({ success: true, message: "Connection successful" })
    } else {
      return c.json({ success: false, error: "Failed to connect to database" }, 400)
    }
  } catch (error) {
    return c.json({ success: false, error: (error as Error).message }, 400)
  }
})
