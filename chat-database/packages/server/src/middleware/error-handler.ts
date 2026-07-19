import type { Context } from "hono"

export function errorHandler(err: Error, c: Context) {
  console.error("Unhandled error:", err)
  return c.json({ error: err.message || "Internal server error" }, 500)
}
