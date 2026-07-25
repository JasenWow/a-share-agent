/**
 * IStateStore — the storage contract the orchestrator depends on.
 *
 * Two implementations live alongside this interface:
 *   - StateStore            (in-memory, for tests + ephemeral runs)
 *   - SqliteStateStore      (bun:sqlite-backed, survives restarts)
 *
 * The orchestrator doesn't care which one it gets; both honour the
 * same surface so tests can use the fast in-memory version while
 * production wires the SQLite one.
 */

import type { RunState, TrackedWork } from "@aquan/core"

export interface IStateStore {
  upsert(work: TrackedWork): void
  get(id: string): TrackedWork | undefined
  listByStates(states: RunState[]): TrackedWork[]
  listAll(): TrackedWork[]
  transition(id: string, nextState: RunState, patch?: Partial<TrackedWork>): TrackedWork
}

/**
 * StateStore — in-memory IStateStore.
 *
 * Default for tests and ephemeral runs. For persistence across restarts,
 * use SqliteStateStore.
 */
export class StateStore implements IStateStore {
  private byId = new Map<string, TrackedWork>()

  upsert(work: TrackedWork): void {
    this.byId.set(work.id, work)
  }

  get(id: string): TrackedWork | undefined {
    return this.byId.get(id)
  }

  listByStates(states: RunState[]): TrackedWork[] {
    return [...this.byId.values()].filter((w) => states.includes(w.state))
  }

  listAll(): TrackedWork[] {
    return [...this.byId.values()]
  }

  transition(id: string, nextState: RunState, patch: Partial<TrackedWork> = {}): TrackedWork {
    const current = this.byId.get(id)
    if (!current) throw new Error(`StateStore: unknown id ${id}`)
    const updated: TrackedWork = {
      ...current,
      ...patch,
      state: nextState,
      stateChangedAt: new Date().toISOString(),
    }
    this.byId.set(id, updated)
    return updated
  }
}
