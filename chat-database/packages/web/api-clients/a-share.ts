"use client"

/**
 * A-Share warehouse API client.
 *
 * Wraps the generic executeQuery with the DuckDB warehouse database ID.
 * The warehouse database must be registered in chat-database's database
 * management (type=duckdb, filePath=<WAREHOUSE_DUCKDB_PATH>).
 *
 * Resolution order for which DB is "the warehouse":
 *   1. localStorage 'a-share-warehouse-db-id' (explicit override)
 *   2. First registered database with dbType=duckdb (auto-detect)
 *   3. null (page shows "no warehouse connected" prompt)
 */

import { executeQuery } from "./database-query"
import type { QueryResponse } from "./database-query"
import { getDatabases } from "./databases"

const A_SHARE_DB_KEY = "a-share-warehouse-db-id"

export function getAShareDbId(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(A_SHARE_DB_KEY)
}

export function setAShareDbId(id: string | null) {
  if (typeof window === "undefined") return
  if (id) localStorage.setItem(A_SHARE_DB_KEY, id)
  else localStorage.removeItem(A_SHARE_DB_KEY)
}

/**
 * Resolve the active warehouse DB id, falling back to auto-detection.
 * Returns null if no duckdb database is registered.
 */
export async function resolveAShareDbId(): Promise<string | null> {
  const explicit = getAShareDbId()
  if (explicit) return explicit

  // Auto-detect: find first registered DuckDB database
  try {
    const res = await getDatabases()
    const databases = res.databases || []
    const duckdb = databases.find((d) => d.dbType === "duckdb")
    if (duckdb) {
      setAShareDbId(String(duckdb.id))
      return String(duckdb.id)
    }
  } catch {
    // ignore — fall through to null
  }
  return null
}

/**
 * Run a query against the A-share DuckDB warehouse.
 * Caller passes a pre-baked SQL string (typically from the metric semantic
 * layer or hand-written for a specific page).
 */
export async function queryWarehouse(sql: string): Promise<QueryResponse> {
  let dbId = getAShareDbId()
  if (!dbId) {
    dbId = await resolveAShareDbId()
  }
  return executeQuery(sql, dbId)
}

// ============ Factor comparison queries ============

export interface FactorRow {
  name: string
  expression: string
  ic: number | null
  icir: number | null
  turnover: number | null
  sharpe: number | null
  max_drawdown: number | null
  universe: string
  status: string
  snapshot_date: string
}

export async function listFactors(): Promise<{ factors: FactorRow[]; error?: string }> {
  // Take the latest snapshot per factor (max snapshot_date)
  const sql = `
    WITH latest AS (
      SELECT name, MAX(snapshot_date) AS max_date
      FROM ods_factor_experiments
      GROUP BY name
    )
    SELECT f.name, f.expression, f.ic, f.icir, f.turnover, f.sharpe,
           f.max_drawdown, f.universe, f.status, f.snapshot_date
    FROM ods_factor_experiments f
    JOIN latest l ON f.name = l.name AND f.snapshot_date = l.max_date
    ORDER BY f.icir DESC NULLS LAST
  `
  const res = await queryWarehouse(sql)
  if ("error" in res) return { factors: [], error: res.error }
  return { factors: res.rows as unknown as FactorRow[] }
}

// ============ Backtest history queries ============

export interface BacktestRow {
  run_id: number
  name: string
  strategy: string
  start_date: string
  end_date: string
  sharpe: number | null
  max_drawdown: number | null
  annual_return: number | null
  created_at: string
  snapshot_date: string
}

export async function listBacktests(): Promise<{ backtests: BacktestRow[]; error?: string }> {
  // Latest snapshot per run_id
  const sql = `
    WITH latest AS (
      SELECT run_id, MAX(snapshot_date) AS max_date
      FROM ods_backtest_runs
      GROUP BY run_id
    )
    SELECT b.run_id, b.name, b.strategy, b.start_date, b.end_date,
           b.sharpe, b.max_drawdown, b.annual_return, b.created_at, b.snapshot_date
    FROM ods_backtest_runs b
    JOIN latest l ON b.run_id = l.run_id AND b.snapshot_date = l.max_date
    ORDER BY b.sharpe DESC NULLS LAST
  `
  const res = await queryWarehouse(sql)
  if ("error" in res) return { backtests: [], error: res.error }
  return { backtests: res.rows as unknown as BacktestRow[] }
}
