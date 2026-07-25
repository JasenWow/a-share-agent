import { afterEach, describe, expect, test } from "bun:test"
import type { WorkItem } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import { startOrchestratorServer } from "./http"

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

let server: ReturnType<typeof Bun.serve> | undefined

function startTestServer(orch: Orchestrator, port = 13410): string {
  server = startOrchestratorServer(orch, port)
  return `http://localhost:${port}`
}

afterEach(() => {
  try {
    server?.stop(true)
  } catch {
    // ignore
  }
  server = undefined
})

async function getJson(base: string, path: string): Promise<unknown> {
  const res = await fetch(`${base}${path}`)
  return res.json()
}

describe("orchestrator HTTP — /api/v1/state", () => {
  test("returns counts + lists + spend + schedules", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w1" }), state: "pending" } as never])
    const orch = new Orchestrator({
      runtime: new StubRuntime(),
      trackers: [tracker],
    })
    orch.start([{ cron: "* * * * *", name: "minute" }])
    const base = startTestServer(orch)

    const payload = (await getJson(base, "/api/v1/state")) as {
      counts: Record<string, number>
      spend?: { daily: number; dailyCap: number | null }
      schedules?: Array<{ spec: { name?: string } }>
    }
    expect(payload.counts).toBeDefined()
    expect(payload.counts.pending + payload.counts.running + payload.counts.done).toBeGreaterThanOrEqual(0)
    expect(payload.spend?.dailyCap).toBe(50) // DEFAULT_POLICY.dailyCap
    expect(payload.schedules?.length).toBe(1)
    expect(payload.schedules?.[0]?.spec.name).toBe("minute")
    orch.stop()
  })
})

describe("orchestrator HTTP — /api/v1/schedules", () => {
  test("returns empty when scheduler not started", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch)
    const payload = (await getJson(base, "/api/v1/schedules")) as {
      schedules: unknown[]
      running: boolean
    }
    expect(payload.schedules).toEqual([])
    expect(payload.running).toBe(false)
  })

  test("returns schedule list when started", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    orch.start([
      { cron: "* * * * *", name: "minutely" },
      { cron: "0 * * * *", name: "hourly" },
    ])
    const base = startTestServer(orch)
    const payload = (await getJson(base, "/api/v1/schedules")) as {
      schedules: Array<{ spec: { name?: string } }>
      running: boolean
    }
    expect(payload.running).toBe(true)
    expect(payload.schedules.length).toBe(2)
    expect(payload.schedules.map((s) => s.spec.name).sort()).toEqual(["hourly", "minutely"])
    orch.stop()
  })
})

describe("orchestrator HTTP — /api/v1/spend", () => {
  test("returns counters + caps", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch)
    const payload = (await getJson(base, "/api/v1/spend")) as {
      daily: number
      weekly: number
      monthly: number
      dailyCap: number | null
    }
    expect(payload.daily).toBe(0)
    expect(payload.weekly).toBe(0)
    expect(payload.monthly).toBe(0)
    expect(payload.dailyCap).toBe(50)
  })
})

describe("orchestrator HTTP — /api/v1/work/:id", () => {
  test("404 for unknown id", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch)
    const res = await fetch(`${base}/api/v1/work/unknown`)
    expect(res.status).toBe(404)
  })

  test("returns work after a tick seeds it", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w-found" }), state: "pending" } as never])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [tracker] })
    await orch.tick()
    const base = startTestServer(orch)

    const work = (await getJson(base, "/api/v1/work/w-found")) as { id: string; state: string }
    expect(work.id).toBe("w-found")
    expect(work.state).toBe("done")
  })
})

describe("orchestrator HTTP — /api/v1/tick", () => {
  test("POST triggers one tick and returns outcome", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w-tick" }), state: "pending" } as never])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [tracker] })
    const base = startTestServer(orch)

    const res = await fetch(`${base}/api/v1/tick`, { method: "POST" })
    const outcome = (await res.json()) as { ran: number; outcomes: { done: number } }
    expect(outcome.ran).toBe(1)
    expect(outcome.outcomes.done).toBe(1)
  })

  test("POST accepts ?trackers= filter", async () => {
    const a = new MemoryTracker()
    a.name = "alpha"
    a.seed([{ ...makeWork({ id: "a1" }), state: "pending" } as never])
    const b = new MemoryTracker()
    b.name = "beta"
    b.seed([{ ...makeWork({ id: "b1" }), state: "pending" } as never])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [a, b] })
    const base = startTestServer(orch)

    const res = await fetch(`${base}/api/v1/tick?trackers=alpha`, { method: "POST" })
    const outcome = (await res.json()) as { ran: number }
    expect(outcome.ran).toBe(1) // only alpha
    expect(orch.store.get("b1")).toBeUndefined()
  })
})

describe("orchestrator HTTP — /healthz", () => {
  test("returns ok", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch)
    const payload = (await getJson(base, "/healthz")) as { ok: boolean }
    expect(payload.ok).toBe(true)
  })
})
