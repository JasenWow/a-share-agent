import bcrypt from "bcryptjs"
import { db } from "../db/connection"
import { users } from "../db/schema"
import { eq } from "drizzle-orm"

export interface SessionUser {
  id: number
  email: string
  name: string
  isAdmin: boolean
}

const BCRYPT_SALT_ROUNDS = 10

export async function hashPassword(password: string): Promise<string> {
  return await bcrypt.hash(password, BCRYPT_SALT_ROUNDS)
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return await bcrypt.compare(password, hash)
}

function createBasicAuthToken(email: string, password: string): string {
  const credentials = `${email}:${password}`
  const base64 = Buffer.from(credentials).toString("base64")
  return `Basic ${base64}`
}

export function parseBasicAuthToken(token: string): { email: string; password: string } | null {
  if (!token.startsWith("Basic ")) return null

  try {
    const base64 = token.slice(6)
    const decoded = Buffer.from(base64, "base64").toString("utf-8")
    const colonIndex = decoded.indexOf(":")
    if (colonIndex === -1) return null

    return {
      email: decoded.slice(0, colonIndex),
      password: decoded.slice(colonIndex + 1),
    }
  } catch {
    return null
  }
}

export async function validateCredentials(email: string, password: string): Promise<SessionUser | null> {
  const user = await db.select().from(users).where(eq(users.email, email)).get()
  if (!user) return null

  const isValid = await verifyPassword(password, user.password)
  if (!isValid) return null

  return { id: user.id, email: user.email, name: user.name, isAdmin: user.isAdmin }
}

export function createSessionToken(email: string, password: string): string {
  return createBasicAuthToken(email, password)
}

export async function validateSession(token: string): Promise<SessionUser | null> {
  const credentials = parseBasicAuthToken(token)
  if (!credentials) return null
  return await validateCredentials(credentials.email, credentials.password)
}

// Cookie helpers
export const SESSION_COOKIE_NAME = "auth_session"
export const SESSION_MAX_AGE = 60 * 60 * 24 * 7 // 7 days

export function getSessionCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    maxAge: SESSION_MAX_AGE,
    path: "/",
  }
}
