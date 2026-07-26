/**
 * ControlPlaneStore — durable operational facts for the control plane.
 *
 * Stores three tables in DuckDB:
 *   pipeline_runs           — one row per PipelineRun
 *   pipeline_run_stages     — one row per stage result
 *   quality_check_results   — one row per QualityCheckResult
 *
 * Persistence rules (per ADR 0015, 0043):
 *   - Operational facts are retained without automatic purge.
 *   - One row per check (never aggregated).
 *   - Status transitions are append-friendly (current status lives on
 *     pipeline_runs, full transition history can be added later).
 *
 * Concurrency: DuckDB has a single writer per file. The ETL stage
 * writes Parquet files (not DuckDB), so this store is the only
 * DuckDB writer in the control plane's vertical slice.
 */

import { DuckDBInstance } from "@duckdb/node-api"

/* ----------------------------- Types ----------------------------- */

export type PipelineRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "quality_failed"
  | "failed"
  | "cancelled"

export type PipelineRunTrigger = "manual" | "scheduled" | "backfill" | "retry"

export interface PipelineRun {
  id: string
  dataset: string
  sessionDate: string
  trigger: PipelineRunTrigger
  status: PipelineRunStatus
  /** 1-based attempt counter within this run. */
  attempt: number
  /** When the run was created. */
  createdAt: string
  /** When execution began. */
  startedAt?: string
  /** When execution finished (any terminal status). */
  finishedAt?: string
  /** Free-form diagnostic surfaced to the dashboard. */
  errorCode?: string
  errorMessage?: string
}

export interface PipelineRunStage {
  runId: string
  stage: "etl" | "dbt"
  status: "ok" | "failed"
  rowCount?: number
  artifactPath?: string
  errorCode?: string
  errorMessage?: string
  startedAt: string
  finishedAt: string
}

export interface QualityCheckResult {
  runId: string
  dataset: string
  sessionDate: string
  /** Stage that produced the check. */
  stage: "etl" | "dbt"
  /** Quality dimension (completeness / uniqueness / validity / freshness). */
  dimension: string
  /** Specific check name (e.g. "min_row_count", "ohlc_invariant"). */
  check: string
  /** Did the check pass? */
  passed: boolean
  /** Is a failure of this check blocking? */
  blocking: boolean
  /** Numeric measurement underlying the verdict. */
  observed?: number
  /** Threshold for the verdict. */
  threshold?: number
  /** Detail message for debugging. */
  message?: string
  recordedAt: string
}

/* --------------------- Schedule definitions (PR2) --------------------- */

export type ScheduleTrigger = "manual" | "scheduled" | "backfill" | "retry"
export type ScheduleStatus = "active" | "paused"

export interface ScheduleDefinition {
  /** Unique name (e.g. "equity_daily"). */
  name: string
  /** Target dataset. */
  dataset: string
  /** Trigger type. */
  trigger: ScheduleTrigger
  /** 5-field cron expression. */
  cron: string
  /** Whether the schedule is paused. */
  paused: boolean
  /** How many times the schedule has fired. */
  fireCount: number
  /** Last fire time (ISO8601). */
  lastFireAt?: string
  /** Creation timestamp. */
  createdAt: string
  /** Last update timestamp. */
  updatedAt: string
}

export interface ScheduleOccurrence {
  id: string
  /** Which schedule created this occurrence. */
  scheduleName: string
  /** Target session_date. */
  sessionDate: string
  /** Final status of the run. */
  status: PipelineRunStatus
  /** Attempt counter. */
  attempt: number
  /** When the occurrence was queued. */
  createdAt: string
}

/* ----------------------- Backfill requests (PR3) ----------------------- */

export type BackfillStatus =
  | "queued"
  | "running"
  | "completed"
  | "partially_failed"
  | "failed"
  | "admission_rejected"

export interface BackfillRequest {
  id: string
  dataset: string
  /** Inclusive start session (YYYY-MM-DD). */
  startSession: string
  /** Inclusive end session (YYYY-MM-DD). */
  endSession: string
  /** Number of trading sessions in scope (<= 20 per ADR 0029). */
  sessionCount: number
  status: BackfillStatus
  /** Why the request was admitted or rejected. */
  admissionReason?: string
  createdAt: string
  startedAt?: string
  finishedAt?: string
  errorMessage?: string
}

