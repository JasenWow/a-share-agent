import { describe, expect, test } from "bun:test"
import type { RunState } from "@aquan/core"
import { FactorMiningTracker } from "./trackers/factor-mining"
import type { InternalStoreReader } from "./internal-store-reader"

/** A fake reader that returns canned expressions for dedup tests. */
function makeReader(active: string[]): Pick<InternalStoreReader, "listActiveFactorExpressions"> {
  return {
    listActiveFactorExpressions: () => active,
  }
}

describe("FactorMiningTracker", () => {
  test("emits exactly one pending sedimentation item on first fetch", async () => {
    const t = new FactorMiningTracker()
    const items = await t.fetchByStates(["pending"])
    expect(items).toHaveLength(1)
    expect(items[0].type).toBe("sedimentation")
    expect(items[0].id).toMatch(/^factor-mine-\d{4}-\d{2}-\d{2}$/)
    expect(items[0].labels).toContain("mining")
  })

  test("does not re-emit the same day's item twice", async () => {
    const t = new FactorMiningTracker()
    const a = await t.fetchByStates(["pending"])
    const b = await t.fetchByStates(["pending"])
    expect(a).toHaveLength(1)
    expect(b).toHaveLength(1)
    expect(b[0].id).toBe(a[0].id)
  })

  test("excludes items whose state is not in the requested set", async () => {
    const t = new FactorMiningTracker()
    const [item] = await t.fetchByStates(["pending"])
    await t.updateState(item.id, "done")
    expect(await t.fetchByStates(["pending"])).toHaveLength(0)
    const done = await t.fetchByStates(["done"])
    expect(done).toHaveLength(1)
  })

  test("updateState supports retry flow", async () => {
    const t = new FactorMiningTracker()
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
    const t = new FactorMiningTracker()
    const [item] = await t.fetchByStates(["pending"])
    const got = await t.fetchById(item.id)
    expect(got?.id).toBe(item.id)
  })

  test("updateState on unknown id is a no-op", async () => {
    const t = new FactorMiningTracker()
    await expect(t.updateState("nope", "done")).resolves.toBeUndefined()
  })

  test("prompt instructs the agent to persist factors with |IC| > 0.03", async () => {
    const t = new FactorMiningTracker()
    const [item] = await t.fetchByStates(["pending"])
    expect(item.description).toContain("factor register")
    expect(item.description).toMatch(/\|IC\|\s*>\s*0\.03/)
    expect(item.description).toContain("qlib eval")
  })

  test("without a reader, prompt notes no existing active factors", async () => {
    const t = new FactorMiningTracker()
    const [item] = await t.fetchByStates(["pending"])
    expect(item.description).toContain("starting fresh")
  })

  test("with a reader, prompt injects active expressions as dedup context", async () => {
    const reader = makeReader(["close/Ref(close,20)-1", "$volume/Mean($volume,20)"])
    const t = new FactorMiningTracker(reader as InternalStoreReader)
    const [item] = await t.fetchByStates(["pending"])
    expect(item.description).toContain("close/Ref(close,20)-1")
    expect(item.description).toContain("$volume/Mean($volume,20)")
    expect(item.description).toContain("do NOT duplicate")
    expect(item.description).not.toContain("starting fresh")
  })

  test("reader that throws is swallowed (agent mines without dedup context)", async () => {
    const brokenReader = {
      listActiveFactorExpressions: () => {
        throw new Error("db locked")
      },
    }
    const t = new FactorMiningTracker(brokenReader as InternalStoreReader)
    const [item] = await t.fetchByStates(["pending"])
    expect(item.description).toContain("starting fresh")
  })

  test("weekday theme rotates (title contains a theme name)", async () => {
    const t = new FactorMiningTracker()
    const [item] = await t.fetchByStates(["pending"])
    // Theme is whatever today is; just assert it's one of the known names.
    const knownThemes = ["momentum", "mean-reversion", "volatility", "volume", "cross-sectional"]
    expect(knownThemes.some((name) => item.title.toLowerCase().includes(name))).toBe(true)
  })

  test("agentToolSpecs advertises qlib + factor tools", () => {
    const t = new FactorMiningTracker()
    const specs = t.agentToolSpecs().map((s) => s.name)
    expect(specs).toContain("qlib")
    expect(specs).toContain("factor")
  })
})

// keep RunState import meaningful for future state-typed assertions
export type _RunState = RunState
