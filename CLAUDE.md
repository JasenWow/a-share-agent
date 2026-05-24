# CLAUDE.md

A-share quantitative analysis system. Python 3.10+, FastMCP, plugin architecture. Output in Chinese; technical terms in English.

## Start

```bash
uv sync
uv run python scripts/check.py
```

## MCP Servers

```bash
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002
```

## Architecture

L3 Meta-Agent → L2 Agent → L1 Skill → L0 Connector

Agents: `/screen`, `/research`, `/factor`, `/backtest`, `/optimize`, `/market`, `/evolve`

## Contributing

See `CONTRIBUTING.md` — everything is there.