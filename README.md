# aquan

A-share quantitative analysis system built as a TS-primary monorepo with a Python data layer. TypeScript side (Bun workspace) hosts the dashboard, API server, and the agent orchestration engine; Python side (uv workspace) hosts MCP data servers, the ETL pipeline, and the quant metrics library.

## Repository layout

```
a-share-agents/
├── packages/                 Bun workspace — TS primary
│   ├── core/                 @aquan/core      types, errors, constants, utils
│   ├── orchestrator/         @aquan/orchestrator  Symphony-like work engine
│   ├── pi-runtime/           @aquan/pi-runtime    Pi agent runtime adapter
│   ├── server/               @aquan/server    Hono + Bun API + Drizzle
│   └── web/                  @aquan/web       Next.js 15 + shadcn/ui dashboard
│
├── python/                   uv workspace — Python data layer
│   ├── aquan/                public layer (core / utils / metrics / cli)
│   ├── mcp-servers/          4 L0 connectors (akshare/tushare/internal-store/qlib)
│   ├── etl/                  DuckDB + Parquet ETL pipeline
│   ├── notebooks/            Jupyter notebooks + helpers
│   ├── dbt/                  dbt-duckdb warehouse models (DWD/DWS/ADS)
│   └── tests/                project-level integration tests
│
├── plugins/                  ZCode/Claude plugin system (agents + skills)
├── legacy/                   deprecated / historical items (see legacy/README.md)
├── scripts/                  repo-level dev/CI tooling (check.py, validate.py, ...)
├── docs/                     specs, plans, reports, reference docs
└── data/                     runtime data (DuckDB warehouse, Qlib dump) — gitignored
```

## Quick start

### Python side

```bash
cd python
uv sync
uv run python -m etl.init                                 # one-time warehouse bootstrap
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000 &
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001 &
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002 &
```

### TypeScript side

```bash
bun install
bun run dev                  # starts @aquan/server (3001) + @aquan/web (3000) in parallel
```

### Repo-level checks

```bash
python scripts/check.py      # boundary rules + structure + env
bun run dep-check            # TS dependency boundary rules
```

See `RESTRUCTURE-PLAN.md` for the migration history (this repo was restructured from a Python-flat layout in 7 phases).

## Architecture

```
TS side (Bun workspace)              Python side (uv workspace)
─────────────────────────            ──────────────────────────
@aquan/web ──┐                       aquan.core / aquan.utils
@aquan/server┼── @aquan/core         aquan.metrics / aquan.cli
@aquan/orch. ┘        │                  │
                      ↓                  ↓
              @aquan/pi-runtime      mcp-servers/ (4× FastMCP)
                      │                  │
                      └──── MCP ─────────┘
                            HTTP
```

Four-layer agent/skill model (legacy plugins/):
**L3 Meta-Agent → L2 Agent → L1 Skill → L0 Connector**

| Layer | Component |
|---|---|
| L3 | `meta-strategist` — autonomous strategy exploration |
| L2 | `equity-researcher`, `strategy-analyst`, `portfolio-manager`, `market-monitor` |
| L1 | `market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor` |
| L0 | `aquan-akshare-server` (8000), `aquan-tushare-server` (8001), `aquan-internal-store-server` (8002), `aquan-qlib-server` (8003) |

Boundary rules: `scripts/check.py` (R1–R6 for Python) and `.dependency-cruiser.cjs` (for TS).

## Slash commands (agent skills)

| Command | Agent | Description |
|---|---|---|
| `/screen` | equity-researcher | Multi-factor stock screening |
| `/research` | equity-researcher | Single-stock deep-dive research |
| `/factor` | strategy-analyst | Factor research and validation |
| `/backtest` | strategy-analyst | Strategy backtesting with A-share constraints |
| `/optimize` | portfolio-manager | Portfolio optimization and risk management |
| `/market` | market-monitor | Market breadth and sentiment monitoring |
| `/evolve` | meta-strategist | Autonomous strategy exploration |

## Contributing

See `CONTRIBUTING.md` for the full guide. Detailed references live in `docs/draft/`.

## License

Private project — not for redistribution.
