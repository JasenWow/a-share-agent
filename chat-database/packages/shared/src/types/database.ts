// Database adapter types

export interface TableColumn {
  name: string
  type: string
  nullable: boolean
}

export interface TableSchema {
  name: string
  columns: TableColumn[]
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
}

export interface QueryError {
  error: string
}

export type QueryResponse = QueryResult | QueryError

export function isQueryError(response: QueryResponse): response is QueryError {
  return "error" in response
}

// External database connection config
export type DatabaseType = "postgresql" | "sqlite" | "duckdb"

export interface ConnectionConfig {
  host: string
  port: number
  database: string
  username: string
  password: string
  sslEnabled: boolean
}

export interface ExternalDbConfig {
  type: DatabaseType
  // PostgreSQL fields
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  sslEnabled?: boolean
  // SQLite fields
  filePath?: string
}

// External database as stored in the system DB
export interface ExternalDatabase {
  id: string
  name: string
  dbType: DatabaseType
  host: string
  port: number
  database: string
  username: string
  password: string
  sslEnabled: boolean
  filePath: string | null
  createdBy: string | null
  createdAt: string | null
  updatedAt: string | null
}

// Frontend form input for creating/editing external databases
export interface DatabaseInput {
  name: string
  dbType?: DatabaseType
  host: string
  port: number
  database: string
  username: string
  password: string
  sslEnabled: boolean
  filePath?: string
}
