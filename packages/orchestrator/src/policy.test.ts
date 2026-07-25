import { describe, expect, test } from "bun:test"
import type { BudgetPolicy, ConcurrencyPolicy } from "@aquan/core"
import { ConcurrencyGate, SpendGuard } from "./policy"

// Fixed clock for deterministic window-rollover tests.
const FIXED_NOW = new Date("2026-07-25T13:30:00Z")

describe("SpendGuard", () => {
  const unlimitedBudget: BudgetPolicy = {
    dailyCap: null,
    weeklyCap: null,
    monthlyCap: null,
  }

  test("unlimited policy never blocks", () => {
    const guard = new SpendGuard(unlimitedBudget, () => FIXED_NOW)
    for (let i = 0; i < 100; i++) {
      guard.recordSpend()
    }
    expect(guard.canStart()).toEqual({ allowed: true })
  })

  test("canStart allows when under cap", () => {
    const guard = new SpendGuard({ ...unlimitedBudget, dailyCap: 5 }, () => FIXED_NOW)
    expect(guard.canStart()).toEqual({ allowed: true })
    guard.recordSpend()
    guard.recordSpend()
    guard.recordSpend()
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: true })
  })

  test("canStart blocks when daily cap reached and names the reason", () => {
    const guard = new SpendGuard({ ...unlimitedBudget, dailyCap: 2 }, () => FIXED_NOW)
    guard.recordSpend()
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: false, reason: "daily" })
  })

  test("weekly cap is checked after daily", () => {
    // daily is null (unlimited); weekly should bind.
    const guard = new SpendGuard({ ...unlimitedBudget, weeklyCap: 1 }, () => FIXED_NOW)
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: false, reason: "weekly" })
  })

  test("monthly cap is checked last", () => {
    const guard = new SpendGuard(
      { dailyCap: null, weeklyCap: null, monthlyCap: 1 },
      () => FIXED_NOW,
    )
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: false, reason: "monthly" })
  })

  test("recordSpend accumulates across all windows", () => {
    const guard = new SpendGuard(
      { dailyCap: 10, weeklyCap: 50, monthlyCap: 200 },
      () => FIXED_NOW,
    )
    guard.recordSpend()
    guard.recordSpend()
    const stats = guard.getStats()
    expect(stats.daily).toBe(2)
    expect(stats.weekly).toBe(2)
    expect(stats.monthly).toBe(2)
  })

  test("daily counter resets at UTC midnight", () => {
    let now = new Date("2026-07-25T23:59:00Z")
    const guard = new SpendGuard({ ...unlimitedBudget, dailyCap: 1 }, () => now)
    guard.recordSpend()
    expect(guard.canStart()).toEqual({ allowed: false, reason: "daily" })

    // Advance to next day.
    now = new Date("2026-07-26T00:01:00Z")
    expect(guard.canStart()).toEqual({ allowed: true })
    expect(guard.getStats().daily).toBe(0)
  })

  test("monthly counter resets on first of month", () => {
    let now = new Date("2026-07-31T23:59:00Z")
    const guard = new SpendGuard({ ...unlimitedBudget, monthlyCap: 1 }, () => now)
    guard.recordSpend()
    expect(guard.canStart().allowed).toBe(false)

    now = new Date("2026-08-01T00:01:00Z")
    expect(guard.canStart()).toEqual({ allowed: true })
  })

  test("reset clears all counters (test helper)", () => {
    const guard = new SpendGuard({ ...unlimitedBudget, dailyCap: 1 }, () => FIXED_NOW)
    guard.recordSpend()
    expect(guard.canStart().allowed).toBe(false)
    guard.reset()
    expect(guard.canStart()).toEqual({ allowed: true })
  })
})

describe("ConcurrencyGate", () => {
  const serial: ConcurrencyPolicy = { maxConcurrent: 1 }

  test("acquire returns release fn that frees the slot", async () => {
    const gate = new ConcurrencyGate(serial)
    const release = await gate.acquire()
    expect(gate.getActive()).toBe(1)
    release()
    expect(gate.getActive()).toBe(0)
  })

  test("second acquire waits when maxConcurrent=1", async () => {
    const gate = new ConcurrencyGate(serial)
    const release = await gate.acquire()
    let secondResolved = false
    const secondPromise = gate.acquire().then((rel) => {
      secondResolved = true
      return rel
    })

    // Yield once; the second acquire must still be waiting.
    await Promise.resolve()
    expect(secondResolved).toBe(false)
    expect(gate.getWaiting()).toBe(1)

    release()
    const secondRelease = await secondPromise
    expect(secondResolved).toBe(true)
    expect(gate.getActive()).toBe(1)
    expect(gate.getWaiting()).toBe(0)

    secondRelease()
    expect(gate.getActive()).toBe(0)
  })

  test("maxConcurrent=2 allows two simultaneous holders", async () => {
    const gate = new ConcurrencyGate({ maxConcurrent: 2 })
    const r1 = await gate.acquire()
    const r2 = await gate.acquire()
    expect(gate.getActive()).toBe(2)
    r1()
    expect(gate.getActive()).toBe(1)
    r2()
    expect(gate.getActive()).toBe(0)
  })

  test("release is idempotent (safe in finally blocks)", async () => {
    const gate = new ConcurrencyGate(serial)
    const release = await gate.acquire()
    release()
    release() // no-op, must not underflow
    expect(gate.getActive()).toBe(0)
    // Next acquire must resolve immediately (slot was freed exactly once).
    const release2 = await gate.acquire()
    expect(gate.getActive()).toBe(1)
    release2()
  })

  test("constructor rejects maxConcurrent < 1", () => {
    expect(() => new ConcurrencyGate({ maxConcurrent: 0 })).toThrow(/>= 1/)
  })
})
