/**
 * schedule-evaluator tests — red/green TDD step 1.
 *
 * Pure-function tests; no I/O. We inject a StaticTradingCalendar so
 * the calendar is deterministic and the evaluator has no real-world
 * coupling to exchange_calendars in CI.
 */

import { describe, expect, test } from "bun:test"
import { StaticTradingCalendar } from "./trading-calendar"
import { validateSessionDate } from "./schedule-evaluator"

const calendar = new StaticTradingCalendar("XSHG", [
  "2026-08-03", // Monday — trading day
  "2026-08-04", // Tuesday — trading day
  "2026-08-05", // Wednesday — trading day
])

const NOW = new Date("2026-08-05T10:00:00Z")

describe("validateSessionDate", () => {
  test("accepts a recent trading day", () => {
    const r = validateSessionDate("equity_daily", "2026-08-04", {
      calendar,
      now: NOW,
    })
    expect(r.ok).toBe(true)
    expect(r.sessionDate).toBe("2026-08-04")
    expect(r.exchange).toBe("XSHG")
  })

  test("rejects an invalid format", () => {
    const r = validateSessionDate("equity_daily", "20260804", {
      calendar,
      now: NOW,
    })
    expect(r.ok).toBe(false)
    expect(r.reason).toBe("invalid_format")
  })

  test("rejects a non-trading day", () => {
    const r = validateSessionDate("equity_daily", "2026-08-02", {
      calendar,
      now: NOW,
    })
    expect(r.ok).toBe(false)
    expect(r.reason).toBe("not_trading_day")
  })

  test("rejects a future session", () => {
    const r = validateSessionDate("equity_daily", "2026-08-05", {
      calendar,
      now: new Date("2026-08-04T10:00:00Z"),
    })
    expect(r.ok).toBe(false)
    expect(r.reason).toBe("future_session")
  })

  test("rejects outside lookback", () => {
    const r = validateSessionDate("equity_daily", "2026-07-01", {
      calendar,
      now: NOW,
      maxLookbackDays: 7,
    })
    expect(r.ok).toBe(false)
    expect(r.reason).toBe("outside_lookback")
  })
})