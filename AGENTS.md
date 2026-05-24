# AGENTS.md

A-share quantitative analysis system. Python 3.10+, FastMCP, plugin architecture.

## Quick Start

```bash
uv sync
uv run python scripts/check.py
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002
```

## Architecture

Four-layer: **L3 Meta-Agent → L2 Agent → L1 Skill → L0 Connector**

| Layer | Component |
|-------|-----------|
| L3 | `meta-strategist` — autonomous strategy exploration |
| L2 | `equity-researcher`, `strategy-analyst`, `portfolio-manager`, `market-monitor` |
| L1 | `market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor` |
| L0 | `akshare-server` (8000), `tushare-server` (8001), `internal-store` (8002) |

Boundary rules in `scripts/check.py` (R1–R6).

## Contributing

Full guidelines → `CONTRIBUTING.md`. Detailed references in `docs/draft/`.