/**
 * ScheduleEvaluator — validate a session_date for a dataset.
 *
 * A session_date is the trading day whose data we want to capture.
 * For v1 the only monitored dataset is `equity_daily`, which uses the
 * Shanghai Stock Exchange (XSHG) trading calendar. A valid run-now
 * request must target a real trading session.
 *
 * Validation rules (per ADR 0004, ADR 0006):
 *   - date format: YYYY-MM-DD
 *   - date must be a trading session in XSHG
 *   - date must not be in the future (we cannot run a session that has
 *     not happened yet — the crawler cannot produce data for it)
 *   - date must not be too far in the past (data sources may drop
 *     retention; configurable via maxLookbackDays)
 *
 * The evaluator is a pure function — no I/O, no clock. Tests inject
 * `now` and a trading-calendar implementation so the function is
 * deterministic and cheap to call.
 */

import type { TradingCalendar } from "./trading-calendar"

/** Maximum lookback window — older sessions cannot be processed. */
export const DEFAULT_MAX_LOOKBACK_DAYS = 30

export interface ScheduleEvaluatorOptions {
  /** Implementation of the trading calendar (XSHG in v1). */
  calendar: TradingCalendar
  /** "Now" reference time. Pass a Date for deterministic tests. */
  now: Date
  /** Maximum days between now and the session_date. */
  maxLookbackDays?: number
  /** Calendar exchange identifier; surfaced for diagnostics. */
  exchange?: string
}

export interface SessionValidation {
  ok: boolean
  reason?:
    | "invalid_format"
    | "not_trading_day"
    | "future_session"
    | "outside_lookback"
  /** Echoed on success for downstream logging. */
  sessionDate?: string
  exchange?: string
}

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Validate a session_date for a given dataset.
 *
 * @param datasetName    Dataset the request targets (e.g. "equity_daily").
 * @param sessionDate    Trading session, YYYY-MM-DD.
 * @param opts           Calendar + clock + lookback configuration.
 */
export function validateSessionDate(
  datasetName: string,
  sessionDate: string,
  opts: ScheduleEvaluatorOptions,
): SessionValidation {
  if (!ISO_DATE_RE.test(sessionDate)) {
    return { ok: false, reason: "invalid_format" }
  }

  const exchange = opts.exchange ?? "XSHG"

  // Lookback check runs before trading-day check: a date outside the
  // lookback window should be rejected as "outside_lookback" regardless
  // of whether it happens to be a trading day, so callers see the most
  // actionable reason.
  const sessionMs = Date.parse(`${sessionDate}T00:00:00Z`)
  const nowMs = opts.now.getTime()
  const dayMs = 24 * 60 * 60 * 1000

  const lookback = opts.maxLookbackDays ?? DEFAULT_MAX_LOOKBACK_DAYS
  const daysAgo = Math.floor((nowMs - sessionMs) / dayMs)
  if (daysAgo > lookback) {
    return { ok: false, reason: "outside_lookback", sessionDate, exchange }
  }

  if (sessionMs > nowMs) {
    return { ok: false, reason: "future_session", sessionDate, exchange }
  }

  const isTrading = opts.calendar.isTradingSession(sessionDate)
  if (!isTrading) {
    return { ok: false, reason: "not_trading_day", sessionDate, exchange }
  }

  // Suppress unused-param warning — datasetName is part of the public
  // contract for future multi-dataset support.
  void datasetName

  return { ok: true, sessionDate, exchange }
}