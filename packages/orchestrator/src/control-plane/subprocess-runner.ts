/**
 * SubprocessRunner — real DataPipelineRunner that invokes Python ETL/dbt.
 *
 * Implements the runner contract using Bun.spawn. For production, the
 * subprocess is `uv run python -m etl.runner` or `dbt run`. In tests
 * we swap in a FakeRunner.
 *
 * This file focuses on the subprocess boundary: argv construction,
 * structured JSON result parsing, and error handling. It does NOT
 * depend on a real Python environment in CI (that's for smoke tests).
 */

import { join } from "node:path"
import type { DataPipelineRunner, RunnerQualityCheck, RunnerRequest, RunnerResult, RunnerStageResult } from "./runner"

export interface SubprocessRunnerOptions {
  /** Full path to `uv` executable. */
  uvPath?: string
  /** Python workspace root (for uv run). */
  pythonWorkspace?: string
  /** dbt project directory. */
  dbtProjectDir?: string
  /** Dry-run mode: prints the command but doesn't execute. */
  dryRun?: boolean
}

interface ProcessResult {
  exitCode: number | null
  stdout: string
  stderr: string
}

/**
 * Execute a command via Bun.spawn, capturing stdout/stderr.
 */
async function spawnProcess(cmd: string[], env?: Record<string, string>): Promise<ProcessResult> {
  const proc = Bun.spawn(cmd, {
    stdout: "pipe",
    stderr: "pipe",
    env,
  })
  const stdout = await new Response(proc.stdout).text()
  const stderr = await new Response(proc.stderr).text()
  const exitCode = await proc.exited
  return { exitCode, stdout, stderr }
}

/**
 * Parse the structured result envelope from ETL stage.
 *
 * Expected JSON shape:
 *   {
 *     "status": "ok" | "quality_failed",
 *     "dataset": "...",
 *     "date": "...",
 *     "rows": <int>,
 *     "load": { ... },
 *     "issues": [ ... ]
 *   }
 */
function parseEtlResult(stdout: string): RunnerStageResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(stdout)
  } catch {
    return {
      stage: "etl",
      dataset: "",
      sessionDate: "",
      status: "failed",
      errorCode: "parse_error",
      errorMessage: "ETL output is not valid JSON",
    }
  }
  if (typeof parsed !== "object" || parsed === null) {
    return {
      stage: "etl",
      dataset: "",
      sessionDate: "",
      status: "failed",
      errorCode: "invalid_result",
      errorMessage: "ETL result is not a JSON object",
    }
  }
  const obj = parsed as Record<string, unknown>
  const status = obj.status
  if (status === "ok" && typeof obj.rows === "number") {
    return {
      stage: "etl",
      dataset: String(obj.dataset ?? ""),
      sessionDate: String(obj.date ?? ""),
      status: "ok",
      rowCount: obj.rows,
    }
  }
  if (status === "quality_failed") {
    const issues = Array.isArray(obj.issues) ? obj.issues : []
    const first = issues[0] as Record<string, unknown> | undefined
    return {
      stage: "etl",
      dataset: String(obj.dataset ?? ""),
      sessionDate: String(obj.date ?? ""),
      status: "failed",
      errorCode: "quality_failed",
      errorMessage: first?.message ? String(first.message) : "quality check failed",
    }
  }
  return {
    stage: "etl",
    dataset: "",
    sessionDate: "",
    status: "failed",
    errorCode: String(obj.error_code ?? "unknown"),
    errorMessage: String(obj.error_message ?? "ETL reported failure"),
  }
}

/**
 * Parse dbt test output (JSON log lines) into quality checks.
 *
 * dbt with `--log-format json` emits one JSON object per line. Test
 * results appear as `node_result` events with `status` pass/fail.
 * Each dbt test maps to a QualityCheck with dimension inferred from
 * the test name (not_null→completeness, unique→uniqueness, etc.).
 */
function parseDbtTestLog(stdout: string): RunnerQualityCheck[] {
  const checks: RunnerQualityCheck[] = []
  for (const line of stdout.split("\n")) {
    const trimmed = line.trim()
    if (!trimmed.startsWith("{")) continue
    let event: Record<string, unknown>
    try {
      event = JSON.parse(trimmed)
    } catch {
      continue
    }
    // Look for test result events
    const info = event.info as Record<string, unknown> | undefined
    if (!info || info.name !== "test") continue
    const nodeName = String(event.node_info?.name ?? event.data?.node_info?.name ?? "unknown")
    const status = String(info.status ?? "")
    const passed = status === "pass"
    checks.push({
      dimension: inferDimension(nodeName),
      check: nodeName,
      passed,
      blocking: true,
      message: passed ? undefined : String(info.message ?? `${nodeName} failed`),
    })
  }
  return checks
}