export interface ControlPlaneStoreOptions {
  /** Path to a DuckDB file. ":memory:" for in-process tests. */
  path: string
}

/* --------------------------- Store class ------------------------- */

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id            TEXT PRIMARY KEY,
  dataset       TEXT NOT NULL,
  session_date  TEXT NOT NULL,
  trigger       TEXT NOT NULL,
  status        TEXT NOT NULL,
  attempt       INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL,
  started_at    TEXT,
  finished_at   TEXT,
  error_code    TEXT,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_run_stages (
  run_id        TEXT NOT NULL,
  stage         TEXT NOT NULL,
  status        TEXT NOT NULL,
  row_count     INTEGER,
  artifact_path TEXT,
  error_code    TEXT,
  error_message TEXT,
  started_at    TEXT NOT NULL,
  finished_at   TEXT NOT NULL,
  PRIMARY KEY (run_id, stage)
);

CREATE TABLE IF NOT EXISTS quality_check_results (
  run_id      TEXT NOT NULL,
  dataset     TEXT NOT NULL,
  session_date TEXT NOT NULL,
  stage       TEXT NOT NULL,
  dimension   TEXT NOT NULL,
  check_name  TEXT NOT NULL,
  passed      BOOLEAN NOT NULL,
  blocking    BOOLEAN NOT NULL,
  observed    DOUBLE,
  threshold   DOUBLE,
  message     TEXT,
  recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dataset_session
  ON pipeline_runs(dataset, session_date);
CREATE INDEX IF NOT EXISTS idx_quality_results_dataset_session
  ON quality_check_results(dataset, session_date);

CREATE TABLE IF NOT EXISTS schedule_definitions (
  name          TEXT PRIMARY KEY,
  dataset       TEXT NOT NULL,
  trigger       TEXT NOT NULL,
  cron          TEXT NOT NULL,
  paused        BOOLEAN NOT NULL DEFAULT false,
  fire_count    INTEGER NOT NULL DEFAULT 0,
  last_fire_at  TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_occurrences (
  id            TEXT PRIMARY KEY,
  schedule_name TEXT NOT NULL,
  session_date  TEXT NOT NULL,
  status        TEXT NOT NULL,
  attempt       INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedule_definitions_dataset
  ON schedule_definitions(dataset);
CREATE INDEX IF NOT EXISTS idx_schedule_occurrences_name_session
  ON schedule_occurrences(schedule_name, session_date);

CREATE TABLE IF NOT EXISTS backfill_requests (
  id               TEXT PRIMARY KEY,
  dataset          TEXT NOT NULL,
  start_session    TEXT NOT NULL,
  end_session      TEXT NOT NULL,
  session_count    INTEGER NOT NULL,
  status           TEXT NOT NULL,
  admission_reason TEXT,
  created_at       TEXT NOT NULL,
  started_at       TEXT,
  finished_at      TEXT,
  error_message    TEXT
);

CREATE INDEX IF NOT EXISTS idx_backfill_requests_dataset
  ON backfill_requests(dataset);
CREATE INDEX IF NOT EXISTS idx_backfill_requests_status
  ON backfill_requests(status);
`

// pipeline_runs gained a backfill_request_id column in PR3. Added
// idempotently so existing dev DBs pick it up without a migration tool.
const MIGRATION_PIPELINE_RUNS_BACKFILL_REF = `
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS backfill_request_id TEXT;
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_backfill ON pipeline_runs(backfill_request_id);
`;

export class ControlPlaneStore {
  private instance: Awaited<ReturnType<typeof DuckDBInstance.create>> | null = null
  private readonly path: string

  constructor(opts: ControlPlaneStoreOptions) {
    this.path = opts.path
  }

  private async getInstance() {
    if (!this.instance) {
      this.instance = await DuckDBInstance.create(this.path)
      const conn = await this.instance.connect()
      try {
        await conn.run(SCHEMA_SQL)
        await conn.run(MIGRATION_PIPELINE_RUNS_BACKFILL_REF)
      } finally {
        conn.closeSync()
      }
    }
    return this.instance
  }

  /* -------- pipeline_runs -------- */

  async insertPipelineRun(run: PipelineRun): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO pipeline_runs
         (id, dataset, session_date, trigger, status, attempt, created_at, started_at, finished_at, error_code, error_message)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          run.id,
          run.dataset,
          run.sessionDate,
          run.trigger,
          run.status,
          run.attempt,
          run.createdAt,
          run.startedAt ?? null,
          run.finishedAt ?? null,
          run.errorCode ?? null,
          run.errorMessage ?? null,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async updatePipelineRunStatus(
    id: string,
    status: PipelineRunStatus,
    patch: Partial<Pick<PipelineRun, "startedAt" | "finishedAt" | "errorCode" | "errorMessage" | "attempt">> = {},
  ): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `UPDATE pipeline_runs
         SET status = ?,
             started_at = COALESCE(?, started_at),
             finished_at = COALESCE(?, finished_at),
             error_code = COALESCE(?, error_code),
             error_message = COALESCE(?, error_message),
             attempt = COALESCE(?, attempt)
         WHERE id = ?;`,
        [
          status,
          patch.startedAt ?? null,
          patch.finishedAt ?? null,
          patch.errorCode ?? null,
          patch.errorMessage ?? null,
          patch.attempt ?? null,
          id,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async getPipelineRun(id: string): Promise<PipelineRun | null> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(
        `SELECT * FROM pipeline_runs WHERE id = ?;`,
        [id],
      )
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      if (rows.length === 0) return null
      return rowToPipelineRun(rows[0] as Row)
    } finally {
      conn.closeSync()
    }
  }

  async listPipelineRuns(dataset?: string): Promise<PipelineRun[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const sql = dataset
        ? `SELECT * FROM pipeline_runs WHERE dataset = ? ORDER BY created_at DESC;`
        : `SELECT * FROM pipeline_runs ORDER BY created_at DESC;`
      const reader = await conn.runAndReadAll(sql, dataset ? [dataset] : [])
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map((r) => rowToPipelineRun(r as Row))
    } finally {
      conn.closeSync()
    }
  }

  /* -------- pipeline_run_stages -------- */

  async insertPipelineRunStage(stage: PipelineRunStage): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO pipeline_run_stages
         (run_id, stage, status, row_count, artifact_path, error_code, error_message, started_at, finished_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          stage.runId,
          stage.stage,
          stage.status,
          stage.rowCount ?? null,
          stage.artifactPath ?? null,
          stage.errorCode ?? null,
          stage.errorMessage ?? null,
          stage.startedAt,
          stage.finishedAt,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async listPipelineRunStages(runId: string): Promise<PipelineRunStage[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(
        `SELECT * FROM pipeline_run_stages WHERE run_id = ? ORDER BY started_at ASC;`,
        [runId],
      )
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map(rowToPipelineRunStage)
    } finally {
      conn.closeSync()
    }
  }

  /* -------- quality_check_results -------- */

  async insertQualityCheckResult(result: QualityCheckResult): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO quality_check_results
         (run_id, dataset, session_date, stage, dimension, check_name, passed, blocking, observed, threshold, message, recorded_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          result.runId,
          result.dataset,
          result.sessionDate,
          result.stage,
          result.dimension,
          result.check,
          result.passed,
          result.blocking,
          result.observed ?? null,
          result.threshold ?? null,
          result.message ?? null,
          result.recordedAt,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async listQualityCheckResults(filter: {
    runId?: string
    dataset?: string
    sessionDate?: string
  } = {}): Promise<QualityCheckResult[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const where: string[] = []
      const params: unknown[] = []
      if (filter.runId) {
        where.push("run_id = ?")
        params.push(filter.runId)
      }
      if (filter.dataset) {
        where.push("dataset = ?")
        params.push(filter.dataset)
      }
      if (filter.sessionDate) {
        where.push("session_date = ?")
        params.push(filter.sessionDate)
      }
      const sql =
        `SELECT * FROM quality_check_results ` +
        (where.length ? `WHERE ${where.join(" AND ")} ` : "") +
        `ORDER BY recorded_at ASC;`
      const reader = await conn.runAndReadAll(sql, params)
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map(rowToQualityCheckResult)
    } finally {
      conn.closeSync()
    }
  }

  /* -------- schedule_definitions (PR2) -------- */

  async upsertScheduleDefinition(def: ScheduleDefinition): Promise<void> {
    const now = new Date().toISOString()
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO schedule_definitions
         (name, dataset, trigger, cron, paused, fire_count, last_fire_at, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)
         ON CONFLICT(name) DO UPDATE SET
           dataset = excluded.dataset,
           trigger = excluded.trigger,
           cron = excluded.cron,
           paused = excluded.paused,
           updated_at = excluded.updated_at;`,
        [
          def.name,
          def.dataset,
          def.trigger,
          def.cron,
          def.paused,
          def.createdAt,
          now,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async getScheduleDefinition(name: string): Promise<ScheduleDefinition | null> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(`SELECT * FROM schedule_definitions WHERE name = ?;`, [name])
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      if (rows.length === 0) return null
      return rowToScheduleDefinition(rows[0] as Row)
    } finally {
      conn.closeSync()
    }
  }

  async listScheduleDefinitions(): Promise<ScheduleDefinition[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(`SELECT * FROM schedule_definitions ORDER BY name;`)
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map((r) => rowToScheduleDefinition(r as Row))
    } finally {
      conn.closeSync()
    }
  }

  async updateScheduleFireCount(name: string, fireAt: string): Promise<void> {
    const now = new Date().toISOString()
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `UPDATE schedule_definitions
         SET fire_count = fire_count + 1,
             last_fire_at = ?,
             updated_at = ?
         WHERE name = ?;`,
        [fireAt, now, name],
      )
    } finally {
      conn.closeSync()
    }
  }

  /* -------- schedule_occurrences (PR2) -------- */

  async insertScheduleOccurrence(occ: ScheduleOccurrence): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO schedule_occurrences
         (id, schedule_name, session_date, status, attempt, created_at)
         VALUES (?, ?, ?, ?, ?, ?);`,
        [occ.id, occ.scheduleName, occ.sessionDate, occ.status, occ.attempt, occ.createdAt],
      )
    } finally {
      conn.closeSync()
    }
  }

  async listScheduleOccurrences(scheduleName: string): Promise<ScheduleOccurrence[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(
        `SELECT * FROM schedule_occurrences WHERE schedule_name = ? ORDER BY created_at DESC;`,
        [scheduleName],
      )
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map(rowToScheduleOccurrence)
    } finally {
      conn.closeSync()
    }
  }

  /* -------- backfill_requests (PR3) -------- */

  async insertBackfillRequest(req: BackfillRequest): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `INSERT INTO backfill_requests
         (id, dataset, start_session, end_session, session_count, status, admission_reason, created_at, started_at, finished_at, error_message)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          req.id,
          req.dataset,
          req.startSession,
          req.endSession,
          req.sessionCount,
          req.status,
          req.admissionReason ?? null,
          req.createdAt,
          req.startedAt ?? null,
          req.finishedAt ?? null,
          req.errorMessage ?? null,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async updateBackfillStatus(
    id: string,
    status: BackfillStatus,
    patch: Partial<Pick<BackfillRequest, "admissionReason" | "startedAt" | "finishedAt" | "errorMessage">> = {},
  ): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `UPDATE backfill_requests
         SET status = ?,
             admission_reason = COALESCE(?, admission_reason),
             started_at = COALESCE(?, started_at),
             finished_at = COALESCE(?, finished_at),
             error_message = COALESCE(?, error_message)
         WHERE id = ?;`,
        [
          status,
          patch.admissionReason ?? null,
          patch.startedAt ?? null,
          patch.finishedAt ?? null,
          patch.errorMessage ?? null,
          id,
        ],
      )
    } finally {
      conn.closeSync()
    }
  }

  async getBackfillRequest(id: string): Promise<BackfillRequest | null> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(
        `SELECT * FROM backfill_requests WHERE id = ?;`,
        [id],
      )
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      if (rows.length === 0) return null
      return rowToBackfillRequest(rows[0])
    } finally {
      conn.closeSync()
    }
  }

  async listBackfillRequests(dataset?: string): Promise<BackfillRequest[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const sql = dataset
        ? `SELECT * FROM backfill_requests WHERE dataset = ? ORDER BY created_at DESC;`
        : `SELECT * FROM backfill_requests ORDER BY created_at DESC;`
      const reader = await conn.runAndReadAll(sql, dataset ? [dataset] : [])
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map(rowToBackfillRequest)
    } finally {
      conn.closeSync()
    }
  }

  /** Update a pipeline_run to link it to a parent backfill request. */
  async linkRunToBackfill(runId: string, backfillRequestId: string): Promise<void> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      await conn.run(
        `UPDATE pipeline_runs SET backfill_request_id = ? WHERE id = ?;`,
        [backfillRequestId, runId],
      )
    } finally {
      conn.closeSync()
    }
  }

  /** List pipeline_runs belonging to a backfill request. */
  async listBackfillChildRuns(backfillRequestId: string): Promise<PipelineRun[]> {
    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(
        `SELECT * FROM pipeline_runs WHERE backfill_request_id = ? ORDER BY created_at ASC;`,
        [backfillRequestId],
      )
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      return rows.map((r) => rowToPipelineRun(r as Row))
    } finally {
      conn.closeSync()
    }
  }

  async close(): Promise<void> {
    if (!this.instance) return
    try {
      this.instance.closeSync()
    } catch {
      // best-effort
    }
    this.instance = null
  }
}

