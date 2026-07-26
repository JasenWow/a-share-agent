/**
 * ControlPlaneScheduler — cron driver for the data-operations control plane.
 *
 * Distinct from the agent `Scheduler` (which drives `orch.tick` for Pi
 * agent work). This scheduler drives `service.fireSchedule(name, date)`
 * for data-pipeline schedules (per ADR 0003: data-pipeline scheduling
 * is separate from agent scheduling).
 *
 * Each registered schedule becomes one in-process CronJob. On fire, the
 * scheduler computes the target trading session (configurable via a
 * session resolver) and calls fireSchedule. Paused schedules are skipped
 * by the service itself, so the scheduler does not need to re-read
 * pause state.
 */

import { CronJob } from "cron"
import type { ControlPlaneService } from "./control-plane-service"
import type { ScheduleDefinition } from "./control-plane-store"

export interface SessionResolver {
  /**
   * Resolve the target trading session (YYYY-MM-DD) for a schedule fire
   * at the given instant. Typically "most recent completed trading
   * session" relative to `now`.
   */
  resolve(now: Date): string
}

export interface ControlPlaneSchedulerOptions {
  service: ControlPlaneService
  /** Resolves the target session for each fire. */
  sessionResolver: SessionResolver
  /** Clock for deterministic tests. */
  now?: () => Date
  logger?: {
    info?(msg: string, extra?: unknown): void
    warn?(msg: string, extra?: unknown): void
    error?(msg: string, extra?: unknown): void
  }
}

interface ManagedJob {
  name: string
  cron: string
  job: CronJob
  fireCount: number
  errorCount: number
  lastError?: string
  lastFireAt?: string
  lastSkipped?: boolean
}

export class ControlPlaneScheduler {
  private readonly service: ControlPlaneService
  private readonly sessionResolver: SessionResolver
  private readonly now: () => Date
  private readonly logger: NonNullable<ControlPlaneSchedulerOptions["logger"]>
  private jobs = new Map<string, ManagedJob>()
  private running = false

  constructor(opts: ControlPlaneSchedulerOptions) {
    this.service = opts.service
    this.sessionResolver = opts.sessionResolver
    this.now = opts.now ?? (() => new Date())
    this.logger = opts.logger ?? console
  }

  /**
   * Register all schedules currently in the store. Idempotent: calling
   * twice is safe; existing jobs are stopped before re-adding.
   */
  async start(): Promise<void> {
    if (this.running) return
    const defs = await this.service.listSchedules()
    for (const def of defs) {
      this.addJob(def)
    }
    this.running = true
    this.logger.info?.(`control-plane scheduler started: ${this.jobs.size} schedule(s)`)
  }

  /** Register a single schedule (used after start() for new definitions). */
  addJob(def: ScheduleDefinition): void {
    if (this.jobs.has(def.name)) {
      this.removeJob(def.name)
    }
    const managed: ManagedJob = {
      name: def.name,
      cron: def.cron,
      job: new CronJob(def.cron, () => this.fire(def.name), undefined, false),
      fireCount: 0,
      errorCount: 0,
    }
    managed.job.start()
    this.jobs.set(def.name, managed)
  }

  removeJob(name: string): void {
    const m = this.jobs.get(name)
    if (!m) return
    try {
      m.job.stop()
    } catch {
      // best-effort
    }
    this.jobs.delete(name)
  }

  stop(): void {
    if (!this.running) return
    for (const m of this.jobs.values()) {
      try {
        m.job.stop()
      } catch {
        // best-effort
      }
    }
    this.jobs.clear()
    this.running = false
  }

  isRunning(): boolean {
    return this.running
  }

  status(): Array<{
    name: string
    cron: string
    fireCount: number
    errorCount: number
    lastError?: string
    lastFireAt?: string
    lastSkipped?: boolean
  }> {
    return [...this.jobs.values()].map((m) => ({
      name: m.name,
      cron: m.cron,
      fireCount: m.fireCount,
      errorCount: m.errorCount,
      lastError: m.lastError,
      lastFireAt: m.lastFireAt,
      lastSkipped: m.lastSkipped,
    }))
  }

  /**
   * Fire one schedule by name. Public so tests can drive it without the
   * cron timer.
   */
  async fire(name: string): Promise<void> {
    const managed = this.jobs.get(name)
    if (!managed) {
      this.logger.warn?.(`fire: unknown schedule ${name}`)
      return
    }
    managed.fireCount += 1
    const nowIso = this.now().toISOString()
    managed.lastFireAt = nowIso
    try {
      const sessionDate = this.sessionResolver.resolve(this.now())
      const result = await this.service.fireSchedule(name, sessionDate)
      managed.lastSkipped = result.skipped
      if (result.skipped) {
        this.logger.info?.(`fire(${name}): skipped (${result.reason})`)
      } else {
        this.logger.info?.(
          `fire(${name}): run=${result.run.run.id} status=${result.run.run.status}`,
        )
      }
    } catch (err) {
      managed.errorCount += 1
      managed.lastError = err instanceof Error ? err.message : String(err)
      this.logger.error?.(`fire(${name}) failed: ${managed.lastError}`)
    }
  }
}