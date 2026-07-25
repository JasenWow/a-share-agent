#!/usr/bin/env bun
/**
 * orchestrator entry — boots the whole agent orchestration stack.
 *
 * Run:
 *   bun run orchestrator             # real LLM agent (reads .env for AQUAN_*)
 *   bun run orchestrator:stub        # StubRuntime, no LLM, for dashboard dev
 *   bun run orchestrator:seed        # like :stub but pre-seeds one demo WorkItem
 *
 * What it does (in order):
 *   1. Loads .env (so AQUAN_PROVIDER / AQUAN_API_KEY / etc. are visible)
 *   2. Builds the agent runtime (PiRuntime or StubRuntime)
 *   3. Opens the SQLite store + PersistedSpendGuard (survives restarts)
 *   4. Constructs the Orchestrator with the chosen trackers
 *   5. Starts the cron Scheduler (different cadences per tracker)
 *   6. Starts the HTTP server on ORCHESTRATOR_PORT (default 3010)
 *   7. Wires SIGINT/SIGTERM for clean shutdown
 *
 * This file lives in /scripts (not inside a package) so it can import both
 * @aquan/orchestrator and @aquan/pi-runtime without tripping the
 * dep-cruiser 'no-runtime-to-app' boundary rule.
 */

import { mkdirSync } from "node:fs"
import { dirname, resolve } from "node:path"

// 1. Load .env (Bun auto-loads .env, but be explicit for clarity when run
// via `bun run scripts/orchestrator.ts` from a fresh shell).
try {
  const { default: dotenv } = await import("dotenv")
  dotenv.config()
} catch {
  // dotenv not installed — Bun loads .env natively, so this is fine.
}

// Resolve workspace packages by relative path. scripts/ lives at repo root,
// outside any package's node_modules resolution scope, so bare "@aquan/..."
// imports don't work here. Relative paths sidestep that without adding
// root-level package.json dependencies.
const ORCH = "../packages/orchestrator/src/index.ts"
const RT = "../packages/pi-runtime/src/index.ts"
const CORE = "../packages/core/src/index.ts"

// Local ScheduleSpec type (mirrors @aquan/orchestrator's). Avoids needing
// a type-only import from a relative path, which Bun's parser dislikes.
interface ScheduleSpec {
  cron: string
  trackers?: string[]
  name?: string
}

const { DEFAULT_POLICY } = await import(CORE)
const {
  FreeExplorationTracker,
  FactorMiningTracker,
  MemoryTracker,
  Orchestrator,
  PersistedSpendGuard,
  SqliteStateStore,
  startOrchestratorServer,
  StubRuntime,
} = await import(ORCH)

// Runtime choice based on argv / env.
const mode = (process.argv[2] ?? process.env.AQUAN_MODE ?? "real").toLowerCase()
const useStub = mode === "stub" || mode === "--stub"
const seedDemo = mode === "seed" || mode === "--seed"

// PiRuntime is optional — only import when running in real mode.
// Dynamic import keeps :stub mode working even if pi-runtime deps break.
async function buildRuntime() {
  if (useStub) {
    return new StubRuntime()
  }
  try {
    const { PiRuntime } = await import(RT)
    return new PiRuntime()
  } catch (e) {
    console.error(
      "[orchestrator] Failed to load PiRuntime. Falling back to StubRuntime.\n" +
        "  Set AQUAN_PROVIDER / AQUAN_API_KEY in .env, or run `bun run orchestrator:stub`.\n" +
        `  Error: ${e instanceof Error ? e.message : String(e)}`,
    )
    return new StubRuntime()
  }
}

// 2. SQLite store (data/orchestrator/state.db).
const dbPath = resolve(process.env.AQUAN_STATE_DB ?? "data/orchestrator/state.db")
mkdirSync(dirname(dbPath), { recursive: true })
const store = new SqliteStateStore(dbPath)
const spendGuard = new PersistedSpendGuard(DEFAULT_POLICY.budget, store.dbHandle)

// 3. Trackers. The real factor-mining / free-exploration trackers are
// stubs today (they return empty WorkItem lists); MemoryTracker + --seed
// gives the dashboard something to show.
const trackers = []
if (seedDemo) {
  const demo = new MemoryTracker()
  demo.seed([
    {
      id: `demo-${Date.now()}`,
      title: "Demo: list experiments",
      type: "sedimentation",
      description:
        "Use the experiment tool with action 'list' to fetch experiments, then summarize how many exist.",
      createdAt: new Date().toISOString(),
      state: "pending",
    },
  ])
  trackers.push(demo)
} else {
  trackers.push(new FactorMiningTracker())
  trackers.push(new FreeExplorationTracker())
}

// 4. Orchestrator.
const runtime = await buildRuntime()
const orch = new Orchestrator({
  runtime,
  trackers,
  store,
  spendGuard,
  policy: DEFAULT_POLICY,
})

// 5. Schedules. Different cadences per tracker:
//   factor-mining:    every 30s (poll the hypothesis queue)
//   free-exploration: 18:00 Mon–Fri (end-of-trading-day market scan)
// In :stub / :seed mode we don't start the scheduler — work is one-shot
// so the dashboard's "Run tick now" button is the trigger.
const schedules: ScheduleSpec[] =
  useStub || seedDemo
    ? []
    : [
        { name: "factor-mining-loop", cron: "*/30 * * * * *", trackers: ["factor-mining"] },
        { name: "daily-exploration", cron: "0 18 * * 1-5", trackers: ["free-exploration"] },
      ]
if (schedules.length > 0) {
  orch.start(schedules)
}

// 6. HTTP server.
const port = Number(process.env.ORCHESTRATOR_PORT ?? 3010)
const server = startOrchestratorServer(orch, port)

// 7. Shutdown wiring.
let shuttingDown = false
function shutdown(signal: string) {
  if (shuttingDown) return
  shuttingDown = true
  console.log(`\n[orchestrator] ${signal} received, shutting down...`)
  orch.stop()
  try {
    server.stop(true)
  } catch {
    // ignore
  }
  store.close()
  console.log("[orchestrator] stopped.")
  process.exit(0)
}
process.on("SIGINT", () => shutdown("SIGINT"))
process.on("SIGTERM", () => shutdown("SIGTERM"))

console.log(`[orchestrator] mode: ${useStub ? "stub" : seedDemo ? "seed" : "real"}`)
console.log(`[orchestrator] runtime: ${useStub ? "StubRuntime" : "PiRuntime"}`)
console.log(`[orchestrator] trackers: ${trackers.map((t) => t.name).join(", ") || "(none)"}`)
console.log(`[orchestrator] schedules: ${schedules.length === 0 ? "(manual tick only)" : schedules.map((s) => s.name).join(", ")}`)
console.log(`[orchestrator] store: ${dbPath}`)
console.log(`[orchestrator] HTTP: http://localhost:${port}`)
console.log(`[orchestrator]   GET  /api/v1/state`)
console.log(`[orchestrator]   POST /api/v1/tick`)
console.log(`[orchestrator] Ctrl+C to stop.`)
