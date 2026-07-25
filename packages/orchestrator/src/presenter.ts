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
