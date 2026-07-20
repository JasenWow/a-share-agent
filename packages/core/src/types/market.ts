/**
 * Market domain types — stocks, factors, portfolios.
 *
 * Phase 5 placeholder. Concrete shapes will be filled in as the
 * orchestrator/pi-runtime packages start to consume them. For now,
 * only the most general identifiers are defined.
 */

/** Ticker symbol in A-share form: 6-digit code, e.g. "000001", "600519". */
export type Ticker = string

/** Stock universe label (e.g. "csi300", "csi500", "all_a_share"). */
export type Universe = string

/** A factor's published name (e.g. "momentum_20d", "book_to_market"). */
export type FactorName = string

/** ISO date in YYYY-MM-DD form (A-share trading day). */
export type TradingDate = string

/** Common result envelope used by MCP tools and ETL runs. */
export interface ResultEnvelope<T> {
  status: "ok" | "error"
  data?: T
  error?: string
}
