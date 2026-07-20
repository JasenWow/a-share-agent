import type { Context, Next } from "hono"
import { getCookie } from "hono/cookie"
import { validateSession, SESSION_COOKIE_NAME, type SessionUser } from "../lib/auth"

// Extend Hono context to include user
declare module "hono" {
  interface ContextVariableMap {
    user: SessionUser
  }
}

export async function authMiddleware(c: Context, next: Next) {
  const token = getCookie(c, SESSION_COOKIE_NAME)

  if (!token) {
    return c.json({ error: "Unauthorized" }, 401)
  }

  const user = await validateSession(token)
  if (!user) {
    return c.json({ error: "Unauthorized" }, 401)
  }

  c.set("user", user)
  await next()
}

export async function adminMiddleware(c: Context, next: Next) {
  const user = c.get("user")
  if (!user || !user.isAdmin) {
    return c.json({ error: "Forbidden: Admin access required" }, 403)
  }
  await next()
}
