/**
 * control-plane-http — Hono routes for the data-operations control plane.
 *
 * Mounted under /api/v1. Implements the run-now vertical slice
 * (POST /pipeline-runs) plus inspection endpoints needed by the
 * dashboard (GET pipeline-run/:id, GET datasets/:name/status,
 * GET quality/results).
 *
 * All responses are JSON. Errors use 4xx for client problems and
 * 5xx for unexpected server faults.
 */

import { Hono } from "hono"
import { cors } from "hono/cors"
import type { ControlPlaneService } from "./control-plane-service"
import type { SemanticMetrics } from "./semantic-metrics"

export interface ControlPlaneHttpDeps {
  service: ControlPlaneService
  metrics?: SemanticMetrics
}

export function controlPlaneHttp(deps: ControlPlaneHttpDeps): Hono {
  const { service } = deps
  const app = new Hono()

  // CORS: the dashboard runs on :3000, the control plane on :3020.
  // Local-only per ADR 0020; allow all origins in dev.
  app.use("*", cors())

  app.post("/api/v1/pipeline-runs", async (c) => {
    const body = await c.req.json().catch(() => null)
    if (!body || typeof body !== "object") {
      return c.json({ error: "invalid_body" }, 400)
    }
    const dataset = String((body as Record<string, unknown>).dataset ?? "")
    const sessionDate = String((body as Record<string, unknown>).session_date ?? "")
    if (!dataset || !sessionDate) {
      return c.json({ error: "missing_fields", required: ["dataset", "session_date"] }, 400)
    }
    const trigger = (body as Record<string, unknown>).trigger as
      | "manual"
      | "scheduled"
      | "backfill"
      | "retry"
      | undefined
    const result = await service.runNow({ dataset, sessionDate, trigger })
    return c.json(
      {
        id: result.run.id,
        dataset: result.run.dataset,
        session_date: result.run.sessionDate,
        status: result.run.status,
        trigger: result.run.trigger,
        attempt: result.run.attempt,
        created_at: result.run.createdAt,
        started_at: result.run.startedAt ?? null,
        finished_at: result.run.finishedAt ?? null,
        error_code: result.run.errorCode ?? null,
        error_message: result.run.errorMessage ?? null,
      },
      201,
    )
  })

  app.get("/api/v1/pipeline-runs/:id", async (c) => {
    const id = c.req.param("id")
    const run = await service.getRun(id)
    if (!run) return c.json({ error: "not_found" }, 404)
    const stages = await service.listStages(id)
    const checks = await service.listQualityChecks({ runId: id })
    return c.json({
      id: run.id,
      dataset: run.dataset,
      session_date: run.sessionDate,
      status: run.status,
      trigger: run.trigger,
      attempt: run.attempt,
      created_at: run.createdAt,
      started_at: run.startedAt ?? null,
      finished_at: run.finishedAt ?? null,
      error_code: run.errorCode ?? null,
      error_message: run.errorMessage ?? null,
      stages: stages.map((s) => ({
        stage: s.stage,
        status: s.status,
        row_count: s.rowCount ?? null,
        artifact_path: s.artifactPath ?? null,
        error_code: s.errorCode ?? null,
        error_message: s.errorMessage ?? null,
        started_at: s.startedAt,
        finished_at: s.finishedAt,
      })),
      quality_checks: checks.map((q) => ({
        stage: q.stage,
        dimension: q.dimension,
        check: q.check,
        passed: q.passed,
        blocking: q.blocking,
        observed: q.observed ?? null,
        threshold: q.threshold ?? null,
        message: q.message ?? null,
        recorded_at: q.recordedAt,
      })),
    })
  })

  app.get("/api/v1/pipeline-runs", async (c) => {
    const dataset = c.req.query("dataset")
    const runs = await service.listRuns(dataset)
    return c.json({
      runs: runs.map((run) => ({
        id: run.id,
        dataset: run.dataset,
        session_date: run.sessionDate,
        status: run.status,
        trigger: run.trigger,
        attempt: run.attempt,
        created_at: run.createdAt,
        finished_at: run.finishedAt ?? null,
      })),
    })
  })

  app.get("/api/v1/datasets/:name/status", async (c) => {
    const name = c.req.param("name")
    const runs = await service.listRuns(name)
    const latest = runs[0] ?? null
    const lastAccepted = runs.find((r) => r.status === "completed") ?? null
    const allChecks = await service.listQualityChecks({ dataset: name })
    const lastCheck = allChecks[allChecks.length - 1] ?? null
    return c.json({
      dataset: name,
      latest_run: latest
        ? {
            id: latest.id,
            status: latest.status,
            session_date: latest.sessionDate,
            finished_at: latest.finishedAt ?? null,
          }
        : null,
      last_accepted: lastAccepted
        ? {
            id: lastAccepted.id,
            session_date: lastAccepted.sessionDate,
            finished_at: lastAccepted.finishedAt ?? null,
          }
        : null,
      last_quality_check: lastCheck
        ? {
            dimension: lastCheck.dimension,
            check: lastCheck.check,
            passed: lastCheck.passed,
            recorded_at: lastCheck.recordedAt,
          }
        : null,
    })
  })

  app.get("/api/v1/quality/results", async (c) => {
    const dataset = c.req.query("dataset")
    const runId = c.req.query("run_id")
    const checks = await service.listQualityChecks({ dataset, runId })
    return c.json({
      results: checks.map((q) => ({
        run_id: q.runId,
        dataset: q.dataset,
        session_date: q.sessionDate,
        stage: q.stage,
        dimension: q.dimension,
        check: q.check,
        passed: q.passed,
        blocking: q.blocking,
        observed: q.observed ?? null,
        threshold: q.threshold ?? null,
        message: q.message ?? null,
        recorded_at: q.recordedAt,
      })),
    })
  })

  app.get("/api/v1/metrics", (c) => {
    if (!deps.metrics) return c.json({ error: "metrics_not_available" }, 501)
    return c.json({
      metrics: deps.metrics.list().map((m) => ({
        name: m.name,
        description: m.description,
        unit: m.unit,
        category: m.category,
        source_table: m.sourceTable,
        dimensions: m.dimensions,
      })),
    })
  })

  app.get("/api/v1/metrics/:name", (c) => {
    if (!deps.metrics) return c.json({ error: "metrics_not_available" }, 501)
    const name = c.req.param("name")
    try {
      const spec = deps.metrics.describe(name)
      return c.json({
        name: spec.name,
        description: spec.description,
        formula: spec.formula,
        unit: spec.unit,
        category: spec.category,
        source_table: spec.sourceTable,
        dimensions: spec.dimensions,
      })
    } catch (err) {
      return c.json({ error: (err as Error).message }, 404)
    }
  })

  app.post("/api/v1/metrics/query", async (c) => {
    if (!deps.metrics) return c.json({ error: "metrics_not_available" }, 501)
    const body = await c.req.json().catch(() => null)
    if (!body || typeof body !== "object") return c.json({ error: "invalid_body" }, 400)
    const metric = String((body as Record<string, unknown>).metric ?? "")
    const dimensions = (body as Record<string, unknown>).dimensions as string[] | undefined
    const filters = (body as Record<string, unknown>).filters as Record<string, string> | undefined
    const limit = (body as Record<string, unknown>).limit as number | undefined
    if (!metric) return c.json({ error: "missing_metric" }, 400)
    try {
      const result = await deps.metrics.query({ metric, dimensions, filters, limit })
      return c.json({ rows: result.rows, columns: result.columns })
    } catch (err) {
      return c.json({ error: (err as Error).message }, 400)
    }
  })

  app.get("/api/v1/health", (c) => c.json({ ok: true }))

  /* ----------------------- Backfill requests (PR3) ----------------------- */

  app.post("/api/v1/backfills", async (c) => {
    const body = await c.req.json().catch(() => null)
    if (!body || typeof body !== "object") return c.json({ error: "invalid_body" }, 400)
    const dataset = String((body as Record<string, unknown>).dataset ?? "")
    const startSession = String((body as Record<string, unknown>).start_session ?? "")
    const endSession = String((body as Record<string, unknown>).end_session ?? "")
    if (!dataset || !startSession || !endSession) {
      return c.json({ error: "missing_fields", required: ["dataset", "start_session", "end_session"] }, 400)
    }
    try {
      const bf = await service.createBackfill({ dataset, startSession, endSession })
      return c.json(backfillPayload(bf), bf.status === "admission_rejected" ? 422 : 201)
    } catch (err) {
      return c.json({ error: (err as Error).message }, 400)
    }
  })

  app.get("/api/v1/backfills", async (c) => {
    const dataset = c.req.query("dataset")
    const bfs = await service.listBackfills(dataset)
    return c.json({ backfills: bfs.map(backfillPayload) })
  })

  app.get("/api/v1/backfills/:id", async (c) => {
    const id = c.req.param("id")
    const bf = await service.getBackfill(id)
    if (!bf) return c.json({ error: "not_found" }, 404)
    const children = await service.listBackfillChildRuns(id)
    return c.json({
      ...backfillPayload(bf),
      child_runs: children.map((r) => ({
        id: r.id,
        session_date: r.sessionDate,
        status: r.status,
        finished_at: r.finishedAt ?? null,
      })),
    })
  })

  app.get("/api/v1/backfills/:id/runs", async (c) => {
    const id = c.req.param("id")
    const bf = await service.getBackfill(id)
    if (!bf) return c.json({ error: "not_found" }, 404)
    const children = await service.listBackfillChildRuns(id)
    return c.json({
      runs: children.map((r) => ({
        id: r.id,
        session_date: r.sessionDate,
        status: r.status,
        trigger: r.trigger,
        started_at: r.startedAt ?? null,
        finished_at: r.finishedAt ?? null,
        error_code: r.errorCode ?? null,
      })),
    })
  })

  /* ----------------------- Schedule control (PR2) ----------------------- */

  app.post("/api/v1/schedules", async (c) => {
    const body = await c.req.json().catch(() => null)
    if (!body || typeof body !== "object") return c.json({ error: "invalid_body" }, 400)
    const name = String((body as Record<string, unknown>).name ?? "")
    const dataset = String((body as Record<string, unknown>).dataset ?? "")
    const cron = String((body as Record<string, unknown>).cron ?? "")
    if (!name || !dataset || !cron) {
      return c.json({ error: "missing_fields", required: ["name", "dataset", "cron"] }, 400)
    }
    try {
      const def = await service.upsertSchedule({
        name,
        dataset,
        trigger: "scheduled",
        cron,
        paused: false,
        createdAt: new Date().toISOString(),
      })
      return c.json(schedulePayload(def), 201)
    } catch (err) {
      return c.json({ error: (err as Error).message }, 400)
    }
  })

  app.patch("/api/v1/schedules/:name", async (c) => {
    const name = c.req.param("name")
    const existing = await service.getSchedule(name)
    if (!existing) return c.json({ error: "not_found" }, 404)
    const body = await c.req.json().catch(() => null)
    if (!body || typeof body !== "object") return c.json({ error: "invalid_body" }, 400)
    const patch = body as Record<string, unknown>
    const updated = await service.upsertSchedule({
      name: existing.name,
      dataset: typeof patch.dataset === "string" ? patch.dataset : existing.dataset,
      trigger: existing.trigger,
      cron: typeof patch.cron === "string" ? patch.cron : existing.cron,
      paused: typeof patch.paused === "boolean" ? patch.paused : existing.paused,
      createdAt: existing.createdAt,
    })
    return c.json(schedulePayload(updated))
  })

  app.get("/api/v1/schedules", async (c) => {
    const defs = await service.listSchedules()
    return c.json({
      schedules: defs.map(schedulePayload),
    })
  })

  app.get("/api/v1/schedules/:name", async (c) => {
    const name = c.req.param("name")
    const def = await service.getSchedule(name)
    if (!def) return c.json({ error: "not_found" }, 404)
    return c.json(schedulePayload(def))
  })

  app.post("/api/v1/schedules/:name/pause", async (c) => {
    const name = c.req.param("name")
    try {
      const def = await service.pause(name)
      return c.json(schedulePayload(def))
    } catch {
      return c.json({ error: "not_found" }, 404)
    }
  })

  app.post("/api/v1/schedules/:name/resume", async (c) => {
    const name = c.req.param("name")
    try {
      const def = await service.resume(name)
      return c.json(schedulePayload(def))
    } catch {
      return c.json({ error: "not_found" }, 404)
    }
  })

  app.get("/api/v1/schedules/:name/occurrences", async (c) => {
    const name = c.req.param("name")
    const occurrences = await service.listOccurrences(name)
    return c.json({
      occurrences: occurrences.map((o) => ({
        id: o.id,
        schedule_name: o.scheduleName,
        session_date: o.sessionDate,
        status: o.status,
        attempt: o.attempt,
        created_at: o.createdAt,
      })),
    })
  })

  return app
}

function schedulePayload(def: import("./control-plane-store").ScheduleDefinition) {
  return {
    name: def.name,
    dataset: def.dataset,
    trigger: def.trigger,
    cron: def.cron,
    paused: def.paused,
    fire_count: def.fireCount,
    last_fire_at: def.lastFireAt ?? null,
    created_at: def.createdAt,
    updated_at: def.updatedAt,
  }
}

function backfillPayload(bf: import("./control-plane-store").BackfillRequest) {
  return {
    id: bf.id,
    dataset: bf.dataset,
    start_session: bf.startSession,
    end_session: bf.endSession,
    session_count: bf.sessionCount,
    status: bf.status,
    admission_reason: bf.admissionReason ?? null,
    created_at: bf.createdAt,
    started_at: bf.startedAt ?? null,
    finished_at: bf.finishedAt ?? null,
    error_message: bf.errorMessage ?? null,
  }
}