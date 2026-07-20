# A-Share Dashboard MVP (子项目 ❺)

Roadmap MVP scope: two warehouse-backed pages for daily research workflow.

## Pages

| Route | Page | Source | Purpose |
|---|---|---|---|
| `/factors` | Factor Comparison | `ods_factor_experiments` | All factors from latest snapshot, ranked by ICIR |
| `/backtests` | Backtest History | `ods_backtest_runs` | All backtest runs from latest snapshot, ranked by Sharpe |

## Setup

1. **Register the DuckDB warehouse** in `/databases`:
   - Type: `duckdb`
   - File path: the value of `WAREHOUSE_DUCKDB_PATH` (default `../data/warehouse/meta.db`)
   - The A-share pages will auto-detect the first DuckDB-typed database as the warehouse
   - To override, set `localStorage['a-share-warehouse-db-id'] = '<database-id>'`

2. **Ingest data** (run from a-share-agents root):
   ```bash
   uv run python -m scripts.etl.init
   # Make sure internal-store MCP is running on :8002, then:
   uv run python -m scripts.etl.runner factor_experiments --date 20260719
   uv run python -m scripts.etl.runner backtest_runs --date 20260719
   ```

3. **View**:
   - Start chat-database: `cd chat-database && bun run dev`
   - Open `http://localhost:3000/factors` and `/backtests`

## Architecture

```
chat-database/packages/web/
  app/(main)/
    factors/page.tsx        ← factor comparison (MVP)
    backtests/page.tsx      ← backtest history (MVP)
  api-clients/
    a-share.ts              ← queryWarehouse() + pre-baked SQL per page
  components/sidebar/
    app-sidebar.tsx         ← nav items for /factors and /backtests
```

Each page:
1. Resolves the warehouse DB ID (localStorage → auto-detect first duckdb DB)
2. Runs pre-baked SQL via the existing `/database/query` endpoint
3. Renders results with shadcn/ui Table + stat cards

The pre-baked SQL takes the **latest snapshot per entity** (factors ranked by ICIR, backtests by Sharpe), matching the metric semantic layer definitions in `metrics/metrics.yml`.

## MVP vs Full (M6)

| Feature | MVP (this sub-project) | Full (M6, future) |
|---|---|---|
| Factor comparison | Table + ICIR ranking | + IC time-series, decay curve, layered returns |
| Backtest history | Table + Sharpe ranking | + nav-curve comparison, Sharpe/MaxDD scatter |
| Strategy overview | — | strategy list + hypothesis + history |
| Market observation | — | northbound flow, industry heatmap |

## Why no separate API routes

The pages reuse the existing generic `/database/query` endpoint with `databaseId=<warehouse>`. Pre-baked SQL lives in `api-clients/a-share.ts` so it's auditable in one place and benefits from the warehouse's read-only access pattern. No new server-side routes needed.
