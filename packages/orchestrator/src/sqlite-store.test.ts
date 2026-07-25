import { describe, expect, test } from "bun:test"
import type { TrackedWork } from "@aquan/core"
import { SqliteStateStore } from "./sqlite-store"

function makeWork(overrides: Partial<TrackedWork> = {}): TrackedWork {
  return {
    id: "w1",
    title: "test",
    type: "sedimentation",
    description: "stub",
    createdAt: "2026-07-25T00:00:00Z",
    state: "pending",
    attempt: 1,
    sessionId: "s1",
    turnCount: 0,
    startedAt: "2026-07-25T00:00:00Z",
    stateChangedAt: "2026-07-25T00:00:00Z",
    ...overrides,
  }
}

describe("SqliteStateStore — basic ops", () => {
  test("upsert + get round-trip", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    const w = makeWork({ id: "w1", state: "running" })
    store.upsert(w)
    const got = store.get("w1")
    expect(got?.id).toBe("w1")
    expect(got?.state).toBe("running")
    store.close()
  })

  test("get unknown id returns undefined", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    expect(store.get("nope")).toBeUndefined()
    store.close()
  })

  test("upsert is idempotent and updates state", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    store.upsert(makeWork({ id: "w1", state: "running" }))
    store.upsert(makeWork({ id: "w1", state: "done", turnCount: 5 }))
    const got = store.get("w1")
    expect(got?.state).toBe("done")
    expect(got?.turnCount).toBe(5)
    store.close()
  })

  test("listAll returns all rows", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    store.upsert(makeWork({ id: "w1" }))
    store.upsert(makeWork({ id: "w2" }))
    store.upsert(makeWork({ id: "w3" }))
    expect(store.listAll().length).toBe(3)
    store.close()
  })

  test("listByStates filters correctly", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    store.upsert(makeWork({ id: "w1", state: "running" }))
    store.upsert(makeWork({ id: "w2", state: "done" }))
    store.upsert(makeWork({ id: "w3", state: "running" }))
    store.upsert(makeWork({ id: "w4", state: "failed" }))

    expect(store.listByStates(["running"]).length).toBe(2)
    expect(store.listByStates(["done", "failed"]).length).toBe(2)
    expect(store.listByStates([])).toEqual([])
    store.close()
  })
})

describe("SqliteStateStore — transition", () => {
  test("transition updates state + indexed columns", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    store.upsert(makeWork({ id: "w1", state: "running" }))
    store.transition("w1", "done", { turnCount: 7, lastMessage: "ok" })

    const got = store.get("w1")
    expect(got?.state).toBe("done")
    expect(got?.turnCount).toBe(7)
    expect(got?.lastMessage).toBe("ok")
    store.close()
  })

  test("transition unknown id throws", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    expect(() => store.transition("nope", "done")).toThrow(/unknown id/)
    store.close()
  })
})

describe("SqliteStateStore — persistence", () => {
  test("data survives close + reopen (real file, tmpdir)", () => {
    const tmpFile = `${import.meta.dir}/.test-state-${Date.now()}.db`
    try {
      // Write
      const s1 = new SqliteStateStore(tmpFile)
      s1.upsert(makeWork({ id: "persist-1", state: "done", turnCount: 42 }))
      s1.close()

      // Reopen
      const s2 = new SqliteStateStore(tmpFile)
      const got = s2.get("persist-1")
      expect(got?.id).toBe("persist-1")
      expect(got?.state).toBe("done")
      expect(got?.turnCount).toBe(42)
      s2.close()
    } finally {
      // cleanup
      try {
        require("node:fs").unlinkSync(tmpFile)
        require("node:fs").unlinkSync(`${tmpFile}-wal`)
        require("node:fs").unlinkSync(`${tmpFile}-shm`)
      } catch {
        // ignore
      }
    }
  })
})

describe("SqliteStateStore — schema evolution safety", () => {
  test("extra fields on TrackedWork are preserved via JSON blob", () => {
    const store = new SqliteStateStore(":memory:", { disableWal: true })
    const w = makeWork({ id: "w1" })
    // Attach a field not present in the indexed columns.
    const extended = { ...w, customMeta: { foo: "bar" } } as TrackedWork
    store.upsert(extended)
    const got = store.get("w1") as TrackedWork & { customMeta?: unknown }
    expect((got.customMeta as { foo: string })?.foo).toBe("bar")
    store.close()
  })
})
