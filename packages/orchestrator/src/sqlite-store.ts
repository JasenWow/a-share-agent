/**
 * SqliteStateStore — IStateStore backed by `bun:sqlite`.
 *
 * Persists TrackedWork across process restarts. Uses a single row per
 * work-item with the full WorkItem JSON stored alongside the indexed
 * columns, so schema evolution doesn't lose data (rebuild the index
 * columns from JSON on read if a field is missing).
 *
 * The DB handle is exposed via the `db` getter so PersistedSpendGuard
 * can share the same file (it writes to a separate `spend_log` table).
 *
 * Concurrency: the orchestrator's ConcurrencyGate defaults to 1 (serial),
 * so writes never overlap. bun:sqlite's WAL mode is enabled anyway as
 * cheap insurance against future concurrent readers (the dashboard).
 */

import { Database } from "bun:sqlite"
import type { AgentEvent, RunState, TrackedWork } from "@aquan/core"
import type { EventQuery, HistoryQuery, IStateStore } from "./state-store"
import {
  DEFAULT_EVENT_LIMIT,
  DEFAULT_HISTORY_LIMIT,
  DEFAULT_HISTORY_STATES,
} from "./state-store"

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS tracked_works (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  session_id TEXT,
  turn_count INTEGER,
  started_at TEXT,
  last_event_at TEXT,
  last_event TEXT,
  last_message TEXT,
  state_changed_at TEXT,
  error TEXT,
  work_item_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_id TEXT NOT NULL,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  event_json TEXT NOT NULL
);
`

const UPSERT_SQL = `
INSERT INTO tracked_works (
  id, state, attempt, session_id, turn_count,
  started_at, last_event_at, last_event, last_message,
  state_changed_at, error, work_item_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
  state = excluded.state,
  attempt = excluded.attempt,
  session_id = excluded.session_id,
  turn_count = excluded.turn_count,
  started_at = excluded.started_at,
  last_event_at = excluded.last_event_at,
  last_event = excluded.last_event,
  last_message = excluded.last_message,
  state_changed_at = excluded.state_changed_at,
  error = excluded.error,
  work_item_json = excluded.work_item_json;
`

const SELECT_BY_ID_SQL = `SELECT * FROM tracked_works WHERE id = ?;`
const SELECT_ALL_SQL = `SELECT * FROM tracked_works;`

export interface SqliteStateStoreOptions {
  /** Skip WAL setup (useful for :memory: tests). Default false. */
  disableWal?: boolean
}

export class SqliteStateStore implements IStateStore {
  private readonly db: Database
  readonly dbHandle: Database

  constructor(path: string, opts: SqliteStateStoreOptions = {}) {
    this.db = new Database(path, { create: true })
    this.dbHandle = this.db
    // Index columns for fast dashboard queries by state.
    this.db.run(SCHEMA_SQL)
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_tracked_works_state ON tracked_works(state);`)
    // History queries filter + sort by state_changed_at; index it so the
    // /loops endpoint stays fast as the table grows (rows are never deleted).
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_tracked_works_state_changed_at ON tracked_works(state_changed_at);`)
    // Event-timeline queries are WHERE work_id=? ORDER BY at; composite index
    // serves both the filter and the sort in one seek.
    this.db.run(`CREATE INDEX IF NOT EXISTS idx_agent_events_work_at ON agent_events(work_id, at);`)
    if (!opts.disableWal && path !== ":memory:") {
      try {
        this.db.run("PRAGMA journal_mode = WAL;")
      } catch {
        // WAL not supported in some environments; ignore.
      }
    }
  }

  upsert(work: TrackedWork): void {
    this.db.run(
      UPSERT_SQL,
      work.id,
      work.state,
      work.attempt ?? 1,
      work.sessionId ?? null,
      work.turnCount ?? null,
      work.startedAt ?? null,
      work.lastEventAt ?? null,
      work.lastEvent ?? null,
      work.lastMessage ?? null,
      work.stateChangedAt ?? null,
      work.error ?? null,
      JSON.stringify(work),
    )
  }

  get(id: string): TrackedWork | undefined {
    const row = this.db.query(SELECT_BY_ID_SQL).get(id) as Row | null
    return row ? rowToWork(row) : undefined
  }

  listByStates(states: RunState[]): TrackedWork[] {
    if (states.length === 0) return []
    const placeholders = states.map(() => "?").join(",")
    const rows = this.db
      .query(`SELECT * FROM tracked_works WHERE state IN (${placeholders});`)
      .all(...states) as Row[]
    return rows.map(rowToWork)
  }

  listAll(): TrackedWork[] {
    const rows = this.db.query(SELECT_ALL_SQL).all() as Row[]
    return rows.map(rowToWork)
  }

  listHistory(opts: HistoryQuery = {}): TrackedWork[] {
    const states = opts.states ?? DEFAULT_HISTORY_STATES
    const limit = opts.limit ?? DEFAULT_HISTORY_LIMIT
    const placeholders = states.map(() => "?").join(",")
    let sql = `SELECT * FROM tracked_works WHERE state IN (${placeholders})`
    const params: unknown[] = [...states]
    if (opts.since) {
      sql += ` AND state_changed_at >= ?`
      params.push(opts.since)
    }
    sql += ` ORDER BY state_changed_at DESC LIMIT ?`
    params.push(limit)
    const rows = this.db.query(sql).all(...params) as Row[]
    return rows.map(rowToWork)
  }

  appendEvents(workId: string, events: AgentEvent[]): void {
    if (events.length === 0) return
    // One prepared INSERT, executed per event. Using a transaction keeps
    // a multi-event turn atomic (and faster than N independent writes).
    const insert = this.db.prepare(
      `INSERT INTO agent_events (work_id, at, kind, event_json) VALUES (?, ?, ?, ?);`,
    )
    this.db.transaction(() => {
      for (const e of events) {
        insert.run(workId, e.at, e.kind, JSON.stringify(e))
      }
    })()
  }

  listEvents(workId: string, opts: EventQuery = {}): AgentEvent[] {
    const limit = opts.limit ?? DEFAULT_EVENT_LIMIT
    let sql = `SELECT event_json FROM agent_events WHERE work_id = ?`
    const params: unknown[] = [workId]
    if (opts.kinds && opts.kinds.length > 0) {
      const placeholders = opts.kinds.map(() => "?").join(",")
      sql += ` AND kind IN (${placeholders})`
      params.push(...opts.kinds)
    }
    if (opts.since) {
      sql += ` AND at >= ?`
      params.push(opts.since)
    }
    sql += ` ORDER BY at ASC LIMIT ?`
    params.push(limit)
    const rows = this.db.query(sql).all(...params) as { event_json: string }[]
    return rows.map((r) => JSON.parse(r.event_json) as AgentEvent)
  }

  transition(id: string, nextState: RunState, patch: Partial<TrackedWork> = {}): TrackedWork {
    const current = this.get(id)
    if (!current) throw new Error(`SqliteStateStore: unknown id ${id}`)
    const updated: TrackedWork = {
      ...current,
      ...patch,
      state: nextState,
      stateChangedAt: new Date().toISOString(),
    }
    this.upsert(updated)
    return updated
  }

  close(): void {
    try {
      this.db.close()
    } catch {
      // best-effort on shutdown
    }
  }
}

interface Row {
  id: string
  state: string
  attempt: number | null
  session_id: string | null
  turn_count: number | null
  started_at: string | null
  last_event_at: string | null
  last_event: string | null
  last_message: string | null
  state_changed_at: string | null
  error: string | null
  work_item_json: string
}

/**
 * Rebuild TrackedWork from a stored row. The JSON blob is authoritative;
 * indexed columns are used only for query filtering. This way schema
 * additions to TrackedWork don't require a migration — just re-serialize.
 */
function rowToWork(row: Row): TrackedWork {
  const parsed = JSON.parse(row.work_item_json) as TrackedWork
  // Overlay the indexed columns back on top so the row's most recent
  // state/attempt/error always wins even if the JSON blob is stale
  // (it shouldn't be, but cheap insurance).
  return {
    ...parsed,
    state: row.state as RunState,
    attempt: row.attempt ?? parsed.attempt ?? 1,
    sessionId: row.session_id ?? parsed.sessionId,
    turnCount: row.turn_count ?? parsed.turnCount,
    startedAt: row.started_at ?? parsed.startedAt,
    lastEventAt: row.last_event_at ?? parsed.lastEventAt,
    lastEvent: row.last_event ?? parsed.lastEvent,
    lastMessage: row.last_message ?? parsed.lastMessage,
    stateChangedAt: row.state_changed_at ?? parsed.stateChangedAt,
    error: row.error ?? parsed.error,
  }
}
