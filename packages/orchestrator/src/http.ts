/**
 * HTTP — Bun.serve wrapper exposing the orchestrator's state.
 *
 * Endpoints (mirror Symphony's /api/v1/state shape):
 *   GET  /api/v1/state       -> StatePayload (counts + per-state lists)
 *   GET  /api/v1/work/:id    -> single TrackedWork
 *   POST /api/v1/tick        -> run one orchestrator pass (dev only)
 *
 * Phase 5: minimal routing; security / auth come later. Production
 * deployments will proxy these through @aquan/server's Hono app instead
 * of running this standalone.
 */

import type { Orchestrator } from "./orchestrator"
import { statePayload } from "./presenter"

export function startOrchestratorServer(orch: Orchestrator, port = 3010): ReturnType<typeof Bun.serve> {
  return Bun.serve({
    port,
    async fetch(req) {
      const url = new URL(req.url)

      if (url.pathname === "/api/v1/state" && req.method === "GET") {
        return jsonResponse(statePayload(orch.store))
      }

      const workMatch = url.pathname.match(/^\/api\/v1\/work\/([^/]+)$/)
      if (workMatch && req.method === "GET") {
        const work = orch.store.get(workMatch[1])
        if (!work) return new Response("not found", { status: 404 })
        return jsonResponse(work)
      }

      if (url.pathname === "/api/v1/tick" && req.method === "POST") {
        const result = await orch.tick()
        return jsonResponse(result)
      }

      return new Response("not found", { status: 404 })
    },
  })
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body, null, 2), {
    headers: { "Content-Type": "application/json" },
  })
}
