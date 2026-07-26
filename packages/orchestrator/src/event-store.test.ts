import { describe, expect, test } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import type { AgentEvent } from "@aquan/core"
import { StateStore } from "./state-store"
import { SqliteStateStore } from "./sqlite-store"

/** Sample events covering the main kinds, in chronological order. */
const EVENTS_A: AgentEvent[] = [
  { at: "2026-07-26T10:00:01Z", kind: "message", detail: "I'll start by listing factors." },
  { at: "2026-07-26T10:00:03Z", kind: "tool_call", detail: "factor list" },
  { at: "2026-07-26T10:00:04Z", kind: "tool_result", detail: "factor list: 12 rows" },
  { at: "2026-07-26T10:00:05Z", kind: "turn_end" },
]
const EVENTS_B: AgentEvent[] = [
  { at: "2026-07-26T10:01:00Z", kind: "message", detail: "Evaluating momentum_20d..." },
  { at: "2026-07-26T10:01:02Z", kind: "tool_call", detail: "qlib eval" },
  { at: "2026-07-26T10:01:03Z", kind: "error", detail: "qlib init failed" },
]

/** Run the same test suite against both store implementations. */
function runSuite(name: string, makeStore: () => StateStore | SqliteStateStore) {
  describe(`${name} — appendEvents + listEvents`, () => {
    test("append then list returns all events ascending by time", () => {
      const store = makeStore()
      store.appendEvents("w1", EVENTS_A)
      store.appendEvents("w1", EVENTS_B) // second batch (e.g. attempt 2 / next turn)
      const got = store.listEvents("w1")
      expect(got).toHaveLength(7)
      // ascending: 10:00:01 ... 10:01:03
      expect(got[0].at).toBe("2026-07-26T10:00:01Z")
      expect(got[6].at).toBe("2026-07-26T10:01:03Z")
    })

    test("events are isolated per work id", () => {
      const store = makeStore()
      store.appendEvents("w1", EVENTS_A)
      store.appendEvents("w2", EVENTS_B)
      expect(store.listEvents("w1")).toHaveLength(4)
      expect(store.listEvents("w2")).toHaveLength(3)
    })

    test("kinds filter narrows results", () => {
      const store = makeStore()
      store.appendEvents("w1", [...EVENTS_A, ...EVENTS_B])
      const tools = store.listEvents("w1", { kinds: ["tool_call", "tool_result"] })
      expect(tools).toHaveLength(3)
      expect(tools.every((e) => e.kind === "tool_call" || e.kind === "tool_result")).toBe(true)
    })

    test("since filter narrows results", () => {
      const store = makeStore()
      store.appendEvents("w1", [...EVENTS_A, ...EVENTS_B])
      const after = store.listEvents("w1", { since: "2026-07-26T10:01:00Z" })
      expect(after).toHaveLength(3) // the EVENTS_B batch
      expect(after[0].kind).toBe("message")
    })

    test("limit caps the result count", () => {
      const store = makeStore()
      store.appendEvents("w1", [...EVENTS_A, ...EVENTS_B])
      expect(store.listEvents("w1", { limit: 2 })).toHaveLength(2)
    })

    test("unknown work id returns empty array", () => {
      const store = makeStore()
      expect(store.listEvents("never")).toEqual([])
    })

    test("appendEvents([], ...) is a no-op", () => {
      const store = makeStore()
      store.appendEvents("w1", [])
      expect(store.listEvents("w1")).toEqual([])
    })

    test("full AgentEvent shape round-trips (detail preserved)", () => {
      const store = makeStore()
      const e: AgentEvent = {
        at: "2026-07-26T10:00:00Z",
        kind: "tool_result",
        detail: "stock quote: 600519 = 1680.5",
        tokens: { input: 120, output: 30, total: 150 },
      }
      store.appendEvents("w1", [e])
      const got = store.listEvents("w1")
      expect(got[0]).toEqual(e)
      expect(got[0].tokens).toEqual({ input: 120, output: 30, total: 150 })
    })
  })
}

runSuite("StateStore (in-memory)", () => new StateStore())

describe("SqliteStateStore — events", () => {
  let dir: string
  let path: string

  function freshDb(): SqliteStateStore {
    dir = mkdtempSync(join(tmpdir(), "aquan-events-"))
    path = join(dir, "state.db")
    return new SqliteStateStore(path)
  }

  test("append + list round-trips, ascending", () => {
    const store = freshDb()
    try {
      store.appendEvents("w1", EVENTS_A)
      store.appendEvents("w1", EVENTS_B)
      const got = store.listEvents("w1")
      expect(got).toHaveLength(7)
      expect(got[0].at).toBe("2026-07-26T10:00:01Z")
      expect(got[6].at).toBe("2026-07-26T10:01:03Z")
    } finally {
      store.close()
      rmSync(dir, { recursive: true, force: true })
    }
  })

  test("events persist across close + reopen", () => {
    const store = freshDb()
    try {
      store.appendEvents("w1", EVENTS_A)
      store.close()
      // Reopen the same file — events must survive.
      const reopened = new SqliteStateStore(path)
      try {
        const got = reopened.listEvents("w1")
        expect(got).toHaveLength(4)
        expect(got[0].kind).toBe("message")
      } finally {
        reopened.close()
      }
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  test("kinds filter", () => {
    const store = freshDb()
    try {
      store.appendEvents("w1", [...EVENTS_A, ...EVENTS_B])
      const tools = store.listEvents("w1", { kinds: ["error"] })
      expect(tools).toHaveLength(1)
      expect(tools[0].detail).toBe("qlib init failed")
    } finally {
      store.close()
      rmSync(dir, { recursive: true, force: true })
    }
  })
})
