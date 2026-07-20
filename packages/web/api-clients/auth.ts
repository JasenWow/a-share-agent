import { API_BASE_URL } from "./config"

export interface AuthUser {
  id: string
  email: string
  name: string
  isAdmin: boolean
}

export interface AuthStatus {
  authenticated: boolean
  user: AuthUser | null
  authEnabled: boolean
}

export async function login(
  email: string,
  password: string
): Promise<{ success: boolean; user?: AuthUser; error?: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  })

  const data = await response.json()
  if (!response.ok) {
    return { success: false, error: data.error || "Login failed" }
  }
  return { success: true, user: data.user }
}

export async function logout(): Promise<{ success: boolean }> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    })
    if (!response.ok) {
      return { success: false }
    }
    return response.json()
  } catch {
    return { success: false }
  }
}

export async function getAuthStatus(): Promise<AuthStatus> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, { credentials: "include" })
    if (!response.ok) {
      return { authenticated: false, user: null, authEnabled: false }
    }
    return response.json()
  } catch {
    return { authenticated: false, user: null, authEnabled: false }
  }
}
