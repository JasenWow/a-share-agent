/**
 * Orchestrator — the middle layer of the three-layer loop model.
 *
 * Owns the poll-run-record cycle:
 *   1. poll each Tracker for pending/retrying WorkItems
 *   2. for each, call AgentRunner.runWork (the inner turn loop)
 *   3. update StateStore + Tracker with the outcome
 *
 * Phase 5: synchronous single-pass runner. Scheduling (cron / interval)
 * and concurrency arrive with the orchestration spec.
 */

import type { TrackedWork, WorkItem, RunState } from "@aquan/core"
import type { Tracker } from "./trackers/tracker"
import type { AgentRuntime } from "./runtime"
import { runWork, type RunOpts } from "./agent-runner"
import { StateStore } from "./state-store"
import { sessionId } from "@aquan/core"

export interface OrchestratorOpts {
  runtime: AgentRuntime
  trackers: Tracker[]
  store?: StateStore
  runOpts?: RunOpts
}

export class Orchestrator {
  readonly store: StateStore
  private readonly runtime: AgentRuntime
  private readonly trackers: Tracker[]
  private readonly runOpts: RunOpts

  constructor(opts: OrchestratorOpts) {
    this.runtime = opts.runtime
    this.trackers = opts.trackers
    this.store = opts.store ?? new StateStore()
    this.runOpts = opts.runOpts ?? {}
  }

  /** Run one full pass: poll every tracker, run each pending item. */
  async tick(): Promise<{ ran: number; outcomes: Record<RunState, number> }> {
    const outcomes: Record<RunState, number> = {
      pending: 0,
      running: 0,
      retrying: 0,
      blocked: 0,
      done: 0,
      failed: 0,
    }
    let ran = 0

    for (const tracker of this.trackers) {
      const items = await tracker.fetchByStates(["pending", "retrying"])
      for (const item of items) {
        ran++
        const tracked = this.toTracked(item)
        this.store.upsert(tracked)
        const result = await runWork(this.runtime, tracked, this.runOpts)
        this.store.transition(tracked.id, result.state, {
          turnCount: result.turnCount,
          lastMessage: result.message,
          error: result.error,
        })
        await tracker.updateState(tracked.id, result.state, result.error)
        outcomes[result.state]++
      }
    }

    return { ran, outcomes }
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
