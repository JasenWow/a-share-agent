/**
 * InternalStoreReader — read-only access to the internal-store SQLite DB.
 *
 * The internal-store MCP server (`python/mcp-servers/internal-store`) owns
 * `data/cache/meta.db`, whose `factor_library` table holds the half-automatic
 * factor lifecycle (active / candidate / rejected / deprecated). This reader
 * lets the orchestrator observe that state without going through MCP:
 *
 *   - FactorMiningTracker injects active expressions into the mining prompt
 *     so the agent doesn't duplicate existing factors.
 *   - The HTTP layer exposes candidates so the dashboard can show what the
 *     agent has produced.
 *
 * Safety: opens the DB read-only (`bun:sqlite`'s `readonly: true`). The MCP
 * server opens a fresh `sqlite3.connect()` per tool call, so concurrent reads
 * from this process are safe (SQLite allows many readers). We never write.
 *
 * Robustness: if the DB file or `factor_library` table is missing (e.g.
 * internal-store hasn't started yet), every method returns an empty result
 * rather than throwing — trackers and the HTTP endpoint degrade gracefully.
 */

import { Database } from "bun:sqlite"

/** A factor_library row, with `walk_forward` parsed into confidence/rationale. */
export interface CandidateFactor {
  id: number
  name: string
  expression: string
  hypothesis: string | null
  operators: string[]
  dataFields: string[]
  ic: number | null
  icir: number | null
  turnover: number | null
  sharpe: number | null
  maxDrawdown: number | null
  universe: string | null
  period: string | null
  /** Confidence in [0,1], parsed from walk_forward JSON for candidates. */
  confidence: number | null
  /** Free-text rationale, parsed from walk_forward JSON for candidates. */
  rationale: string | null
  status: string
  sourceExperimentId: number | null
  createdAt: string | null
}

/** Result of a promote/reject mutation. */
export interface FactorMutationResult {
  ok: boolean
  factorId: number
  /** New status when ok, e.g. "active" / "rejected". */
  targetStatus?: "active" | "rejected"
  /**
   * Error code when !ok:
   *   not-found       — factor id doesn't exist
   *   not-candidate   — promote guard: row isn't status='candidate'
   *   unavailable     — DB missing / locked / write failed
   */
  error?: "not-found" | "not-candidate" | "unavailable"
  /** Current status (for not-candidate errors). */
  currentStatus?: string | null
  /** Diagnostic message (for unavailable errors). */
  message?: string
  /** Audit fields — returned for logging, NOT persisted to DB. */
  reviewer?: string
  notes?: string
  reason?: string
}

interface FactorLibraryRow {
  id: number
  name: string
  expression: string
  hypothesis: string | null
  operators: string | null
  data_fields: string | null
  ic: number | null
  icir: number | null
  turnover: number | null
  sharpe: number | null
  max_drawdown: number | null
  universe: string | null
  period: string | null
  walk_forward: string | null
  status: string | null
  source_experiment_id: number | null
  created_at: string | null
}

export class InternalStoreReader {
  constructor(private dbPath: string) {}

  /** All candidate factors (status='candidate'), newest first. */
  listCandidates(limit = 50): CandidateFactor[] {
    const rows = this.queryFactors(
      `SELECT * FROM factor_library WHERE status = 'candidate' ORDER BY id DESC LIMIT ?;`,
      [limit],
    )
    return rows
  }

  /** Expressions of all active factors — used by the tracker for dedup context. */
  listActiveFactorExpressions(): string[] {
    const rows = this.queryRaw<{ expression: string }>(
      `SELECT expression FROM factor_library WHERE status = 'active' ORDER BY id ASC;`,
      [],
    )
    return rows.map((r) => r.expression)
  }

  /** Count of candidate factors (cheap dashboard metric). */
  candidateCount(): number {
    const rows = this.queryRaw<{ n: number }>(
      `SELECT COUNT(*) AS n FROM factor_library WHERE status = 'candidate';`,
      [],
    )
    return rows[0]?.n ?? 0
  }

  /** True when the DB file exists and the factor_library table is present. */
  isAvailable(): boolean {
    try {
      const db = this.openReadOnly()
      try {
        db.query(`SELECT 1 FROM factor_library LIMIT 1;`).get()
      } finally {
        db.close()
      }
      return true
    } catch {
      return false
    }
  }

  // --- write path (promote / reject) ---
  //
  // These open the DB read-write (without `readonly: true`), mirroring the
  // internal-store MCP server's own per-call connect-and-write pattern. The
  // guards (only `candidate` rows can be promoted) are re-implemented here
  // rather than calling through MCP — keeps the orchestrator self-contained
  // and avoids subprocess/IPC overhead per click.

