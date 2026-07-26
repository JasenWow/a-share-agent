import { afterEach, describe, expect, test } from "bun:test"
import { Database } from "bun:sqlite"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import type { WorkItem } from "@aquan/core"
import { Orchestrator } from "./orchestrator"
import { MemoryTracker } from "./trackers/tracker"
import { StubRuntime } from "./runtime"
import { startOrchestratorServer } from "./http"
import { InternalStoreReader } from "./internal-store-reader"
import type { CandidateFactor } from "./internal-store-reader"

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

function startTestServer(
  orch: Orchestrator,
  port = 13410,
  reader?: InternalStoreReader,
): string {
  server = startOrchestratorServer(orch, port, reader ? { internalStoreReader: reader } : {})
  return `http://localhost:${port}`
}

/** A fake reader that returns canned candidates (no DB needed). */
function makeFakeReader(candidates: CandidateFactor[], available = true): InternalStoreReader {
  return {
    listCandidates: () => candidates,
    listActiveFactorExpressions: () => [],
    candidateCount: () => candidates.length,
    isAvailable: () => available,
  } as InternalStoreReader
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

describe("orchestrator HTTP — /api/v1/factors/candidates", () => {
  const sampleCandidate: CandidateFactor = {
    id: 7,
    name: "momentum_20d",
    expression: "close/Ref(close,20)-1",
    hypothesis: "20-day momentum",
    operators: ["div", "sub", "ref"],
    dataFields: ["close"],
    ic: 0.05,
    icir: 0.42,
    turnover: 0.3,
    sharpe: 1.1,
    maxDrawdown: 0.18,
    universe: "csi300",
    period: "2020-2024",
    confidence: 0.7,
    rationale: "stable in backtest",
    status: "candidate",
    sourceExperimentId: 3,
    createdAt: "2026-07-25T00:00:00Z",
  }

  test("returns candidates from the reader with source=internal-store", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const reader = makeFakeReader([sampleCandidate], true)
    const base = startTestServer(orch, 13420, reader)
    const payload = (await getJson(base, "/api/v1/factors/candidates")) as {
      candidates: CandidateFactor[]
      count: number
      source: string
    }
    expect(payload.source).toBe("internal-store")
    expect(payload.count).toBe(1)
    expect(payload.candidates[0].name).toBe("momentum_20d")
    expect(payload.candidates[0].confidence).toBe(0.7)
  })

  test("reports source=unavailable when reader present but DB missing", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const reader = makeFakeReader([], false)
    const base = startTestServer(orch, 13421, reader)
    const payload = (await getJson(base, "/api/v1/factors/candidates")) as {
      candidates: unknown[]
      count: number
      source: string
    }
    expect(payload.source).toBe("unavailable")
    expect(payload.candidates).toEqual([])
    expect(payload.count).toBe(0)
  })

  test("reports source=unavailable when no reader wired (stub mode)", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13422)
    const payload = (await getJson(base, "/api/v1/factors/candidates")) as {
      candidates: unknown[]
      count: number
      source: string
    }
    expect(payload.source).toBe("unavailable")
    expect(payload.candidates).toEqual([])
    expect(payload.count).toBe(0)
  })
})

describe("orchestrator HTTP — /api/v1/loops", () => {
  test("returns history payload with aggregation", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "factor-mine-2026-07-20" }), state: "pending" } as never])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [tracker] })
    await orch.tick() // → done
    const base = startTestServer(orch, 13430)

    const payload = (await getJson(base, "/api/v1/loops")) as {
      generatedAt: string
      items: Array<{ id: string; state: string }>
      byTracker: Record<string, { total: number; done: number }>
      totals: { total: number; done: number }
    }
    expect(payload.items.length).toBeGreaterThanOrEqual(1)
    expect(payload.items[0].id).toBe("factor-mine-2026-07-20")
    expect(payload.items[0].state).toBe("done")
    expect(payload.byTracker["factor-mining"].done).toBe(1)
    expect(payload.totals.done).toBe(1)
  })

  test("?state= filter narrows items", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([
      { ...makeWork({ id: "w-done" }), state: "pending" } as never,
      { ...makeWork({ id: "w-pending" }), state: "pending" } as never,
    ])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [tracker] })
    await orch.tick() // both → done
    const base = startTestServer(orch, 13431)

    const payload = (await getJson(base, "/api/v1/loops?state=failed")) as {
      items: unknown[]
      totals: { total: number }
    }
    expect(payload.items).toEqual([])
    expect(payload.totals.total).toBe(0)
  })
})