/* ----------------------------- Mappers ----------------------------- */

interface Row {
  id: string
  dataset: string
  session_date: string
  trigger: string
  status: string
  attempt: number | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  error_message: string | null
  name: string
  cron: string
  paused: boolean
  fire_count: number | null
  last_fire_at: string | null
  updated_at: string
  backfill_request_id: string | null
}

function rowToPipelineRun(row: Row): PipelineRun {
  return {
    id: row.id,
    dataset: row.dataset,
    sessionDate: row.session_date,
    trigger: row.trigger as PipelineRunTrigger,
    status: row.status as PipelineRunStatus,
    attempt: row.attempt ?? 1,
    createdAt: row.created_at,
    startedAt: row.started_at ?? undefined,
    finishedAt: row.finished_at ?? undefined,
    errorCode: row.error_code ?? undefined,
    errorMessage: row.error_message ?? undefined,
  }
}

function rowToPipelineRunStage(row: Record<string, unknown>): PipelineRunStage {
  return {
    runId: String(row.run_id),
    stage: row.stage as "etl" | "dbt",
    status: row.status as "ok" | "failed",
    rowCount: row.row_count == null ? undefined : Number(row.row_count),
    artifactPath: row.artifact_path == null ? undefined : String(row.artifact_path),
    errorCode: row.error_code == null ? undefined : String(row.error_code),
    errorMessage: row.error_message == null ? undefined : String(row.error_message),
    startedAt: String(row.started_at),
    finishedAt: String(row.finished_at),
  }
}

