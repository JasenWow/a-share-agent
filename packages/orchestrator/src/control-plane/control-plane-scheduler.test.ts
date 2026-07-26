/**
 * control-plane-scheduler tests — red/green TDD PR2 (Step 3).
 *
 * Drives the scheduler manually via `fire()` so tests don't wait for the
 * cron timer. Uses FakeRunner + a fixed session resolver.
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { ControlPlaneStore } from "./control-plane-store"
import { ControlPlaneService } from "./control-plane-service"
import { FakeRunner } from "./fake-runner"
import { ControlPlaneScheduler, type SessionResolver } from "./control-plane-scheduler"

let store: ControlPlaneStore | null = null
let tmpDir: string | null = null

const FIXED_SESSION: SessionResolver = {
  resolve: () => "2026-08-04",
}

function fresh(): { svc: ControlPlaneService; scheduler: ControlPlaneScheduler } {
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true })
  tmpDir = mkdtempSync(join(tmpdir(), "cps-driver-"))
  store = new ControlPlaneStore({ path: join(tmpDir, "control.db") })
  const svc = new ControlPlaneService({
    store,
    runner: new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4231 },
      { stage: "dbt", status: "ok" },
    ]),
    idGenerator: (() => {
      let n = 0
      return () => `run-${++n}`
    })(),
    clock: () => new Date("2026-08-04T18:00:00Z"),
  })
  const scheduler = new ControlPlaneScheduler({
    service: svc,
    sessionResolver: FIXED_SESSION,
    now: () => new Date("2026-08-04T18:00:00Z"),
    logger: { info() {}, warn() {}, error() {} },
  })
  return { svc, scheduler }
}

afterEach(async () => {
  if (store) {
    await store.close()
    store = null
  }
  if (tmpDir) {
    rmSync(tmpDir, { recursive: true, force: true })
    tmpDir = null
  }
})

describe("ControlPlaneScheduler", () => {
  test("start registers jobs for all schedules in store", async () => {
    const { svc, scheduler } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    await scheduler.start()
    expect(scheduler.isRunning()).toBe(true)
    const status = scheduler.status()
    expect(status.map((s) => s.name)).toEqual(["equity_daily"])
    scheduler.stop()
  })

  test("fire on active schedule creates run + bumps counters", async () => {
    const { svc, scheduler } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    scheduler.addJob({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    })
    await scheduler.fire("equity_daily")
    const status = scheduler.status()
    expect(status[0]?.fireCount).toBe(1)
    expect(status[0]?.lastSkipped).toBe(false)

    const def = await svc.getSchedule("equity_daily")
    expect(def?.fireCount).toBe(1)

    const occurrences = await svc.listOccurrences("equity_daily")
    expect(occurrences).toHaveLength(1)

    const runs = await svc.listRuns("equity_daily")
    expect(runs.length).toBeGreaterThanOrEqual(1)
    expect(runs[0]?.trigger).toBe("scheduled")
  })

  test("fire on paused schedule records skip", async () => {
    const { svc, scheduler } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: true,
      createdAt: "2026-08-04T00:00:00Z",
    })
    scheduler.addJob({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: true,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    })
    await scheduler.fire("equity_daily")
    const status = scheduler.status()
    expect(status[0]?.lastSkipped).toBe(true)
    // No occurrence recorded when skipped
    const occurrences = await svc.listOccurrences("equity_daily")
    expect(occurrences).toEqual([])
  })

  test("fire on unknown schedule is a no-op", async () => {
    const { scheduler } = fresh()
    await scheduler.fire("nope")
    expect(scheduler.status()).toEqual([])
  })

  test("stop clears all jobs", async () => {
    const { svc, scheduler } = fresh()
    await svc.upsertSchedule({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      createdAt: "2026-08-04T00:00:00Z",
    })
    await scheduler.start()
    scheduler.stop()
    expect(scheduler.isRunning()).toBe(false)
    expect(scheduler.status()).toEqual([])
  })
})