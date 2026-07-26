/**
 * fake-runner tests — red/green TDD step 2.
 */

import { describe, expect, test } from "bun:test"
import { FakeRunner } from "./fake-runner"

describe("FakeRunner", () => {
  test("returns two ok stages by default", async () => {
    const fake = new FakeRunner()
    const result = await fake.run({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      workdir: "/tmp/test",
    })
    expect(result.stages).toHaveLength(2)
    expect(result.stages[0]?.stage).toBe("etl")
    expect(result.stages[0]?.status).toBe("ok")
    expect(result.stages[1]?.stage).toBe("dbt")
    expect(result.stages[1]?.status).toBe("ok")
  })

  test("uses scripted row counts", async () => {
    const fake = new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4231 },
      { stage: "dbt", status: "ok" },
    ])
    const result = await fake.run({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      workdir: "/tmp/test",
    })
    expect(result.stages[0]?.rowCount).toBe(4231)
  })

  test("stops on a failed scripted stage", async () => {
    const fake = new FakeRunner([
      { stage: "etl", status: "ok", rowCount: 4001 },
      {
        stage: "dbt",
        status: "failed",
        errorCode: "quality_failed",
        errorMessage: "OHLC invariant violated",
      },
    ])
    const result = await fake.run({
      dataset: "equity_daily",
      sessionDate: "2026-08-04",
      workdir: "/tmp/test",
    })
    expect(result.stages).toHaveLength(2)
    expect(result.stages[1]?.status).toBe("failed")
    expect(result.stages[1]?.errorCode).toBe("quality_failed")
  })

  test("rejects out-of-order script", () => {
    const fake = new FakeRunner([{ stage: "dbt", status: "ok" }])
    expect(
      fake.run({
        dataset: "equity_daily",
        sessionDate: "2026-08-04",
        workdir: "/tmp/test",
      }),
    ).rejects.toThrow(/script out of order/)
  })
})