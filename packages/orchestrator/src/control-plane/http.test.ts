/**
 * control-plane-http tests — red/green TDD step 6-8.
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { ControlPlaneStore } from "./control-plane-store"
import { ControlPlaneService } from "./control-plane-service"
import { FakeRunner } from "./fake-runner"
import { controlPlaneHttp } from "./http"
import { SemanticMetrics } from "./semantic-metrics"
import { StaticSessionExpander } from "./session-expander"

let store: ControlPlaneStore | null = null
let tmpDir: string | null = null

function fresh() {
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true })
  tmpDir = mkdtempSync(join(tmpdir(), "cps-http-"))
  store = new ControlPlaneStore({ path: join(tmpDir, "control.db") })
  const svc = new ControlPlaneService({
    store,
    runner: new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4231 },
      { stage: "dbt", status: "ok" },
    ]),
    sessionExpander: new StaticSessionExpander([
      "2026-07-20",
      "2026-07-21",
      "2026-07-22",
      "2026-07-23",
      "2026-07-24",
    ]),
    idGenerator: (() => {
      let n = 0
      return () => `run-${++n}`
    })(),
    clock: () => new Date("2026-08-05T10:00:00Z"),
  })
  const metrics = new SemanticMetrics({ path: join(tmpDir, "control.db") })
  const app = controlPlaneHttp({ service: svc, metrics })
  return { app, metrics, svc }
}

afterEach(async () => {
  if (store) {
    await store.close()
    store = null
  }
  if (tmpDir) {
    rmSync(tmpDir, { recursive: true, force: true })
    tmpDir = null
  }
})

describe("control-plane HTTP", () => {
  test("POST /pipeline-runs returns 201", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/pipeline-runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        dataset: "equity_daily",
        session_date: "2026-08-04",
      }),
    })
    expect(res.status).toBe(201)
    const body = await res.json()
    expect(body.id).toBe("run-1")
    expect(body.status).toBe("completed")
    expect(body.dataset).toBe("equity_daily")
    expect(body.session_date).toBe("2026-08-04")
  })

  test("POST /pipeline-runs rejects missing fields", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/pipeline-runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dataset: "equity_daily" }),
    })
    expect(res.status).toBe(400)
  })

  test("GET /pipeline-runs/:id returns full record", async () => {
    const { app } = fresh()
    await app.request("/api/v1/pipeline-runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        dataset: "equity_daily",
        session_date: "2026-08-04",
      }),
    })
    const res = await app.request("/api/v1/pipeline-runs/run-1")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.stages).toHaveLength(2)
    expect(body.quality_checks).toHaveLength(1)
  })

  test("GET /pipeline-runs/:id returns 404 for missing id", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/pipeline-runs/missing")
    expect(res.status).toBe(404)
  })

  test("GET /datasets/:name/status reflects latest accepted", async () => {
    const { app } = fresh()
    await app.request("/api/v1/pipeline-runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        dataset: "equity_daily",
        session_date: "2026-08-04",
      }),
    })
    const res = await app.request("/api/v1/datasets/equity_daily/status")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.dataset).toBe("equity_daily")
    expect(body.latest_run?.id).toBe("run-1")
    expect(body.last_accepted?.id).toBe("run-1")
    expect(body.last_quality_check?.dimension).toBe("completeness")
  })

  test("GET /health returns ok", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/health")
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ ok: true })
  })

  test("GET /metrics returns catalog", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/metrics")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(Array.isArray(body.metrics)).toBe(true)
    expect(body.metrics.map((m: Record<string, unknown>) => m.name).sort()).toEqual(["freshness_lag_days", "quality_pass_rate"])
  })

  test("POST /metrics/query executes quality_pass_rate", async () => {
    const { app, metrics } = fresh()
    // Seed check results via the store (same underlying db)
    await store!.insertQualityCheckResult({
      runId: "run-a",
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      stage: "etl",
      dimension: "completeness",
      check: "min_row_count",
      passed: true,
      blocking: true,
      recordedAt: "2026-08-04T10:01:00Z",
    })
    await store!.insertQualityCheckResult({
      runId: "run-a",
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      stage: "dbt",
      dimension: "validity",
      check: "ohlc_invariant",
      passed: false,
      blocking: true,
      recordedAt: "2026-08-04T10:02:00Z",
    })
    const res = await app.request("/api/v1/metrics/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        metric: "quality_pass_rate",
        filters: { dataset: "equity_daily" },
      }),
    })
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.columns).toContain("quality_pass_rate")
    expect(body.rows.length).toBeGreaterThanOrEqual(1)
  })

  test("POST /metrics/query rejects unknown metric", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/metrics/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        metric: "bogus",
      }),
    })
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error).toContain("Unknown metric")
  })
})

describe("control-plane HTTP — schedules (PR2)", () => {
  test("POST /schedules creates a new schedule", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: "equity_daily",
        dataset: "equity_daily",
        cron: "0 18 * * 1-5",
      }),
    })
    expect(res.status).toBe(201)
    const body = await res.json()
    expect(body.name).toBe("equity_daily")
    expect(body.cron).toBe("0 18 * * 1-5")
    expect(body.paused).toBe(false)
  })

  test("POST /schedules rejects missing fields", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "equity_daily" }),
    })
    expect(res.status).toBe(400)
  })

  test("PATCH /schedules/:name updates cron", async () => {
    const { app, svc } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    const res = await app.request("/api/v1/schedules/equity_daily", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cron: "0 19 * * 1-5" }),
    })
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.cron).toBe("0 19 * * 1-5")
  })

  test("PATCH /schedules/:name returns 404 for missing", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules/nope", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cron: "0 19 * * 1-5" }),
    })
    expect(res.status).toBe(404)
  })

  test("GET /schedules returns empty when none registered", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules")
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ schedules: [] })
  })

  test("GET /schedules/:name returns registered schedule", async () => {
    const { app, svc } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    const res = await app.request("/api/v1/schedules/equity_daily")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.name).toBe("equity_daily")
    expect(body.paused).toBe(false)
    expect(body.cron).toBe("0 18 * * 1-5")
  })

  test("GET /schedules/:name returns 404 for missing", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules/nope")
    expect(res.status).toBe(404)
  })

  test("POST /schedules/:name/pause sets paused=true", async () => {
    const { app, svc } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    const res = await app.request("/api/v1/schedules/equity_daily/pause", { method: "POST" })
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.paused).toBe(true)
    // Idempotent across GET
    const get = await app.request("/api/v1/schedules/equity_daily")
    expect((await get.json()).paused).toBe(true)
  })

  test("POST /schedules/:name/resume sets paused=false", async () => {
    const { app, svc } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: true,
      createdAt: "2026-08-04T00:00:00Z",
    })
    const res = await app.request("/api/v1/schedules/equity_daily/resume", { method: "POST" })
    expect(res.status).toBe(200)
    expect((await res.json()).paused).toBe(false)
  })

  test("POST pause on missing returns 404", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules/nope/pause", { method: "POST" })
    expect(res.status).toBe(404)
  })

  test("GET occurrences returns empty when none fired", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/schedules/equity_daily/occurrences")
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ occurrences: [] })
  })
})

describe("control-plane HTTP — backfills (PR3)", () => {
  test("POST /backfills creates an admitted request", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/backfills", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        dataset: "equity_daily",
        start_session: "2026-07-20",
        end_session: "2026-07-24",
      }),
    })
    expect(res.status).toBe(201)
    const body = await res.json()
    expect(body.status).toBe("queued")
    expect(body.session_count).toBe(5)
  })

  test("POST /backfills rejects missing fields", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/backfills", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dataset: "equity_daily" }),
    })
    expect(res.status).toBe(400)
  })

  test("GET /backfills lists requests", async () => {
    const { app } = fresh()
    await app.request("/api/v1/backfills", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        dataset: "equity_daily",
        start_session: "2026-07-20",
        end_session: "2026-07-21",
      }),
    })
    const res = await app.request("/api/v1/backfills")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.backfills).toHaveLength(1)
  })

  test("GET /backfills/:id returns detail with child_runs", async () => {
    const { app, svc } = fresh()
    const bf = await svc.createBackfill({
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-21",
    })
    await svc.executeBackfill(bf.id)
    const res = await app.request(`/api/v1/backfills/${bf.id}`)
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.status).toBe("completed")
    expect(body.child_runs).toHaveLength(2)
  })

  test("GET /backfills/:id returns 404 for missing", async () => {
    const { app } = fresh()
    const res = await app.request("/api/v1/backfills/nope")
    expect(res.status).toBe(404)
  })

  test("GET /backfills/:id/runs returns child pipeline runs", async () => {
    const { app, svc } = fresh()
    const bf = await svc.createBackfill({
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-20",
    })
    await svc.executeBackfill(bf.id)
    const res = await app.request(`/api/v1/backfills/${bf.id}/runs`)
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.runs).toHaveLength(1)
    expect(body.runs[0]?.trigger).toBe("backfill")
  })
})