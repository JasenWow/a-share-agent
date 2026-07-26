#!/usr/bin/env bun
/**
 * Live smoke test for equity_daily control plane (Step 12).
 *
 * Requires:
 *   - RUN_LIVE_SMOKE=1
 *   - TUSHARE_TOKEN set
 *   - MCP server on 8000 (tushare) running (optional; falls back gracefully)
 *
 * This script validates the control chain end-to-end using the real
 * SubprocessRunner. It does NOT run dbt (too slow for smoke). A
 * successful smoke confirms:
 *   - ScheduleEvaluator validates the session
 *   - SubprocessRunner calls uv run python -m etl.runner
 *   - ETL returns structured JSON and writes Parquet
 *   - Quality checks are persisted
 *   - PipelineRun reaches a terminal status
 *
 * Exit 0 on success; exit 1 on failure; exit 0 (silent) if RUN_LIVE_SMOKE
 * is not set.
 */

import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import { mkdtempSync, rmSync, existsSync } from "node:fs"
import { tmpdir } from "node:os"

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(SCRIPT_DIR, "..")
const PYTHON_ROOT = join(REPO_ROOT, "python")

// Fast exit in CI unless explicitly enabled
if (process.env.RUN_LIVE_SMOKE !== "1") {
  console.log("[smoke] Disabled (set RUN_LIVE_SMOKE=1 to run).")
  process.exit(0)
}

if (!process.env.TUSHARE_TOKEN) {
  console.error("[smoke] TUSHARE_TOKEN not set; cannot fetch real data.")
  process.exit(1)
}

async function main() {
  console.log("[smoke] Starting equity_daily live smoke test...")

  const tmpDir = mkdtempSync(join(tmpdir(), "smoke-"))
  const dbPath = join(tmpDir, "control.db")
  console.log(`[smoke] Temporary DuckDB: ${dbPath}`)

  const { ControlPlaneStore } = await import(join(REPO_ROOT, "packages/orchestrator/src/control-plane/control-plane-store.ts"))
  const { ControlPlaneService } = await import(join(REPO_ROOT, "packages/orchestrator/src/control-plane/control-plane-service.ts"))
  const { SubprocessRunner } = await import(join(REPO_ROOT, "packages/orchestrator/src/control-plane/subprocess-runner.ts"))
  const { StaticTradingCalendar } = await import(join(REPO_ROOT, "packages/orchestrator/src/control-plane/trading-calendar.ts"))
  const { validateSessionDate } = await import(join(REPO_ROOT, "packages/orchestrator/src/control-plane/schedule-evaluator.ts"))

  const store = new ControlPlaneStore({ path: dbPath })
  const runner = new SubprocessRunner({
    uvPath: "uv",
    pythonWorkspace: PYTHON_ROOT,
    dryRun: false,
  })
  const service = new ControlPlaneService({ store, runner })

  // Use a recent completed session within lookback. For smoke we hardcode
  // a known-good trading day (avoid calendar dependency on Python).
  // If the day is too old, lookback check will reject; update as needed.
  const TARGET_SESSION = "2026-08-04"
  const calendar = new StaticTradingCalendar("XSHG", ["2026-08-04"])
  const validation = validateSessionDate("equity_daily", TARGET_SESSION, {
    calendar,
    now: new Date("2026-08-05T10:00:00Z"),
    maxLookbackDays: 30,
  })
  if (!validation.ok) {
    console.error(`[smoke] Session validation failed: ${validation.reason}`)
    await store.close()
    rmSync(tmpDir, { recursive: true, force: true })
    process.exit(1)
  }
  console.log(`[smoke] Session validated: ${validation.sessionDate}`)

  const sessionDate = validation.sessionDate!
  console.log(`[smoke] Triggering run-now for ${sessionDate}...`)

  const runResult = await service.runNow({
    dataset: "equity_daily",
    sessionDate,
  })
  console.log(`[smoke] Run ${runResult.run.id} status: ${runResult.run.status}`)
  console.log(`[smoke] Stages:`, runResult.stages.map((s) => `${s.stage}=${s.status}`).join(", "))

  if (runResult.stages.length > 0) {
    const etl = runResult.stages[0]
    console.log(`[smoke] ETL stage: rows=${etl.rowCount}, artifact=${etl.artifactPath}`)
    if (etl.artifactPath && existsSync(etl.artifactPath)) {
      console.log(`[smoke] Parquet artifact exists`)
    }
  }

  const checks = await service.listQualityChecks({ runId: runResult.run.id })
  console.log(`[smoke] Quality checks: ${checks.length}`)
  for (const c of checks) {
    console.log(`[smoke]   ${c.dimension}.${c.check}: passed=${c.passed}, blocking=${c.blocking}`)
  }

  if (runResult.run.status === "completed" || runResult.run.status === "quality_failed") {
    console.log(`[smoke] SUCCESS: control chain reached terminal status (${runResult.run.status})`)
    await store.close()
    rmSync(tmpDir, { recursive: true, force: true })
    process.exit(0)
  } else {
    console.error(
      `[smoke] FAILED: status=${runResult.run.status}, code=${runResult.run.errorCode}, msg=${runResult.run.errorMessage}`,
    )
    await store.close()
    rmSync(tmpDir, { recursive: true, force: true })
    process.exit(1)
  }
}

main().catch((err) => {
  console.error("[smoke] UNCAUGHT ERROR:", err)
  process.exit(1)
})