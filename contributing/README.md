# Contributing to A-Share Agents

> Engineering guide for human contributors and AI agents working on the A-share quantitative analysis system. Start here, then open the specific file you need.

A-Share Agents is an AI-assisted quantitative research and investment decision-support platform for China's A-share market. It follows a four-layer architecture: **Meta-Agent** (autonomous exploration) → **Agent** (workflow orchestration) → **Skill** (domain knowledge + scripts) → **Connector** (MCP data access). The system covers stock screening, factor research, strategy backtesting, portfolio management, market monitoring, and autonomous strategy evolution — all with built-in A-share market constraints (T+1, price limits, stamp duty).

## First-Time Setup

```bash
# 1. Install dependencies (managed by uv)
uv sync

# 2. Verify environment
uv run python scripts/check.py

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your TUSHARE_TOKEN

# 4. Start MCP servers
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --host 0.0.0.0 --port 8000 &
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --host 0.0.0.0 --port 8001 &
uv run uvicorn mcp-servers.internal-store.server:mcp_app --host 0.0.0.0 --port 8002 &
```

## Slash Commands

| Command | Agent | Description |
|---------|-------|-------------|
| `/screen` | equity-researcher | Multi-factor stock screening |
| `/research` | equity-researcher | Single-stock deep-dive research |
| `/factor` | strategy-analyst | Factor research and validation |
| `/backtest` | strategy-analyst | Strategy backtesting with A-share constraints |
| `/optimize` | portfolio-manager | Portfolio optimization and risk management |
| `/market` | market-monitor | Market breadth and sentiment monitoring |
| `/evolve` | meta-strategist | Autonomous strategy exploration |

## Files in This Directory

| File | Scope |
|------|-------|
| `architecture.md` | Tech stack, four-layer architecture (L0–L3), Meta-Agent design, data flow, agent/skill/connector catalogs |
| `coding-standards.md` | ruff rules, naming conventions, commit convention, PR checklist |
| `testing.md` | pytest conventions, MCP integration testing, E2E testing, coverage targets |
| `mcp-servers.md` | FastMCP patterns, tool definition, caching strategy, adding new tools and servers |
| `playbooks.md` | Step-by-step checklists — adding a new skill, agent, MCP tool, slash command, or simulation component |
| `a-share-rules.md` | A-share market rules reference: T+1, price limits, costs, exclusion rules, Shenwan classification |
| `notebooks.md` | Jupyter notebook conventions: MCP tool access, kernel setup, CI execution via nbconvert |

## Quick Architecture Reference

```
L3  meta-strategist      /evolve     Autonomous strategy exploration
L2  equity-researcher    /screen     Stock screening + research
    strategy-analyst     /factor     Factor + strategy + backtest
    portfolio-manager    /optimize   Portfolio optimization
    market-monitor       /market     Market monitoring
L1  market-data                      Data fetch, factor compute, preprocess
    equity-research                   Financials, valuation
    trading-strategy                  Backtest, signals, risk control
    simulation                        Trading simulator, experiments, evolution
    market-monitor                    Breadth, northbound
L0  akshare-server                   Real-time quotes (port 8000)
    tushare-server                    Historical data (port 8001)
    internal-store                    Cache + experiments + memory (port 8002)
```

See `architecture.md` for full details.
