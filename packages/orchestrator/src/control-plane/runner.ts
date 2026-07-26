/**
 * runner — DataPipelineRunner interface.
 *
 * A pipeline run consists of one or more named stages executed in
 * order. The runner accepts a typed request and returns a typed
 * result; it does not know about DuckDB, ETL, or dbt. This is the
 * single seam tests use to swap real implementation for a fake.
 */

export type RunnerStageName = "etl" | "dbt"

export interface RunnerStageRequest {
  stage: RunnerStageName
  /** Dataset under operation. */
  dataset: string
  /** Trading session, YYYY-MM-DD. */
  sessionDate: string
  /** Free-form parameters the stage implementation may consume. */
  params?: Record<string, unknown>
  /** Working directory the runner may write into. */
  workdir?: string
}

export interface RunnerQualityCheck {
  /** Quality dimension (completeness / uniqueness / validity / freshness). */
  dimension: string
  /** Specific check name (e.g. "not_null_ods_equity_daily_code"). */
  check: string
  /** Did the check pass? */
  passed: boolean
  /** Is a failure blocking? dbt tests are blocking by default. */
  blocking: boolean
  /** Optional detail message. */
  message?: string
}

export interface RunnerStageResult {
  stage: RunnerStageName
  dataset: string
  sessionDate: string
  status: "ok" | "failed"
  /** Rows produced or consumed by the stage (when known). */
  rowCount?: number
  /** Path to a writeable artifact (Parquet file, dbt run artifact, etc). */
  artifactPath?: string
  /** Machine-readable error code, if status=failed. */
  errorCode?: string
  /** Human-readable error message, if status=failed. */
  errorMessage?: string
  /** Quality checks produced by this stage (dbt tests, pre-write guards). */
  qualityChecks?: RunnerQualityCheck[]
}

export interface RunnerRequest {
  dataset: string
  sessionDate: string
  workdir: string
}

export interface RunnerResult {
  dataset: string
  sessionDate: string
  stages: RunnerStageResult[]
}

export interface DataPipelineRunner {
  /**
   * Run the full pipeline (ETL → dbt). Implementations may be a fake
   * (in-memory), a subprocess (Bun.spawn), or anything else that
   * fulfils the contract.
   */
  run(req: RunnerRequest): Promise<RunnerResult>
}