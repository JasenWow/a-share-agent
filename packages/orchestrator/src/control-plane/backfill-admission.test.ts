/**
 * backfill-admission tests — red/green TDD PR3 (Step 3).
 */

import { describe, expect, test } from "bun:test"
import {
  BACKFILL_MAX_SESSIONS,
  DefaultBackfillAdmissionPolicy,
} from "./backfill-admission"

const policy = new DefaultBackfillAdmissionPolicy()
const NOW = new Date("2026-08-05T10:00:00Z")

describe("DefaultBackfillAdmissionPolicy", () => {
  test("admits a small, historical backfill", () => {
    const r = policy.admit({
      sessionCount: 5,
      endSession: "2026-07-24",
      now: NOW,
    })
    expect(r.admitted).toBe(true)
  })

  test("rejects when scope exceeds 20 sessions", () => {
    const r = policy.admit({
      sessionCount: 21,
      endSession: "2026-07-01",
      now: NOW,
    })
    expect(r.admitted).toBe(false)
    expect(r.reason).toContain("exceeds limit")
    expect(r.reason).toContain("21")
  })

  test("admits exactly 20 sessions (boundary)", () => {
    const r = policy.admit({
      sessionCount: BACKFILL_MAX_SESSIONS,
      endSession: "2026-07-01",
      now: NOW,
    })
    expect(r.admitted).toBe(true)
  })

  test("rejects when end session is inside protected window", () => {
    // NOW = 2026-08-05; protected window = 2 days → cutoff 2026-08-03
    const r = policy.admit({
      sessionCount: 1,
      endSession: "2026-08-04",
      now: NOW,
    })
    expect(r.admitted).toBe(false)
    expect(r.reason).toContain("protected window")
  })

  test("rejects when end session equals the cutoff boundary", () => {
    // cutoff = 2026-08-03; endSession == cutoff → inside window (>=)
    const r = policy.admit({
      sessionCount: 1,
      endSession: "2026-08-03",
      now: NOW,
    })
    expect(r.admitted).toBe(false)
  })

  test("admits when end session is just before the cutoff", () => {
    // cutoff = 2026-08-03; endSession = 2026-08-02 → before window
    const r = policy.admit({
      sessionCount: 1,
      endSession: "2026-08-02",
      now: NOW,
    })
    expect(r.admitted).toBe(true)
  })
})