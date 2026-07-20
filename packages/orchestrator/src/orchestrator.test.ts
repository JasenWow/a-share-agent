import { describe, expect, test } from "bun:test"
import type { WorkItem } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import { buildInitialPrompt } from "./prompt-builder"
import { statePayload } from "./presenter"

function makeWork(overrides: Partial<WorkItem> = {}): WorkItem {
  return {
    id: "test-work",
    title: "Test work",
    type: "sedimentation",
    description: "stub description",
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("prompt-builder", () => {
  test("initial prompt includes title and description", () => {
    const work = makeWork({ title: "Mine momentum factors", description: "Find good momentum factors." })
    const prompt = buildInitialPrompt(work)
    expect(prompt).toContain("Mine momentum factors")
    expect(prompt).toContain("Find good momentum factors")
    expect(prompt).toContain("sedimentation")
  })
})

describe("orchestrator with StubRuntime + MemoryTracker", () => {
  test("tick runs pending work and transitions to done", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])

    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
    })

    const result = await orch.tick()
    expect(result.ran).toBe(1)
    expect(result.outcomes.done).toBe(1)

    const work = orch.store.get("w1")
    expect(work?.state).toBe("done")
    expect(work?.turnCount).toBe(1)
  })

  test("statePayload reports counts by state", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([
      { ...makeWork({ id: "w1" }), state: "pending" },
      { ...makeWork({ id: "w2" }), state: "pending" },
    ])

    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
    })

    await orch.tick()

    const payload = statePayload(orch.store)
    expect(payload.counts.done).toBe(2)
    expect(payload.counts.running).toBe(0)
    expect(payload.running).toEqual([])
    expect(payload.recent.length).toBe(2)
  })

  test("empty tracker produces empty tick", async () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [new MemoryTracker()],
    })
    const result = await orch.tick()
    expect(result.ran).toBe(0)
  })
})
