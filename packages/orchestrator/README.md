# @aquan/orchestrator

Symphony-like work-orchestration engine. Polls one or more **trackers** for `WorkItem`s, runs each through the configured **agent runtime** (default: `@aquan/pi-runtime`), and exposes the state of every active/retrying/blocked run via an HTTP API for the dashboard.

## Design reference

Modeled on [`openai/symphony`](https://github.com/openai/symphony) but:
- runtime is pluggable (Symphony hard-codes Codex AppServer; we abstract it via `AgentRuntime`)
- trackers are work-source adapters, not Linear-specific
- state model is the same three live states (running / retrying / blocked) plus terminal (done / failed)

## Status

Stage 3 complete. The orchestrator ships:
- ✅ poll-run-record loop with hardening (spend cap / concurrency / anti-injection)
- ✅ in-process cron Scheduler (different trackers on different cadences)
- ✅ pluggable IStateStore (in-memory + bun:sqlite-backed persistence)
- ✅ PersistedSpendGuard (spend counters survive restarts)
- ✅ HTTP presenter + server (`/api/v1/state`, `/api/v1/work/:id`, `/api/v1/tick`)

See `docs/superpowers/specs/2026-07-25-orchestrator-hardening-design.md` and `2026-07-25-orchestrator-scheduling-persistence-design.md`.

## Quick start

```typescript
import { Orchestrator, SqliteStateStore, PersistedSpendGuard, DEFAULT_POLICY } from "@aquan/orchestrator"
import { PiRuntime } from "@aquan/pi-runtime"

// Persistence: one SQLite file shared by store + spend guard.
const store = new SqliteStateStore("data/orchestrator/state.db")
const spendGuard = new PersistedSpendGuard(DEFAULT_POLICY.budget, store.dbHandle)

const orch = new Orchestrator({
  runtime: new PiRuntime(),
  trackers: [new FactorMiningTracker(), new FreeExplorationTracker()],
  store,
  spendGuard,
})

// Self-driving: different cadences per tracker.
orch.start([
  { name: "factor-mining-loop", cron: "*/30 * * * * *", trackers: ["factor-mining"] },
  { name: "daily-exploration",   cron: "0 18 * * 1-5",   trackers: ["free-exploration"] },
])

process.on("SIGINT", () => { orch.stop(); process.exit(0) })
```

For tests / ephemeral runs, omit `store` and `spendGuard` to use the in-memory defaults:

```typescript
const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [new MemoryTracker()] })
await orch.tick()
```

## Layout

```
src/
├── index.ts                public API
├── orchestrator.ts         main poll-run-record loop + start/stop scheduling
├── agent-runner.ts         single WorkItem turn loop (calls AgentRuntime)
├── state-store.ts          IStateStore interface + in-memory StateStore
├── sqlite-store.ts         SqliteStateStore: bun:sqlite-backed persistence
├── persisted-spend-guard.ts SpendGuard that replays spend_log on restart
├── scheduler.ts            in-process cron driver (one job per ScheduleSpec)
├── policy.ts               SpendGuard + ConcurrencyGate
├── presenter.ts            state -> HTTP response shape (Symphony-like)
├── http.ts                 /api/v1/state, /api/v1/work/:id, /api/v1/tick
├── prompt-builder.ts       build system + user prompt from WorkItem
├── workspace.ts            per-WorkItem workspace management
├── runtime.ts              AgentRuntime interface + StubRuntime for tests
└── trackers/
    ├── tracker.ts          Tracker interface + MemoryTracker
    ├── factor-mining.ts    sedimentation tracker (stub)
    └── free-exploration.ts free-exploration tracker (stub)
```

## Boundary rules

Enforced by `/.dependency-cruiser.cjs`:
- `@aquan/orchestrator` may depend on `@aquan/core` (types, errors, constants, utils).
- `@aquan/orchestrator` must NOT depend on `@aquan/{server, web, pi-runtime}`.
- The runtime is injected (PiRuntime is a peer, not a hard dep) so the boundary stays clean.

## Persistence model

Two SQLite tables live in the same file (`tracked_works`, `spend_log`):

```sql
CREATE TABLE tracked_works (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  attempt INTEGER, session_id TEXT, turn_count INTEGER,
  started_at TEXT, last_event_at TEXT, last_event TEXT,
  last_message TEXT, state_changed_at TEXT, error TEXT,
  work_item_json TEXT NOT NULL  -- full WorkItem; survives schema evolution
);

CREATE TABLE spend_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,  -- tracker name or "global"
  at TEXT       -- ISO8601
);
```

`SqliteStateStore.dbHandle` is exposed so `PersistedSpendGuard` can share the file (its table is created lazily on construction).

## What's next (Stage 4)

- Dashboard `/orchestration` three-state view (reads SqliteStateStore)
- Standalone executable entry (`packages/orchestrator/src/entry.ts`)
- RetryPolicy with exponential backoff
- Real FactorMiningTracker / FreeExplorationTracker (currently return empty)
