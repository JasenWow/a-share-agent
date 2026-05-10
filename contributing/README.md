# Contributing to A-Share Agents

> Engineering guide for human contributors and AI agents working on the A-share quantitative analysis system. Start here, then open the specific file you need.

A-Share Agents is an AI-assisted quantitative research and investment decision-support platform for China's A-share market. It follows a three-layer architecture: **Agent** (workflow orchestration) → **Skill** (domain knowledge) → **Connector** (MCP data access). The system covers stock screening, factor research, strategy backtesting, portfolio management, and market monitoring — all with built-in A-share market constraints (T+1, price limits, stamp duty).

## First-Time Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify environment
python scripts/check.py

# 4. Configure environment variables
cp .env.example .env
# Edit .env and add your TUSHARE_TOKEN

# 5. Start MCP servers
uvicorn mcp-servers.akshare-server.server:mcp_app --host 0.0.0.0 --port 8000 &
uvicorn mcp-servers.tushare-server.server:mcp_app --host 0.0.0.0 --port 8001 &
uvicorn mcp-servers.internal-store.server:mcp_app --host 0.0.0.0 --port 8002 &
```

## Slash Commands

| Command | Agent | Description |
|---------|-------|-------------|
| `/screen` | stock-screener | Multi-factor stock screening |
| `/research` | equity-researcher | Single-stock deep-dive research |
| `/factor` | factor-analyst | Factor research and validation |
| `/backtest` | backtester | Strategy backtesting with A-share constraints |
| `/optimize` | portfolio-manager | Portfolio optimization and risk management |
| `/market` | market-monitor | Market breadth and sentiment monitoring |

## Files in This Directory

| File | Scope |
|------|-------|
| `architecture.md` | Tech stack, project layout, three-layer architecture (R1–R5), data flow, agent/skill/connector catalogs |
| `coding-standards.md` | ruff rules, naming conventions, commit convention, PR checklist |
| `testing.md` | pytest conventions, MCP integration testing, E2E testing, coverage targets |
| `mcp-servers.md` | FastMCP patterns, tool definition, caching strategy, adding new tools and servers |
| `playbooks.md` | Step-by-step checklists — adding a new skill, agent, MCP tool, or slash command |
| `a-share-rules.md` | A-share market rules reference: T+1, price limits, costs, exclusion rules, Shenwan classification |

## Design Documents

Full system design documents live in `docs/交易系统构建设计/`:

| Document | Content |
|----------|---------|
| `00-系统架构总览.md` | System architecture overview, three layers, security design |
| `01-Agent设计.md` | Six agent system prompts (Persona → Deliverables → Workflow → Guardrails) |
| `02-技能设计.md` | Seven skill definitions with workflows, data sources, and output templates |
| `03-MCP数据连接器设计.md` | MCP server design, AKShare/Tushare/Internal Store implementation |
| `04-目录结构与实现指南.md` | Directory structure, file naming, templates, sync and check scripts |
| `05-分阶段实施路线图.md` | Six-phase implementation roadmap |
