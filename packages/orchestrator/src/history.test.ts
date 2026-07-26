import { describe, expect, test } from "bun:test"
import type { TrackedWork, WorkItem, RunState } from "@aquan/core"
import { StateStore } from "./state-store"
import {
  historyPayload,
  deriveTracker,
  deriveDay,
} from "./presenter"

/** Build a TrackedWork with sensible defaults for history tests. */
function makeTracked(overrides: Partial<TrackedWork> & { id: string }): TrackedWork {
  const base: WorkItem = {
    id: overrides.id,
    title: overrides.title ?? overrides.id,
    type: overrides.type ?? "sedimentation",
    description: overrides.description ?? "stub",
    createdAt: overrides.createdAt ?? "2026-07-20T00:00:00Z",
  }
  return {
    ...base,
    state: overrides.state ?? "done",
    attempt: overrides.attempt ?? 1,
    stateChangedAt: overrides.stateChangedAt ?? "2026-07-20T10:00:00Z",
    ...overrides,
  }
}

describe("deriveTracker", () => {
  test("factor-mine-* → factor-mining", () => {
    expect(deriveTracker("factor-mine-2026-07-20")).toBe("factor-mining")
  })
  test("free-exploration-* → free-exploration", () => {
    expect(deriveTracker("free-exploration-2026-07-20")).toBe("free-exploration")
  })
  test("unknown prefix → unknown", () => {
    expect(deriveTracker("demo-123")).toBe("unknown")
  })
})

describe("deriveDay", () => {
  test("extracts trailing YYYY-MM-DD", () => {
    expect(deriveDay("factor-mine-2026-07-20")).toBe("2026-07-20")
  })
  test("returns null when no date suffix", () => {
    expect(deriveDay("demo-123")).toBeNull()
  })
})

describe("StateStore.listHistory", () => {
  test("returns only done/failed/retrying by default, newest-first", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "factor-mine-2026-07-20", state: "done", stateChangedAt: "2026-07-20T10:00:00Z" }))
    store.upsert(makeTracked({ id: "factor-mine-2026-07-21", state: "failed", stateChangedAt: "2026-07-21T10:00:00Z" }))
    store.upsert(makeTracked({ id: "free-exploration-2026-07-21", state: "retrying", stateChangedAt: "2026-07-21T11:00:00Z" }))
    store.upsert(makeTracked({ id: "w-pending", state: "pending", stateChangedAt: "2026-07-21T12:00:00Z" }))
    store.upsert(makeTracked({ id: "w-running", state: "running", stateChangedAt: "2026-07-21T13:00:00Z" }))

    const hist = store.listHistory()
    expect(hist).toHaveLength(3)
    expect(hist.map((w) => w.id)).toEqual([
      "free-exploration-2026-07-21", // 11:00 newest of the three
      "factor-mine-2026-07-21",      // 10:00
      "factor-mine-2026-07-20",      // 10:00 prev day
    ])
  })

  test("respects states filter", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "w-done", state: "done" }))
    store.upsert(makeTracked({ id: "w-failed", state: "failed" }))
    const hist = store.listHistory({ states: ["failed"] })
    expect(hist.map((w) => w.id)).toEqual(["w-failed"])
  })

  test("respects since filter", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "old", state: "done", stateChangedAt: "2026-07-01T00:00:00Z" }))
    store.upsert(makeTracked({ id: "new", state: "done", stateChangedAt: "2026-07-25T00:00:00Z" }))
    const hist = store.listHistory({ since: "2026-07-20T00:00:00Z" })
    expect(hist.map((w) => w.id)).toEqual(["new"])
  })

  test("respects limit", () => {
    const store = new StateStore()
    for (let i = 0; i < 10; i++) {
      store.upsert(makeTracked({ id: `w-${i}`, state: "done", stateChangedAt: `2026-07-${20 - i}T00:00:00Z` }))
    }
    const hist = store.listHistory({ limit: 3 })
    expect(hist).toHaveLength(3)
  })
})

describe("historyPayload", () => {
  test("aggregates byTracker + byDay + totals", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "factor-mine-2026-07-20", state: "done", stateChangedAt: "2026-07-20T10:00:00Z" }))
    store.upsert(makeTracked({ id: "factor-mine-2026-07-21", state: "failed", stateChangedAt: "2026-07-21T10:00:00Z" }))
    store.upsert(makeTracked({ id: "free-exploration-2026-07-21", state: "done", stateChangedAt: "2026-07-21T11:00:00Z" }))
    store.upsert(makeTracked({ id: "free-exploration-2026-07-22", state: "retrying", stateChangedAt: "2026-07-22T12:00:00Z", attempt: 2 }))

    const payload = historyPayload(store)

    expect(payload.totals).toEqual({ done: 2, failed: 1, retrying: 1, total: 4 })
    expect(payload.byTracker["factor-mining"]).toEqual({ done: 1, failed: 1, retrying: 0, total: 2 })
    expect(payload.byTracker["free-exploration"]).toEqual({ done: 1, failed: 0, retrying: 1, total: 2 })
    expect(payload.byDay["2026-07-20"]).toEqual({ done: 1, failed: 0, retrying: 0, total: 1 })
    expect(payload.byDay["2026-07-21"]).toEqual({ done: 1, failed: 1, retrying: 0, total: 2 })
    expect(payload.byDay["2026-07-22"]).toEqual({ done: 0, failed: 0, retrying: 1, total: 1 })
  })

  test("items sorted newest-first", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "a", state: "done", stateChangedAt: "2026-07-20T10:00:00Z" }))
    store.upsert(makeTracked({ id: "b", state: "done", stateChangedAt: "2026-07-21T10:00:00Z" }))
    const payload = historyPayload(store)
    expect(payload.items[0].id).toBe("b")
    expect(payload.items[1].id).toBe("a")
  })

  test("tracker filter narrows items + aggregation", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "factor-mine-2026-07-20", state: "done" }))
    store.upsert(makeTracked({ id: "free-exploration-2026-07-20", state: "done" }))
    const payload = historyPayload(store, { tracker: "factor-mining" })
    expect(payload.items).toHaveLength(1)
    expect(payload.items[0].id).toBe("factor-mine-2026-07-20")
    expect(payload.byTracker).toEqual({
      "factor-mining": { done: 1, failed: 0, retrying: 0, total: 1 },
    })
    expect(payload.totals).toEqual({ done: 1, failed: 0, retrying: 0, total: 1 })
  })

  test("items without a date suffix don't crash byDay (day = null, skipped)", () => {
    const store = new StateStore()
    store.upsert(makeTracked({ id: "demo-123", state: "done", stateChangedAt: "2026-07-21T10:00:00Z" }))
    const payload = historyPayload(store)
    expect(payload.items).toHaveLength(1)
    expect(payload.byTracker["unknown"]).toEqual({ done: 1, failed: 0, retrying: 0, total: 1 })
    expect(Object.keys(payload.byDay)).toEqual([])
  })

  test("generatedAt is a valid ISO timestamp", () => {
    const store = new StateStore()
    const payload = historyPayload(store)
    expect(() => new Date(payload.generatedAt).toISOString()).not.toThrow()
  })
})

// keep RunState import meaningful for future state-typed fixtures
export type _RunState = RunState
