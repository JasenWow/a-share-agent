/**
 * semantic-metrics tests — red/green TDD step 9-10.
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { DuckDBInstance } from "@duckdb/node-api"
import { SemanticMetrics } from "./semantic-metrics"
import { ControlPlaneStore } from "./control-plane-store"
import type { QualityCheckResult } from "./control-plane-store"

let store: ControlPlaneStore | null = null
let metrics: SemanticMetrics | null = null
let tmpDir: string | null = null

async function fresh() {
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true })
  tmpDir = mkdtempSync(join(tmpdir(), "cps-metrics-"))
  store = new ControlPlaneStore({ path: join(tmpDir, "control.db") })
  // Force schema creation
  await store.insertPipelineRun({
    id: "seed",
    dataset: "equity_daily",
    sessionDate: "2026-08-04",
    trigger: "manual",
    status: "completed",
    attempt: 1,
    createdAt: "2026-08-04T10:00:00Z",
  })
  metrics = new SemanticMetrics({ path: join(tmpDir, "control.db") })
  return { store, metrics }
}

afterEach(async () => {
  if (store) await store.close()
  store = null
  if (metrics) await metrics.close()
  metrics = null
  if (tmpDir) {
    rmSync(tmpDir, { recursive: true, force: true })
    tmpDir = null
  }
})

async function seedChecks(store: ControlPlaneStore): Promise<void> {
  const checks: QualityCheckResult[] = [
    {
      runId: "run-1",
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      stage: "etl",
      dimension: "completeness",
      check: "min_row_count",
      passed: true,
      blocking: true,
      observed: 4231,
      threshold: 4000,
      message: "ok",
      recordedAt: "2026-08-04T10:01:00Z",
    },
    {
      runId: "run-1",
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      stage: "dbt",
      dimension: "validity",
      check: "ohlc_invariant",
      passed: true,
      blocking: true,
      observed: 0,
      threshold: 0,
      message: "ok",
      recordedAt: "2026-08-04T10:02:00Z",
    },
    {
      runId: "run-2",
      dataset: "equity_daily",
      sessionDate: "2026-08-05",
      stage: "dbt",
      dimension: "validity",
      check: "ohlc_invariant",
      passed: false,
      blocking: true,
      observed: 3,
      threshold: 0,
      message: "3 rows violated",
      recordedAt: "2026-08-05T10:02:00Z",
    },
  ]
  for (const c of checks) await store.insertQualityCheckResult(c)
}

describe("SemanticMetrics", () => {
  test("lists the catalog", async () => {
    const { metrics } = await fresh()
    const list = metrics.list()
    expect(list.map((m) => m.name).sort()).toEqual([
      "freshness_lag_days",
      "quality_pass_rate",
    ])
  })

  test("quality_pass_rate computes correctly", async () => {
    const { store, metrics } = await fresh()
    await seedChecks(store)
    const result = await metrics.query({
      metric: "quality_pass_rate",
      filters: { dataset: "equity_daily" },
    })
    expect(result.rows).toHaveLength(1)
    expect(Number(result.rows[0]?.quality_pass_rate)).toBeCloseTo(2 / 3, 5)
  })

  test("rejects unknown metric", async () => {
    const { metrics } = await fresh()
    expect(
      metrics.query({ metric: "bogus", filters: {} }),
    ).rejects.toThrow(/Unknown metric/)
  })

  test("rejects dimension not in metric spec", async () => {
    const { metrics } = await fresh()
    expect(
      metrics.query({
        metric: "quality_pass_rate",
        dimensions: ["strategy_name"],
        filters: {},
      }),
    ).rejects.toThrow(/not allowed/)
  })

  test("rejects filter not in metric spec", async () => {
    const { metrics } = await fresh()
    expect(
      metrics.query({
        metric: "quality_pass_rate",
        filters: { strategy_name: "x" },
      }),
    ).rejects.toThrow(/not allowed/)
  })

  test("freshness_lag_days returns latest completed session_date", async () => {
    const { metrics } = await fresh()
    // The seed run is already inserted by fresh(). Add a second.
    // Re-open the store through the metrics' path:
    const tmpInstance = await DuckDBInstance.create(join(tmpDir!, "control.db"))
    const conn = await tmpInstance.connect()
    try {
      await conn.run(
        `INSERT INTO pipeline_runs (id, dataset, session_date, trigger, status, attempt, created_at) VALUES ('run-b','equity_daily','2026-08-06','manual','completed',1,'2026-08-06T10:00:00Z');`,
      )
    } finally {
      conn.closeSync()
    }
    tmpInstance.closeSync()

    const result = await metrics.query({
      metric: "freshness_lag_days",
      filters: { dataset: "equity_daily" },
    })
    expect(result.rows[0]?.latest_session_date).toBe("2026-08-06")
  })
})