import { describe, expect, test, mock } from "bun:test"
import type { WorkItem } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import { Scheduler, type ScheduleSpec } from "./scheduler"

function makeWork(overrides: Partial<WorkItem> = {}): WorkItem {
  return {
    id: "w1",
    title: "test",
    type: "sedimentation",
    description: "stub",
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

describe("Scheduler — lifecycle", () => {
  test("start sets running state", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [new MemoryTracker()],
    })
    const s = new Scheduler(orch)
    expect(s.isRunning()).toBe(false)
    s.start([])
    expect(s.isRunning()).toBe(true)
    s.stop()
    expect(s.isRunning()).toBe(false)
  })

  test("stop is idempotent", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s = new Scheduler(orch)
    s.stop() // never started
    s.stop() // still no-op
    expect(s.isRunning()).toBe(false)
  })

  test("start is idempotent (calling twice doesn't double up)", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s = new Scheduler(orch)
    s.start([{ cron: "0 0 * * *", name: "daily" }])
    s.start([{ cron: "0 0 * * *", name: "daily" }])
    expect(s.status().length).toBe(1)
    s.stop()
  })
})

describe("Scheduler — fire()", () => {
  test("fire drives orchestrator.tick with tracker filter", async () => {
    const trackerA = new MemoryTracker()
    trackerA.name = "alpha"
    trackerA.seed([{ ...makeWork({ id: "a1" }), state: "pending" } as never])
    const trackerB = new MemoryTracker()
    trackerB.name = "beta"
    trackerB.seed([{ ...makeWork({ id: "b1" }), state: "pending" } as never])

    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [trackerA, trackerB],
    })

    const tickSpy = mock(() => orch.tick())
    // Patch orch.tick on a wrapper scheduler so we capture the filter.
    const s = new Scheduler(orch)
    // Use the public fire() API directly instead of waiting on cron timing.
    const managed = {
      spec: { cron: "* * * * *", trackers: ["alpha"], name: "alpha-only" },
      job: undefined as never,
      fireCount: 0,
      errorCount: 0,
    }
    // Call fire through the scheduler so we exercise its accounting.
    await (s as unknown as { fire(m: unknown): Promise<void> }).fire(managed)
    expect(managed.fireCount).toBe(1)
    expect(managed.errorCount).toBe(0)
    expect(managed.lastFireAt).toBeDefined()

    // Only the alpha tracker should have run; beta's work stays untouched.
    expect(orch.store.get("a1")?.state).toBe("done")
    expect(orch.store.get("b1")).toBeUndefined()
    void tickSpy
  })

  test("fire counts errors without crashing the scheduler", async () => {
    const orch = new Orchestrator({
      runtime: {
        async startSession() {
          throw new Error("boom")
        },
        async stopSession() {},
      },
      trackers: [
        {
          name: "broken",
          async fetchByStates() {
            return [makeWork({ id: "x1" })]
          },
          async fetchById() {
            return undefined
          },
          async updateState() {},
          agentToolSpecs() {
            return []
          },
        },
      ],
    })

    const s = new Scheduler(orch)
    const managed = {
      spec: { cron: "* * * * *", name: "broken-test" },
      job: undefined as never,
      fireCount: 0,
      errorCount: 0,
    }
    await (s as unknown as { fire(m: unknown): Promise<void> }).fire(managed)
    // The orchestrator catches runWork failures internally, so this tick
    // succeeds even though the runtime throws. fire() should not have
    // counted it as an error.
    expect(managed.errorCount).toBe(0)
    expect(managed.fireCount).toBe(1)
  })

  test("status() reflects running jobs", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s = new Scheduler(orch)
    s.start([
      { cron: "0 0 * * *", name: "daily" },
      { cron: "0 * * * *", name: "hourly" },
    ])
    const status = s.status()
    expect(status.length).toBe(2)
    expect(status.map((x) => x.spec.name).sort()).toEqual(["daily", "hourly"])
    s.stop()
  })
})

describe("Orchestrator.start/stop integration", () => {
  test("orch.start returns a running scheduler", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s = orch.start([{ cron: "0 0 * * *", name: "daily" }])
    expect(s.isRunning()).toBe(true)
    expect(orch.getScheduler()).toBeDefined()
    orch.stop()
    expect(orch.getScheduler()).toBeUndefined()
  })

  test("calling start twice replaces the previous scheduler", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s1 = orch.start([{ cron: "0 0 * * *", name: "daily" }])
    const s2 = orch.start([{ cron: "0 * * * *", name: "hourly" }])
    expect(s1.isRunning()).toBe(false) // s1 was stopped by the second start
    expect(s2.isRunning()).toBe(true)
    expect(orch.getScheduler()).toBe(s2)
    orch.stop()
  })
})

// Validations on ScheduleSpec shape (no real cron firing).
describe("Scheduler — schedule validation", () => {
  test("CronJob accepts valid 5-field expression", () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const s = new Scheduler(orch)
    const valid: ScheduleSpec[] = [
      { cron: "0 18 * * 1-5", name: "weekday-close" },
      { cron: "30 9 * * *", name: "morning" },
    ]
    expect(() => s.start(valid)).not.toThrow()
    s.stop()
  })
})
