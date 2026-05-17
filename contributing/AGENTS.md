# Contributing Guidelines

**Scope:** Engineering guidelines for this project — not a Python package, not a traditional monorepo.

## FILES

| File | Content |
|------|---------|
| `coding-standards.md` | ruff rules (120 char, double quotes, 4-space), naming, commits, PR checklist |
| `a-share-rules.md` | T+1, price limits, transaction costs, exclusion rules, factor preprocessing |
| `architecture.md` | Tech stack, four-layer architecture (L0-L3), data flow, catalogs, Meta-Agent design |
| `testing.md` | pytest conventions, integration/E2E testing, coverage targets |
| `mcp-servers.md` | FastMCP patterns, tool patterns, caching, adding tools/servers |
| `playbooks.md` | Step-by-step: add skill, agent, MCP tool, slash command, or simulation component |
| `README.md` | This directory's index |

## KEY RULES

| Rule | Source |
|------|--------|
| `uv run python scripts/check.py` must pass before any work | R0 |
| Boundary R1: MCP servers must not import Agent or Skill code | `scripts/check.py` |
| Boundary R2: Skills must not reference Agent code | `scripts/check.py` |
| Boundary R3: Agents may reference Skills but **never modify** Skill source files | `scripts/check.py` |
| Boundary R4: MCP servers are self-contained — no cross-server imports | `scripts/check.py` |
| Boundary R5: `internal-store` is the only shared data layer | `scripts/check.py` |
| Boundary R6: MCP servers contain only data access logic — no domain/business logic | `scripts/check.py` |

## ARCHITECTURE LAYERS

| Layer | Component | Location |
|-------|-----------|----------|
| L3 | Meta-Agent (autonomous exploration) | `plugins/agent-plugins/meta-strategist/` |
| L2 | Agents (workflow orchestration) | `plugins/agent-plugins/<name>/` |
| L1 | Skills (domain knowledge + scripts) | `plugins/vertical-plugins/<vertical>/skills/` |
| L0 | Connectors (MCP data access) | `mcp-servers/<name>/` |

**Dependency: downward only.** L3 → L2 → L1 → L0. Never upward.

## VERTICAL PLUGINS

Skills are organized into domain verticals:

| Vertical | Purpose |
|----------|---------|
| `market-data` | Core: data fetching, factor computation, preprocessing |
| `equity-research` | Fundamentals, financials, valuation |
| `trading-strategy` | Backtest, signal generation, risk control |
| `simulation` | Trading simulator, experiment tracking, evolution loop |
| `market-monitor` | Market breadth, northbound flow |

## AGENT CATALOG

| Agent | Trigger | Description |
|-------|---------|-------------|
| meta-strategist | `/evolve` | Autonomous strategy exploration via simulation |
| equity-researcher | `/screen`, `/research` | Stock screening + deep research + valuation |
| strategy-analyst | `/factor`, `/backtest` | Factor research + strategy + backtest |
| portfolio-manager | `/optimize` | Portfolio construction + optimization |
| market-monitor | `/market` | Market monitoring + northbound flow |

## CONVENTIONS (DEVIATIONS FROM STANDARD)

- No `__init__.py` anywhere — not a standard Python package
- Agents/skills are `.md` files — never Python packages
- Skill scripts (`scripts/*.py`) are standalone executables invoked via `uv run python`
- Tests co-located with servers as `test_server.py`, not `tests/test_*.py`
- `tests/fixtures/` is the only root-level tests directory — contains fixture data only
- Environment managed by `uv` — use `uv run` for all commands
- Stock codes: always 6-digit strings (leading zeros matter)

## MCP SERVER PATTERN

Every MCP server directory must contain:
```
mcp-servers/<name>/
├── server.py      # FastMCP app, @mcp.tool() functions
├── pyproject.toml # dependencies
└── README.md      # tool documentation
```

Entry point: `uv run uvicorn mcp-servers.<name>.server:mcp_app --port XXXX`

## INTERNAL STORE SCHEMA

The internal-store MCP server manages these tables:

| Table | Purpose |
|-------|---------|
| `query_cache` | API response cache (TTL-based) |
| `backtest_results` | Backtest outputs |
| `portfolio` | Portfolio state |
| `experiments` | Meta-Agent experiment records (hypothesis, params, result, lineage) |
| `transitions` | RL transitions (state, strategy, reward, next_state) |
| `episode_summaries` | Simulation run summaries (period, capital, final_nav) |
