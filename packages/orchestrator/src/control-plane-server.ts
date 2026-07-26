/**
 * Control-plane server — standalone HTTP server for the data-operations
 * control plane.
 *
 * Boots the Hono app from control-plane/http.ts on a configurable port.
 * Run separately or alongside the orchestrator server.
 *
 * Usage:
 *   bun run packages/orchestrator/src/control-plane-server.ts
 *   PORT=3020 bun run packages/orchestrator/src/control-plane-server.ts
 */

import { join } from "node:path"
import { controlPlaneHttp } from "./control-plane/http"
import { ControlPlaneStore } from "./control-plane/control-plane-store"
import { ControlPlaneService } from "./control-plane/control-plane-service"
import { SubprocessRunner } from "./control-plane/subprocess-runner"
import { SemanticMetrics } from "./control-plane/semantic-metrics"
import { ControlPlaneScheduler } from "./control-plane/control-plane-scheduler"
import { FileBackedSessionResolver } from "./control-plane/xshg-calendar"

const PORT = Number(process.env.PORT ?? 3020)
const DB_PATH = process.env.CONTROL_PLANE_DB ?? join(process.cwd(), "data/control-plane/control.db")
const PYTHON_ROOT = process.env.PYTHON_ROOT ?? join(process.cwd(), "python")

async function main() {
  console.log(`[control-plane] DuckDB: ${DB_PATH}`)
  const store = new ControlPlaneStore({ path: DB_PATH })
  const runner = new SubprocessRunner({ pythonWorkspace: PYTHON_ROOT })
  const service = new ControlPlaneService({
    store,
    runner,
    sessionExpander: new (await import("./control-plane/xshg-calendar")).FileBackedSessionExpander(),
  })
  const metrics = new SemanticMetrics({ path: DB_PATH })
  const app = controlPlaneHttp({ service, metrics })

  // Start the scheduler with real XSHG session resolution.
  const scheduler = new ControlPlaneScheduler({
    service,
    sessionResolver: new FileBackedSessionResolver(),
  })
  await scheduler.start()

  const server = Bun.serve({
    port: PORT,
    hostname: "127.0.0.1", // local-only per ADR 0020
    fetch: app.fetch,
  })

  console.log(`[control-plane] Listening on http://127.0.0.1:${server.port}`)
  console.log(`[control-plane] Scheduler: ${scheduler.isRunning() ? "running" : "stopped"} (${scheduler.status().length} schedule(s))`)

  process.on("SIGINT", () => {
    console.log("[control-plane] Shutting down...")
    scheduler.stop()
    server.stop()
    process.exit(0)
  })
}

main().catch((err) => {
  console.error("[control-plane] Fatal:", err)
  process.exit(1)
})