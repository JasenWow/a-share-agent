"use client"

/**
 * API client for the orchestrator server (:3010 by default).
 *
 * The orchestrator runs as a separate Bun process and exposes a small
 * HTTP surface for the dashboard to poll:
 *   GET /api/v1/state       — counts + per-state work lists + spend + schedules
 *   GET /api/v1/work/:id    — single work item
 *   GET /api/v1/schedules   — scheduler status
 *   GET /api/v1/spend       — spend counters + caps
 *   POST /api/v1/tick       — manual tick (with optional ?trackers= filter)
 *
 * This module follows the same pattern as api-clients/databases.ts: SWR
 * key generators alongside typed fetchers, returns { data?, error? }
 * shapes instead of throwing. The orchestrator has no auth (localhost only).
 */

import type { AgentEvent, AgentEventKind, RunState, TrackedWork } from "@aquan/core"
import { ORCHESTRATOR_URL } from "./config"

// --- Response shapes (mirror orchestrator/src/presenter.ts) ---

export interface SpendPayload {
  daily: number
  weekly: number
  monthly: number
  dailyCap: number | null
  weeklyCap: number | null
  monthlyCap: number | null
  dayStart: string
  weekStart: string
  monthStart: string
}

export interface ScheduleStatusPayload {
  spec: {
    cron: string
    trackers?: string[]
    name?: string
  }
  fireCount: number
  errorCount: number
  lastError?: string
  lastFireAt?: string
}

export interface StatePayload {
  generatedAt: string
  counts: Record<RunState, number>
  running: TrackedWork[]
  retrying: TrackedWork[]
  blocked: TrackedWork[]
  pending: TrackedWork[]
  recent: TrackedWork[]
  spend?: SpendPayload
  schedules?: ScheduleStatusPayload[]
}

export interface TickOutcome {
  ran: number
  throttled: number
  outcomes: Record<RunState, number>
}

// --- History (/loops view) shapes (mirror orchestrator/src/presenter.ts) ---

export interface HistoryBucket {
  done: number
  failed: number
  retrying: number
  total: number
}

export interface HistoryPayload {
  generatedAt: string
  items: TrackedWork[]
  byTracker: Record<string, HistoryBucket>
  byDay: Record<string, HistoryBucket>
  totals: HistoryBucket
}

export interface HistoryQuery {
  state?: RunState
  tracker?: string
  since?: string
  limit?: number
}

export interface WorkEventsPayload {
  workId: string
  events: AgentEvent[]
  count: number
}

export interface WorkEventsQuery {
  kinds?: AgentEventKind[]
  since?: string
  limit?: number
}

// --- SWR key generators ---

export function getOrchestrationStateKey() {
  return `${ORCHESTRATOR_URL}/api/v1/state`
}

export function getOrchestrationWorkKey(id: string) {
  return `${ORCHESTRATOR_URL}/api/v1/work/${id}`
}

export function getOrchestrationWorkEventsKey(id: string, opts: WorkEventsQuery = {}) {
  const params = new URLSearchParams()
  if (opts.kinds && opts.kinds.length > 0) params.set("kind", opts.kinds.join(","))
  if (opts.since) params.set("since", opts.since)
  if (opts.limit) params.set("limit", String(opts.limit))
  const qs = params.toString()
  return `${ORCHESTRATOR_URL}/api/v1/work/${encodeURIComponent(id)}/events${qs ? `?${qs}` : ""}`
}

export function getOrchestrationSchedulesKey() {
  return `${ORCHESTRATOR_URL}/api/v1/schedules`
}

export function getOrchestrationSpendKey() {
  return `${ORCHESTRATOR_URL}/api/v1/spend`
}

export function getLoopsHistoryKey(opts: HistoryQuery = {}) {
  const params = new URLSearchParams()
  if (opts.state) params.set("state", opts.state)
  if (opts.tracker) params.set("tracker", opts.tracker)
  if (opts.since) params.set("since", opts.since)
  if (opts.limit) params.set("limit", String(opts.limit))
  const qs = params.toString()
  return `${ORCHESTRATOR_URL}/api/v1/loops${qs ? `?${qs}` : ""}`
}

// --- Fetchers ---

async function fetchJson(url: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(url, init)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json()
}

export async function getOrchestrationState(): Promise<StatePayload> {
  return (await fetchJson(getOrchestrationStateKey())) as StatePayload
}

export async function getOrchestrationWork(id: string): Promise<TrackedWork | null> {
  try {
    return (await fetchJson(getOrchestrationWorkKey(id))) as TrackedWork
  } catch {
    return null
  }
}

export async function getOrchestrationWorkEvents(
  id: string,
  opts: WorkEventsQuery = {},
): Promise<WorkEventsPayload> {
  return (await fetchJson(getOrchestrationWorkEventsKey(id, opts))) as WorkEventsPayload
}

export async function getOrchestrationSchedules(): Promise<{
  schedules: ScheduleStatusPayload[]
  running: boolean
}> {
  return (await fetchJson(getOrchestrationSchedulesKey())) as {
    schedules: ScheduleStatusPayload[]
    running: boolean
  }
}

export async function getOrchestrationSpend(): Promise<SpendPayload> {
  return (await fetchJson(getOrchestrationSpendKey())) as SpendPayload
}

export async function getLoopsHistory(opts: HistoryQuery = {}): Promise<HistoryPayload> {
  return (await fetchJson(getLoopsHistoryKey(opts))) as HistoryPayload
}

// --- Candidate review (promote / reject) ---

export interface FactorMutationResponse {
  ok: boolean
  factorId: number
  targetStatus?: "active" | "rejected"
  error?: "not-found" | "not-candidate" | "unavailable"
  currentStatus?: string | null
  message?: string
  reviewer?: string
  notes?: string
  reason?: string
}

export async function promoteCandidate(
  factorId: number,
  opts: { reviewer?: string; notes?: string } = {},
): Promise<FactorMutationResponse> {
  const res = await fetch(
    `${ORCHESTRATOR_URL}/api/v1/factors/${factorId}/promote`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    },
  )
  return (await res.json()) as FactorMutationResponse
}

export async function rejectCandidate(
  factorId: number,
  opts: { reason?: string; reviewer?: string } = {},
): Promise<FactorMutationResponse> {
  const res = await fetch(
    `${ORCHESTRATOR_URL}/api/v1/factors/${factorId}/reject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    },
  )
  return (await res.json()) as FactorMutationResponse
}

// --- Candidate list (read path for the review panel) ---

export interface CandidateFactor {
  id: number
  name: string
  expression: string
  hypothesis: string | null
  operators: string[]
  dataFields: string[]
  ic: number | null
  icir: number | null
  turnover: number | null
  sharpe: number | null
  maxDrawdown: number | null
  universe: string | null
  period: string | null
  confidence: number | null
  rationale: string | null
  status: string
  sourceExperimentId: number | null
  createdAt: string | null
}

export interface CandidatesPayload {
  candidates: CandidateFactor[]
  count: number
  source: "internal-store" | "unavailable"
}

export function getCandidatesKey() {
  return `${ORCHESTRATOR_URL}/api/v1/factors/candidates`
}

export async function getCandidates(): Promise<CandidatesPayload> {
  return (await fetchJson(getCandidatesKey())) as CandidatesPayload
}

export async function triggerTick(trackers?: string[]): Promise<TickOutcome> {
  const qs = trackers && trackers.length > 0 ? `?trackers=${encodeURIComponent(trackers.join(","))}` : ""
  return (await fetchJson(`${ORCHESTRATOR_URL}/api/v1/tick${qs}`, { method: "POST" })) as TickOutcome
}
