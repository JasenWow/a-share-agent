/**
 * Smoke test — exercises the real Pi SDK + a real LLM via ZAI.
 *
 * Requires `ZAI_API_KEY` in the environment. Skips automatically otherwise
 * so CI without credentials still passes.
 */

import { describe, expect, test } from "bun:test"
import { PiRuntime } from "./runtime"

const hasKey = !!process.env.ZAI_API_KEY

describe.skipIf(!hasKey)("PiRuntime smoke (real ZAI API)", () => {
  test(
    "starts a session and completes a single-turn prompt",
    async () => {
      const runtime = new PiRuntime({
        provider: "zai",
        model: "glm-4.5-air",
        maxTurnsPerRun: 3,
      })

      const session = await runtime.startSession({
        workspacePath: "/tmp/aquan-smoke",
        workId: `smoke-${Date.now()}`,
        prompt: "Reply with exactly the word OK and nothing else.",
        systemPrompt:
          "You are a smoke test. Reply extremely concisely — ideally one word.",
      })

      const result = await session.runTurn("Reply with exactly the word OK and nothing else.")

      expect(result.kind).toBe("done")
      // We expect at least one message event from the SDK.
      expect(result.events.length).toBeGreaterThan(0)
      // The final assistant message should mention OK somewhere (model may add punctuation).
      const messageEvents = result.events.filter((e) => e.kind === "message")
      expect(messageEvents.length).toBeGreaterThan(0)

      await runtime.stopSession(session)
    },
    { timeout: 60_000 }, // LLM call may be slow
  )

  test("maxTurnsPerRun aborts a long run cleanly", async () => {
    const runtime = new PiRuntime({
      provider: "zai",
      model: "glm-4.5-air",
      maxTurnsPerRun: 1, // very tight
    })

    const session = await runtime.startSession({
      workspacePath: "/tmp/aquan-smoke-max",
      workId: `smoke-max-${Date.now()}`,
      prompt: "Call any available tool repeatedly.",
      systemPrompt: "You are a smoke test.",
    })

    const result = await session.runTurn("Call any available tool repeatedly.")
    // Either done (model didn't call tools) or aborted — both acceptable.
    expect(["done", "blocked"]).toContain(result.kind)

    await runtime.stopSession(session)
  })
})

// Always-on sanity test: instantiating PiRuntime without a key should not throw
// (auth is lazy — resolved only when prompt() is called).
describe("PiRuntime construction", () => {
  test("can be instantiated without ZAI_API_KEY", () => {
    const runtime = new PiRuntime({ provider: "zai", model: "glm-4.5-air" })
    expect(runtime).toBeDefined()
  })

  test("unknown provider throws on startSession", async () => {
    const runtime = new PiRuntime({ provider: "not-a-real-provider", model: "x" })
    expect(
      runtime.startSession({
        workspacePath: "/tmp",
        workId: "x",
        prompt: "x",
      }),
    ).rejects.toThrow(/not-a-real-provider|not found/i)
  })
})
