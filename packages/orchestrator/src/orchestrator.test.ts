import { describe, expect, test } from "bun:test"
import type { PolicyBundle, WorkItem } from "@aquan/core"
import { UNLIMITED_POLICY } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import { buildInitialPrompt, buildInitialPromptParts } from "./prompt-builder"
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

  test("initial prompt parts isolate untrusted content from system slot", () => {
    const parts = buildInitialPromptParts(makeWork({ description: "untrusted payload" }))
    expect(parts.user).toContain("untrusted payload")
    expect(parts.system).not.toContain("untrusted payload")
  })
})

describe("orchestrator with StubRuntime + MemoryTracker", () => {
  test("tick runs pending work and transitions to done", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])

    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
      policy: UNLIMITED_POLICY,
    })

    const result = await orch.tick()
    expect(result.ran).toBe(1)
    expect(result.outcomes.done).toBe(1)
    expect(result.throttled).toBe(0)

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
      policy: UNLIMITED_POLICY,
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
      policy: UNLIMITED_POLICY,
    })
    const result = await orch.tick()
    expect(result.ran).toBe(0)
  })
})

describe("orchestrator hardening — spend cap", () => {
  test("exhausted daily cap leaves work pending and reports throttled", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([
      { ...makeWork({ id: "w1" }), state: "pending" },
      { ...makeWork({ id: "w2" }), state: "pending" },
    ])

    const strictPolicy: PolicyBundle = {
      budget: { dailyCap: 1, weeklyCap: null, monthlyCap: null },
      concurrency: { maxConcurrent: 1 },
      retry: { maxAttempts: 1, backoffMs: 0 },
    }

    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
      policy: strictPolicy,
    })

    const result = await orch.tick()
    expect(result.ran).toBe(1)
    expect(result.throttled).toBe(1)
    expect(result.outcomes.done).toBe(1)
    expect(result.outcomes.pending).toBe(1)

    // The throttled work is still in pending — never started.
    const w2 = orch.store.get("w2")
    expect(w2).toBeUndefined()

    // spend guard reflects exactly one spend.
    expect(orch.spend.getStats().daily).toBe(1)
  })

  test("default policy runs the smoke suite without surprises", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
      // no explicit policy → DEFAULT_POLICY
    })
    const result = await orch.tick()
    expect(result.ran).toBe(1)
    expect(result.throttled).toBe(0)
  })
})

describe("orchestrator hardening — concurrency", () => {
  test("serial policy (maxConcurrent=1) drains items sequentially", async () => {
    // Use a runtime that tracks overlap.
    let active = 0
    let maxOverlap = 0
    class TrackingRuntime extends StubRuntime {
      override async startSession(opts: { workspacePath: string; workId: string; prompt: string }) {
        active += 1
        maxOverlap = Math.max(maxOverlap, active)
        const sess = await super.startSession(opts)
        return {
          ...sess,
          runTurn: async () => {
            // Simulate some async work so concurrency would show if it could.
            await Promise.resolve()
            active -= 1
            return { kind: "done" as const, events: [] }
          },
        }
      }
    }

    const tracker = new MemoryTracker()
    tracker.seed([
      { ...makeWork({ id: "w1" }), state: "pending" },
      { ...makeWork({ id: "w2" }), state: "pending" },
      { ...makeWork({ id: "w3" }), state: "pending" },
    ])

    const orch = new Orchestrator({
      runtime: new TrackingRuntime() as never,
      trackers: [tracker],
      policy: {
        budget: { dailyCap: null, weeklyCap: null, monthlyCap: null },
        concurrency: { maxConcurrent: 1 },
        retry: { maxAttempts: 1, backoffMs: 0 },
      },
    })

    await orch.tick()
    expect(maxOverlap).toBe(1)
    expect(orch.concurrency.getActive()).toBe(0)
  })
})
