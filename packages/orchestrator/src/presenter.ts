/**
 * Presenter — project StateStore + SpendGuard + Scheduler into HTTP
 * response shapes.
 *
 * Mirrors Symphony's Presenter.state_payload: counts + per-state lists,
 * extended with spend statistics and scheduler status so the dashboard
 * can render everything from a single endpoint.
 */

import type { TrackedWork } from "@aquan/core"
import type { SpendGuard } from "./policy"
import type { Scheduler } from "./scheduler"
import type { IStateStore } from "./state-store"

export interface SpendPayload {
  /** Current window counters. */
  daily: number
  weekly: number
  monthly: number
  /** Configured caps (null = unlimited). */
  dailyCap: number | null
  weeklyCap: number | null
  monthlyCap: number | null
  /** Window boundaries (ISO8601). */
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
  counts: {
    running: number
    retrying: number
    blocked: number
    pending: number
    done: number
    failed: number
  }
  running: TrackedWork[]
  retrying: TrackedWork[]
  blocked: TrackedWork[]
  pending: TrackedWork[]
  recent: TrackedWork[]
  /** Spend snapshot — only present when a SpendGuard is wired in. */
  spend?: SpendPayload
  /** Scheduler status — only present when orch.start() has been called. */
  schedules?: ScheduleStatusPayload[]
}

export interface StatePayloadOptions {
  spend?: SpendGuard
  scheduler?: Scheduler
}

export function statePayload(
  store: IStateStore,
  opts: StatePayloadOptions = {},
): StatePayload {
  const all = store.listAll()
  const payload: StatePayload = {
    generatedAt: new Date().toISOString(),
    counts: {
      running: count(all, "running"),
      retrying: count(all, "retrying"),
      blocked: count(all, "blocked"),
      pending: count(all, "pending"),
      done: count(all, "done"),
      failed: count(all, "failed"),
    },
    running: filter(all, "running"),
    retrying: filter(all, "retrying"),
    blocked: filter(all, "blocked"),
    pending: filter(all, "pending"),
    recent: all
      .slice()
      .sort((a, b) => (b.stateChangedAt ?? "").localeCompare(a.stateChangedAt ?? ""))
      .slice(0, 20),
  }

  if (opts.spend) {
    const stats = opts.spend.getStats()
    const policy = opts.spend.policy ?? { dailyCap: null, weeklyCap: null, monthlyCap: null }
    payload.spend = {
      daily: stats.daily,
      weekly: stats.weekly,
      monthly: stats.monthly,
      dailyCap: policy.dailyCap,
      weeklyCap: policy.weeklyCap,
      monthlyCap: policy.monthlyCap,
      dayStart: stats.dayStart.toISOString(),
      weekStart: stats.weekStart.toISOString(),
      monthStart: stats.monthStart.toISOString(),
    }
  }

  if (opts.scheduler) {
    payload.schedules = opts.scheduler.status()
  }

  return payload
}

function count(items: TrackedWork[], state: TrackedWork["state"]): number {
  return items.filter((w) => w.state === state).length
}

function filter(items: TrackedWork[], state: TrackedWork["state"]): TrackedWork[] {
  return items.filter((w) => w.state === state)
}

// --- History payload (the /loops view) ---

/** Counts for a single bucket (tracker or day). */
export interface HistoryBucket {
  done: number
  failed: number
  retrying: number
  total: number
}

export interface HistoryPayload {
  generatedAt: string
  /** Items already sorted newest-first by stateChangedAt. */
  items: TrackedWork[]
  /** Aggregated counts keyed by derived tracker name. */
  byTracker: Record<string, HistoryBucket>
  /** Aggregated counts keyed by derived day (YYYY-MM-DD). */
  byDay: Record<string, HistoryBucket>
  totals: HistoryBucket
}

export interface HistoryPayloadOptions {
  /** Filter items further by tracker (derived from id prefix). */
  tracker?: string
  states?: import("@aquan/core").RunState[]
  since?: string
  limit?: number
}

/**
 * Build the /loops payload. Tracker + day are derived from the WorkItem id
 * (e.g. `factor-mine-2026-07-20` → tracker "factor-mining", day "2026-07-20")
 * rather than from timestamps — the id is stable across restarts and always
 * carries both, while startedAt may be null for never-run items.
 */
export function historyPayload(
  store: IStateStore,
  opts: HistoryPayloadOptions = {},
): HistoryPayload {
  let items = store.listHistory({
    states: opts.states,
    since: opts.since,
    limit: opts.limit,
  })
  if (opts.tracker) {
    items = items.filter((w) => deriveTracker(w.id) === opts.tracker)
  }

  const byTracker: Record<string, HistoryBucket> = {}
  const byDay: Record<string, HistoryBucket> = {}
  const totals: HistoryBucket = { done: 0, failed: 0, retrying: 0, total: 0 }

  for (const w of items) {
    const t = deriveTracker(w.id)
    const d = deriveDay(w.id)
    bump(byTracker, t, w.state)
    if (d) bump(byDay, d, w.state)
    bumpTotals(totals, w.state)
  }

  return {
    generatedAt: new Date().toISOString(),
    items,
    byTracker,
    byDay,
    totals,
  }
}

function bump(buckets: Record<string, HistoryBucket>, key: string, state: TrackedWork["state"]): void {
  if (!buckets[key]) buckets[key] = { done: 0, failed: 0, retrying: 0, total: 0 }
  bumpTotals(buckets[key], state)
}

function bumpTotals(b: HistoryBucket, state: TrackedWork["state"]): void {
  b.total += 1
  if (state === "done") b.done += 1
  else if (state === "failed") b.failed += 1
  else if (state === "retrying") b.retrying += 1
}

/** Derive the tracker name from a WorkItem id prefix. */
export function deriveTracker(id: string): string {
  if (id.startsWith("factor-mine-")) return "factor-mining"
  if (id.startsWith("free-exploration-")) return "free-exploration"
  return "unknown"
}

/** Derive the day (YYYY-MM-DD) from a WorkItem id suffix, or null. */
export function deriveDay(id: string): string | null {
  const m = id.match(/(\d{4}-\d{2}-\d{2})$/)
  return m ? m[1] : null
}
