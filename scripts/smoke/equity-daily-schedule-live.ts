#!/usr/bin/env bun
/**
 * Live smoke test for the control-plane scheduler (Step 7 / PR2).
 *
 * Validates the scheduled-fire chain end-to-end:
 *   schedule_definition (paused=false)
 *     → ControlPlaneScheduler.fire(name)
 *     → ControlPlaneService.fireSchedule(name, session)
 *     → occurrence recorded + fireCount bumped
 *     → SubprocessRunner.run (real uv run python -m etl.runner)
 *     → PipelineRun terminal status
 *
 * Same gating as equity-daily-live.ts:
 *   - RUN_LIVE_SMOKE=1 required to run (silent skip otherwise)
 *   - TUSHARE_TOKEN required
 *
 * The session is resolved by a fixed resolver (the most recent hardcoded
 * trading session) so the smoke doesn't depend on the calendar.
 */

import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(SCRIPT_DIR, "..")
const PYTHON_ROOT = join(REPO_ROOT, "python")

if (process.env.RUN_LIVE_SMOKE !== "1") {
  console.log("[smoke-sched] Disabled (set RUN_LIVE_SMOKE=1 to run).")
  process.exit(0)
}

if (!process.env.TUSHARE_TOKEN) {
  console.error("[smoke-sched] TUSHARE_TOKEN not set; cannot fetch real data.")
  process.exit(1)
}

async function main() {
  console.log("[smoke-sched] Starting control-plane scheduler live smoke...")
  const tmpDir = mkdtempSync(join(tmpdir(), "smoke-sched-"))
  const dbPath = join(tmpDir, "control.db")
  console.log(`[smoke-sched] Temporary DuckDB: ${dbPath}`)

  const { ControlPlaneStore } = await import(
    join(REPO_ROOT, "packages/orchestrator/src/control-plane/control-plane-store.ts")
  )
  const { ControlPlaneService } = await import(
    join(REPO_ROOT, "packages/orchestrator/src/control-plane/control-plane-service.ts")
  )
  const { SubprocessRunner } = await import(
    join(REPO_ROOT, "packages/orchestrator/src/control-plane/subprocess-runner.ts")
  )
  const { ControlPlaneScheduler } = await import(
    join(REPO_ROOT, "packages/orchestrator/src/control-plane/control-plane-scheduler.ts")
  )

  const store = new ControlPlaneStore({ path: dbPath })
  const runner = new SubprocessRunner({
    uvPath: "uv",
    pythonWorkspace: PYTHON_ROOT,
    dryRun: false,
  })
  const service = new ControlPlaneService({ store, runner })

  // Register the equity_daily schedule (18:00 Asia/Shanghai, per ADR 0006).
  // Note: cron field is informational here — we drive fire() manually.
  await service.upsertSchedule({
    name: "equity_daily",
    dataset: "equity_daily",
    trigger: "scheduled",
    cron: "0 18 * * 1-5",
    paused: false,
    createdAt: new Date().toISOString(),
  })

  const scheduler = new ControlPlaneScheduler({
    service,
    sessionResolver: { resolve: () => "2026-08-04" },
    now: () => new Date(),
  })
  await scheduler.start()

  console.log("[smoke-sched] Firing schedule equity_daily manually...")
  await scheduler.fire("equity_daily")

  const status = scheduler.status()
  const s0 = status[0]
  console.log(`[smoke-sched] fireCount=${s0?.fireCount} lastSkipped=${s0?.lastSkipped} lastError=${s0?.lastError ?? "none"}`)

  const occurrences = await service.listOccurrences("equity_daily")
  console.log(`[smoke-sched] Occurrences: ${occurrences.length}`)

  const def = await service.getSchedule("equity_daily")
  console.log(`[smoke-sched] Schedule fireCount=${def?.fireCount} lastFireAt=${def?.lastFireAt}`)

  const runs = await service.listRuns("equity_daily")
  const latest = runs[0]
  console.log(`[smoke-sched] Latest run status=${latest?.status} trigger=${latest?.trigger}`)

  scheduler.stop()
  await store.close()
  rmSync(tmpDir, { recursive: true, force: true })

  if (s0?.lastError) {
    console.error(`[smoke-sched] FAILED: ${s0.lastError}`)
    process.exit(1)
  }
  if (latest && (latest.status === "completed" || latest.status === "quality_failed")) {
    console.log(`[smoke-sched] SUCCESS (run ${latest.id} = ${latest.status})`)
    process.exit(0)
  }
  console.error(`[smoke-sched] FAILED: no terminal run produced`)
  process.exit(1)
}

main().catch((err) => {
  console.error("[smoke-sched] UNCAUGHT ERROR:", err)
  process.exit(1)
})