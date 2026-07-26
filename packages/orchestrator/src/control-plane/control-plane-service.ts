/**
 * ControlPlaneService — orchestrates store + runner for run-now.
 *
 * Glue layer between the HTTP handlers and the system boundaries
 * (store, runner, evaluator). Pure orchestration; no business rules
 * about trading sessions, quality thresholds, or scheduling.
 */

import type { DataPipelineRunner, RunnerResult, RunnerStageResult } from "./runner"
import type {
  ControlPlaneStore,
  PipelineRun,
  QualityCheckResult,
  ScheduleDefinition,
  ScheduleOccurrence,
  BackfillRequest,
  BackfillStatus,
} from "./control-plane-store"
import type { SessionExpander } from "./session-expander"
import type { BackfillAdmissionPolicy } from "./backfill-admission"
import { DefaultBackfillAdmissionPolicy } from "./backfill-admission"

export interface ControlPlaneServiceDeps {
  store: ControlPlaneStore
  runner: DataPipelineRunner
  /** Expands a [start,end] range into trading sessions (backfill). */
  sessionExpander?: SessionExpander
  /** Admission gate for backfill requests. */
  admissionPolicy?: BackfillAdmissionPolicy
  /** Generates unique run ids; injectable so tests can stub. */
  idGenerator?: () => string
  /** Returns current time; injectable so tests can stub. */
  clock?: () => Date
}

export interface RunNowRequest {
  dataset: string
  sessionDate: string
  trigger?: "manual" | "scheduled" | "backfill" | "retry"
}

export interface RunNowResult {
  run: PipelineRun
  stages: RunnerStageResult[]
}

const QUALITY_DIMENSIONS = new Set([
  "completeness",
  "uniqueness",
  "validity",
  "freshness",
])

/**
 * Build a QualityCheckResult from a stage result. Stages report
 * coarse-grained row counts; the service synthesizes a
 * `completeness.min_row_count` check from etl stage results.
 * dbt stage results carry an attached quality report via params
 * (out of scope for the first slice; the fake returns empty checks).
 */
function synthesizeQualityChecks(args: {
  runId: string
  dataset: string
  sessionDate: string
  stage: RunnerStageResult
  recordedAt: string
}): QualityCheckResult[] {
  const { runId, dataset, sessionDate, stage, recordedAt } = args
  if (stage.status === "failed") {
    return [
      {
        runId,
        dataset,
        sessionDate,
        stage: stage.stage,
        dimension: "validity",
        check: "stage_succeeded",
        passed: false,
        blocking: true,
        message: stage.errorMessage ?? stage.errorCode ?? "stage failed",
        recordedAt,
      },
    ]
  }
  if (stage.stage === "etl" && typeof stage.rowCount === "number") {
    return [
      {
        runId,
        dataset,
        sessionDate,
        stage: "etl",
        dimension: "completeness",
        check: "min_row_count",
        passed: stage.rowCount >= 4000,
        blocking: true,
        observed: stage.rowCount,
        threshold: 4000,
        message: `${stage.rowCount} rows produced`,
        recordedAt,
      },
    ]
  }
  return []
}

export class ControlPlaneService {
  private readonly store: ControlPlaneStore
  private readonly runner: DataPipelineRunner
  private readonly sessionExpander: SessionExpander | undefined
  private readonly admissionPolicy: BackfillAdmissionPolicy
  private readonly idGenerator: () => string
  private readonly clock: () => Date

  constructor(deps: ControlPlaneServiceDeps) {
    this.store = deps.store
    this.runner = deps.runner
    this.sessionExpander = deps.sessionExpander
    this.admissionPolicy = deps.admissionPolicy ?? new DefaultBackfillAdmissionPolicy()
    this.idGenerator = deps.idGenerator ?? defaultIdGenerator
    this.clock = deps.clock ?? (() => new Date())
    this.runner = deps.runner
    this.idGenerator = deps.idGenerator ?? defaultIdGenerator
    this.clock = deps.clock ?? (() => new Date())
  }