describe("orchestrator HTTP — /api/v1/work/:id/events", () => {
  test("returns events after a tick produces them", async () => {
    const tracker = new MemoryTracker()
    tracker.seed([{ ...makeWork({ id: "w-events" }), state: "pending" } as never])
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [tracker] })
    await orch.tick() // → done (StubRuntime emits no events, so we seed some)
    orch.store.appendEvents("w-events", [
      { at: "2026-07-26T10:00:01Z", kind: "message", detail: "hello" },
      { at: "2026-07-26T10:00:02Z", kind: "tool_call", detail: "factor list" },
      { at: "2026-07-26T10:00:03Z", kind: "turn_end" },
    ])
    const base = startTestServer(orch, 13440)

    const payload = (await getJson(base, "/api/v1/work/w-events/events")) as {
      workId: string
      events: Array<{ at: string; kind: string; detail?: string }>
      count: number
    }
    expect(payload.workId).toBe("w-events")
    expect(payload.count).toBe(3)
    expect(payload.events[0].kind).toBe("message")
    expect(payload.events[2].kind).toBe("turn_end")
  })

  test("?kind= filters events", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    orch.store.appendEvents("w1", [
      { at: "2026-07-26T10:00:01Z", kind: "message", detail: "a" },
      { at: "2026-07-26T10:00:02Z", kind: "tool_call", detail: "x" },
      { at: "2026-07-26T10:00:03Z", kind: "tool_result", detail: "y" },
    ])
    const base = startTestServer(orch, 13441)
    const payload = (await getJson(base, "/api/v1/work/w1/events?kind=tool_call,tool_result")) as {
      events: Array<{ kind: string }>
      count: number
    }
    expect(payload.count).toBe(2)
    expect(payload.events.every((e) => e.kind.startsWith("tool"))).toBe(true)
  })

  test("unknown work id returns empty array (not 404)", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13442)
    const payload = (await getJson(base, "/api/v1/work/never/events")) as {
      events: unknown[]
      count: number
    }
    expect(payload.count).toBe(0)
    expect(payload.events).toEqual([])
  })
})

/** Build a temp meta.db with one candidate row, return reader + cleanup. */
function makeTempReaderWithCandidate(): { reader: InternalStoreReader; cleanup: () => void } {
  const dir = mkdtempSync(join(tmpdir(), "aquan-http-promote-"))
  const path = join(dir, "meta.db")
  const db = new Database(path, { create: true })
  db.run(`
    CREATE TABLE factor_library (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, expression TEXT NOT NULL,
      hypothesis TEXT, operators TEXT NOT NULL, data_fields TEXT NOT NULL,
      ic REAL, icir REAL, turnover REAL, sharpe REAL, max_drawdown REAL,
      universe TEXT, period TEXT, walk_forward TEXT, status TEXT DEFAULT 'active',
      source_experiment_id INTEGER, created_at TEXT
    );
  `)
  db.run(
    `INSERT INTO factor_library (name, expression, hypothesis, operators, data_fields, status) VALUES (?, ?, ?, ?, ?, 'candidate');`,
    "mom20",
    "close/Ref(close,20)-1",
    "",
    '["div"]',
    '["close"]',
  )
  db.close()
  return {
    reader: new InternalStoreReader(path),
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  }
}

describe("orchestrator HTTP — POST /api/v1/factors/:id/promote + /reject", () => {
  let cleanup: () => void

  afterEach(() => {
    try {
      cleanup?.()
    } catch {
      // ignore
    }
  })

  test("promote moves candidate → active (200)", async () => {
    const made = makeTempReaderWithCandidate()
    cleanup = made.cleanup
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13450, made.reader)

    const res = await fetch(`${base}/api/v1/factors/1/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer: "alice", notes: "good IC" }),
    })
    const payload = (await res.json()) as { ok: boolean; targetStatus?: string; reviewer?: string }
    expect(res.status).toBe(200)
    expect(payload.ok).toBe(true)
    expect(payload.targetStatus).toBe("active")
    expect(payload.reviewer).toBe("alice")
    // Candidate list now empty
    const after = (await getJson(base, "/api/v1/factors/candidates")) as { count: number }
    expect(after.count).toBe(0)
  })

  test("promote on non-candidate returns 409", async () => {
    const made = makeTempReaderWithCandidate()
    cleanup = made.cleanup
    // Promote first to make it active, then try again
    made.reader.promoteCandidate(1)
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13451, made.reader)

    const res = await fetch(`${base}/api/v1/factors/1/promote`, { method: "POST" })
    const payload = (await res.json()) as { ok: boolean; error?: string }
    expect(res.status).toBe(409)
    expect(payload.ok).toBe(false)
    expect(payload.error).toBe("not-candidate")
  })

  test("promote on missing id returns 404", async () => {
    const made = makeTempReaderWithCandidate()
    cleanup = made.cleanup
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13452, made.reader)

    const res = await fetch(`${base}/api/v1/factors/999/promote`, { method: "POST" })
    expect(res.status).toBe(404)
  })

  test("reject sets rejected (200)", async () => {
    const made = makeTempReaderWithCandidate()
    cleanup = made.cleanup
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13453, made.reader)

    const res = await fetch(`${base}/api/v1/factors/1/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "low IC", reviewer: "bob" }),
    })
    const payload = (await res.json()) as { ok: boolean; targetStatus?: string; reason?: string }
    expect(res.status).toBe(200)
    expect(payload.ok).toBe(true)
    expect(payload.targetStatus).toBe("rejected")
    expect(payload.reason).toBe("low IC")
    // No longer a candidate
    const after = (await getJson(base, "/api/v1/factors/candidates")) as { count: number }
    expect(after.count).toBe(0)
  })

  test("returns 503 when no reader wired", async () => {
    const orch = new Orchestrator({ runtime: new StubRuntime(), trackers: [] })
    const base = startTestServer(orch, 13454)
    const res = await fetch(`${base}/api/v1/factors/1/promote`, { method: "POST" })
    expect(res.status).toBe(503)
    const payload = (await res.json()) as { ok: boolean; error?: string }
    expect(payload.ok).toBe(false)
    expect(payload.error).toBe("unavailable")
  })
})
