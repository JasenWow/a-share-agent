"use client"

/**
 * API client for the data-operations control plane (:3020 by default).
 *
 * Mirrors the endpoints defined in packages/orchestrator/src/control-plane/http.ts.
 * Follows the same pattern as api-clients/orchestration.ts: typed fetchers
 * + SWR key generators.
 */

import { CONTROL_PLANE_URL } from "./config"

// --- Types (mirror control-plane-store.ts) ---

export interface PipelineRun {
  id: string
  dataset: string
  session_date: string
  status: "queued" | "running" | "completed" | "quality_failed" | "failed" | "cancelled"
  trigger: "manual" | "scheduled" | "backfill" | "retry"
  attempt: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  error_message: string | null
}

export interface PipelineRunDetail extends PipelineRun {
  stages: Array<{
    stage: "etl" | "dbt"
    status: "ok" | "failed"
    row_count: number | null
    artifact_path: string | null
    error_code: string | null
    error_message: string | null
    started_at: string
    finished_at: string
  }>
  quality_checks: Array<{
    stage: "etl" | "dbt"
    dimension: string
    check: string
    passed: boolean
    blocking: boolean
    observed: number | null
    threshold: number | null
    message: string | null
    recorded_at: string
  }>
}

export interface DatasetStatus {
  dataset: string
  latest_run: {
    id: string
    status: string
    session_date: string
    finished_at: string | null
  } | null
  last_accepted: {
    id: string
    session_date: string
    finished_at: string | null
  } | null
  last_quality_check: {
    dimension: string
    check: string
    passed: boolean
    recorded_at: string
  } | null
}

export interface QualityResult {
  run_id: string
  dataset: string
  session_date: string
  stage: "etl" | "dbt"
  dimension: string
  check: string
  passed: boolean
  blocking: boolean
  observed: number | null
  threshold: number | null
  message: string | null
  recorded_at: string
}

export interface ScheduleDef {
  name: string
  dataset: string
  trigger: string
  cron: string
  paused: boolean
  fire_count: number
  last_fire_at: string | null
  created_at: string
  updated_at: string
}

export interface BackfillRequest {
  id: string
  dataset: string
  start_session: string
  end_session: string
  session_count: number
  status: "queued" | "running" | "completed" | "partially_failed" | "failed" | "admission_rejected"
  admission_reason: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface MetricSpec {
  name: string
  description: string
  unit: string
  category: string
  source_table: string
  dimensions: string[]
}

export interface MetricQueryResult {
  rows: Record<string, unknown>[]
  columns: string[]
}

// --- SWR key generators ---

export function getDatasetStatusKey(name: string) {
  return `${CONTROL_PLANE_URL}/api/v1/datasets/${name}/status`
}
export function getPipelineRunsKey(dataset?: string) {
  const qs = dataset ? `?dataset=${dataset}` : ""
  return `${CONTROL_PLANE_URL}/api/v1/pipeline-runs${qs}`
}
export function getPipelineRunKey(id: string) {
  return `${CONTROL_PLANE_URL}/api/v1/pipeline-runs/${id}`
}
export function getQualityResultsKey(dataset?: string) {
  const qs = dataset ? `?dataset=${dataset}` : ""
  return `${CONTROL_PLANE_URL}/api/v1/quality/results${qs}`
}
export function getSchedulesKey() {
  return `${CONTROL_PLANE_URL}/api/v1/schedules`
}
export function getBackfillsKey(dataset?: string) {
  const qs = dataset ? `?dataset=${dataset}` : ""
  return `${CONTROL_PLANE_URL}/api/v1/backfills${qs}`
}
export function getMetricsCatalogKey() {
  return `${CONTROL_PLANE_URL}/api/v1/metrics`
}

// --- Fetchers ---

async function fetchJson(url: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(url, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function getDatasetStatus(name: string): Promise<DatasetStatus> {
  return (await fetchJson(getDatasetStatusKey(name))) as DatasetStatus
}

export async function getPipelineRuns(dataset?: string): Promise<{ runs: PipelineRun[] }> {
  return (await fetchJson(getPipelineRunsKey(dataset))) as { runs: PipelineRun[] }
}

export async function getPipelineRun(id: string): Promise<PipelineRunDetail> {
  return (await fetchJson(getPipelineRunKey(id))) as PipelineRunDetail
}

export async function getQualityResults(dataset?: string): Promise<{ results: QualityResult[] }> {
  return (await fetchJson(getQualityResultsKey(dataset))) as { results: QualityResult[] }
}

export async function getSchedules(): Promise<{ schedules: ScheduleDef[] }> {
  return (await fetchJson(getSchedulesKey())) as { schedules: ScheduleDef[] }
}

export async function getBackfills(dataset?: string): Promise<{ backfills: BackfillRequest[] }> {
  return (await fetchJson(getBackfillsKey(dataset))) as { backfills: BackfillRequest[] }
}

export async function getMetricsCatalog(): Promise<{ metrics: MetricSpec[] }> {
  return (await fetchJson(getMetricsCatalogKey())) as { metrics: MetricSpec[] }
}

// --- Mutations ---

export async function createPipelineRun(opts: {
  dataset: string
  session_date: string
}): Promise<PipelineRun> {
  const res = await fetch(`${CONTROL_PLANE_URL}/api/v1/pipeline-runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  })
  return (await res.json()) as PipelineRun
}

export async function pauseSchedule(name: string): Promise<ScheduleDef> {
  const res = await fetch(`${CONTROL_PLANE_URL}/api/v1/schedules/${name}/pause`, { method: "POST" })
  return (await res.json()) as ScheduleDef
}

export async function resumeSchedule(name: string): Promise<ScheduleDef> {
  const res = await fetch(`${CONTROL_PLANE_URL}/api/v1/schedules/${name}/resume`, { method: "POST" })
  return (await res.json()) as ScheduleDef
}

export async function createBackfill(opts: {
  dataset: string
  start_session: string
  end_session: string
}): Promise<BackfillRequest> {
  const res = await fetch(`${CONTROL_PLANE_URL}/api/v1/backfills`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  })
  return (await res.json()) as BackfillRequest
}

export async function queryMetric(opts: {
  metric: string
  filters?: Record<string, string>
}): Promise<MetricQueryResult> {
  const res = await fetch(`${CONTROL_PLANE_URL}/api/v1/metrics/query`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  })
  return (await res.json()) as MetricQueryResult
}