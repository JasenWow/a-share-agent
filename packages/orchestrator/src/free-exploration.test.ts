import { describe, expect, test } from "bun:test"
import { FreeExplorationTracker } from "./trackers/free-exploration"

/**
 * FreeExplorationTracker — one observation WorkItem per local day.
 * Tests pin the dedup + lifecycle contract described in the tracker doc.
 */
describe("FreeExplorationTracker", () => {
  test("emits exactly one pending item on first fetchByStates(pending)", async () => {
    const t = new FreeExplorationTracker()
    const items = await t.fetchByStates(["pending"])
    expect(items).toHaveLength(1)
    expect(items[0].type).toBe("free-exploration")
    expect(items[0].id).toMatch(/^free-exploration-\d{4}-\d{2}-\d{2}$/)
  })

  test("does not re-emit the same day's item twice", async () => {
    const t = new FreeExplorationTracker()
    const a = await t.fetchByStates(["pending"])
    const b = await t.fetchByStates(["pending"])
    expect(a).toHaveLength(1)
    expect(b).toHaveLength(1)
    expect(b[0].id).toBe(a[0].id)
  })

  test("excludes items whose state is not in the requested set", async () => {
    const t = new FreeExplorationTracker()
    const [item] = await t.fetchByStates(["pending"])
    await t.updateState(item.id, "done")
    // After done, fetching pending should not return it.
    expect(await t.fetchByStates(["pending"])).toHaveLength(0)
    // But fetching done should.
    const done = await t.fetchByStates(["done"])
    expect(done).toHaveLength(1)
    expect(done[0].id).toBe(item.id)
  })

  test("updateState supports retry flow (pending → running → retrying → done)", async () => {
    const t = new FreeExplorationTracker()
    const [item] = await t.fetchByStates(["pending"])
    await t.updateState(item.id, "running")
    expect(await t.fetchByStates(["pending", "retrying"])).toHaveLength(0)

    await t.updateState(item.id, "retrying", "tool timeout")
    const retrying = await t.fetchByStates(["pending", "retrying"])
    expect(retrying).toHaveLength(1)

    await t.updateState(item.id, "done")
    expect(await t.fetchByStates(["pending", "retrying"])).toHaveLength(0)
  })

  test("fetchById returns the item after first fetch", async () => {
    const t = new FreeExplorationTracker()
    const [item] = await t.fetchByStates(["pending"])
    const got = await t.fetchById(item.id)
    expect(got?.id).toBe(item.id)
  })

  test("updateState on unknown id is a no-op (not a throw)", async () => {
    const t = new FreeExplorationTracker()
    await expect(t.updateState("does-not-exist", "done")).resolves.toBeUndefined()
  })

  test("agentToolSpecs advertises the stock CLI tool", () => {
    const t = new FreeExplorationTracker()
    const specs = t.agentToolSpecs()
    expect(specs.length).toBeGreaterThanOrEqual(1)
    expect(specs.some((s) => s.name === "stock")).toBe(true)
  })
})
