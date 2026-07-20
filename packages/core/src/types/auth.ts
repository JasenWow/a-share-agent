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

export interface CreateUserPayload {
  name: string
  email: string
  password: string
  isAdmin?: boolean
}

export interface AdminUser {
  id: string
  name: string
  email: string
  isAdmin: boolean
  createdAt: string | null
}
