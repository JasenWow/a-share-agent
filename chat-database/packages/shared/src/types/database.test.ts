import { describe, test, expect } from "bun:test"
import { isQueryError } from "./database"
import type { QueryResponse } from "./database"

describe("isQueryError", () => {
  test("returns true when response has error field", () => {
    const response: QueryResponse = { error: "Something went wrong" }
    expect(isQueryError(response)).toBe(true)
  })

  test("returns false for a successful QueryResult", () => {
    const response: QueryResponse = {
      columns: ["id", "name"],
      rows: [{ id: 1, name: "test" }],
      rowCount: 1,
    }
    expect(isQueryError(response)).toBe(false)
  })

  test("returns true for empty error string", () => {
    const response: QueryResponse = { error: "" }
    expect(isQueryError(response)).toBe(true)
  })

  test("returns false for empty result set", () => {
    const response: QueryResponse = {
      columns: [],
      rows: [],
      rowCount: 0,
    }
    expect(isQueryError(response)).toBe(false)
  })
})
