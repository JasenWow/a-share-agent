# @aquan/orchestrator

Symphony-like work-orchestration engine. Polls one or more **trackers** for `WorkItem`s, runs each through the configured **agent runtime** (default: `@aquan/pi-runtime`), and exposes the state of every active/retrying/blocked run via an HTTP API for the dashboard.

## Design reference

Modeled on [`openai/symphony`](https://github.com/openai/symphony) but:
- runtime is pluggable (Symphony hard-codes Codex AppServer; we abstract it via `AgentRuntime`)
- trackers are work-source adapters, not Linear-specific
- state model is the same three live states (running / retrying / blocked) plus terminal (done / failed)

## Phase 5 status: skeleton

Only type contracts and interface declarations are filled in. Concrete implementations (loop logic, HTTP server, Pi runtime integration) arrive in a follow-up spec under `docs/superpowers/specs/`.

## Layout

```
src/
├── index.ts              public API
├── orchestrator.ts       main poll-run-record loop
├── agent-runner.ts       single WorkItem turn loop (calls AgentRuntime)
├── state-store.ts        in-memory store of TrackedWork (future: persisted)
├── presenter.ts          state -> HTTP response shape (mirrors Symphony Presenter)
├── http.ts               /api/v1/state, /api/v1/work/:id endpoints
├── prompt-builder.ts     build agent prompt from WorkItem
├── workspace.ts          per-WorkItem workspace management
└── trackers/
    ├── tracker.ts        Tracker interface
    ├── memory.ts         in-memory tracker (for tests)
    ├── factor-mining.ts  sedimentation type: pulls from factor queue
    └── free-exploration.ts free-exploration type: scheduled market scan
```
