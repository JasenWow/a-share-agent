# @aquan/pi-runtime

Pi agent-runtime adapter — implements `AgentRuntime` from `@aquan/orchestrator` by delegating to the [Pi agent SDK](https://github.com/earendil-works/pi) (`@earendil-works/pi-agent-core` + `@earendil-works/pi-ai`).

## Status: Stage 1 — in-process, real SDK ✅

Backed by the real Pi SDK running in-process (no Docker, no subprocess). Verified via spike + smoke tests. See [`docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md`](../../docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md).

Default LLM: **ZAI / GLM-4.5-air** (China-available, Pi SDK builtin, OpenAI-completions API).

## Quick start

```bash
# Set the provider key (ZAI default)
export ZAI_API_KEY=xxx

# Use it from the orchestrator
import { Orchestrator } from "@aquan/orchestrator"
import { PiRuntime } from "@aquan/pi-runtime"

const runtime = new PiRuntime({
  provider: "zai",           // optional, defaults to "zai"
  model: "glm-4.5-air",      // optional, defaults to "glm-4.5-air"
  maxTurnsPerRun: 20,        // optional
})
const orch = new Orchestrator({ runtime, trackers })
```

Other Pi-SDK builtin providers work too (`openai`, `anthropic`, `google`, ...) — set the matching env var (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) or pass `apiKey` explicitly.

## Why a separate package

- Isolates the Pi SDK dependency: orchestrator / web / server depend only on `@aquan/core` and `@aquan/orchestrator`, never on `pi-runtime` directly.
- Lets us swap runtimes without touching the orchestration loop.
- Keeps the dep tree lean for the dashboard — Pi SDK is heavy and only needed where agents actually run.

## Layout

```
src/
├── index.ts        public exports
├── config.ts       PiRuntimeOptions + defaults (provider/model/maxTurns)
├── runtime.ts      PiRuntime: implements AgentRuntime, constructs Agent
├── session.ts      PiSession: implements AgentSession, drives agent.prompt()
├── events.ts       Pi SDK AgentEvent → @aquan/core AgentEvent translator
├── events.test.ts  translation table unit tests
├── smoke.test.ts   real-LLM smoke test (skips without ZAI_API_KEY)
└── tools.ts        ToolRegistration interface (MCP bridge lands in Step 2)
```

## What's next (Step 2)

- MCP client bridge: expose `aquan-akshare/tushare/internal-store/qlib-server` MCP tools to the agent
- Tool whitelist enforcement (hardening iron rule 3: never expose merge_pr / commit_config)
- Coding tools (read/bash/edit/write) if/when needed

## Pi SDK version pin

`@earendil-works/pi-agent-core` + `@earendil-works/pi-ai` at `0.82.0`. The previous `0.80.7` had an npm resolution issue with `@aws-sdk/credential-provider-web-identity`; 0.82.0 fixes it. The AWS dep is only used by the Bedrock provider — irrelevant for the ZAI/OpenAI code path.
