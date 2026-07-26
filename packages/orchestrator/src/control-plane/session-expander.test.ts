/**
 * session-expander tests — red/green TDD PR3 (Step 1).
 */

import { describe, expect, test } from "bun:test"
import { StaticSessionExpander } from "./session-expander"

const expander = new StaticSessionExpander([
  "2026-08-03",
  "2026-08-04",
  "2026-08-05",
  "2026-08-06",
  "2026-08-07",
])

describe("StaticSessionExpander", () => {
  test("expands a full range inclusively", () => {
    expect(expander.expand("2026-08-03", "2026-08-07")).toEqual([
      "2026-08-03",
      "2026-08-04",
      "2026-08-05",
      "2026-08-06",
      "2026-08-07",
    ])
  })

  test("single-session range returns one element", () => {
    expect(expander.expand("2026-08-04", "2026-08-04")).toEqual(["2026-08-04"])
  })

  test("partial range", () => {
    expect(expander.expand("2026-08-04", "2026-08-06")).toEqual([
      "2026-08-04",
      "2026-08-05",
      "2026-08-06",
    ])
  })

  test("throws when start is not a trading session", () => {
    expect(() => expander.expand("2026-08-02", "2026-08-05")).toThrow(/not a known trading session/)
  })

  test("throws when end is not a trading session", () => {
    expect(() => expander.expand("2026-08-03", "2026-08-10")).toThrow(/not a known trading session/)
  })

  test("throws when start is after end", () => {
    expect(() => expander.expand("2026-08-06", "2026-08-03")).toThrow(/after end/)
  })
})