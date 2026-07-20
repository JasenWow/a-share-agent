import type { TableSchema, QueryResult } from "@aquan/core"

export interface DatabaseAdapter {
  /** Execute a SQL query and return structured results */
  executeQuery(sql: string): Promise<QueryResult>

  /** Introspect the database schema */
  getSchema(): Promise<TableSchema[]>

  /** Test connectivity */
  testConnection(): Promise<boolean>

  /** Clean up resources */
  close(): Promise<void>
}
