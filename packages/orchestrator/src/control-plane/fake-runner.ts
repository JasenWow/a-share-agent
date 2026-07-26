/**
 * FakeRunner — preset stage results for tests.
 *
 * Tests provide a script of results, one per stage. The fake walks
 * the script in order; if the request asks for more stages than
 * the script defines, the fake returns a default success. If a
 * scripted stage has status "failed", the fake stops the pipeline
 * and surfaces the error.
 */

import type {
  DataPipelineRunner,
  RunnerRequest,
  RunnerResult,
  RunnerStageResult,
} from "./runner"

export interface FakeRunnerScriptEntry {
  stage: "etl" | "dbt"
  status: "ok" | "failed"
  rowCount?: number
  artifactPath?: string
  errorCode?: string
  errorMessage?: string
  qualityChecks?: import("./runner").RunnerQualityCheck[]
}

export class FakeRunner implements DataPipelineRunner {
  private readonly script: FakeRunnerScriptEntry[]

  constructor(script: FakeRunnerScriptEntry[] = []) {
    // Copy so callers can mutate their own array safely.
    this.script = script.map((e) => ({ ...e }))
  }

  async run(req: RunnerRequest): Promise<RunnerResult> {
    const stages: RunnerStageResult[] = []
    const order: Array<"etl" | "dbt"> = ["etl", "dbt"]
    for (const stage of order) {
      const scripted = this.script.shift()
      if (scripted && scripted.stage !== stage) {
        throw new Error(
          `FakeRunner: script out of order — expected '${stage}' next, got '${scripted.stage}'`,
        )
      }
      if (scripted && scripted.status === "failed") {
        stages.push({
          stage,
          dataset: req.dataset,
          sessionDate: req.sessionDate,
          status: "failed",
          errorCode: scripted.errorCode,
          errorMessage: scripted.errorMessage,
        })
        return { dataset: req.dataset, sessionDate: req.sessionDate, stages }
      }
      stages.push({
        stage,
        dataset: req.dataset,
        sessionDate: req.sessionDate,
        status: "ok",
        rowCount: scripted?.rowCount,
        artifactPath: scripted?.artifactPath,
        qualityChecks: scripted?.qualityChecks,
      })
    }
    return { dataset: req.dataset, sessionDate: req.sessionDate, stages }
  }
}