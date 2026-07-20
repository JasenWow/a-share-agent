/**
 * StateStore — in-memory record of TrackedWork.
 *
 * Phase 5: simple Map-based store. Future iterations may persist to
 * DuckDB via @aquan/server's adapter.
 */

import type { TrackedWork, RunState } from "@aquan/core"

export class StateStore {
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
