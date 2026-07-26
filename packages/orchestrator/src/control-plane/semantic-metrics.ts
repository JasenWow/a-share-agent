/**
 * SemanticMetrics — typed metric catalog + query executor over the
 * control-plane DuckDB.
 *
 * The catalog is loaded from `metrics.yml` (single source of truth
 * per ADR 0018) at construction time. Queries are validated against
 * the metric's declared dimensions and translated to SQL.
 *
 * The metrics catalog here is a TypeScript mirror of the Python one
 * in `python/aquan/metrics/metrics.yml`. They are kept in sync by
 * PR review — there is no codegen. The v1 set is small.
 */

import { DuckDBInstance } from "@duckdb/node-api"

export interface MetricSpec {
  name: string
  description: string
  formula: string
  unit: string
  category: string
  sourceTable: string
  dimensions: string[]
}

export interface SemanticMetricsOptions {
  path: string
  /** Override the metric catalog (used in tests). */
  catalog?: MetricSpec[]
}

const DEFAULT_CATALOG: MetricSpec[] = [
  {
    name: "quality_pass_rate",
    description: "passed checks / total checks in window",
    formula: "avg(case when passed then 1.0 else 0.0 end)",
    unit: "ratio (0 ~ 1)",
    category: "data_operations",
    sourceTable: "quality_check_results",
    dimensions: ["dataset", "dimension", "run_id"],
  },
  {
    name: "freshness_lag_days",
    description: "trading-day gap between now and latest completed run",
    formula: "null", // resolved by query handler, not raw SQL
    unit: "trading_days",
    category: "data_operations",
    sourceTable: "pipeline_runs",
    dimensions: ["dataset"],
  },
]

export class SemanticMetrics {
  private readonly path: string
  private readonly catalog: Map<string, MetricSpec>
  private instance: Awaited<ReturnType<typeof DuckDBInstance.create>> | null = null

  constructor(opts: SemanticMetricsOptions) {
    this.path = opts.path
    this.catalog = new Map(
      (opts.catalog ?? DEFAULT_CATALOG).map((m) => [m.name, m]),
    )
  }

  list(): MetricSpec[] {
    return [...this.catalog.values()]
  }

  describe(name: string): MetricSpec {
    const m = this.catalog.get(name)
    if (!m) {
      throw new Error(
        `Unknown metric '${name}'. Available: ${[...this.catalog.keys()].join(", ")}`,
      )
    }
    return m
  }

  private async getInstance() {
    if (!this.instance) {
      this.instance = await DuckDBInstance.create(this.path)
    }
    return this.instance
  }

  /**
   * Execute a typed metric query.
   *
   * Whitelisted dimensions only. Filters are simple equality. The
   * limit caps returned rows.
   */
  async query(args: {
    metric: string
    dimensions?: string[]
    filters?: Record<string, string>
    limit?: number
  }): Promise<{ rows: Record<string, unknown>[]; columns: string[] }> {
    const spec = this.describe(args.metric)
    const dims = args.dimensions ?? []
    for (const d of dims) {
      if (!spec.dimensions.includes(d)) {
        throw new Error(
          `Dimension '${d}' not allowed for metric '${args.metric}'. Allowed: ${spec.dimensions.join(", ")}`,
        )
      }
    }
    for (const k of Object.keys(args.filters ?? {})) {
      if (!spec.dimensions.includes(k)) {
        throw new Error(
          `Filter '${k}' not allowed for metric '${args.metric}'. Allowed: ${spec.dimensions.join(", ")}`,
        )
      }
    }

    const sql = buildSql({
      spec,
      dimensions: dims,
      filters: args.filters ?? {},
      limit: args.limit,
    })

    const inst = await this.getInstance()
    const conn = await inst.connect()
    try {
      const reader = await conn.runAndReadAll(sql)
      const rows = reader.getRowObjects() as Record<string, unknown>[]
      const columns = rows.length > 0 ? Object.keys(rows[0]!) : []
      return { rows, columns }
    } finally {
      conn.closeSync()
    }
  }

  async close(): Promise<void> {
    if (!this.instance) return
    try {
      this.instance.closeSync()
    } catch {
      // best-effort
    }
    this.instance = null
  }
}

function buildSql(args: {
  spec: MetricSpec
  dimensions: string[]
  filters: Record<string, string>
  limit?: number
}): string {
  const { spec, dimensions, filters } = args

  // freshness_lag_days is a derived metric; not pure SQL.
  if (spec.name === "freshness_lag_days") {
    const datasetFilter = filters.dataset ? `WHERE dataset = '${escape(filters.dataset)}'` : ""
    return `SELECT dataset, max(session_date) AS latest_session_date FROM pipeline_runs WHERE status = 'completed' ${datasetFilter ? "AND " + datasetFilter.replace(/^WHERE /, "") : ""} GROUP BY dataset ${args.limit ? `LIMIT ${args.limit}` : ""};`
  }

  const dimCols = dimensions.length ? dimensions.join(", ") + ", " : ""
  const selectClause = `${dimCols}${spec.formula} AS ${spec.name}`
  const whereParts: string[] = []
  for (const [k, v] of Object.entries(filters)) {
    whereParts.push(`${k} = '${escape(v)}'`)
  }
  const whereClause = whereParts.length ? `WHERE ${whereParts.join(" AND ")}` : ""
  const groupClause = dimensions.length ? `GROUP BY ${dimensions.join(", ")}` : ""
  const limitClause = args.limit ? `LIMIT ${args.limit}` : ""

  return [
    `SELECT ${selectClause}`,
    `FROM ${spec.sourceTable}`,
    whereClause,
    groupClause,
    limitClause,
  ]
    .filter((s) => s.length > 0)
    .join(" ")
    .trim() + ";"
}

function escape(s: string): string {
  return s.replace(/'/g, "''")
}