import { describe, expect, test } from "bun:test"
import type { PolicyBundle, TrackedWork, WorkItem } from "@aquan/core"
import { UNLIMITED_POLICY } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import type { RunOutcome } from "./agent-runner"
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

// --- Retry / backoff fixtures ---

/**
 * A runtime whose runTurn behavior is scripted by attempt number. Each
 * startSession bumps a per-work counter; runTurn returns the scripted
 * outcome for the current attempt. Used to simulate infra failures that
 * should retry, agent failures that should not, etc.
 */
class ScriptedRuntime extends StubRuntime {
  // attempt → outcome for that attempt's runTurn
  private scripts = new Map<string, Map<number, "infra-fail" | "agent-fail" | "done">>()
  private counts = new Map<string, number>()

  /** Script the outcome for each attempt number (1-indexed). */
  script(workId: string, byAttempt: Record<number, "infra-fail" | "agent-fail" | "done">) {
    this.scripts.set(workId, new Map(Object.entries(byAttempt).map(([k, v]) => [Number(k), v])))
  }

  override async startSession(opts: { workspacePath: string; workId: string; prompt: string }) {
    const id = opts.workId
    const next = (this.counts.get(id) ?? 0) + 1
    this.counts.set(id, next)
    const outcome = this.scripts.get(id)?.get(next) ?? "done"
    const sess = await super.startSession(opts)
    return {
      ...sess,
      runTurn: async () => {
        if (outcome === "infra-fail") {
          throw new Error(`infra error on attempt ${next}`)
        }
        if (outcome === "agent-fail") {
          // The agent-runner wraps a non-throwing "failed" by returning
          // a TurnResult — but StubRuntime always returns done. To model
          // an agent decision to fail, we throw and rely on the runner
          // classifying it. For a true "agent failure" (not retried),
          // we instead return done here and test that path via the
          // failureKind contract at the runWork level. Here, infra-fail
          // is the retry-eligible case we care about for orchestrator
          // retry logic; agent-fail is covered by the decideRetry unit
          // assertion below.
          return { kind: "done" as const, events: [] }
        }
        return { kind: "done" as const, events: [] }
      },
    }
  }
}

const RETRY_POLICY: PolicyBundle = {
  budget: { dailyCap: null, weeklyCap: null, monthlyCap: null },
  concurrency: { maxConcurrent: 1 },
  retry: { maxAttempts: 3, backoffMs: 0 }, // 0ms so backoff elapses immediately
}

