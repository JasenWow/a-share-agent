# Architecture

> A-Share Agents' static architecture: tech stack, project layout, three-layer architecture, dependency rules, and data flow.

## Tech Stack

- **Language**: Python 3.10+
- **MCP Framework**: FastMCP (`mcp.server.fastmcp`)
- **HTTP Transport**: uvicorn (ASGI)
- **Data Sources**: AKShare (free, real-time), Tushare (token, historical)
- **Local Storage**: SQLite (metadata), Parquet (cached data)
- **Testing**: pytest, pytest-mock
- **Linting**: ruff
- **Agent Host**: Claude Code with custom plugins

## Project Layout

```
a-share-agents/
├── plugins/                          # Plugin directory
│   ├── agent-plugins/                # Agent plugins (one per agent)
│   │   ├── stock-screener/           # Stock screening agent
│   │   ├── equity-researcher/        # Single-stock research agent
│   │   ├── factor-analyst/           # Factor research agent
│   │   ├── backtester/               # Strategy backtesting agent
│   │   ├── portfolio-manager/        # Portfolio management agent
│   │   └── market-monitor/           # Market monitoring agent
│   └── vertical-plugins/             # Domain skill packages
│       └── a-share-analysis/         # A-share analysis skill pack
│           ├── skills/               # Skill definitions (SKILL.md + prompt.md)
│           ├── commands/             # Slash command definitions (*.json)
│           ├── .mcp.json             # MCP connector config for this plugin
│           └── plugin.json           # Plugin manifest
├── mcp-servers/                      # MCP Server implementations
│   ├── akshare-server/               # AKShare data server
│   ├── tushare-server/               # Tushare data server
│   └── internal-store/               # Local cache and state store
├── scripts/                          # Utility scripts
│   ├── sync-agent-skills.py          # Sync skills to agent directories
│   ├── check.py                      # Environment verification
│   └── init-data.py                  # Initialize local data
├── data/                             # Local data (.gitignore)
│   ├── cache/                        # Cached data (akshare/, tushare/, meta.db)
│   ├── backtest/                     # Backtest results
│   └── logs/                         # Server logs
├── docs/                             # Design documents
├── contributing/                     # This directory — engineering how-to
├── .mcp.json                         # Project-level MCP config
├── .env.example                      # Environment variable template
├── .gitignore
└── CLAUDE.md                         # Claude Code project instructions
```

## Three-Layer Architecture

The system is organized into three layers with a **downward-only dependency rule**. Higher layers may reference lower layers; lower layers must never reference higher ones.

```text
L2  Agent Layer  (workflow orchestration)
    plugins/agent-plugins/<name>/
    ├── AGENT.md              Persona, deliverables, workflow, guardrails
    ├── system-prompt.md      System prompt for Claude
    └── plugin.json           Skills list, commands, MCP dependencies
    ↓ may use
L1  Skill Layer  (domain knowledge + executable logic)
    plugins/vertical-plugins/a-share-analysis/skills/<name>/
    ├── SKILL.md              Trigger conditions, inputs, outputs, steps
    ├── prompt.md             Execution prompt template
    ├── scripts/              Domain logic (Python, invoked by agents via Bash)
    ├── references/           Lookup tables, formulas, thresholds
    └── examples/             Input/output examples
    ↓ may use
L0  Connector Layer  (MCP data access only)
    mcp-servers/<name>/server.py
    ├── @mcp.tool()           One function per data endpoint
    └── .mcp.json             Server URL and transport config
```

### Boundary Rules

These rules are enforced by `scripts/check.py` where possible.

| Rule | Statement |
|------|-----------|
| **R1** | MCP Server code (`mcp-servers/`) must not import Agent or Skill code (`plugins/`). |
| **R2** | Skill definitions (`skills/`) must not import or reference Agent code (`agent-plugins/`). |
| **R3** | Agents may reference Skill definitions but must never modify Skill source files. |
| **R4** | Each MCP Server must be self-contained — no cross-server imports between `akshare-server/`, `tushare-server/`, `internal-store/`. |
| **R5** | `mcp-servers/internal-store/` is the only shared data layer. All servers read/write through it, never through each other. |
| **R6** | MCP servers must contain only data access logic — no domain/business logic (e.g., no factor calculation, backtest logic, or screening rules). Domain logic belongs in skill `scripts/`. |

