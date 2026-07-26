/**
 * Orchestrator — the middle layer of the three-layer loop model.
 *
 * Owns the poll-run-record cycle:
 *   1. poll each Tracker for pending/retrying WorkItems
 *   2. for each: pre-flight spend check → acquire concurrency slot
 *   3. call AgentRunner.runWork (the inner turn loop)
 *   4. record spend + transition StateStore + Tracker
 *
 * Hardening (2026-07-25): every run goes through SpendGuard and
 * ConcurrencyGate before any provider call. See
 * docs/superpowers/specs/2026-07-25-orchestrator-hardening-design.md.
 */

import { DEFAULT_POLICY, sessionId } from "@aquan/core"
import type { PolicyBundle, RunState, TrackedWork, WorkItem } from "@aquan/core"
import type { AgentRuntime } from "./runtime"
import { runWork, type RunOpts, type RunOutcome } from "./agent-runner"
import { ConcurrencyGate, SpendGuard } from "./policy"
import type { IStateStore } from "./state-store"
import { StateStore } from "./state-store"
import { Scheduler, type ScheduleSpec } from "./scheduler"
import type { Tracker } from "./trackers/tracker"

export interface OrchestratorOpts {
  runtime: AgentRuntime
  trackers: Tracker[]
  /**
   * State store. Defaults to in-memory StateStore; pass SqliteStateStore
   * for persistence across restarts.
   */
  store?: IStateStore
  runOpts?: RunOpts
  /** Policy bundle. Defaults to DEFAULT_POLICY (conservative caps). */
  policy?: PolicyBundle
  /**
   * SpendGuard override. Pass a PersistedSpendGuard (sharing the same
   * SQLite file as `store`) to make the spend counters durable.
   * Defaults to an in-memory SpendGuard built from policy.budget.
   */
  spendGuard?: SpendGuard
}

export interface TickOutcome {
  ran: number
  /** How many items were skipped due to spend cap (left pending). */
  throttled: number
  outcomes: Record<RunState, number>
}

export interface TickOptions {
  /** Only run trackers whose name is in this list; omit for all trackers. */
  trackerNames?: string[]
}

export class Orchestrator {
  readonly store: IStateStore
  private readonly runtime: AgentRuntime
  private readonly trackers: Tracker[]
  private readonly runOpts: RunOpts
  readonly policy: PolicyBundle
  readonly spend: SpendGuard
  readonly concurrency: ConcurrencyGate
  private scheduler: Scheduler | undefined

  constructor(opts: OrchestratorOpts) {
    this.runtime = opts.runtime
    this.trackers = opts.trackers
    this.store = opts.store ?? new StateStore()
    this.runOpts = opts.runOpts ?? {}
    this.policy = opts.policy ?? DEFAULT_POLICY
    this.spend = opts.spendGuard ?? new SpendGuard(this.policy.budget)
    this.concurrency = new ConcurrencyGate(this.policy.concurrency)
  }

