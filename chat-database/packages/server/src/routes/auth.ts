import { Hono } from "hono"
import { setCookie } from "hono/cookie"
import { validateCredentials, createSessionToken, getSessionCookieOptions, SESSION_COOKIE_NAME } from "../lib/auth"

export const authRoutes = new Hono()

// POST /auth/login
authRoutes.post("/login", async (c) => {
  const { email, password } = await c.req.json()

  if (!email || !password) {
    return c.json({ error: "Email and password are required" }, 400)
  }

  const user = await validateCredentials(email, password)
  if (!user) {
    return c.json({ error: "Invalid email or password" }, 401)
  }

  const token = createSessionToken(email, password)
  setCookie(c, SESSION_COOKIE_NAME, token, getSessionCookieOptions())

  return c.json({
    success: true,
    user: {
      id: String(user.id),
      email: user.email,
      name: user.name,
      isAdmin: user.isAdmin,
    },
  })
})

// POST /auth/logout
authRoutes.post("/logout", async (c) => {
  // Set cookie with immediate expiry to clear it
  setCookie(c, SESSION_COOKIE_NAME, "", {
    ...getSessionCookieOptions(),
    maxAge: 0,
  })
  return c.json({ success: true })
})

// GET /auth/me
authRoutes.get("/me", async (c) => {
  // Import auth parsing inline since this route doesn't go through authMiddleware
  const { getCookie } = await import("hono/cookie")
  const { validateSession, SESSION_COOKIE_NAME } = await import("../lib/auth")

  const token = getCookie(c, SESSION_COOKIE_NAME)
  if (!token) {
    return c.json({ authenticated: false, user: null, authEnabled: true })
  }

  const user = await validateSession(token)
  if (!user) {
    return c.json({ authenticated: false, user: null, authEnabled: true })
  }

  return c.json({
    authenticated: true,
    authEnabled: true,
    user: {
      id: String(user.id),
      email: user.email,
      name: user.name,
      isAdmin: user.isAdmin,
    },
  })
})
