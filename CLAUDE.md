# CLAUDE.md — A-Share Agents

## Project Overview
A-share quantitative analysis Agent system built on MCP data connectors and a plugin architecture.

## Architecture
- Agent → Skill → Connector (three-layer, downward-only dependency)
- Agent plugins: `plugins/agent-plugins/`
- Vertical plugin (skills + commands): `plugins/vertical-plugins/a-share-analysis/`
- MCP servers: `mcp-servers/` (AKShare, Tushare, Internal Store)

## Key Conventions
- Plugin directory: `.claude-plugin/plugin.json` for metadata
- Agent definitions: `agents/<name>.md` with YAML frontmatter
- Skill definitions: `skills/<name>/SKILL.md`
- Commands: `commands/*.md` with YAML frontmatter
- MCP config: `.mcp.json` (type: "http")
- Data sources: AKShare (free/realtime) + Tushare (token/high-quality)
- All analysis output in Chinese, technical terms keep English

## Commands
- `/screen [filters]` — Multi-factor stock screening
- `/research <code>` — Deep financial analysis
- `/factor <name>` — Factor research and validation
- `/backtest [strategy]` — Strategy backtesting
- `/optimize [method]` — Portfolio optimization
- `/market [focus]` — Market breadth and sentiment

## MCP Servers
- AKShare: http://localhost:8000/mcp
- Tushare: http://localhost:8001/mcp
- Internal Store: http://localhost:8002/mcp

## Before Working
1. Run `python scripts/check.py` to verify environment
2. Ensure MCP servers are running
3. Check `TUSHARE_TOKEN` is set

## A-Share Constraints
- T+1 settlement (buy today, sellable tomorrow)
- Board price limits: main ±10%, ChiNext/STAR ±20%, BSE ±30%, ST ±5%
- Transaction costs: commission 0.025%, stamp duty 0.05% sell-only
- Lot size: 100 shares minimum
- Industry: Shenwan Level 1 (31 sectors)
- Exclusions: ST/*ST, suspended, listed < 1 year, delisted

## Contributing
See `contributing/` directory for full guidelines.