  /**
   * Promote a candidate factor to active. Only `status='candidate'` rows
   * may be promoted (matches promote_factor in internal-store/server.py).
   * reviewer/notes are returned to the caller for audit logging but are
   * NOT persisted (the MCP server has no DB columns for them either).
   */
  promoteCandidate(factorId: number, reviewer?: string, notes?: string): FactorMutationResult {
    return this.mutate(factorId, "active", "candidate", { reviewer, notes })
  }

  /**
   * Reject a factor (set status='rejected'). No status guard — any existing
   * row may be rejected (matches reject_factor in internal-store/server.py).
   * reason/reviewer are returned for audit logging, not persisted.
   */
  rejectCandidate(factorId: number, reason?: string, reviewer?: string): FactorMutationResult {
    return this.mutate(factorId, "rejected", undefined, { reason, reviewer })
  }

  /**
   * Shared write path. `requiredCurrentStatus` enforces the promote guard
   * (reject passes undefined = no guard, matching MCP semantics).
   */
  private mutate(
    factorId: number,
    targetStatus: "active" | "rejected",
    requiredCurrentStatus: string | undefined,
    audit: { reviewer?: string; notes?: string; reason?: string },
  ): FactorMutationResult {
    let db: Database | undefined
    try {
      db = new Database(this.dbPath)
      db.run("PRAGMA busy_timeout = 5000;")
      const row = db.query(`SELECT status FROM factor_library WHERE id = ?;`).get(factorId) as
        | { status: string | null }
        | null
      if (!row) {
        return { ok: false, factorId, error: "not-found" }
      }
      if (requiredCurrentStatus && row.status !== requiredCurrentStatus) {
        return { ok: false, factorId, error: "not-candidate", currentStatus: row.status ?? null }
      }
      db.run(`UPDATE factor_library SET status = ? WHERE id = ?;`, targetStatus, factorId)
      return { ok: true, factorId, targetStatus, ...audit }
    } catch (e) {
      return {
        ok: false,
        factorId,
        error: "unavailable",
        message: e instanceof Error ? e.message : String(e),
      }
    } finally {
      try {
        db?.close()
      } catch {
        // ignore
      }
    }
  }

  // --- internals ---

  /**
   * Run a factor-row query: returns rows parsed into CandidateFactor shape.
   * Used by listCandidates (the SELECT * path).
   */
  private queryFactors(sql: string, params: unknown[]): CandidateFactor[] {
    const rows = this.queryRaw<FactorLibraryRow>(sql, params)
    return rows.map((r) => parseRow(r))
  }

  /**
   * Run a query against a short-lived read-only connection. Each MCP tool
   * call in internal-store opens its own connection, so we mirror that
   * pattern: open → query → close. Keeps things simple and avoids holding
   * a handle across long-lived orchestrator ticks.
   */
  private queryRaw<T>(sql: string, params: unknown[]): T[] {
    let db: Database | undefined
    try {
      db = this.openReadOnly()
      return db.query(sql).all(...params) as unknown as T[]
    } catch {
      // DB missing, table missing, locked, ... — degrade to empty.
      return []
    } finally {
      try {
        db?.close()
      } catch {
        // ignore
      }
    }
  }

  private openReadOnly(): Database {
    // `readonly: true` fails if the file doesn't exist (we want that — caught
    // by query()'s try/catch and surfaced as empty results).
    return new Database(this.dbPath, { readonly: true })
  }
}

/** Parse a snake_case DB row into a CandidateFactor, decoding JSON columns. */
function parseRow(row: FactorLibraryRow): CandidateFactor {
  // `walk_forward` is overloaded: for candidates it holds {"confidence","rationale"}.
  let confidence: number | null = null
  let rationale: string | null = null
  if (row.walk_forward) {
    try {
      const wf = JSON.parse(row.walk_forward) as { confidence?: number; rationale?: string }
      if (typeof wf.confidence === "number") confidence = wf.confidence
      if (typeof wf.rationale === "string") rationale = wf.rationale
    } catch {
      // legacy walk_forward payloads may be a different shape; ignore
    }
  }
  return {
    id: row.id,
    name: row.name,
    expression: row.expression,
    hypothesis: row.hypothesis,
    operators: parseJsonArray(row.operators),
    dataFields: parseJsonArray(row.data_fields),
    ic: row.ic,
    icir: row.icir,
    turnover: row.turnover,
    sharpe: row.sharpe,
    maxDrawdown: row.max_drawdown,
    universe: row.universe,
    period: row.period,
    confidence,
    rationale,
    status: row.status ?? "active",
    sourceExperimentId: row.source_experiment_id,
    createdAt: row.created_at,
  }
}

/** operators / data_fields are stored as JSON arrays; fall back to empty. */
function parseJsonArray(raw: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.map(String) : []
  } catch {
    return []
  }
}
