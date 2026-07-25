/**
 * Policy enforcers — runtime guards that bound what the orchestrator
 * will let an agent do before it makes any provider call.
 *
 * Two guards, mirroring pi-dispatch's pre-flight checks:
 *
 *   SpendGuard       — job-count cap per day/week/month.
 *                      Checked BEFORE the run starts; never trust the
 *                      agent or the provider to self-limit.
 *
 *   ConcurrencyGate  — max simultaneous runs. Default 1 (serial).
 *                      Backed by a Promise-based semaphore so callers
 *                      can `await acquire()` and get a release fn.
 *
 * Why in-process and not Valkey/BullMQ:
 *   aquan's first deployment is a single Bun process. In-memory state
 *   is correct for that scope. When we go multi-process, these
 *   interfaces stay; only the backing implementation changes (e.g. a
 *   DuckDB row counter, or a Redis INCR).
 */

import type { BudgetPolicy, ConcurrencyPolicy } from "@aquan/core"

/**
 * Reason a job was rejected by SpendGuard.canStart().
 * Surfaced on the dashboard so operators know which cap to bump.
 */
export type SpendRejectReason = "daily" | "weekly" | "monthly"

export interface SpendCheckResult {
  allowed: boolean
  reason?: SpendRejectReason
}

export interface SpendStats {
  /** Start of the current day (UTC midnight). */
  dayStart: Date
  /** Start of the current 7-day rolling window. */
  weekStart: Date
  /** Start of the current calendar month. */
  monthStart: Date
  /** Jobs counted in each window so far. */
  daily: number
  weekly: number
  monthly: number
}

/**
 * SpendGuard — enforces BudgetPolicy.
 *
 * Counters are in-memory. They reset automatically when the current
 * day/week/month rolls over (checked on each call).
 */
export class SpendGuard {
  private readonly clock: () => Date
  private dayStart: Date
  private weekStart: Date
  private monthStart: Date
  private daily = 0
  private weekly = 0
  private monthly = 0

  constructor(
    private readonly policy: BudgetPolicy,
    clock: () => Date = () => new Date(),
  ) {
    this.clock = clock
    this.dayStart = startOfDay(this.clock())
    this.weekStart = startOfDay(addDays(this.clock(), -6))
    this.monthStart = startOfMonth(this.clock())
  }

  /**
   * Pre-run check.
   *
   * Returns allowed=false if starting one more job would exceed any cap.
   * The reason names the tightest cap that blocked it (in priority order:
   * daily > weekly > monthly) so the dashboard can show the binding one.
   */
  canStart(): SpendCheckResult {
    this.maybeRollWindows()
    if (this.policy.dailyCap !== null && this.daily >= this.policy.dailyCap) {
      return { allowed: false, reason: "daily" }
    }
    if (this.policy.weeklyCap !== null && this.weekly >= this.policy.weeklyCap) {
      return { allowed: false, reason: "weekly" }
    }
    if (this.policy.monthlyCap !== null && this.monthly >= this.policy.monthlyCap) {
      return { allowed: false, reason: "monthly" }
    }
    return { allowed: true }
  }

  /**
   * Record a finished job (success OR failure — an attempt is a spend).
   *
   * Called by the orchestrator after runWork returns, regardless of the
   * outcome state. This matches pi-dispatch's "container starts are
   * the spend unit, not their result".
   */
  recordSpend(): void {
    this.maybeRollWindows()
    this.daily += 1
    this.weekly += 1
    this.monthly += 1
  }

  /** Snapshot of current counters — for dashboard / observability. */
  getStats(): SpendStats {
    this.maybeRollWindows()
    return {
      dayStart: this.dayStart,
      weekStart: this.weekStart,
      monthStart: this.monthStart,
      daily: this.daily,
      weekly: this.weekly,
      monthly: this.monthly,
    }
  }

  /** Reset all counters. Test-only. */
  reset(): void {
    this.dayStart = startOfDay(this.clock())
    this.weekStart = startOfDay(addDays(this.clock(), -6))
    this.monthStart = startOfMonth(this.clock())
    this.daily = 0
    this.weekly = 0
    this.monthly = 0
  }

  /**
   * Roll over any windows whose boundary has passed.
   *
   * Daily window resets at UTC midnight. Weekly window is a rolling
   * 7-day window anchored to "6 days ago at midnight" (so it always
   * covers today + the previous 6 days). Monthly window resets on the
   * first of the month.
   */
  private maybeRollWindows(): void {
    const now = this.clock()
    const todayStart = startOfDay(now)
    if (todayStart > this.dayStart) {
      this.dayStart = todayStart
      this.daily = 0
    }
    const weekAnchor = startOfDay(addDays(now, -6))
    if (weekAnchor > this.weekStart) {
      this.weekStart = weekAnchor
      this.weekly = 0
    }
    const monthAnchor = startOfMonth(now)
    if (monthAnchor > this.monthStart) {
      this.monthStart = monthAnchor
      this.monthly = 0
    }
  }
}

/**
 * ConcurrencyGate — bounds simultaneous agent runs.
 *
 * Promise-based semaphore. acquire() resolves immediately when a slot
 * is free; otherwise the caller awaits until a previous holder calls
 * the returned release function. The release function is idempotent
 * (safe to call from a `finally` block that may run twice on edge cases).
 */
export class ConcurrencyGate {
  private active = 0
  private waiters: Array<() => void> = []

  constructor(private readonly policy: ConcurrencyPolicy) {
    if (policy.maxConcurrent < 1) {
      throw new Error(`ConcurrencyPolicy.maxConcurrent must be >= 1, got ${policy.maxConcurrent}`)
    }
  }

  /** Number of slots currently held. */
  getActive(): number {
    return this.active
  }

  /** Number of callers waiting in acquire(). */
  getWaiting(): number {
    return this.waiters.length
  }

  /**
   * Acquire a slot. Returns a release function the caller MUST invoke
   * (typically via `try { ... } finally { release() }`).
   */
  acquire(): Promise<() => void> {
    if (this.active < this.policy.maxConcurrent) {
      this.active += 1
      return Promise.resolve(this.makeRelease())
    }
    return new Promise((resolve) => {
      this.waiters.push(() => {
        this.active += 1
        resolve(this.makeRelease())
      })
    })
  }

  private makeRelease(): () => void {
    let released = false
    return () => {
      if (released) return
      released = true
      this.active -= 1
      const next = this.waiters.shift()
      if (next) next()
    }
  }
}

// --- date helpers (UTC, no DST surprises) ---

function startOfDay(d: Date): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
}

function startOfMonth(d: Date): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1))
}

function addDays(d: Date, days: number): Date {
  const copy = new Date(d.getTime())
  copy.setUTCDate(copy.getUTCDate() + days)
  return copy
}
