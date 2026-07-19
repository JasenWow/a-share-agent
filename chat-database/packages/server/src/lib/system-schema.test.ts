import { describe, test, expect } from "bun:test"
import { escapeSqliteIdentifier } from "./system-schema"

describe("escapeSqliteIdentifier", () => {
  test("wraps a simple name in double quotes", () => {
    expect(escapeSqliteIdentifier("users")).toBe('"users"')
  })

  test("wraps a name with underscores", () => {
    expect(escapeSqliteIdentifier("user_accounts")).toBe('"user_accounts"')
  })

  test("throws for name containing double quote", () => {
    expect(() => escapeSqliteIdentifier('table"with"quotes')).toThrow(
      "Invalid table name"
    )
  })

  test("throws for name containing semicolon", () => {
    expect(() => escapeSqliteIdentifier("users; DROP TABLE")).toThrow(
      "Invalid table name"
    )
  })

  test("throws for name containing single quote", () => {
    expect(() => escapeSqliteIdentifier("users'")).toThrow(
      "Invalid table name"
    )
  })

  test("throws for name containing backslash", () => {
    expect(() => escapeSqliteIdentifier("users\\table")).toThrow(
      "Invalid table name"
    )
  })

  test("accepts a name with spaces (no injection chars)", () => {
    expect(escapeSqliteIdentifier("my table")).toBe('"my table"')
  })
})
