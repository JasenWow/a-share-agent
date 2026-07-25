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
import { runWork, type RunOpts } from "./agent-runner"
import { ConcurrencyGate, SpendGuard } from "./policy"
import { StateStore } from "./state-store"
import type { Tracker } from "./trackers/tracker"

export interface OrchestratorOpts {
  runtime: AgentRuntime
  trackers: Tracker[]
  store?: StateStore
  runOpts?: RunOpts
  /** Policy bundle. Defaults to DEFAULT_POLICY (conservative caps). */
  policy?: PolicyBundle
}

export interface TickOutcome {
  ran: number
  /** How many items were skipped due to spend cap (left pending). */
  throttled: number
  outcomes: Record<RunState, number>
}

export class Orchestrator {
  readonly store: StateStore
  private readonly runtime: AgentRuntime
  private readonly trackers: Tracker[]
  private readonly runOpts: RunOpts
  readonly policy: PolicyBundle
  readonly spend: SpendGuard
  readonly concurrency: ConcurrencyGate

  constructor(opts: OrchestratorOpts) {
    this.runtime = opts.runtime
    this.trackers = opts.trackers
    this.store = opts.store ?? new StateStore()
    this.runOpts = opts.runOpts ?? {}
    this.policy = opts.policy ?? DEFAULT_POLICY
    this.spend = new SpendGuard(this.policy.budget)
    this.concurrency = new ConcurrencyGate(this.policy.concurrency)
  }

  /**
   * Run one full pass: poll every tracker, run each pending item that
   * passes the spend + concurrency checks.
   *
   * Items rejected by SpendGuard stay in `pending` and will be retried
   * on the next tick (when counters roll over or caps are raised).
   */
  async tick(): Promise<TickOutcome> {
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

    for (const tracker of this.trackers) {
      const items = await tracker.fetchByStates(["pending", "retrying"])
      for (const item of items) {
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
          this.store.transition(tracked.id, result.state, {
            turnCount: result.turnCount,
            lastMessage: result.message,
            error: result.error,
          })
          await tracker.updateState(tracked.id, result.state, result.error)
          outcomes[result.state]++
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
}
