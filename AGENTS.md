# AGENTS.md

A-share quantitative analysis system. TS-primary monorepo (Bun workspace) with a Python data layer (uv workspace under `python/`). FastMCP-based connectors, plugin architecture for agent skills.

## Quick start

```bash
# Python side — all Python code lives under python/
cd python
uv sync
# Start MCP servers (each in its own terminal):
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# TS side — from repo root
bun install
bun run dev                  # @aquan/server (3001) + @aquan/web (3000)

# Repo-level structure check — run from repo root, not python/
python scripts/check.py
```

## Repository layout (post-restructure)

| Path | What |
|---|---|
| `packages/` | Bun workspace: `@aquan/{core, orchestrator, pi-runtime, server, web}` |
| `python/` | uv workspace: `aquan/` (public layer), `mcp-servers/`, `etl/`, `notebooks/`, `dbt/`, `tests/` |
| `plugins/` | ZCode/Claude plugin system (L1 skills + L2/L3 agents). Unchanged by restructure. |
| `scripts/` | Repo-level dev tooling: `check.py` (boundary rules), `validate.py`, `sync-agent-skills.py` |
| `legacy/` | Deprecated / historical items. See `legacy/README.md` for fate of each. |
| `docs/` | Specs, plans, reports, reference docs (`docs/draft/`, `docs/superpowers/`) |
| `data/` | Runtime data (gitignored). DuckDB warehouse, Qlib dump. |

Migration history: see `RESTRUCTURE-PLAN.md` (7-phase migration from a Python-flat layout).

## Architecture

### Agent / skill layers

Four-layer: **L3 Meta-Agent → L2 Agent → L1 Skill → L0 Connector**

| Layer | Component |
|---|---|
| L3 | `meta-strategist` — autonomous strategy exploration |
| L2 | `equity-researcher`, `strategy-analyst`, `portfolio-manager`, `market-monitor` |
| L1 | `market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor` |
| L0 | `aquan-akshare-server` (8000), `aquan-tushare-server` (8001), `aquan-internal-store-server` (8002), `aquan-qlib-server` (8003) |

### TS package boundaries

Enforced by `.dependency-cruiser.cjs`:
- `@aquan/core` depends on nothing internal
- `@aquan/{server, web, orchestrator, pi-runtime}` may depend on `@aquan/core`
- `@aquan/orchestrator` and `@aquan/pi-runtime` must NOT depend on `@aquan/{server, web}`

### Python boundary rules

Enforced by `scripts/check.py` (R1–R6):
- **R1**: MCP servers must NOT import `plugins/` code
- **R4**: No cross-server imports between MCP servers
- **R6**: MCP servers should NOT contain domain logic

## Working directory conventions

| Operation | Where |
|---|---|
| Python tests / uvicorn / ETL | `cd python && uv run ...` |
| TS dev / build / db migrations | repo root, `bun run ...` |
| Repo-level boundary check | repo root, `python scripts/check.py` |
| dbt commands | `cd python/dbt && dbt ...` |

## Contributing

Full guidelines → `CONTRIBUTING.md`. Detailed references in `docs/draft/`.
