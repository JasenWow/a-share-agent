/**
 * Policy types for orchestrator hardening.
 *
 * Borrowed from pi-dispatch's "non-negotiables" philosophy
 * (https://github.com/edgehero/pi-dispatch/blob/main/specs/constitution.md):
 * the agent is treated as an untrusted component. These policies bound
 * what it can do before it ever makes a provider call.
 *
 * See docs/superpowers/specs/2026-07-25-orchestrator-hardening-design.md
 * for the design rationale (especially: why spend is measured in
 * job-count, not tokens).
 */

/**
 * Budget cap on how many jobs may run per period.
 *
 * Modeled on pi-dispatch: counts container/process starts, not tokens,
 * because job-count is discrete, observable across providers, and
 * directly expresses the "never pay twice for the same answer" goal.
 *
 * `null` means unlimited for that period.
 */
export interface BudgetPolicy {
  /** Max jobs per day. null = unlimited. */
  dailyCap: number | null
  /** Max jobs per 7-day rolling window. null = unlimited. */
  weeklyCap: number | null
  /** Max jobs per calendar month. null = unlimited. */
  monthlyCap: number | null
}

/**
 * Concurrency limit on simultaneous agent runs.
 *
 * Default 1 — agents run serially unless explicitly tuned higher.
 */
export interface ConcurrencyPolicy {
  /** Max simultaneous runs. */
  maxConcurrent: number
}

/**
 * Retry policy for failed runs.
 *
 * Mirrors pi-dispatch: only infrastructure failures retry. An agent
 * that concludes it cannot fix the issue counts as success and must
 * not be retried (otherwise we'd pay twice for the same answer).
 */
export interface RetryPolicy {
  /** Max attempts per WorkItem before giving up. */
  maxAttempts: number
  /** Base ms for exponential backoff (1×, 2×, 4×, ...). */
  backoffMs: number
}

/** Aggregate policy bundle handed to the orchestrator. */
export interface PolicyBundle {
  budget: BudgetPolicy
  concurrency: ConcurrencyPolicy
  retry: RetryPolicy
}

/**
 * Default policy — conservative caps suitable for an unattended
 * single-developer deployment. Override per-environment in production.
 */
export const DEFAULT_POLICY: PolicyBundle = {
  budget: { dailyCap: 50, weeklyCap: 200, monthlyCap: 800 },
  concurrency: { maxConcurrent: 1 },
  retry: { maxAttempts: 3, backoffMs: 1000 },
}

/** Policy that disables all caps — for tests only. */
export const UNLIMITED_POLICY: PolicyBundle = {
  budget: { dailyCap: null, weeklyCap: null, monthlyCap: null },
  concurrency: { maxConcurrent: 1 },
  retry: { maxAttempts: 1, backoffMs: 0 },
}
