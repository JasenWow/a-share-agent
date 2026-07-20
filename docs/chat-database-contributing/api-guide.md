# API Guide

## Routes

Export `new Hono()`, mount in `app.ts`:

```ts
app.use("/my-route/*", authMiddleware)
app.route("/my-route", myRoutes)
```

Public: `/auth/*`, `/health`. Everything else: `authMiddleware`.

Auth sets `c.get("user")` → `{ id, email, name, isAdmin }`.

## Ownership

GET single / PUT / DELETE on resources with `createdBy`:

```ts
if (row.createdBy && row.createdBy !== user.id && !user.isAdmin) return c.json({ error: "Forbidden" }, 403)
```

Admins bypass. List and create: no check.

## Responses

- Success: `{ item: {...} }` | `{ items: [...] }` | `{ success: true }`
- Error: `{ error: "message" }` with appropriate status (400/401/403/404/500)
- Never leak passwords, stack traces, or internal details

## PUT (partial update)

```ts
const updates: Record<string, unknown> = { updatedAt: new Date().toISOString() }
if (body.name !== undefined) updates.name = body.name
```

## System DB queries

```ts
if (!/^\s*(SELECT|PRAGMA)/i.test(sql)) throw new Error("Only SELECT and PRAGMA allowed")
```

## Web API clients

```ts
try {
  const response = await fetch(url)
  const data = await response.json()
  if (!response.ok) return { error: data.error || "Failed" }
  return data
} catch { return { error: "Network error" } }
```