  /**
   * Create + execute a single PipelineRun.
   *
   * Lifecycle:
   *   queued → running → (completed | quality_failed | failed)
   *
   * Quality checks observed at runtime are persisted as
   * QualityCheckResult rows.
   */
  async runNow(req: RunNowRequest): Promise<RunNowResult> {
    const id = this.idGenerator()
    const createdAt = this.clock().toISOString()

    const run: PipelineRun = {
      id,
      dataset: req.dataset,
      sessionDate: req.sessionDate,
      trigger: req.trigger ?? "manual",
      status: "queued",
      attempt: 1,
      createdAt,
    }
    await this.store.insertPipelineRun(run)

    const startedAt = this.clock().toISOString()
    await this.store.updatePipelineRunStatus(id, "running", { startedAt })

    const workdir = `/tmp/${id}`
    let runnerResult: RunnerResult
    try {
      runnerResult = await this.runner.run({
        dataset: req.dataset,
        sessionDate: req.sessionDate,
        workdir,
      })
    } catch (err) {
      const finishedAt = this.clock().toISOString()
      await this.store.updatePipelineRunStatus(id, "failed", {
        finishedAt,
        errorCode: "runner_error",
        errorMessage: err instanceof Error ? err.message : String(err),
      })
      const finalRun = (await this.store.getPipelineRun(id))!
      return { run: finalRun, stages: [] }
    }

    // Persist stage rows + synthesized quality checks.
    for (const stage of runnerResult.stages) {
      const stageStartedAt = createdAt
      const stageFinishedAt = this.clock().toISOString()
      await this.store.insertPipelineRunStage({
        runId: id,
        stage: stage.stage,
        status: stage.status,
        rowCount: stage.rowCount,
        artifactPath: stage.artifactPath,
        errorCode: stage.errorCode,
        errorMessage: stage.errorMessage,
        startedAt: stageStartedAt,
        finishedAt: stageFinishedAt,
      })
      // Persist quality checks: runner-provided checks take precedence
      // (real dbt tests), then synthesize any missing checks from the
      // stage result (e.g. min_row_count from etl row count).
      const runnerChecks = stage.qualityChecks ?? []
      const synthesized = synthesizeQualityChecks({
        runId: id,
        dataset: req.dataset,
        sessionDate: req.sessionDate,
        stage,
        recordedAt: stageFinishedAt,
      })
      const allChecks = [...runnerChecks.map((qc) => ({
        runId: id,
        dataset: req.dataset,
        sessionDate: req.sessionDate,
        stage: stage.stage,
        dimension: qc.dimension,
        check: qc.check,
        passed: qc.passed,
        blocking: qc.blocking,
        message: qc.message,
        recordedAt: stageFinishedAt,
      })), ...synthesized]
      for (const check of allChecks) {
        await this.store.insertQualityCheckResult(check)
      }
    }

    // Decide final status. Quality-failed takes precedence over
    // generic failure because the ETL may have written but dbt rejected.
    const finishedAt = this.clock().toISOString()
    const dbtFailed = runnerResult.stages.some(
      (s) => s.stage === "dbt" && s.status === "failed",
    )
    const etlFailed = runnerResult.stages.find(
      (s) => s.stage === "etl",
    )?.status === "failed"

    let finalStatus: PipelineRun["status"]
    let errorCode: string | undefined
    let errorMessage: string | undefined
    if (dbtFailed) {
      finalStatus = "quality_failed"
      const dbtStage = runnerResult.stages.find((s) => s.stage === "dbt")!
      errorCode = dbtStage.errorCode
      errorMessage = dbtStage.errorMessage
    } else if (etlFailed) {
      finalStatus = "failed"
      const etlStage = runnerResult.stages.find((s) => s.stage === "etl")!
      errorCode = etlStage.errorCode
      errorMessage = etlStage.errorMessage
    } else {
      finalStatus = "completed"
    }

    await this.store.updatePipelineRunStatus(id, finalStatus, {
      finishedAt,
      errorCode,
      errorMessage,
    })

    const finalRun = (await this.store.getPipelineRun(id))!
    return { run: finalRun, stages: runnerResult.stages }
  }

