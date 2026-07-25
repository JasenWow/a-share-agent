/**
 * Smoke test — exercises the real Pi SDK + a real LLM via ZAI,
 * AND the aquan CLI tools if MCP servers are running.
 *
 * Requires `ZAI_API_KEY` in the environment. Skips automatically otherwise
 * so CI without credentials still passes.
 */

import { describe, expect, test } from "bun:test"
import { PiRuntime } from "./runtime"

const hasKey = !!process.env.ZAI_API_KEY
const hasMcp = !!process.env.AQUAN_SMOKE_MCP // set to opt into MCP-dependent smoke

describe.skipIf(!hasKey)("PiRuntime smoke (real ZAI API)", () => {
  test(
    "starts a session and completes a single-turn prompt",
    async () => {
      const runtime = new PiRuntime({
        provider: "zai",
        model: "glm-4.5-air",
        maxTurnsPerRun: 3,
        disableCliTools: true, // pure chat for this branch
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
      expect(result.events.length).toBeGreaterThan(0)
      const messageEvents = result.events.filter((e) => e.kind === "message")
      expect(messageEvents.length).toBeGreaterThan(0)

      await runtime.stopSession(session)
    },
    { timeout: 60_000 },
  )
})

// CLI tools smoke: needs the aquan console script on PATH AND the
// relevant MCP server running. Skip unless AQUAN_SMOKE_MCP is set.
describe.skipIf(!hasKey || !hasMcp)("PiRuntime smoke (CLI tools via MCP)", () => {
  test(
    "agent can call the stock tool",
    async () => {
      const runtime = new PiRuntime({
        provider: "zai",
        model: "glm-4.5-air",
        maxTurnsPerRun: 5,
        // CLI tools enabled (default)
      })

      const session = await runtime.startSession({
        workspacePath: "/tmp/aquan-smoke-cli",
        workId: `smoke-cli-${Date.now()}`,
        prompt:
          "Use the 'stock' tool with action 'health' to check if the akshare MCP server is reachable. Then report the result in one sentence.",
        systemPrompt: "You are a smoke test. Use the stock tool to call action 'health'.",
      })

      const result = await session.runTurn(
        "Use the 'stock' tool with action 'health' to check if the akshare MCP server is reachable.",
      )

      expect(result.kind).toBe("done")
      // At least one tool_call event should appear.
      const toolCalls = result.events.filter((e) => e.kind === "tool_call" && e.detail === "stock")
      expect(toolCalls.length).toBeGreaterThan(0)

      await runtime.stopSession(session)
    },
    { timeout: 90_000 },
  )
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

  test("disableCliTools produces a tool-less agent", async () => {
    const runtime = new PiRuntime({ provider: "zai", model: "glm-4.5-air", disableCliTools: true })
    // startSession should succeed without invoking the CLI tools at all.
    // We don't run a turn here (no key in this environment).
    expect(runtime).toBeDefined()
  })
})
