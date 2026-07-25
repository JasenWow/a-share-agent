/**
 * PersistedSpendGuard — SpendGuard that survives restarts.
 *
 * Wraps the in-memory SpendGuard and writes every recordSpend() call to
 * a `spend_log` table. On construction, it replays the relevant window
 * of rows to rebuild the daily / weekly / monthly counters via the
 * protected SpendGuard.setRawCounts() hook.
 *
 * Shares the same SQLite file as SqliteStateStore via the injected
 * Database handle (creates its own table if missing).
 *
 * Window semantics match SpendGuard exactly:
 *   - daily:   UTC midnight rollover
 *   - weekly:  rolling 7-day window anchored 6 days ago at midnight
 *   - monthly: first of the month
 *
 * The spend_log table is append-only and grows unbounded; a periodic
 * cleanup (delete rows older than 31 days) can be added later. The
 * rebuild query is window-bounded so it stays fast even with a large
 * log — it only counts rows newer than the start of the current week.
 */

import type { Database } from "bun:sqlite"
import type { BudgetPolicy } from "@aquan/core"
import { SpendGuard } from "./policy"

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS spend_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spend_log_at ON spend_log(at);
`

const INSERT_SQL = `INSERT INTO spend_log (source, at) VALUES (?, ?);`
const COUNT_SINCE_SQL = `SELECT COUNT(*) AS n FROM spend_log WHERE at >= ?;`

export class PersistedSpendGuard extends SpendGuard {
  private readonly db: Database

  constructor(policy: BudgetPolicy, db: Database, clock: () => Date = () => new Date()) {
    super(policy, clock)
    this.db = db
    this.db.run(SCHEMA_SQL)
    this.rebuildFromLog()
  }

  /**
   * Record a spend event to both the in-memory counter (via super) and
   * the durable log.
   *
   * @param source tracker name or "global"; surfaced on the dashboard
   *               so operators can see which tracker is burning budget.
   */
  recordSpend(source = "global"): void {
    super.recordSpend()
    this.db.run(INSERT_SQL, source, this.clock().toISOString())
  }

  /**
   * Rebuild daily/weekly/monthly counters from the log.
   *
   * Called once at construction. SpendGuard.maybeRollWindows already
   * snaps the window boundaries to "now"; we then count log rows in
   * each window and write them via setRawCounts().
   */
  private rebuildFromLog(): void {
    const stats = this.getStats()
    this.setRawCounts({
      daily: this.countSince(stats.dayStart),
      weekly: this.countSince(stats.weekStart),
      monthly: this.countSince(stats.monthStart),
    })
  }

  private countSince(date: Date): number {
    const row = this.db.query(COUNT_SINCE_SQL).get(date.toISOString()) as { n: number } | null
    return row?.n ?? 0
  }
}
