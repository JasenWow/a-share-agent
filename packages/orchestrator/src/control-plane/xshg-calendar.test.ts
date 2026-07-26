/**
 * xshg-calendar tests — red/green TDD PR4 (Steps A2/A3).
 *
 * Uses a small static slice of the real fixture so tests are fast and
 * deterministic while still exercising the binary-search logic.
 */

import { describe, expect, test } from "bun:test"
import { FileBackedSessionExpander, FileBackedSessionResolver } from "./xshg-calendar"

// A small curated slice for deterministic tests.
const SLICE = [
  "2026-08-03",
  "2026-08-04",
  "2026-08-05",
  "2026-08-06",
  "2026-08-07",
  "2026-08-10",
]

describe("FileBackedSessionExpander", () => {
  test("expands a valid range", () => {
    const exp = new FileBackedSessionExpander(SLICE)
    expect(exp.expand("2026-08-03", "2026-08-07")).toEqual([
      "2026-08-03",
      "2026-08-04",
      "2026-08-05",
      "2026-08-06",
      "2026-08-07",
    ])
  })

  test("single session", () => {
    const exp = new FileBackedSessionExpander(SLICE)
    expect(exp.expand("2026-08-05", "2026-08-05")).toEqual(["2026-08-05"])
  })

  test("throws on non-trading session", () => {
    const exp = new FileBackedSessionExpander(SLICE)
    expect(() => exp.expand("2026-08-02", "2026-08-05")).toThrow(/not a trading session/)
  })

  test("throws when start > end", () => {
    const exp = new FileBackedSessionExpander(SLICE)
    expect(() => exp.expand("2026-08-07", "2026-08-03")).toThrow(/after end/)
  })

  test("uses the real XSHG fixture by default", () => {
    const exp = new FileBackedSessionExpander()
    const sessions = exp.expand("2026-08-03", "2026-08-07")
    expect(sessions).toEqual([
      "2026-08-03",
      "2026-08-04",
      "2026-08-05",
      "2026-08-06",
      "2026-08-07",
    ])
  })
})

describe("FileBackedSessionResolver", () => {
  test("resolves the most recent session at or before now", () => {
    const res = new FileBackedSessionResolver(SLICE)
    // 2026-08-05 is a trading day
    expect(res.resolve(new Date("2026-08-05T18:00:00Z"))).toBe("2026-08-05")
  })

  test("resolves to previous session when now is a non-trading day", () => {
    const res = new FileBackedSessionResolver(SLICE)
    // 2026-08-08 is a Saturday — resolves to 2026-08-07 (Friday)
    expect(res.resolve(new Date("2026-08-08T18:00:00Z"))).toBe("2026-08-07")
  })

  test("resolves to previous session when now is before market close", () => {
    const res = new FileBackedSessionResolver(SLICE)
    // 2026-08-06 at 08:00 — still resolves to 2026-08-06 (same calendar day)
    expect(res.resolve(new Date("2026-08-06T08:00:00Z"))).toBe("2026-08-06")
  })

  test("throws when now is before the first known session", () => {
    const res = new FileBackedSessionResolver(SLICE)
    expect(() => res.resolve(new Date("2019-01-01T00:00:00Z"))).toThrow(/No trading session/)
  })

  test("uses the real XSHG fixture by default", () => {
    const res = new FileBackedSessionResolver()
    expect(res.resolve(new Date("2026-08-05T18:00:00Z"))).toBe("2026-08-05")
  })
})