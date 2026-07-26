/**
 * control-plane-store tests — red/green TDD step 3.
 *
 * Each test uses a fresh temporary DuckDB file so the suite has no
 * cross-test state. The store is a system boundary: real DuckDB.
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import {
  ControlPlaneStore,
  type PipelineRun,
  type PipelineRunStage,
  type QualityCheckResult,
  type ScheduleDefinition,
  type ScheduleOccurrence,
  type BackfillRequest,
} from "./control-plane-store"

let store: ControlPlaneStore | null = null
let tmpDir: string | null = null

function freshStore(): ControlPlaneStore {
  if (tmpDir) {
    rmSync(tmpDir, { recursive: true, force: true })
  }
  tmpDir = mkdtempSync(join(tmpdir(), "cps-"))
  store = new ControlPlaneStore({ path: join(tmpDir, "control.db") })
  return store
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

function sampleRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
  return {
    id: "run-1",
    dataset: "equity_daily",
    sessionDate: "2026-08-04",
    trigger: "manual",
    status: "queued",
    attempt: 1,
    createdAt: "2026-08-04T10:00:00Z",
    ...overrides,
  }
}

describe("ControlPlaneStore — pipeline_runs", () => {
  test("insert and read", async () => {
    const s = freshStore()
    await s.insertPipelineRun(sampleRun())
    const got = await s.getPipelineRun("run-1")
    expect(got).not.toBeNull()
    expect(got?.dataset).toBe("equity_daily")
    expect(got?.status).toBe("queued")
    expect(got?.sessionDate).toBe("2026-08-04")
  })

  test("update status preserves other fields", async () => {
    const s = freshStore()
    await s.insertPipelineRun(sampleRun())
    await s.updatePipelineRunStatus("run-1", "running", { startedAt: "2026-08-04T10:01:00Z" })
    await s.updatePipelineRunStatus("run-1", "completed", { finishedAt: "2026-08-04T10:02:00Z" })
    const got = await s.getPipelineRun("run-1")
    expect(got?.status).toBe("completed")
    expect(got?.startedAt).toBe("2026-08-04T10:01:00Z")
    expect(got?.finishedAt).toBe("2026-08-04T10:02:00Z")
  })

  test("list by dataset", async () => {
    const s = freshStore()
    await s.insertPipelineRun(sampleRun({ id: "run-1" }))
    await s.insertPipelineRun(sampleRun({ id: "run-2", sessionDate: "2026-08-05" }))
    await s.insertPipelineRun(
      sampleRun({ id: "run-3", dataset: "other_dataset", sessionDate: "2026-08-04" }),
    )
    const runs = await s.listPipelineRuns("equity_daily")
    expect(runs).toHaveLength(2)
    expect(runs.map((r) => r.id).sort()).toEqual(["run-1", "run-2"])
  })
})

describe("ControlPlaneStore — pipeline_run_stages", () => {
  test("insert and list stages for a run", async () => {
    const s = freshStore()
    const stage: PipelineRunStage = {
      runId: "run-1",
      stage: "etl",
      status: "ok",
      rowCount: 4231,
      artifactPath: "/tmp/ods/dt=2026-08-04/file.parquet",
      startedAt: "2026-08-04T10:00:00Z",
      finishedAt: "2026-08-04T10:01:00Z",
    }
    await s.insertPipelineRunStage(stage)
    const got = await s.listPipelineRunStages("run-1")
    expect(got).toHaveLength(1)
    expect(got[0]?.stage).toBe("etl")
    expect(got[0]?.rowCount).toBe(4231)
  })
})

describe("ControlPlaneStore — quality_check_results", () => {
  test("insert and list by runId, dataset, session", async () => {
    const s = freshStore()
    const result: QualityCheckResult = {
      runId: "run-1",
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      stage: "etl",
      dimension: "completeness",
      check: "min_row_count",
      passed: true,
      blocking: true,
      observed: 4231,
      threshold: 4000,
      message: "OK",
      recordedAt: "2026-08-04T10:01:30Z",
    }
    await s.insertQualityCheckResult(result)
    const got = await s.listQualityCheckResults({ runId: "run-1" })
    expect(got).toHaveLength(1)
    expect(got[0]?.dimension).toBe("completeness")
    expect(got[0]?.passed).toBe(true)
  })
})

describe("ControlPlaneStore — schedule_definitions (PR2)", () => {
  test("upsert + get round-trip", async () => {
    const s = freshStore()
    const def: ScheduleDefinition = {
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    }
    await s.upsertScheduleDefinition(def)
    const got = await s.getScheduleDefinition("equity_daily")
    expect(got?.name).toBe("equity_daily")
    expect(got?.cron).toBe("0 18 * * 1-5")
    expect(got?.paused).toBe(false)
  })

  test("upsert is idempotent and preserves fire_count on partial update", async () => {
    const s = freshStore()
    const def: ScheduleDefinition = {
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    }
    await s.upsertScheduleDefinition(def)
    // Simulate a fire: bump fire_count via the dedicated method.
    await s.updateScheduleFireCount("equity_daily", "2026-08-04T18:00:00Z")
    // Re-upsert (e.g. to pause) without passing fireCount — should be preserved.
    await s.upsertScheduleDefinition({
      ...def,
      paused: true,
      fireCount: 0,
      lastFireAt: undefined,
    })
    const got = await s.getScheduleDefinition("equity_daily")
    expect(got?.paused).toBe(true)
    expect(got?.fireCount).toBe(1)
    expect(got?.lastFireAt).toBe("2026-08-04T18:00:00Z")
  })

  test("list returns all definitions", async () => {
    const s = freshStore()
    await s.upsertScheduleDefinition({
      name: "equity_daily",
      dataset: "equity_daily",
      trigger: "scheduled",
      cron: "0 18 * * 1-5",
      paused: false,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    })
    await s.upsertScheduleDefinition({
      name: "index_constituents",
      dataset: "index_constituents",
      trigger: "scheduled",
      cron: "0 19 * * 1-5",
      paused: true,
      fireCount: 0,
      createdAt: "2026-08-04T00:00:00Z",
      updatedAt: "2026-08-04T00:00:00Z",
    })
    const all = await s.listScheduleDefinitions()
    expect(all.map((d) => d.name).sort()).toEqual(["equity_daily", "index_constituents"])
  })

  test("getScheduleDefinition returns null for missing name", async () => {
    const s = freshStore()
    const got = await s.getScheduleDefinition("nope")
    expect(got).toBeNull()
  })
})

describe("ControlPlaneStore — schedule_occurrences (PR2)", () => {
  test("insert and list by schedule name", async () => {
    const s = freshStore()
    const occ: ScheduleOccurrence = {
      id: "occ-1",
      scheduleName: "equity_daily",
      sessionDate: "2026-08-04",
      status: "queued",
      attempt: 1,
      createdAt: "2026-08-04T18:00:00Z",
    }
    await s.insertScheduleOccurrence(occ)
    const got = await s.listScheduleOccurrences("equity_daily")
    expect(got).toHaveLength(1)
    expect(got[0]?.sessionDate).toBe("2026-08-04")
    expect(got[0]?.status).toBe("queued")
  })

  test("list returns empty for schedule with no occurrences", async () => {
    const s = freshStore()
    const got = await s.listScheduleOccurrences("nothing")
    expect(got).toEqual([])
  })
})

describe("ControlPlaneStore — backfill_requests (PR3)", () => {
  test("insert + get round-trip", async () => {
    const s = freshStore()
    const req: BackfillRequest = {
      id: "bf-1",
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-24",
      sessionCount: 5,
      status: "queued",
      createdAt: "2026-08-04T10:00:00Z",
    }
    await s.insertBackfillRequest(req)
    const got = await s.getBackfillRequest("bf-1")
    expect(got?.startSession).toBe("2026-07-20")
    expect(got?.sessionCount).toBe(5)
    expect(got?.status).toBe("queued")
  })

  test("update status + timestamps", async () => {
    const s = freshStore()
    await s.insertBackfillRequest({
      id: "bf-1",
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-24",
      sessionCount: 5,
      status: "queued",
      createdAt: "2026-08-04T10:00:00Z",
    })
    await s.updateBackfillStatus("bf-1", "completed", {
      startedAt: "2026-08-04T10:01:00Z",
      finishedAt: "2026-08-04T10:05:00Z",
    })
    const got = await s.getBackfillRequest("bf-1")
    expect(got?.status).toBe("completed")
    expect(got?.startedAt).toBe("2026-08-04T10:01:00Z")
    expect(got?.finishedAt).toBe("2026-08-04T10:05:00Z")
  })

  test("list by dataset", async () => {
    const s = freshStore()
    await s.insertBackfillRequest({
      id: "bf-1",
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-24",
      sessionCount: 5,
      status: "completed",
      createdAt: "2026-08-04T10:00:00Z",
    })
    await s.insertBackfillRequest({
      id: "bf-2",
      dataset: "other",
      startSession: "2026-07-20",
      endSession: "2026-07-20",
      sessionCount: 1,
      status: "failed",
      createdAt: "2026-08-04T11:00:00Z",
    })
    const got = await s.listBackfillRequests("equity_daily")
    expect(got).toHaveLength(1)
    expect(got[0]?.id).toBe("bf-1")
  })

  test("linkRunToBackfill + listBackfillChildRuns", async () => {
    const s = freshStore()
    // Parent request
    await s.insertBackfillRequest({
      id: "bf-1",
      dataset: "equity_daily",
      startSession: "2026-07-20",
      endSession: "2026-07-21",
      sessionCount: 2,
      status: "running",
      createdAt: "2026-08-04T10:00:00Z",
    })
    // Two child runs
    await s.insertPipelineRun({ ...sampleRun({ id: "run-a", sessionDate: "2026-07-20", trigger: "backfill" }) })
    await s.insertPipelineRun({ ...sampleRun({ id: "run-b", sessionDate: "2026-07-21", trigger: "backfill" }) })
    // Unlinked run should not appear
    await s.insertPipelineRun({ ...sampleRun({ id: "run-c", sessionDate: "2026-08-04" }) })

    await s.linkRunToBackfill("run-a", "bf-1")
    await s.linkRunToBackfill("run-b", "bf-1")

    const children = await s.listBackfillChildRuns("bf-1")
    expect(children).toHaveLength(2)
    expect(children.map((r) => r.sessionDate).sort()).toEqual(["2026-07-20", "2026-07-21"])
  })

  test("getBackfillRequest returns null for missing", async () => {
    const s = freshStore()
    expect(await s.getBackfillRequest("nope")).toBeNull()
  })
})