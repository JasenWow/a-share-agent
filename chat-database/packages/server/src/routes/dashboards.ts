import { Hono } from "hono"
import { db } from "../db/connection"
import { customDashboards, customCharts, users } from "../db/schema"
import { eq, desc, inArray } from "drizzle-orm"
import type { DashboardRenderConfig, DashboardChartItem } from "@chat-database/shared"

export const dashboardRoutes = new Hono()

// GET /dashboards
dashboardRoutes.get("/", async (c) => {
  const rows = await db.select({
    id: customDashboards.id,
    name: customDashboards.name,
    createdAt: customDashboards.createdAt,
    updatedAt: customDashboards.updatedAt,
    creatorId: users.id,
    creatorName: users.name,
    creatorEmail: users.email,
  })
    .from(customDashboards)
    .leftJoin(users, eq(customDashboards.createdBy, users.id))
    .orderBy(desc(customDashboards.updatedAt))

  return c.json({
    dashboards: rows.map((r) => ({
      id: String(r.id),
      name: r.name,
      createdAt: r.createdAt,
      updatedAt: r.updatedAt,
      creator: r.creatorId
        ? { id: String(r.creatorId), name: r.creatorName!, email: r.creatorEmail! }
        : null,
    })),
  })
})

// GET /dashboards/:id
dashboardRoutes.get("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const dashboard = await db.select().from(customDashboards).where(eq(customDashboards.id, id)).get()

  if (!dashboard) {
    return c.json({ error: "Dashboard not found" }, 404)
  }

  if (dashboard.createdBy && dashboard.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  const creator = dashboard.createdBy
    ? await db.select().from(users).where(eq(users.id, dashboard.createdBy)).get()
    : null

  const renderConfig: DashboardRenderConfig = JSON.parse(dashboard.renderConfig)

  // Fetch referenced charts
  const chartIds = renderConfig.charts.map((item: DashboardChartItem) => Number(item.chartId))
  const charts = chartIds.length > 0
    ? await db.select().from(customCharts).where(inArray(customCharts.id, chartIds))
    : []

  const chartMap = new Map(charts.map((ch) => [String(ch.id), ch]))

  const orderedCharts = renderConfig.charts
    .map((item: DashboardChartItem) => {
      const chart = chartMap.get(item.chartId)
      if (!chart) return null
      return {
        id: String(chart.id),
        name: chart.name,
        sql: chart.sql,
        chartConfig: JSON.parse(chart.chartConfig),
        databaseId: chart.databaseId ? String(chart.databaseId) : null,
        width: item.width,
      }
    })
    .filter(Boolean)

  return c.json({
    dashboard: {
      id: String(dashboard.id),
      name: dashboard.name,
      renderConfig,
      charts: orderedCharts,
      createdAt: dashboard.createdAt,
      updatedAt: dashboard.updatedAt,
      creator: creator
        ? { id: String(creator.id), name: creator.name, email: creator.email }
        : null,
    },
  })
})

// POST /dashboards
dashboardRoutes.post("/", async (c) => {
  const user = c.get("user")
  const { name, renderConfig } = await c.req.json()

  if (!name || !renderConfig) {
    return c.json({ error: "Name and renderConfig are required" }, 400)
  }

  const dashboard = await db.insert(customDashboards).values({
    name,
    renderConfig: JSON.stringify(renderConfig),
    createdBy: user.id,
  }).returning().get()

  const creator = await db.select().from(users).where(eq(users.id, user.id)).get()

  return c.json({
    success: true,
    dashboard: {
      id: String(dashboard.id),
      name: dashboard.name,
      createdAt: dashboard.createdAt,
      updatedAt: dashboard.updatedAt,
      creator: creator
        ? { id: String(creator.id), name: creator.name, email: creator.email }
        : null,
    },
  })
})

// PUT /dashboards/:id
dashboardRoutes.put("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))
  const { name, renderConfig } = await c.req.json()

  if (!name || !renderConfig) {
    return c.json({ error: "Missing required fields: name, renderConfig" }, 400)
  }

  const existing = await db.select().from(customDashboards).where(eq(customDashboards.id, id)).get()
  if (!existing) {
    return c.json({ error: "Dashboard not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  const dashboard = await db.update(customDashboards).set({
    name,
    renderConfig: JSON.stringify(renderConfig),
    updatedAt: new Date().toISOString(),
  }).where(eq(customDashboards.id, id)).returning().get()

  const creator = dashboard.createdBy
    ? await db.select().from(users).where(eq(users.id, dashboard.createdBy)).get()
    : null

  return c.json({
    success: true,
    dashboard: {
      id: String(dashboard.id),
      name: dashboard.name,
      createdAt: dashboard.createdAt,
      updatedAt: dashboard.updatedAt,
      creator: creator
        ? { id: String(creator.id), name: creator.name, email: creator.email }
        : null,
    },
  })
})

// DELETE /dashboards/:id
dashboardRoutes.delete("/:id", async (c) => {
  const user = c.get("user")
  const id = Number(c.req.param("id"))

  const existing = await db.select().from(customDashboards).where(eq(customDashboards.id, id)).get()
  if (!existing) {
    return c.json({ error: "Dashboard not found" }, 404)
  }

  if (existing.createdBy && existing.createdBy !== user.id && !user.isAdmin) {
    return c.json({ error: "Forbidden" }, 403)
  }

  await db.delete(customDashboards).where(eq(customDashboards.id, id))
  return c.json({ success: true })
})
