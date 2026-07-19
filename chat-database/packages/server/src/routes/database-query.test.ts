import { describe, test, expect, mock } from "bun:test"
import { databaseQueryRoutes } from "./database-query"

describe("POST /database/query", () => {
  test("rejects non-SELECT/PRAGMA on system database", async () => {
    const res = await databaseQueryRoutes.fetch(
      new Request("http://localhost/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: "DROP TABLE users" }),
      })
    )

    expect(res.status).toBe(500)
    const body = await res.json()
    expect(body.error).toBe("Only SELECT and PRAGMA queries are allowed on the system database")
  })

  test("rejects INSERT on system database", async () => {
    const res = await databaseQueryRoutes.fetch(
      new Request("http://localhost/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: "INSERT INTO users (name) VALUES ('hack')" }),
      })
    )

    expect(res.status).toBe(500)
    const body = await res.json()
    expect(body.error).toBe("Only SELECT and PRAGMA queries are allowed on the system database")
  })

  test("returns 400 when SQL is missing", async () => {
    const res = await databaseQueryRoutes.fetch(
      new Request("http://localhost/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      })
    )

    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error).toBe("SQL query is required")
  })

  test("returns 400 when SQL is not a string", async () => {
    const res = await databaseQueryRoutes.fetch(
      new Request("http://localhost/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: 123 }),
      })
    )

    expect(res.status).toBe(400)
  })
})
