import { describe, expect, test } from "bun:test"
import type { AgentEvent as PiAgentEvent } from "@earendil-works/pi-agent-core"
import { translatePiEvent, translatePiEvents } from "./events"

const NOW = "2026-07-25T10:00:00Z"

describe("translatePiEvent — message family", () => {
  test("message_start with text becomes a message event", () => {
    const raw: PiAgentEvent = {
      type: "message_start",
      message: { role: "assistant", content: [{ type: "text", text: "Hello" }] } as never,
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.kind).toBe("message")
  })

  test("message_update with no extractable text is dropped", () => {
    const raw: PiAgentEvent = {
      type: "message_update",
      message: {} as never,
      assistantMessageEvent: { type: "text", textDelta: "" } as never,
    }
    expect(translatePiEvent(raw, NOW)).toBeNull()
  })

  test("message_end is always surfaced even with no text", () => {
    const raw: PiAgentEvent = {
      type: "message_end",
      message: {} as never,
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.kind).toBe("message")
  })
})

describe("translatePiEvent — tool family", () => {
  test("tool_execution_start → tool_call with toolName", () => {
    const raw: PiAgentEvent = {
      type: "tool_execution_start",
      toolCallId: "tc1",
      toolName: "read_file",
      args: { path: "/etc/passwd" },
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.kind).toBe("tool_call")
    expect(e?.detail).toBe("read_file")
  })

  test("tool_execution_update is dropped (too noisy)", () => {
    const raw: PiAgentEvent = {
      type: "tool_execution_update",
      toolCallId: "tc1",
      toolName: "read_file",
      args: {},
      partialResult: "partial",
    }
    expect(translatePiEvent(raw, NOW)).toBeNull()
  })

  test("tool_execution_end success → tool_result", () => {
    const raw: PiAgentEvent = {
      type: "tool_execution_end",
      toolCallId: "tc1",
      toolName: "read_file",
      result: { ok: true },
      isError: false,
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.kind).toBe("tool_result")
    expect(e?.detail).toContain("read_file")
  })

  test("tool_execution_end error is flagged in detail", () => {
    const raw: PiAgentEvent = {
      type: "tool_execution_end",
      toolCallId: "tc1",
      toolName: "read_file",
      result: "permission denied",
      isError: true,
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.kind).toBe("tool_result")
    expect(e?.detail).toContain("error")
    expect(e?.detail).toContain("read_file")
  })

  test("tool_result detail is truncated for long results", () => {
    const longText = "x".repeat(500)
    const raw: PiAgentEvent = {
      type: "tool_execution_end",
      toolCallId: "tc1",
      toolName: "big",
      result: longText,
      isError: false,
    }
    const e = translatePiEvent(raw, NOW)
    expect(e?.detail?.endsWith("…")).toBe(true)
    expect((e?.detail?.length ?? 0) < longText.length).toBe(true)
  })
})

describe("translatePiEvent — lifecycle", () => {
  test("agent_start is dropped", () => {
    expect(translatePiEvent({ type: "agent_start" }, NOW)).toBeNull()
  })

  test("turn_start is dropped", () => {
    expect(translatePiEvent({ type: "turn_start" }, NOW)).toBeNull()
  })

  test("turn_end → turn_end kind", () => {
    const raw: PiAgentEvent = {
      type: "turn_end",
      message: {} as never,
      toolResults: [],
    }
    expect(translatePiEvent(raw, NOW)?.kind).toBe("turn_end")
  })

  test("agent_end → turn_end kind", () => {
    const raw: PiAgentEvent = {
      type: "agent_end",
      messages: [],
    }
    expect(translatePiEvent(raw, NOW)?.kind).toBe("turn_end")
  })
})

describe("translatePiEvents — batch", () => {
  test("filters out nulls and keeps order", () => {
    // Use message_end (always kept) + tool_execution_start + agent_end.
    const raws: PiAgentEvent[] = [
      { type: "agent_start" }, // dropped
      { type: "message_end", message: {} as never }, // kept
      {
        type: "tool_execution_start",
        toolCallId: "t1",
        toolName: "lookup",
        args: {},
      }, // kept
      { type: "agent_end", messages: [] }, // kept
    ]
    const out = translatePiEvents(raws, NOW)
    expect(out.length).toBe(3)
    expect(out[0].kind).toBe("message")
    expect(out[1].kind).toBe("tool_call")
    expect(out[2].kind).toBe("turn_end")
  })
})
