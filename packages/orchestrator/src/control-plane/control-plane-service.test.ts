/**
 * control-plane-service tests — red/green TDD step 4.
 */

import { describe, expect, test, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { ControlPlaneStore } from "./control-plane-store"
import { ControlPlaneService } from "./control-plane-service"
import { FakeRunner } from "./fake-runner"

let store: ControlPlaneStore | null = null
let tmpDir: string | null = null

function freshStore(): ControlPlaneStore {
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true })
  tmpDir = mkdtempSync(join(tmpdir(), "cps-svc-"))
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

describe("ControlPlaneService.runNow", () => {
  test("happy path: queued → running → completed", async () => {
    const s = freshStore()
    const runner = new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4231 },
      { stage: "dbt", status: "ok" },
    ])
    const svc = new ControlPlaneService({
      store: s,
      runner,
      idGenerator: () => "run-happy",
      clock: () => new Date("2026-08-04T10:00:00Z"),
    })

    const { run } = await svc.runNow({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
    })

    expect(run.status).toBe("completed")
    expect(run.startedAt).toBe("2026-08-04T10:00:00.000Z")
    expect(run.finishedAt).toBe("2026-08-04T10:00:00.000Z")
    expect(run.errorCode).toBeUndefined()

    const stages = await svc.listStages("run-happy")
    expect(stages).toHaveLength(2)
    expect(stages.map((st) => st.stage)).toEqual(["etl", "dbt"])

    const checks = await svc.listQualityChecks({ runId: "run-happy" })
    expect(checks).toHaveLength(1)
    expect(checks[0]?.check).toBe("min_row_count")
    expect(checks[0]?.passed).toBe(true)
    expect(checks[0]?.observed).toBe(4231)
    expect(checks[0]?.blocking).toBe(true)
  })

  test("dbt failed → quality_failed", async () => {
    const s = freshStore()
    const runner = new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4001 },
      {
        stage: "dbt",
        status: "failed",
        errorCode: "ohlc_invariant",
        errorMessage: "close > high on 3 rows",
      },
    ])
    const svc = new ControlPlaneService({
      store: s,
      runner,
      idGenerator: () => "run-qf",
    })

    const { run } = await svc.runNow({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
    })

    expect(run.status).toBe("quality_failed")
    expect(run.errorCode).toBe("ohlc_invariant")
    expect(run.errorMessage).toBe("close > high on 3 rows")

    const checks = await svc.listQualityChecks({ runId: "run-qf" })
    expect(checks.some((c) => c.dimension === "validity" && !c.passed)).toBe(true)
  })

  test("etl failed → failed (not quality_failed)", async () => {
    const s = freshStore()
    const runner = new FakeRunner([
      {
        stage: "etl",
        status: "failed",
        errorCode: "extract_failed",
        errorMessage: "Tushare returned 401",
      },
    ])
    const svc = new ControlPlaneService({
      store: s,
      runner,
      idGenerator: () => "run-etl-fail",
    })

    const { run } = await svc.runNow({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
    })

    expect(run.status).toBe("failed")
    expect(run.errorCode).toBe("extract_failed")
  })

  test("below row floor → etl ok but check fails", async () => {
    const s = freshStore()
    const runner = new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 1234 },
      { stage: "dbt", status: "ok" },
    ])
    const svc = new ControlPlaneService({
      store: s,
      runner,
      idGenerator: () => "run-low",
    })

    await svc.runNow({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
    })

    const checks = await svc.listQualityChecks({ runId: "run-low" })
    expect(checks[0]?.passed).toBe(false)
    expect(checks[0]?.observed).toBe(1234)
  })

  test("runner throws → run marked failed", async () => {
    const s = freshStore()
    const runner: import("./runner").DataPipelineRunner = {
      run: async () => {
        throw new Error("subprocess crashed")
      },
    }
    const svc = new ControlPlaneService({
      store: s,
      runner,
      idGenerator: () => "run-throw",
    })

    const { run } = await svc.runNow({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
    })

    expect(run.status).toBe("failed")
    expect(run.errorCode).toBe("runner_error")
    expect(run.errorMessage).toBe("subprocess crashed")
  })
})