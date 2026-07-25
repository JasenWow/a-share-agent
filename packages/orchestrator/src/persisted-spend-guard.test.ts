import { describe, expect, test } from "bun:test"
import { Database } from "bun:sqlite"
import type { BudgetPolicy } from "@aquan/core"
import { PersistedSpendGuard } from "./persisted-spend-guard"

const FIXED_NOW = new Date("2026-07-25T13:30:00Z")

function freshDb(): Database {
  const db = new Database(":memory:")
  return db
}

const unlimitedBudget: BudgetPolicy = {
  dailyCap: null,
  weeklyCap: null,
  monthlyCap: null,
}

describe("PersistedSpendGuard — basic", () => {
  test("fresh DB → zero counters", () => {
    const db = freshDb()
    const guard = new PersistedSpendGuard(unlimitedBudget, db, () => FIXED_NOW)
    const stats = guard.getStats()
    expect(stats.daily).toBe(0)
    expect(stats.weekly).toBe(0)
    expect(stats.monthly).toBe(0)
    db.close()
  })

  test("recordSpend writes to spend_log and bumps counters", () => {
    const db = freshDb()
    const guard = new PersistedSpendGuard(unlimitedBudget, db, () => FIXED_NOW)
    guard.recordSpend("factor-mining")
    guard.recordSpend("factor-mining")
    guard.recordSpend("free-exploration")

    const stats = guard.getStats()
    expect(stats.daily).toBe(3)
    expect(stats.weekly).toBe(3)
    expect(stats.monthly).toBe(3)

    const rows = db.query("SELECT source, at FROM spend_log ORDER BY id").all() as Array<{ source: string; at: string }>
    expect(rows.length).toBe(3)
    expect(rows[0].source).toBe("factor-mining")
    expect(rows[2].source).toBe("free-exploration")
    db.close()
  })

  test("canStart respects cap (replays count against it)", () => {
    const db = freshDb()
    const guard = new PersistedSpendGuard(
      { ...unlimitedBudget, dailyCap: 2 },
      db,
      () => FIXED_NOW,
    )
    guard.recordSpend()
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: false, reason: "daily" })
    db.close()
  })
})

describe("PersistedSpendGuard — restart replay", () => {
  test("new guard on existing DB sees previous spends", () => {
    const db = freshDb()
    const g1 = new PersistedSpendGuard(unlimitedBudget, db, () => FIXED_NOW)
    for (let i = 0; i < 5; i++) g1.recordSpend()

    // Simulate restart: new guard wrapping the same DB.
    const g2 = new PersistedSpendGuard(unlimitedBudget, db, () => FIXED_NOW)
    const stats = g2.getStats()
    expect(stats.daily).toBe(5)
    expect(stats.weekly).toBe(5)
    expect(stats.monthly).toBe(5)
    db.close()
  })

  test("replay respects dailyCap from prior session", () => {
    const db = freshDb()
    const budget: BudgetPolicy = { ...unlimitedBudget, dailyCap: 3 }
    const g1 = new PersistedSpendGuard(budget, db, () => FIXED_NOW)
    for (let i = 0; i < 3; i++) g1.recordSpend()
    expect(g1.canStart().allowed).toBe(false)

    const g2 = new PersistedSpendGuard(budget, db, () => FIXED_NOW)
    expect(g2.canStart()).toEqual({ allowed: false, reason: "daily" })
    db.close()
  })

  test("spends from yesterday don't count toward today", () => {
    const yesterday = new Date("2026-07-24T13:30:00Z")
    let now = yesterday
    const db = freshDb()
    const guard = new PersistedSpendGuard(
      { ...unlimitedBudget, dailyCap: 1 },
      db,
      () => now,
    )
    guard.recordSpend()
    expect(guard.canStart().allowed).toBe(false)

    // Advance to next day; the previous spend should no longer block today.
    now = FIXED_NOW
    // New guard instance to re-trigger rebuildFromLog with the new clock.
    const guardNextDay = new PersistedSpendGuard(
      { ...unlimitedBudget, dailyCap: 1 },
      db,
      () => now,
    )
    expect(guardNextDay.canStart()).toEqual({ allowed: true })
    // But weekly window still includes yesterday's spend.
    expect(guardNextDay.getStats().weekly).toBe(1)
    db.close()
  })
})
