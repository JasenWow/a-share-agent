import { describe, test, expect } from "bun:test"
import { app } from "./app"

describe("GET /health", () => {
  test("returns status ok", async () => {
    const res = await app.request("/health")
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body).toEqual({ status: "ok" })
  })
})