  async getRun(id: string): Promise<PipelineRun | null> {
    return this.store.getPipelineRun(id)
  }

  async listRuns(dataset?: string): Promise<PipelineRun[]> {
    return this.store.listPipelineRuns(dataset)
  }

  async listStages(runId: string) {
    return this.store.listPipelineRunStages(runId)
  }

  async listQualityChecks(filter: { runId?: string; dataset?: string } = {}) {
    return this.store.listQualityCheckResults(filter)
  }

  /* ----------------------- Schedule control (PR2) ----------------------- */

  /**
   * Register or update a schedule definition. Fire counters are NOT
   * reset on update — only the definition fields (cron, paused, etc.)
   * are written.
   */
  async upsertSchedule(def: Omit<ScheduleDefinition, "fireCount" | "lastFireAt" | "updatedAt">): Promise<ScheduleDefinition> {
    const full: ScheduleDefinition = {
      ...def,
      fireCount: 0,
      createdAt: def.createdAt ?? this.clock().toISOString(),
      updatedAt: this.clock().toISOString(),
    } as ScheduleDefinition
    await this.store.upsertScheduleDefinition(full)
    const got = await this.store.getScheduleDefinition(def.name)
    return got!
  }

  async getSchedule(name: string): Promise<ScheduleDefinition | null> {
    return this.store.getScheduleDefinition(name)
  }

  async listSchedules(): Promise<ScheduleDefinition[]> {
    return this.store.listScheduleDefinitions()
  }

  async pause(name: string): Promise<ScheduleDefinition> {
    const def = await this.store.getScheduleDefinition(name)
    if (!def) throw new Error(`Schedule not found: ${name}`)
    await this.store.upsertScheduleDefinition({ ...def, paused: true })
    const updated = await this.store.getScheduleDefinition(name)
    return updated!
  }

  async resume(name: string): Promise<ScheduleDefinition> {
    const def = await this.store.getScheduleDefinition(name)
    if (!def) throw new Error(`Schedule not found: ${name}`)
    await this.store.upsertScheduleDefinition({ ...def, paused: false })
    const updated = await this.store.getScheduleDefinition(name)
    return updated!
  }

  /**
   * Scheduler tick entry point. Called by the cron driver.
   *
   * - Looks up the named schedule; skips if missing or paused.
   * - Records a schedule_occurrence.
   * - Bumps fire_count + last_fire_at.
   * - Delegates to runNow with trigger=scheduled and the given sessionDate.
   *
   * Returns null when the fire was skipped (missing or paused).
   */
  async fireSchedule(name: string, sessionDate: string): Promise<{
    skipped: true
    reason: "missing" | "paused"
  } | {
    skipped: false
    occurrence: ScheduleOccurrence
    run: RunNowResult
  }> {
    const def = await this.store.getScheduleDefinition(name)
    if (!def) return { skipped: true, reason: "missing" }
    if (def.paused) return { skipped: true, reason: "paused" }

    const nowIso = this.clock().toISOString()
    const occurrence: ScheduleOccurrence = {
      id: this.idGenerator().replace("run-", "occ-"),
      scheduleName: name,
      sessionDate,
      status: "queued",
      attempt: 1,
      createdAt: nowIso,
    }
    await this.store.insertScheduleOccurrence(occurrence)
    await this.store.updateScheduleFireCount(name, nowIso)

    const run = await this.runNow({
      dataset: def.dataset,
      sessionDate,
      trigger: "scheduled",
    })

    return { skipped: false, occurrence, run }
  }

  async listOccurrences(scheduleName: string): Promise<ScheduleOccurrence[]> {
    return this.store.listScheduleOccurrences(scheduleName)
  }

