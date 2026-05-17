# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A-share quantitative analysis Agent system. Python 3.10+, FastMCP for data connectors, plugin architecture for agents/skills. All analysis output in Chinese, technical terms keep English.

## Architecture

Four-layer, downward-only dependency: **Meta-Agent (L3) → Agent (L2) → Skill (L1) → Connector (L0)**

- **L3 Meta-Agent**: `meta-strategist` — autonomous strategy exploration via simulation
- **L2 Agents**: `equity-researcher`, `strategy-analyst`, `portfolio-manager`, `market-monitor`
- **L1 Skills**: organized by vertical (`market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor`)
- **L0 Connectors**: `akshare-server` (8000), `tushare-server` (8001), `internal-store` (8002)

Boundary rules enforced by `scripts/check.py`: R1–R6. See `contributing/architecture.md`.

## Quick Start

```bash
uv sync                                         # Install dependencies
uv run python scripts/check.py                  # Verify environment
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002
```

## Contributing

All engineering guidelines live in `contributing/`:

| File | Content |
|------|---------|
| `architecture.md` | Four-layer architecture, Meta-Agent, Trading Simulator, Memory Store, catalogs |
| `coding-standards.md` | ruff rules, naming, commits, PR checklist |
| `a-share-rules.md` | T+1, price limits, costs, exclusions, factor preprocessing |
| `mcp-servers.md` | FastMCP patterns, caching, adding tools/servers |
| `playbooks.md` | Step-by-step: add skill, agent, MCP tool, simulation component, factor |
| `testing.md` | pytest conventions, coverage targets |

Start with `contributing/README.md`.
