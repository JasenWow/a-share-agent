export interface ParsedDatabaseUrl {
  host: string
  port: number
  database: string
  username: string
  password: string
  sslEnabled: boolean
}

/**
 * Parse a PostgreSQL connection URL into its components
 */
export function parseDatabaseUrl(url: string): ParsedDatabaseUrl | null {
  try {
    const normalizedUrl = url.replace(/^postgres:\/\//, "postgresql://")
    if (!normalizedUrl.startsWith("postgresql://")) return null

    const parsed = new URL(normalizedUrl)
    const host = parsed.hostname
    const port = parsed.port ? parseInt(parsed.port, 10) : 5432
    const database = parsed.pathname.slice(1)
    const username = decodeURIComponent(parsed.username)
    const password = decodeURIComponent(parsed.password)
    const sslmode = parsed.searchParams.get("sslmode")
    const sslEnabled = sslmode === "require" || sslmode === "verify-full"

    if (!host || !database || !username) return null

    return { host, port, database, username, password, sslEnabled }
  } catch {
    return null
  }
}

export function buildDatabaseUrl(config: ParsedDatabaseUrl): string {
  const encodedUsername = encodeURIComponent(config.username)
  const encodedPassword = encodeURIComponent(config.password)
  const encodedDatabase = encodeURIComponent(config.database)
  const ssl = config.sslEnabled ? "?sslmode=require" : ""
  return `postgresql://${encodedUsername}:${encodedPassword}@${config.host}:${config.port}/${encodedDatabase}${ssl}`
}

export function isValidDatabaseUrl(url: string): boolean {
  return parseDatabaseUrl(url) !== null
}
