"use client"

import { API_BASE_URL } from "./config"

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
}

export interface QueryError {
  error: string
}

export type QueryResponse = QueryResult | QueryError

export interface TableColumn {
  name: string
  type: string
  nullable: boolean
}

export interface TableSchema {
  name: string
  columns: TableColumn[]
}

export interface SchemaResponse {
  schema: TableSchema[]
  error?: string
}

export function isQueryError(response: QueryResponse): response is QueryError {
  return "error" in response
}

export async function executeQuery(
  sql: string,
  databaseId?: string | null
): Promise<QueryResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/database/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ sql, databaseId: databaseId || undefined }),
    })

    const data = await response.json()
    if (!response.ok) return { error: (data as any).error || "Failed to execute query" }
    return data as QueryResult
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Failed to execute query" }
  }
}

export async function fetchSchema(databaseId?: string | null): Promise<SchemaResponse> {
  const params = databaseId ? `?databaseId=${databaseId}` : ""
  const response = await fetch(`${API_BASE_URL}/database/schema${params}`, {
    credentials: "include",
  })
  return response.json() as Promise<SchemaResponse>
}