describe("orchestrator retry — exponential backoff", () => {
  test("infra failure transitions to retrying with incremented attempt + nextRetryAt", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail", 2: "done" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    const r1 = await orch.tick()

    expect(r1.outcomes.retrying).toBe(1)
    const w = orch.store.get("w1")
    expect(w?.state).toBe("retrying")
    expect(w?.attempt).toBe(2) // incremented for the upcoming retry
    expect(w?.nextRetryAt).toBeDefined()
    expect(w?.error).toContain("infra error")
  })

  test("retrying item is skipped while backoff window hasn't elapsed", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail", 2: "done" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    await orch.tick() // → retrying, attempt 2, nextRetryAt set

    // Force a future nextRetryAt so the next tick skips it.
    orch.store.transition("w1", "retrying", {
      nextRetryAt: new Date(Date.now() + 60_000).toISOString(),
    })

    const r2 = await orch.tick()
    expect(r2.ran).toBe(0) // skipped, not run
    expect(r2.outcomes.retrying).toBe(1)
    // attempt unchanged — we didn't run.
    expect(orch.store.get("w1")?.attempt).toBe(2)
  })

  test("retrying item re-runs once backoff elapses and succeeds", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail", 2: "done" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    await orch.tick() // attempt 1 → infra fail → retrying, attempt 2
    // backoffMs=0 → nextRetryAt is already in the past; next tick runs it.
    const r2 = await orch.tick()
    expect(r2.outcomes.done).toBe(1)
    const w = orch.store.get("w1")
    expect(w?.state).toBe("done")
    expect(w?.nextRetryAt).toBeUndefined() // cleared on terminal transition
  })

  test("maxAttempts exhausted → failed (terminal)", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail", 2: "infra-fail", 3: "infra-fail" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    await orch.tick() // attempt 1 → retrying
    await orch.tick() // attempt 2 → retrying
    const r3 = await orch.tick() // attempt 3 → maxAttempts hit → failed

    expect(r3.outcomes.failed).toBe(1)
    const w = orch.store.get("w1")
    expect(w?.state).toBe("failed")
    expect(w?.nextRetryAt).toBeUndefined()
  })

  test("failed item is not re-fetched (terminal, tracker stops returning it)", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail", 2: "infra-fail", 3: "infra-fail" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    await orch.tick()
    await orch.tick()
    await orch.tick() // → failed
    const r4 = await orch.tick() // tracker no longer returns the failed item
    expect(r4.ran).toBe(0)
  })

  test("successful run → done, attempt stays 1, no nextRetryAt", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "done" })

    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy: RETRY_POLICY })
    const r = await orch.tick()
    expect(r.outcomes.done).toBe(1)
    const w = orch.store.get("w1")
    expect(w?.state).toBe("done")
    expect(w?.attempt).toBe(1)
    expect(w?.nextRetryAt).toBeUndefined()
  })

  test("backoff delay grows exponentially (1000 → 2000 → 4000)", async () => {
    // Assert computeBackoff math directly. attempt N failing schedules a
    // retry backoffMs * 2^(N-1) ms in the future.
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" }])
    const rt = new ScriptedRuntime()
    rt.script("w1", { 1: "infra-fail" })

    const policy: PolicyBundle = {
      budget: { dailyCap: null, weeklyCap: null, monthlyCap: null },
      concurrency: { maxConcurrent: 1 },
      retry: { maxAttempts: 3, backoffMs: 1000 },
    }
    const orch = new Orchestrator({ runtime: rt as never, trackers: [tracker], policy })

    // attempt 1 fails → retry scheduled ~1s out (1000 * 2^0)
    await orch.tick()
    const w1 = orch.store.get("w1")!
    const delay1 = new Date(w1.nextRetryAt!).getTime() - Date.now()
    expect(delay1).toBeGreaterThan(800)
    expect(delay1).toBeLessThan(1200)

    // Recompute for attempts 2 and 3 to verify exponential growth without
    // waiting for real time to elapse.
    const d2 = new Date(orch["computeBackoff"](2)).getTime() - Date.now()
    const d3 = new Date(orch["computeBackoff"](3)).getTime() - Date.now()
    expect(d2).toBeGreaterThan(1900) // 1000 * 2^1
    expect(d3).toBeGreaterThan(3900) // 1000 * 2^2
  })
})

describe("orchestrator retry — decideRetry contract", () => {
  test("agent-done is terminal (not retried)", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [],
      policy: RETRY_POLICY,
    })
    const work: TrackedWork = { ...makeWork({ id: "w1" }), state: "running", attempt: 1 }
    const result: RunOutcome = { state: "done", events: [], turnCount: 1 }
    expect(orch["decideRetry"](work, result)).toBe("done")
  })

  test("agent-blocked is terminal (not retried)", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [],
      policy: RETRY_POLICY,
    })
    const work: TrackedWork = { ...makeWork({ id: "w1" }), state: "running", attempt: 1 }
    const result: RunOutcome = { state: "blocked", events: [], turnCount: 1 }
    expect(orch["decideRetry"](work, result)).toBe("blocked")
  })

  test("infra failure with attempts remaining → retrying", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [],
      policy: RETRY_POLICY, // maxAttempts: 3
    })
    const work: TrackedWork = { ...makeWork({ id: "w1" }), state: "running", attempt: 1 }
    const result: RunOutcome = { state: "failed", events: [], turnCount: 0, failureKind: "infra" }
    expect(orch["decideRetry"](work, result)).toBe("retrying")
  })

  test("infra failure at maxAttempts → failed (terminal)", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [],
      policy: RETRY_POLICY, // maxAttempts: 3
    })
    const work: TrackedWork = { ...makeWork({ id: "w1" }), state: "running", attempt: 3 }
    const result: RunOutcome = { state: "failed", events: [], turnCount: 0, failureKind: "infra" }
    expect(orch["decideRetry"](work, result)).toBe("failed")
  })

  test("agent failure (failureKind='agent') → failed (terminal, not retried)", () => {
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [],
      policy: RETRY_POLICY,
    })
    const work: TrackedWork = { ...makeWork({ id: "w1" }), state: "running", attempt: 1 }
    const result: RunOutcome = { state: "failed", events: [], turnCount: 1, failureKind: "agent" }
    expect(orch["decideRetry"](work, result)).toBe("failed")
  })
})
