import { Hono } from "hono"
import { db } from "../db/connection"
import { users } from "../db/schema"
import { eq, desc } from "drizzle-orm"
import { hashPassword } from "../lib/auth"
import { adminMiddleware } from "../middleware/auth"

export const adminUserRoutes = new Hono()

// All admin routes require admin access
adminUserRoutes.use("*", adminMiddleware)

// GET /admin/users
adminUserRoutes.get("/users", async (c) => {
  const rows = await db.select({
    id: users.id,
    name: users.name,
    email: users.email,
    isAdmin: users.isAdmin,
    createdAt: users.createdAt,
  }).from(users).orderBy(desc(users.createdAt))

  return c.json({
    users: rows.map((u) => ({
      id: String(u.id),
      name: u.name,
      email: u.email,
      isAdmin: u.isAdmin,
      createdAt: u.createdAt,
    })),
  })
})

// POST /admin/users
adminUserRoutes.post("/users", async (c) => {
  const { name, email, password, isAdmin } = await c.req.json()

  if (!name || !email || !password) {
    return c.json({ error: "Name, email, and password are required" }, 400)
  }

  const existing = await db.select().from(users).where(eq(users.email, email)).get()
  if (existing) {
    return c.json({ error: "User with this email already exists" }, 409)
  }

  const hashedPasswordValue = await hashPassword(password)
  const user = await db.insert(users).values({
    name,
    email,
    password: hashedPasswordValue,
    isAdmin: isAdmin ?? false,
  }).returning().get()

  return c.json({
    success: true,
    user: {
      id: String(user.id),
      name: user.name,
      email: user.email,
      isAdmin: user.isAdmin,
      createdAt: user.createdAt,
    },
  })
})

// DELETE /admin/users/:id
adminUserRoutes.delete("/users/:id", async (c) => {
  const currentUser = c.get("user")
  const id = Number(c.req.param("id"))

  if (currentUser.id === id) {
    return c.json({ error: "Cannot delete your own account" }, 400)
  }

  const user = await db.select().from(users).where(eq(users.id, id)).get()
  if (!user) {
    return c.json({ error: "User not found" }, 404)
  }

  await db.delete(users).where(eq(users.id, id))
  return c.json({ success: true })
})
