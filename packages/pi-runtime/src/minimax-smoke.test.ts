/**
 * MiniMax smoke test — real LLM call via PiRuntime + MiniMax-M2.7.
 *
 * Requires MINIMAX_API_KEY (or MINIMAX_CN_API_KEY) in the environment.
 * The default model is MiniMax-M2.7 on the minimax-cn provider.
 *
 * Run:
 *   MINIMAX_API_KEY=sk-... bun test packages/pi-runtime/src/minimax-smoke.test.ts
 */

import { describe, expect, test } from "bun:test"
import { PiRuntime } from "./runtime"

const key =
  process.env.AQUAN_API_KEY ??
  process.env.MINIMAX_API_KEY ??
  process.env.MINIMAX_CN_API_KEY

describe.skipIf(!key)("PiRuntime + MiniMax (real API)", () => {
  test(
    "MiniMax-M2.7 completes a single-turn prompt",
    async () => {
      const runtime = new PiRuntime({
        provider: "minimax-cn",
        model: "MiniMax-M2.7",
        apiKey: key,
        maxTurnsPerRun: 3,
        disableCliTools: true,
        // MiniMax models support thinking; leave default but keep run short.
      })

      const session = await runtime.startSession({
        workspacePath: "/tmp/aquan-minimax-smoke",
        workId: `minimax-${Date.now()}`,
        prompt: "Reply with exactly: OK",
        systemPrompt:
          "You are a smoke test. Reply extremely concisely. The expected reply is the literal text 'OK'.",
      })

      const result = await session.runTurn("Reply with exactly: OK")

      expect(result.kind).toBe("done")
      // We should see at least one message event (the assistant reply).
      const messages = result.events.filter((e) => e.kind === "message")
      expect(messages.length).toBeGreaterThan(0)

      await runtime.stopSession(session)
    },
    { timeout: 90_000 },
  )
})
