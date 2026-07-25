# @aquan/pi-runtime

Pi agent-runtime adapter — implements `AgentRuntime` from `@aquan/orchestrator` by delegating to the [Pi agent SDK](https://github.com/earendil-works/pi) (`@earendil-works/pi-agent-core` + `@earendil-works/pi-ai`).

## Status: Stage 1 + Step 2 — in-process, real SDK, CLI tools ✅

Backed by the real Pi SDK running in-process (no Docker, no subprocess, no Redis). Verified via spike + smoke tests. See [`docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md`](../../docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md).

**Four domain CLI tools** are registered on the agent by default (`stock`, `factor`, `experiment`, `qlib`) — these spawn the `aquan` Python CLI rather than speaking MCP directly, saving token budget vs. exposing 44 raw MCP tool schemas. See [`docs/superpowers/specs/2026-07-25-aquan-cli-design.md`](../../docs/superpowers/specs/2026-07-25-aquan-cli-design.md).

Default LLM: **ZAI / GLM-4.5-air** (China-available, Pi SDK builtin, OpenAI-completions API).

## Quick start

```bash
# Set the provider key (ZAI default)
export ZAI_API_KEY=xxx

# Make sure the Python side is installed (provides the `aquan` console script)
cd python && uv sync && cd ..

# Use it from the orchestrator
import { Orchestrator } from "@aquan/orchestrator"
import { PiRuntime } from "@aquan/pi-runtime"

const runtime = new PiRuntime({
  provider: "zai",           // optional, defaults to "zai"
  model: "glm-4.5-air",      // optional, defaults to "glm-4.5-air"
  maxTurnsPerRun: 20,        // optional
  // disableCliTools: true,  // optional, opt out of stock/factor/experiment/qlib tools
})
const orch = new Orchestrator({ runtime, trackers })
```

The agent now has four tools available:

| Tool | Domain | Example action |
|---|---|---|
| `stock` | quotes / fundamentals / concepts / indices / flow | `{action: "hist", code: "600519", start: "20240101"}` |
| `factor` | factor lifecycle | `{action: "list"}` or `{action: "register", name: "...", expression: "..."}` |
| `experiment` | experiments / backtests / strategies | `{action: "best", top: 5}` |
| `qlib` | Qlib quant engine | `{action: "eval", expression: "Mean($close, 20)"}` |

Each tool's `execute` spawns `aquan <domain> <action> --flags` (Python CLI), which calls the corresponding MCP server. Output is a compact table (or `--json`) returned to the agent as tool result text.

Other Pi-SDK builtin providers work too (`openai`, `anthropic`, `google`, ...) — set the matching env var (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) or pass `apiKey` explicitly.

## Why a separate package

- Isolates the Pi SDK dependency: orchestrator / web / server depend only on `@aquan/core` and `@aquan/orchestrator`, never on `pi-runtime` directly.
- Lets us swap runtimes without touching the orchestration loop.
- Keeps the dep tree lean for the dashboard — Pi SDK is heavy and only needed where agents actually run.

## Layout

```
src/
├── index.ts           public exports
├── config.ts          PiRuntimeOptions + defaults (provider/model/maxTurns/disableCliTools)
├── runtime.ts         PiRuntime: implements AgentRuntime, constructs Agent + registers CLI tools
├── session.ts         PiSession: implements AgentSession, drives agent.prompt()
├── cli-tools.ts       four domain AgentTools (stock/factor/experiment/qlib)
├── cli-runner.ts      spawn `aquan` CLI as subprocess, capture stdout, enforce timeout
├── events.ts          Pi SDK AgentEvent → @aquan/core AgentEvent translator
├── events.test.ts     translation table unit tests
├── cli-tools.test.ts  tool schema + execute unit tests
├── cli-runner.test.ts argv builder unit tests
├── smoke.test.ts      real-LLM smoke test (skips without ZAI_API_KEY)
└── tools.ts           legacy ToolRegistration interface (unused by default)
```

## What's next (Step 3+)

- Tool call persistence (write each call into internal-store experiment_step table)
- Per-tool rate limit / cost tracking
- Coding tools (read/bash/edit/write) if/when needed
- The legacy `tools.ts` `ToolRegistration` interface is kept for compatibility but unused by default

## Pi SDK version pin

`@earendil-works/pi-agent-core` + `@earendil-works/pi-ai` at `0.82.0`. The previous `0.80.7` had an npm resolution issue with `@aws-sdk/credential-provider-web-identity`; 0.82.0 fixes it. The AWS dep is only used by the Bedrock provider — irrelevant for the ZAI/OpenAI code path.
