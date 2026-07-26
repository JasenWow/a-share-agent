/**
 * HTTP — Bun.serve wrapper exposing the orchestrator's state.
 *
 * Endpoints (mirror Symphony's /api/v1/state shape, extended):
 *   GET  /api/v1/state         → counts + per-state lists + spend + schedules
 *   GET  /api/v1/work/:id      → single TrackedWork
 *   GET  /api/v1/schedules     → scheduler.status() (schedule fire/error counts)
 *   GET  /api/v1/spend         → spend counters + caps + window boundaries
 *   GET  /api/v1/loops         → historical work items + byTracker/byDay aggregation
 *   GET  /api/v1/factors/candidates → internal-store candidate factors (agent output)
 *   POST /api/v1/tick          → run one orchestrator pass (dev/manual trigger)
 *
 * Stage 3 additions: /schedules + /spend + state payload now carries both
 * when SpendGuard / Scheduler are wired in. The dashboard polls /state
 * every 2s for everything; the finer-grained endpoints exist for ad-hoc
 * inspection and future single-panel refresh.
 *
 * Production deployments can proxy these through @aquan/server's Hono app
 * instead of running this standalone server.
 */

import type { Orchestrator } from "./orchestrator"
import { statePayload, historyPayload } from "./presenter"
import type { InternalStoreReader } from "./internal-store-reader"

export interface OrchestratorHttpOptions {
  /**
   * Read-only view into the internal-store SQLite DB. When supplied, the
   * server exposes `/api/v1/factors/candidates` so the dashboard can show
   * factors the agent has persisted. Without it, that endpoint reports
   * `source: "unavailable"`.
   */
  internalStoreReader?: InternalStoreReader
}

export function startOrchestratorServer(
  orch: Orchestrator,
  port = 3010,
  opts: OrchestratorHttpOptions = {},
): ReturnType<typeof Bun.serve> {
  const reader = opts.internalStoreReader
  return Bun.serve({
    port,
    async fetch(req) {
      const url = new URL(req.url)

      if (url.pathname === "/api/v1/state" && req.method === "GET") {
        return jsonResponse(
          statePayload(orch.store, {
            spend: orch.spend,
            scheduler: orch.getScheduler(),
          }),
        )
      }

      const workMatch = url.pathname.match(/^\/api\/v1\/work\/([^/]+)$/)
      if (workMatch && req.method === "GET") {
        const work = orch.store.get(workMatch[1])
        if (!work) return new Response("not found", { status: 404 })
        return jsonResponse(work)
      }

      if (url.pathname === "/api/v1/schedules" && req.method === "GET") {
        const scheduler = orch.getScheduler()
        if (!scheduler) {
          return jsonResponse({ schedules: [], running: false })
        }
        return jsonResponse({ schedules: scheduler.status(), running: scheduler.isRunning() })
      }

      if (url.pathname === "/api/v1/spend" && req.method === "GET") {
        const stats = orch.spend.getStats()
        const policy = orch.spend.policy
        return jsonResponse({
          daily: stats.daily,
          weekly: stats.weekly,
          monthly: stats.monthly,
          dailyCap: policy.dailyCap,
          weeklyCap: policy.weeklyCap,
          monthlyCap: policy.monthlyCap,
          dayStart: stats.dayStart.toISOString(),
          weekStart: stats.weekStart.toISOString(),
          monthStart: stats.monthStart.toISOString(),
        })
      }

      if (url.pathname === "/api/v1/loops" && req.method === "GET") {
        // Optional filters: ?state=done&tracker=factor-mining&limit=100&since=ISO
        const stateParam = url.searchParams.get("state")
        const tracker = url.searchParams.get("tracker") ?? undefined
        const since = url.searchParams.get("since") ?? undefined
        const limitParam = url.searchParams.get("limit")
        const limit = limitParam ? Number(limitParam) : undefined
        const states = stateParam ? stateParam.split(",").map((s) => s.trim()).filter(Boolean) : undefined
        return jsonResponse(
          historyPayload(orch.store, { states: states as never, tracker, since, limit }),
        )
      }

      if (url.pathname === "/api/v1/factors/candidates" && req.method === "GET") {
        // Reader may be absent (stub mode) or the DB unavailable. Degrade
        // gracefully so the dashboard can render an empty state.
        if (!reader) {
          return jsonResponse({ candidates: [], count: 0, source: "unavailable" })
        }
        const candidates = reader.listCandidates()
        return jsonResponse({
          candidates,
          count: candidates.length,
          source: reader.isAvailable() ? "internal-store" : "unavailable",
        })
      }

      if (url.pathname === "/api/v1/tick" && req.method === "POST") {
        const trackerNames = parseTrackerFilter(url.searchParams.get("trackers"))
        const result = await orch.tick({ trackerNames })
        return jsonResponse(result)
      }

      // Health check for the orchestrator server itself.
      if (url.pathname === "/healthz" && req.method === "GET") {
        return jsonResponse({ ok: true })
      }

      return new Response("not found", { status: 404 })
    },
  })
}

function parseTrackerFilter(param: string | null): string[] | undefined {
  if (!param) return undefined
  const names = param
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
  return names.length > 0 ? names : undefined
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body, null, 2), {
    headers: { "Content-Type": "application/json" },
  })
}
