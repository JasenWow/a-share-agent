import { describe, test, expect } from "bun:test"
import {
  parseBasicAuthToken,
  createSessionToken,
  hashPassword,
  verifyPassword,
} from "./auth"

describe("parseBasicAuthToken", () => {
  test("parses a valid Basic auth token", () => {
    // user@example.com:password123
    const token = "Basic dXNlckBleGFtcGxlLmNvbTpwYXNzd29yZDEyMw=="
    const result = parseBasicAuthToken(token)
    expect(result).toEqual({
      email: "user@example.com",
      password: "password123",
    })
  })

  test("returns null when token lacks Basic prefix", () => {
    const result = parseBasicAuthToken("dXNlckBleGFtcGxlLmNvbTpwYXNzd29yZA==")
    expect(result).toBeNull()
  })

  test("returns null for empty string", () => {
    expect(parseBasicAuthToken("")).toBeNull()
  })

  test("returns null when decoded value has no colon", () => {
    // "nocolonhere" base64
    const token = "Basic bm9jb2xvbmhlcmU="
    expect(parseBasicAuthToken(token)).toBeNull()
  })

  test("handles email with colon in password part", () => {
    // user:pass:with:colons
    const token = "Basic dXNlcjpwYXNzOndpdGg6Y29sb25z"
    const result = parseBasicAuthToken(token)
    expect(result).toEqual({
      email: "user",
      password: "pass:with:colons",
    })
  })
})

describe("createSessionToken", () => {
  test("creates a token that can be parsed back", () => {
    const token = createSessionToken("admin@test.com", "secret123")
    const parsed = parseBasicAuthToken(token)
    expect(parsed).toEqual({
      email: "admin@test.com",
      password: "secret123",
    })
  })

  test("token starts with 'Basic '", () => {
    const token = createSessionToken("user", "pass")
    expect(token.startsWith("Basic ")).toBe(true)
  })
})

describe("hashPassword / verifyPassword", () => {
  test("hashes a password and verifies it correctly", async () => {
    const hash = await hashPassword("my-password")
    expect(typeof hash).toBe("string")
    expect(hash).not.toBe("my-password")
    expect(await verifyPassword("my-password", hash)).toBe(true)
  })

  test("verification fails for wrong password", async () => {
    const hash = await hashPassword("correct-password")
    expect(await verifyPassword("wrong-password", hash)).toBe(false)
  })

  test("different hashes for same password (salt randomness)", async () => {
    const hash1 = await hashPassword("same-password")
    const hash2 = await hashPassword("same-password")
    expect(hash1).not.toBe(hash2)
    // But both should verify
    expect(await verifyPassword("same-password", hash1)).toBe(true)
    expect(await verifyPassword("same-password", hash2)).toBe(true)
  })
})
