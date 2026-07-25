/**
 * Scheduler — in-process cron driver for the orchestrator.
 *
 * One Scheduler owns N cron jobs. Each job fires orchestrator.tick()
 * with an optional tracker-name filter, so different trackers can run
 * on different cadences (e.g. factor-mining every 30s, free-exploration
 * once per trading day).
 *
 * Why not BullMQ / external cron / OS launchd:
 *   - BullMQ adds Valkey + a worker process; overkill for a single-host
 *     orchestrator with one writer.
 *   - External cron means another moving part + deployment config.
 *   - launchd/systemd work but make local dev harder.
 * In-process cron with the `cron` npm package is the lightest option
 * that still gives us 5-field cron syntax (the lingua franca).
 *
 * Lifecycle:
 *   const s = new Scheduler(orch)
 *   s.start([{ cron: "every-30-seconds", trackers: ["factor-mining"] }])
 *   ... time passes, ticks fire ...
 *   s.stop()   // halt all jobs (e.g. on SIGINT)
 *
 * Errors thrown by tick() are caught per-job and logged; one failing
 * schedule does not halt the others.
 */

import { CronJob } from "cron"
import type { Orchestrator } from "./orchestrator"

export interface ScheduleSpec {
  /**
   * 5-field cron expression (min hour dom mon dow).
   * Examples (6-field seconds form is also accepted by the cron package):
   *   every-30-seconds  — use a 6-field string
   *   "0 18 * * 1-5"     — 18:00 Mon–Fri
   *   "0 0 * * 0"        — midnight every Sunday
   */
  cron: string
  /** Tracker names to include in this tick; omit for all trackers. */
  trackers?: string[]
  /** Display name for logs + dashboard. Defaults to the cron string. */
  name?: string
}

export interface SchedulerLogger {
  info?(msg: string, extra?: unknown): void
  warn?(msg: string, extra?: unknown): void
  error?(msg: string, extra?: unknown): void
}

interface ManagedJob {
  spec: ScheduleSpec
  job: CronJob
  /** Increments on every fire, regardless of success/failure. */
  fireCount: number
  /** Increments when tick() throws. */
  errorCount: number
  /** Last error message, surfaced on the dashboard. */
  lastError?: string
  /** Last fire time (ISO8601). */
  lastFireAt?: string
}

export class Scheduler {
  private jobs: ManagedJob[] = []
  private running = false

  constructor(
    private readonly orch: Orchestrator,
    private readonly logger: SchedulerLogger = console,
  ) {}

  /**
   * Start all schedules. Idempotent: calling start() twice is a no-op
   * (the second call returns without re-adding jobs).
   *
   * Each spec becomes one CronJob that calls orch.tick({ trackerNames }).
   */
  start(schedules: ScheduleSpec[]): void {
    if (this.running) return
    for (const spec of schedules) {
      const managed: ManagedJob = {
        spec,
        job: new CronJob(
          spec.cron,
          () => this.fire(managed),
          // onComplete callback (fires after the task fn resolves)
          undefined,
          false, // doNotStart — we call job.start() explicitly below
        ),
        fireCount: 0,
        errorCount: 0,
      }
      managed.job.start()
      this.jobs.push(managed)
    }
    this.running = true
    this.logger.info?.(
      `scheduler started: ${this.jobs.length} schedule(s) — ${this.jobs.map((j) => j.spec.name ?? j.spec.cron).join(", ")}`,
    )
  }

  /** Halt every job. Safe to call multiple times. */
  stop(): void {
    if (!this.running) return
    for (const m of this.jobs) {
      try {
        m.job.stop()
      } catch {
        // best-effort shutdown
      }
    }
    this.jobs = []
    this.running = false
  }

  isRunning(): boolean {
    return this.running
  }

  /** Snapshot for dashboard / tests. */
  status(): Array<{ spec: ScheduleSpec; fireCount: number; errorCount: number; lastError?: string; lastFireAt?: string }> {
    return this.jobs.map((m) => ({
      spec: m.spec,
      fireCount: m.fireCount,
      errorCount: m.errorCount,
      lastError: m.lastError,
      lastFireAt: m.lastFireAt,
    }))
  }

  /**
   * Fire one tick. Public for tests that want to bypass the cron timer.
   */
  async fire(managed: ManagedJob): Promise<void> {
    managed.fireCount += 1
    managed.lastFireAt = new Date().toISOString()
    try {
      const result = await this.orch.tick({ trackerNames: managed.spec.trackers })
      if (result.ran > 0 || result.throttled > 0) {
        this.logger.info?.(
          `tick(${managed.spec.name ?? managed.spec.cron}): ran=${result.ran} throttled=${result.throttled}`,
        )
      }
    } catch (err) {
      managed.errorCount += 1
      managed.lastError = err instanceof Error ? err.message : String(err)
      // Log + continue — one bad tick must not kill the schedule.
      this.logger.error?.(`tick(${managed.spec.name ?? managed.spec.cron}) failed: ${managed.lastError}`)
    }
  }
}
