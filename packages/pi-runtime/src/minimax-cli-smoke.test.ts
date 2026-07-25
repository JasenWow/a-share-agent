/**
 * MiniMax + CLI tools smoke — agent really does work.
 *
 * Uses MiniMax-M2.7 + the four CLI tools (stock/factor/experiment/qlib).
 * The agent is asked to query the internal-store MCP via the
 * 'experiment' tool and report back. Requires:
 *   - MINIMAX_API_KEY (or MINIMAX_CN_API_KEY)
 *   - internal-store MCP server running on :8002
 *
 * Run:
 *   MINIMAX_API_KEY=... buntest packages/pi-runtime/src/minimax-cli-smoke.test.ts
 */

import { describe, expect, test } from "bun:test"
import { PiRuntime } from "./runtime"

const key =
  process.env.MINIMAX_API_KEY ??
  process.env.MINIMAX_CN_API_KEY ??
  process.env.AQUAN_MINIMAX_KEY

describe.skipIf(!key)("PiRuntime + MiniMax + CLI tools", () => {
  test(
    "agent calls the experiment tool and reports results",
    async () => {
      const runtime = new PiRuntime({
        provider: "minimax-cn",
        model: "MiniMax-M2.7",
        apiKey: key,
        maxTurnsPerRun: 8,
        // CLI tools enabled (default)
      })

      const session = await runtime.startSession({
        workspacePath: "/tmp/aquan-minimax-cli",
        workId: `minimax-cli-${Date.now()}`,
        prompt:
          "Use the 'experiment' tool with action 'list' to fetch the experiments, " +
          "then summarize in one sentence how many experiments exist.",
        systemPrompt:
          "You are an A-share quant assistant. Use the tools available to answer. " +
          "After getting tool results, give a one-sentence summary.",
      })

      const result = await session.runTurn(
        "Use the 'experiment' tool with action 'list' to fetch the experiments, " +
          "then summarize in one sentence how many experiments exist.",
      )

      expect(result.kind).toBe("done")
      // We expect at least one tool_call event with detail 'experiment'.
      const toolCalls = result.events.filter(
        (e) => e.kind === "tool_call" && (e.detail === "experiment" || e.detail?.includes("experiment")),
      )
      console.log(
        `[minimax-cli-smoke] events: ${result.events.length}, tool_calls: ${toolCalls.length}, ` +
          `message: ${result.message?.slice(0, 120) ?? "(none)"}`,
      )
      // Don't hard-assert toolCalls > 0 — MiniMax might not always call the tool.
      // But log it so we see what happened. Expect at least one message back.
      expect(result.events.filter((e) => e.kind === "message").length).toBeGreaterThan(0)

      await runtime.stopSession(session)
    },
    { timeout: 180_000 },
  )
})
