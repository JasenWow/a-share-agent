/**
 * BackfillAdmissionPolicy — gate a backfill before it starts.
 *
 * Per ADR 0028, a backfill must pass an admission check that protects
 * the daily schedule window. The policy returns a deterministic admit/
 * reject decision + reason. The control plane does not run a single
 * child PipelineRun until admission passes.
 *
 * Per ADR 0029, the scope (session count) is also bounded at 20.
 */

export interface BackfillAdmissionContext {
  /** Number of trading sessions in the backfill scope. */
  sessionCount: number
  /** The latest session in the scope (YYYY-MM-DD). */
  endSession: string
  /** Current wall-clock time for the protected-window calculation. */
  now: Date
}

export interface BackfillAdmissionResult {
  admitted: boolean
  reason: string
}

export interface BackfillAdmissionPolicy {
  admit(ctx: BackfillAdmissionContext): BackfillAdmissionResult
}

export const BACKFILL_MAX_SESSIONS = 20

/**
 * DefaultAdmissionPolicy — the v1 deterministic gate.
 *
 * Rules (in order):
 *   1. sessionCount > 20  → reject (ADR 0029 scope limit)
 *   2. endSession within the protected window → reject
 *      (the protected window is the most recent N calendar days; the
 *       daily schedule owns those sessions, ADR 0028)
 *
 * The protected window is computed in calendar days (not trading days)
 * so it stays deterministic without a calendar dependency. A future
 * policy can use trading-day distance once the XSHG calendar is wired.
 */
export class DefaultBackfillAdmissionPolicy implements BackfillAdmissionPolicy {
  /** How many calendar days before `now` are "protected". */
  static readonly PROTECTED_WINDOW_DAYS = 2

  admit(ctx: BackfillAdmissionContext): BackfillAdmissionResult {
    if (ctx.sessionCount > BACKFILL_MAX_SESSIONS) {
      return {
        admitted: false,
        reason: `scope exceeds limit: ${ctx.sessionCount} sessions > ${BACKFILL_MAX_SESSIONS}`,
      }
    }

    const cutoff = new Date(ctx.now)
    cutoff.setUTCDate(cutoff.getUTCDate() - DefaultBackfillAdmissionPolicy.PROTECTED_WINDOW_DAYS)
    const cutoffStr = cutoff.toISOString().slice(0, 10)

    if (ctx.endSession >= cutoffStr) {
      return {
        admitted: false,
        reason: `end session ${ctx.endSession} is inside protected window (cutoff ${cutoffStr})`,
      }
    }

    return { admitted: true, reason: "admitted" }
  }
}