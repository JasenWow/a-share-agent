# @aquan/pi-runtime

Pi agent-runtime adapter — implements `AgentRuntime` from `@aquan/orchestrator` by delegating to the [Pi agent SDK](https://github.com/earendil-works/pi).

## Phase 5 status: skeleton only

Concrete SDK bindings land in a follow-up spec once the Pi SDK's actual API surface (`pi-agent-core`) is verified from upstream docs. The interface here is pinned to what `@aquan/orchestrator` expects, so the orchestrator can already be exercised against a `StubRuntime`.

## Why a separate package

- Isolates Pi SDK uncertainty: orchestrator / web / server depend only on `@aquan/core` and `@aquan/orchestrator`, never on `pi-runtime` directly.
- Lets us swap runtimes without touching the orchestration loop.
- Keeps the dep tree lean — Pi SDK is heavy and optional for the dashboard.

## Layout

```
src/
├── index.ts        public exports
├── session.ts      PiSession: implements AgentSession
├── runtime.ts      PiRuntime: implements AgentRuntime
├── events.ts       Pi SDK event -> AgentEvent translator
└── tools.ts        expose MCP tools to Pi
```
