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

import type { AgentEvent, AgentEventKind, RunState, TrackedWork } from "@aquan/core"

/** Filter options for history queries. */
export interface HistoryQuery {
  /** Only include items in these states. Default: done + failed + retrying. */
  states?: RunState[]
  /** ISO8601 — only items with state_changed_at >= this. */
  since?: string
  /** Max items to return. Default 200. */
  limit?: number
}

/** Filter options for per-work-item event queries. */
export interface EventQuery {
  /** Only include events of these kinds. */
  kinds?: AgentEventKind[]
  /** ISO8601 — only events with at >= this. */
  since?: string
  /** Max events to return. Default 500. */
  limit?: number
}

/** Default states queried by the history view (terminal + in-retry). */
export const DEFAULT_HISTORY_STATES: RunState[] = ["done", "failed", "retrying"]
export const DEFAULT_HISTORY_LIMIT = 200
export const DEFAULT_EVENT_LIMIT = 500

export interface IStateStore {
  upsert(work: TrackedWork): void
  get(id: string): TrackedWork | undefined
  listByStates(states: RunState[]): TrackedWork[]
  listAll(): TrackedWork[]
  transition(id: string, nextState: RunState, patch?: Partial<TrackedWork>): TrackedWork
  /**
   * Query historical work items (terminal + retrying states by default),
   * newest-first by stateChangedAt. Used by the /loops dashboard to show
   * trends without pulling the full table.
   */
  listHistory(opts?: HistoryQuery): TrackedWork[]
  /**
   * Persist agent events for a work item. Append-only — a retried work
   * appends a second batch so the timeline shows the full story (attempt
   * 1 failing, attempt 2 succeeding) rather than only the last attempt.
   */
  appendEvents(workId: string, events: AgentEvent[]): void
  /**
   * Load a work item's events, ascending by time (timeline order).
   */
  listEvents(workId: string, opts?: EventQuery): AgentEvent[]
}

/**
 * StateStore — in-memory IStateStore.
 *
 * Default for tests and ephemeral runs. For persistence across restarts,
 * use SqliteStateStore.
 */
export class StateStore implements IStateStore {
  private byId = new Map<string, TrackedWork>()
  private eventsByWork = new Map<string, AgentEvent[]>()

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

  listHistory(opts: HistoryQuery = {}): TrackedWork[] {
    const states = opts.states ?? DEFAULT_HISTORY_STATES
    const limit = opts.limit ?? DEFAULT_HISTORY_LIMIT
    return [...this.byId.values()]
      .filter((w) => states.includes(w.state))
      .filter((w) => (opts.since ? (w.stateChangedAt ?? "") >= opts.since : true))
      .sort((a, b) => (b.stateChangedAt ?? "").localeCompare(a.stateChangedAt ?? ""))
      .slice(0, limit)
  }

  appendEvents(workId: string, events: AgentEvent[]): void {
    const existing = this.eventsByWork.get(workId) ?? []
    this.eventsByWork.set(workId, [...existing, ...events])
  }

  listEvents(workId: string, opts: EventQuery = {}): AgentEvent[] {
    const limit = opts.limit ?? DEFAULT_EVENT_LIMIT
    const all = this.eventsByWork.get(workId) ?? []
    return all
      .filter((e) => (opts.kinds ? opts.kinds.includes(e.kind) : true))
      .filter((e) => (opts.since ? e.at >= opts.since : true))
      .sort((a, b) => a.at.localeCompare(b.at))
      .slice(0, limit)
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
