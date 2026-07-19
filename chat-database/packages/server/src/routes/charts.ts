import { Hono } from "hono"
import { db } from "../db/connection"
import { customCharts, users } from "../db/schema"
import { eq, desc } from "drizzle-orm"

export const chartRoutes = new Hono()

// Helper: serialize a chart row
function serializeChart(chart: typeof customCharts.$inferSelect & { creator?: typeof users.$inferSelect | null }) {
  return {
    id: String(chart.id),
    name: chart.name,
    sql: chart.sql,
    chartConfig: JSON.parse(chart.chartConfig),
    databaseId: chart.databaseId ? String(chart.databaseId) : null,
    createdAt: chart.createdAt,
    updatedAt: chart.updatedAt,
    creator: chart.creator
      ? { id: String(chart.creator.id), name: chart.creator.name, email: chart.creator.email }
      : null,
  }
}

// GET /custom-charts
chartRoutes.get("/", async (c) => {
  const rows = await db.select({
    id: customCharts.id,
    name: customCharts.name,
    databaseId: customCharts.databaseId,
    createdAt: customCharts.createdAt,
    updatedAt: customCharts.updatedAt,
    creatorId: users.id,
    creatorName: users.name,
    creatorEmail: users.email,
  })
    .from(customCharts)
    .leftJoin(users, eq(customCharts.createdBy, users.id))
    .orderBy(desc(customCharts.updatedAt))

  return c.json({
    charts: rows.map((r) => ({
      id: String(r.id),
      name: r.name,
      databaseId: r.databaseId ? String(r.databaseId) : null,
      createdAt: r.createdAt,
      updatedAt: r.updatedAt,
      creator: r.creatorId
        ? { id: String(r.creatorId), name: r.creatorName!, email: r.creatorEmail! }
        : null,
    })),
  })
})

// GET /custom-charts/:id
chartRoutes.get("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const chart = await db.select().from(customCharts).where(eq(customCharts.id, id)).get()

  if (!chart) {
    return c.json({ error: "Chart not found" }, 404)
  }

  if (chart.createdBy && chart.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  const creator = chart.createdBy
    ? await db.select().from(users).where(eq(users.id, chart.createdBy)).get()
    : null

  return c.json({
    chart: serializeChart({ ...chart, creator }),
  })
})

// POST /custom-charts
chartRoutes.post("/", async (c) => {
  const user = c.get("user")
  const { name, sql, chartConfig, databaseId } = await c.req.json()

  if (!name || !sql || !chartConfig) {
    return c.json({ error: "Name, sql, and chartConfig are required" }, 400)
  }

  const chart = await db.insert(customCharts).values({
    name,
    sql,
    chartConfig: JSON.stringify(chartConfig),
    databaseId: databaseId ? Number(databaseId) : null,
    createdBy: user.id,
  }).returning().get()

  const creator = await db.select().from(users).where(eq(users.id, user.id)).get()

  return c.json({
    success: true,
    chart: serializeChart({ ...chart, creator }),
  })
})

// PUT /custom-charts/:id
chartRoutes.put("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const { name, sql, chartConfig, databaseId } = await c.req.json()

  if (!name || !sql || !chartConfig) {
    return c.json({ error: "Missing required fields: name, sql, chartConfig" }, 400)
  }

  const existing = await db.select().from(customCharts).where(eq(customCharts.id, id)).get()
  if (!existing) {
    return c.json({ error: "Chart not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  const chart = await db.update(customCharts).set({
    name,
    sql,
    chartConfig: JSON.stringify(chartConfig),
    databaseId: databaseId ? Number(databaseId) : null,
    updatedAt: new Date().toISOString(),
  }).where(eq(customCharts.id, id)).returning().get()

  const creator = chart.createdBy
    ? await db.select().from(users).where(eq(users.id, chart.createdBy)).get()
    : null

  return c.json({
    success: true,
    chart: serializeChart({ ...chart, creator }),
  })
})

// DELETE /custom-charts/:id
chartRoutes.delete("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))

  const existing = await db.select().from(customCharts).where(eq(customCharts.id, id)).get()
  if (!existing) {
    return c.json({ error: "Chart not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  await db.delete(customCharts).where(eq(customCharts.id, id))
  return c.json({ success: true })
})