  /**
   * Run one full pass: poll every tracker, run each pending item that
   * passes the spend + concurrency checks.
   *
   * Items rejected by SpendGuard stay in `pending` and will be retried
   * on the next tick (when counters roll over or caps are raised).
   *
   * @param opts.trackerNames restrict this tick to a subset of trackers
   *        (used by the Scheduler so different schedules can drive
   *        different tracker sets on different cadences).
   */
  async tick(opts?: TickOptions): Promise<TickOutcome> {
    const outcomes: Record<RunState, number> = {
      pending: 0,
      running: 0,
      retrying: 0,
      blocked: 0,
      done: 0,
      failed: 0,
    }
    let ran = 0
    let throttled = 0

    const filter = opts?.trackerNames
    const trackers = filter
      ? this.trackers.filter((t) => filter.includes(t.name))
      : this.trackers

    for (const tracker of trackers) {
      const items = await tracker.fetchByStates(["pending", "retrying"])
      for (const item of items) {
        // Backoff gate: a `retrying` item whose backoff window hasn't
        // elapsed is skipped this tick (re-fetched next tick). This is
        // what turns "poll every 30s" into exponential backoff.
        const existing = this.store.get(item.id)
        if (existing?.nextRetryAt && new Date(existing.nextRetryAt) > new Date()) {
          outcomes.retrying += 1
          continue
        }

        // Hardening rule 1: pre-run spend check (before any provider call).
        const check = this.spend.canStart()
        if (!check.allowed) {
          throttled += 1
          outcomes.pending += 1
          continue
        }

        // Hardening rule 2: bounded concurrency.
        const release = await this.concurrency.acquire()
        try {
          const tracked = this.toTracked(item)
          this.store.upsert(tracked)
          const result = await runWork(this.runtime, tracked, this.runOpts)
          // Spend is recorded whether the run succeeded or failed —
          // an attempt is a spend unit (pi-dispatch model).
          this.spend.recordSpend()

          // Persist the event stream before result goes out of scope.
          // Without this the whole turn-by-turn timeline (tool calls,
          // messages, turn_end markers) would be GC'd — only lastMessage
          // would survive. Retried attempts append a second batch so the
          // timeline shows the full story.
          if (result.events.length > 0) {
            this.store.appendEvents(tracked.id, result.events)
          }

          // Retry decision: only infra failures retry (pi-dispatch rule —
          // never pay twice for the same agent answer). Agent-done/blocked
          // and agent-failed are terminal.
          const nextState = this.decideRetry(tracked, result)
          const patch: Partial<TrackedWork> = {
            turnCount: result.turnCount,
            lastMessage: result.message,
            error: result.error,
          }
          if (nextState === "retrying") {
            // Increment attempt for the upcoming retry, and stamp the
            // backoff deadline so the next tick knows when to unblock.
            patch.attempt = tracked.attempt + 1
            patch.nextRetryAt = this.computeBackoff(tracked.attempt)
          }
          // Clear nextRetryAt on any non-retrying transition so a later
          // manual re-run (e.g. dashboard "Run now") isn't gated by a
          // stale deadline. transition() merges the patch, so omitting
          // the key keeps the old value — explicitly clear it.
          if (nextState !== "retrying") {
            patch.nextRetryAt = undefined
          }

          this.store.transition(tracked.id, nextState, patch)
          await tracker.updateState(tracked.id, nextState, result.error)
          outcomes[nextState]++
          ran += 1
        } finally {
          release()
        }
      }
    }

    return { ran, throttled, outcomes }
  }

  private toTracked(item: WorkItem): TrackedWork {
    const existing = this.store.get(item.id)
    const now = new Date().toISOString()
    return (
      existing ?? {
        ...item,
        state: "running",
        attempt: 1,
        sessionId: sessionId(),
        startedAt: now,
        stateChangedAt: now,
      }
    )
  }

  /**
   * Decide the next RunState after a run attempt. Only infrastructure
   * failures (failureKind="infra") are eligible for retry, and only while
   * attempts remain. Everything else — done, blocked, agent-failed — is
   * terminal. Mirrors pi-dispatch: "never pay twice for the same answer."
   */
  private decideRetry(work: TrackedWork, result: RunOutcome): RunState {
    // done/blocked pass through unchanged.
    if (result.state !== "failed") return result.state
    // An agent-decided failure (failureKind="agent" or undefined) is terminal.
    if (result.failureKind !== "infra") return "failed"
    // Infra failure: retry only if attempts remain.
    if (work.attempt >= this.policy.retry.maxAttempts) return "failed"
    return "retrying"
  }

  /**
   * Compute the backoff deadline for the next retry. `completedAttempts`
   * is the number of attempts already run (the just-failed attempt's
   * count). Delay = backoffMs * 2^(completedAttempts-1):
   *   attempt 1 fails → wait backoffMs * 1
   *   attempt 2 fails → wait backoffMs * 2
   *   attempt 3 fails → wait backoffMs * 4
   */
  private computeBackoff(completedAttempts: number): string {
    const { backoffMs } = this.policy.retry
    const delay = backoffMs * Math.pow(2, completedAttempts - 1)
    return new Date(Date.now() + delay).toISOString()
  }

  /**
   * Start the in-process Scheduler driving this orchestrator.
   * Each ScheduleSpec becomes one cron job that fires `tick({ trackerNames })`.
   *
   * Safe to call multiple times — subsequent calls replace the previous
   * scheduler (the old one is stopped first).
   */
  start(schedules: ScheduleSpec[]): Scheduler {
    this.stop()
    this.scheduler = new Scheduler(this)
    this.scheduler.start(schedules)
    return this.scheduler
  }

  /** Halt the scheduler if one is running. Safe to call when not started. */
  stop(): void {
    this.scheduler?.stop()
    this.scheduler = undefined
  }

  /** Current scheduler (if any). Useful for dashboard / tests. */
  getScheduler(): Scheduler | undefined {
    return this.scheduler
  }
}
