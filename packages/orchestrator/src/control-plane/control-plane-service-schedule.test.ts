/**
 * control-plane-service schedule tests — red/green TDD PR2 (Steps 2/4/5/6).
 *
 * Covers pause/resume, schedule registration, and fireSchedule integration
 * with runNow (skip-when-paused, occurrence recording, fireCount bump).
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { ControlPlaneStore } from "./control-plane-store"
import { ControlPlaneService } from "./control-plane-service"
import { FakeRunner } from "./fake-runner"
import type { ScheduleDefinition } from "./control-plane-store"

let store: ControlPlaneStore | null = null
let tmpDir: string | null = null

function fresh(): ControlPlaneService {
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true })
  tmpDir = mkdtempSync(join(tmpdir(), "cps-sched-"))
  store = new ControlPlaneStore({ path: join(tmpDir, "control.db") })
  return new ControlPlaneService({
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
}

function sampleDef(overrides: Partial<ScheduleDefinition> = {}): Omit<ScheduleDefinition, "fireCount" | "lastFireAt" | "updatedAt"> {
  return {
    name: "equity_daily",
    dataset: "equity_daily",
    trigger: "scheduled",
    cron: "0 18 * * 1-5",
    paused: false,
    createdAt: "2026-08-04T00:00:00Z",
    ...overrides,
  }
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

describe("ControlPlaneService — schedule control (PR2)", () => {
  test("upsert + get schedule", async () => {
    const svc = fresh()
    const def = await svc.upsertSchedule(sampleDef())
    expect(def.name).toBe("equity_daily")
    expect(def.paused).toBe(false)
    expect(def.cron).toBe("0 18 * * 1-5")
    const got = await svc.getSchedule("equity_daily")
    expect(got?.name).toBe("equity_daily")
  })

  test("pause sets paused=true and preserves cron", async () => {
    const svc = fresh()
    await svc.upsertSchedule(sampleDef())
    const paused = await svc.pause("equity_daily")
    expect(paused.paused).toBe(true)
    expect(paused.cron).toBe("0 18 * * 1-5")
  })

  test("resume sets paused=false", async () => {
    const svc = fresh()
    await svc.upsertSchedule(sampleDef({ paused: true }))
    const resumed = await svc.resume("equity_daily")
    expect(resumed.paused).toBe(false)
  })

  test("pause on missing schedule throws", async () => {
    const svc = fresh()
    expect(svc.pause("nope")).rejects.toThrow(/not found/i)
  })

  test("list schedules returns all", async () => {
    const svc = fresh()
    await svc.upsertSchedule(sampleDef({ name: "equity_daily", dataset: "equity_daily" }))
    await svc.upsertSchedule(sampleDef({ name: "index_constituents", dataset: "index_constituents" }))
    const all = await svc.listSchedules()
    expect(all.map((s) => s.name).sort()).toEqual(["equity_daily", "index_constituents"])
  })

  test("fireSchedule on active schedule triggers runNow and records occurrence", async () => {
    const svc = fresh()
    await svc.upsertSchedule(sampleDef())
    const result = await svc.fireSchedule("equity_daily", "2026-08-04")
    expect(result.skipped).toBe(false)
    if (result.skipped) return
    expect(result.run.run.status).toBe("completed")
    expect(result.run.run.trigger).toBe("scheduled")
    expect(result.occurrence.scheduleName).toBe("equity_daily")

    const occurrences = await svc.listOccurrences("equity_daily")
    expect(occurrences).toHaveLength(1)

    const def = await svc.getSchedule("equity_daily")
    expect(def?.fireCount).toBe(1)
    expect(def?.lastFireAt).toBe("2026-08-04T18:00:00.000Z")
  })

  test("fireSchedule on paused schedule is skipped", async () => {
    const svc = fresh()
    await svc.upsertSchedule(sampleDef({ paused: true }))
    const result = await svc.fireSchedule("equity_daily", "2026-08-04")
    expect(result.skipped).toBe(true)
    if (!result.skipped) return
    expect(result.reason).toBe("paused")

    // No occurrence recorded when skipped.
    const occurrences = await svc.listOccurrences("equity_daily")
    expect(occurrences).toEqual([])

    const def = await svc.getSchedule("equity_daily")
    expect(def?.fireCount).toBe(0)
  })

  test("fireSchedule on missing schedule is skipped", async () => {
    const svc = fresh()
    const result = await svc.fireSchedule("nope", "2026-08-04")
    expect(result.skipped).toBe(true)
    if (!result.skipped) return
    expect(result.reason).toBe("missing")
  })
})