  /* ----------------------- Backfill requests (PR3) ----------------------- */

  /**
   * Create + persist a backfill request. Runs admission + scope validation
   * but does NOT execute. Returns the persisted request (status may be
   * admission_rejected). Call executeBackfill to run an admitted request.
   */
  async createBackfill(req: {
    dataset: string
    startSession: string
    endSession: string
  }): Promise<BackfillRequest> {
    if (!this.sessionExpander) {
      throw new Error("Backfill requires a sessionExpander to be configured")
    }
    const sessions = this.sessionExpander.expand(req.startSession, req.endSession)
    const sessionCount = sessions.length

    const now = this.clock()
    const admission = this.admissionPolicy.admit({
      sessionCount,
      endSession: req.endSession,
      now,
    })

    const id = `bf-${this.idGenerator().replace(/^run-/, "")}`
    const backfill: BackfillRequest = {
      id,
      dataset: req.dataset,
      startSession: req.startSession,
      endSession: req.endSession,
      sessionCount,
      status: admission.admitted ? "queued" : "admission_rejected",
      admissionReason: admission.reason,
      createdAt: now.toISOString(),
    }
    await this.store.insertBackfillRequest(backfill)
    return backfill
  }

  /**
   * Execute an admitted backfill request. Non-interruptible: runs every
   * session to a terminal outcome, then aggregates the parent status
   * (ADR 0027, 0030).
   *
   *   all succeed      → completed
   *   some succeed      → partially_failed
   *   none succeed       → failed
   */
  async executeBackfill(id: string): Promise<BackfillRequest> {
    const backfill = await this.store.getBackfillRequest(id)
    if (!backfill) throw new Error(`Backfill not found: ${id}`)
    if (backfill.status === "admission_rejected") {
      throw new Error(`Cannot execute admission_rejected backfill: ${id}`)
    }
    if (!this.sessionExpander) {
      throw new Error("Backfill requires a sessionExpander to be configured")
    }

    const sessions = this.sessionExpander.expand(backfill.startSession, backfill.endSession)
    const startedAt = this.clock().toISOString()
    await this.store.updateBackfillStatus(id, "running", { startedAt })

    let succeeded = 0
    let failed = 0
    for (const sessionDate of sessions) {
      // Continue-and-aggregate: catch per-session failures so one bad
      // session doesn't stop the rest (ADR 0030).
      try {
        const result = await this.runNow({
          dataset: backfill.dataset,
          sessionDate,
          trigger: "backfill",
        })
        await this.store.linkRunToBackfill(result.run.id, id)
        if (result.run.status === "completed") {
          succeeded += 1
        } else {
          failed += 1
        }
      } catch {
        failed += 1
      }
    }

    const finishedAt = this.clock().toISOString()
    let finalStatus: BackfillStatus
    let errorMessage: string | undefined
    if (failed === 0) {
      finalStatus = "completed"
    } else if (succeeded > 0) {
      finalStatus = "partially_failed"
      errorMessage = `${failed} of ${sessions.length} session(s) failed`
    } else {
      finalStatus = "failed"
      errorMessage = `all ${sessions.length} session(s) failed`
    }
    await this.store.updateBackfillStatus(id, finalStatus, { finishedAt, errorMessage })
    const updated = await this.store.getBackfillRequest(id)
    return updated!
  }

  async getBackfill(id: string): Promise<BackfillRequest | null> {
    return this.store.getBackfillRequest(id)
  }

  async listBackfills(dataset?: string): Promise<BackfillRequest[]> {
    return this.store.listBackfillRequests(dataset)
  }

  async listBackfillChildRuns(id: string): Promise<PipelineRun[]> {
    return this.store.listBackfillChildRuns(id)
  }
}

function defaultIdGenerator(): string {
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

// Keep QUALITY_DIMENSIONS exported so consumers (semantic metrics)
// can validate filter keys. Tree-shake if unused.
void QUALITY_DIMENSIONS