function rowToQualityCheckResult(row: Record<string, unknown>): QualityCheckResult {
  return {
    runId: String(row.run_id),
    dataset: String(row.dataset),
    sessionDate: String(row.session_date),
    stage: row.stage as "etl" | "dbt",
    dimension: String(row.dimension),
    check: String(row.check_name),
    passed: Boolean(row.passed),
    blocking: Boolean(row.blocking),
    observed: row.observed == null ? undefined : Number(row.observed),
    threshold: row.threshold == null ? undefined : Number(row.threshold),
    message: row.message == null ? undefined : String(row.message),
    recordedAt: String(row.recorded_at),
  }
}

function rowToScheduleDefinition(row: Row): ScheduleDefinition {
  return {
    name: row.name,
    dataset: row.dataset,
    trigger: row.trigger as ScheduleTrigger,
    cron: row.cron,
    paused: Boolean(row.paused),
    fireCount: row.fire_count ?? 0,
    lastFireAt: row.last_fire_at ?? undefined,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

function rowToScheduleOccurrence(row: Record<string, unknown>): ScheduleOccurrence {
  return {
    id: String(row.id),
    scheduleName: String(row.schedule_name),
    sessionDate: String(row.session_date),
    status: row.status as PipelineRunStatus,
    attempt: row.attempt == null ? 1 : Number(row.attempt),
    createdAt: String(row.created_at),
  }
}

function rowToBackfillRequest(row: Record<string, unknown>): BackfillRequest {
  return {
    id: String(row.id),
    dataset: String(row.dataset),
    startSession: String(row.start_session),
    endSession: String(row.end_session),
    sessionCount: Number(row.session_count),
    status: row.status as BackfillStatus,
    admissionReason: row.admission_reason == null ? undefined : String(row.admission_reason),
    createdAt: String(row.created_at),
    startedAt: row.started_at == null ? undefined : String(row.started_at),
    finishedAt: row.finished_at == null ? undefined : String(row.finished_at),
    errorMessage: row.error_message == null ? undefined : String(row.error_message),
  }
}