/**
 * HTTP — Bun.serve wrapper exposing the orchestrator's state.
 *
 * Endpoints (mirror Symphony's /api/v1/state shape, extended):
 *   GET  /api/v1/state         → counts + per-state lists + spend + schedules
 *   GET  /api/v1/work/:id      → single TrackedWork
 *   GET  /api/v1/schedules     → scheduler.status() (schedule fire/error counts)
 *   GET  /api/v1/spend         → spend counters + caps + window boundaries
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
import { statePayload } from "./presenter"

export function startOrchestratorServer(orch: Orchestrator, port = 3010): ReturnType<typeof Bun.serve> {
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