## Data Flow

```
User (CLI / slash command / natural language)
  │
  ▼
Agent Layer — parses intent, orchestrates workflow
  │
  ▼
Skill Layer — applies domain knowledge, calculation methodology
  │
  ▼
Connector Layer — fetches data via MCP tools
  │
  ├──→ AKShare MCP Server (localhost:8000)  — real-time quotes, northbound flow, dragon-tiger
  ├──→ Tushare MCP Server (localhost:8001)  — financials, index weights, historical
  └──→ Internal Store (localhost:8002)      — cache, backtest results, portfolio state
```

Two data access patterns exist:

1. **Direct pull**: Agent calls MCP tool → server fetches from external API → returns data.
2. **Cache-first**: Agent calls Internal Store → cache hit → return local data. Cache miss → fall back to direct pull.

## Agent Catalog

| Agent | Directory | Trigger | Description |
|-------|-----------|---------|-------------|
| stock-screener | `agent-plugins/stock-screener/` | `/screen` | Multi-factor stock screening with A-share exclusion rules |
| equity-researcher | `agent-plugins/equity-researcher/` | `/research` | Single-stock deep-dive: financials, valuation, catalysts |
| factor-analyst | `agent-plugins/factor-analyst/` | `/factor` | Factor construction, IC/ICIR analysis, walk-forward validation |
| backtester | `agent-plugins/backtester/` | `/backtest` | Strategy backtesting with T+1, price limits, transaction costs |
| portfolio-manager | `agent-plugins/portfolio-manager/` | `/optimize` | Portfolio optimization (MVO, HRP, Risk Parity), risk monitoring |
| market-monitor | `agent-plugins/market-monitor/` | `/market` | Market breadth, northbound flow, dragon-tiger, regime detection |

## Skill Catalog

Skills are grouped by domain under `plugins/vertical-plugins/a-share-analysis/skills/`.

| Skill | Directory | Used By |
|-------|-----------|---------|
| factor-screen | `skills/factor-screen/` | stock-screener |
| financial-analysis | `skills/financial-analysis/` | equity-researcher |
| factor-research | `skills/factor-research/` | factor-analyst |
| backtest-engine | `skills/backtest-engine/` | backtester |
| portfolio-optimize | `skills/portfolio-optimize/` | portfolio-manager |
| market-breadth | `skills/market-breadth/` | market-monitor |
| xlsx-author | `skills/xlsx-author/` | all agents (shared utility) |

## Connector Catalog

| Server | URL | Transport | Auth | Data |
|--------|-----|-----------|------|------|
| AKShare | `localhost:8000/mcp` | HTTP (FastMCP) | None | Real-time quotes, OHLCV, northbound flow, dragon-tiger, Shenwan classification |
| Tushare | `localhost:8001/mcp` | HTTP (FastMCP) | Token (`TUSHARE_TOKEN`) | Financial statements, index weights (point-in-time), concept sectors |
| Internal Store | `localhost:8002/mcp` | HTTP (FastMCP) | None | Cache queries, backtest results, portfolio state |

## Common Commands

```bash
# Environment
python scripts/check.py            # Verify all dependencies and configs
python scripts/sync-agent-skills.py # Sync skills to agent directories

# MCP Servers
uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# Code quality
ruff check .                       # Lint
ruff format .                      # Format

# Testing
pytest                             # Unit tests
pytest -m integration              # Integration tests (requires MCP servers running)
pytest -m e2e                      # End-to-end tests
```

## Language Distribution

| Language | Purpose | Location |
|----------|---------|----------|
| Python | MCP servers, skill scripts, utility scripts | `mcp-servers/`, `skills/*/scripts/`, `scripts/` |
| Markdown | Agent manifests, skill definitions, references | `plugins/`, `contributing/`, `skills/*/references/` |
| JSON | Command definitions, plugin configs | `plugins/*/commands/`, `plugin.json` |
| SQL | Database schema | `mcp-servers/internal-store/schema.sql` |
| YAML | Future: CI/CD, Docker Compose | — |