function inferDimension(testName: string): string {
  if (testName.includes("not_null")) return "completeness"
  if (testName.includes("unique")) return "uniqueness"
  if (testName.includes("freshness")) return "freshness"
  return "validity"
}

/**
 * Build the dbt stage result from run + test subprocess outputs.
 */
function buildDbtStage(
  runExitCode: number | null,
  testExitCode: number | null,
  testStdout: string,
  dataset: string,
  sessionDate: string,
): RunnerStageResult {
  if (runExitCode !== 0) {
    return {
      stage: "dbt",
      dataset,
      sessionDate,
      status: "failed",
      errorCode: "dbt_run_failed",
      errorMessage: `dbt run exited with code ${runExitCode}`,
    }
  }
  const qualityChecks = parseDbtTestLog(testStdout)
  const failed = qualityChecks.some((c) => !c.passed)
  return {
    stage: "dbt",
    dataset,
    sessionDate,
    status: failed ? "failed" : "ok",
    errorCode: failed ? "quality_failed" : undefined,
    errorMessage: failed
      ? `${qualityChecks.filter((c) => !c.passed).length} test(s) failed`
      : undefined,
    qualityChecks,
  }
}

export class SubprocessRunner implements DataPipelineRunner {
  private readonly uvPath: string
  private readonly pythonWorkspace: string
  private readonly dbtProjectDir: string
  private readonly dryRun: boolean

  constructor(opts: SubprocessRunnerOptions = {}) {
    this.uvPath = opts.uvPath ?? "uv"
    this.pythonWorkspace = opts.pythonWorkspace ?? "/Volumes/data/documents/codes/a-share-agents/python"
    this.dbtProjectDir = opts.dbtProjectDir ?? join(this.pythonWorkspace, "dbt")
    this.dryRun = opts.dryRun ?? false
  }

  async run(req: RunnerRequest): Promise<RunnerResult> {
    // ETL stage
    const etlCmd = [
      this.uvPath,
      "run",
      "-C",
      this.pythonWorkspace,
      "python",
      "-m",
      "etl.runner",
      "--domain",
      req.dataset,
      "--date",
      req.sessionDate.replace(/-/g, ""),
    ]
    if (this.dryRun) {
      console.log("[SubprocessRunner DRY-RUN] ETL:", etlCmd.join(" "))
    }
    const etlResult: ProcessResult = this.dryRun
      ? { exitCode: 0, stdout: JSON.stringify({ status: "ok", dataset: req.dataset, date: req.sessionDate, rows: 0 }), stderr: "" }
      : await spawnProcess(etlCmd, { WORKDIR: req.workdir })

    const etlStage = parseEtlResult(etlResult.stdout)
    if (etlStage.status === "failed") {
      etlStage.dataset = req.dataset
      etlStage.sessionDate = req.sessionDate
      return { dataset: req.dataset, sessionDate: req.sessionDate, stages: [etlStage] }
    }

    // dbt stage: real `dbt run` + `dbt test`
    const dbtBaseCmd = [
      this.uvPath,
      "run",
      "-C",
      this.pythonWorkspace,
      "dbt",
    ]
    const dbtRunCmd = [
      ...dbtBaseCmd,
      "run",
      "--project-dir",
      this.dbtProjectDir,
      "--profiles-dir",
      this.dbtProjectDir,
    ]
    const dbtTestCmd = [
      ...dbtBaseCmd,
      "test",
      "--project-dir",
      this.dbtProjectDir,
      "--profiles-dir",
      this.dbtProjectDir,
      "--log-format",
      "json",
    ]

    if (this.dryRun) {
      console.log("[SubprocessRunner DRY-RUN] dbt run:", dbtRunCmd.join(" "))
      console.log("[SubprocessRunner DRY-RUN] dbt test:", dbtTestCmd.join(" "))
    }

    let dbtRunResult: ProcessResult
    let dbtTestResult: ProcessResult
    if (this.dryRun) {
      dbtRunResult = { exitCode: 0, stdout: "", stderr: "" }
      dbtTestResult = { exitCode: 0, stdout: "", stderr: "" }
    } else {
      dbtRunResult = await spawnProcess(dbtRunCmd)
      dbtTestResult = dbtRunResult.exitCode === 0
        ? await spawnProcess(dbtTestCmd)
        : { exitCode: 1, stdout: "", stderr: "skipped (dbt run failed)" }
    }

    const dbtStage = buildDbtStage(
      dbtRunResult.exitCode,
      dbtTestResult.exitCode,
      dbtTestResult.stdout,
      req.dataset,
      req.sessionDate,
    )

    return {
      dataset: req.dataset,
      sessionDate: req.sessionDate,
      stages: [etlStage, dbtStage],
    }
  }
}