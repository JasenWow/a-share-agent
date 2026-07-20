/** ID generation helpers for WorkItems, runs, sessions. */

/**
 * Build a WorkItem id from a prefix and a date. Stable across reruns
 * on the same day so trackers can dedupe.
 *
 * Example: workId("factor-mine", "2026-07-20") -> "factor-mine-2026-07-20"
 */
export function workId(prefix: string, date: string): string {
  return `${prefix}-${date}`
}

/** Generate a short random session id (8 hex chars). */
export function sessionId(): string {
  return Math.random().toString(16).slice(2, 10)
}
