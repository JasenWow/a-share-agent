# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A-share quantitative analysis Agent system. Python 3.10+, FastMCP for data connectors, plugin architecture for agents/skills. All analysis output in Chinese, technical terms keep English.

## Architecture

Three-layer, downward-only dependency: **Agent (L2) → Skill (L1) → Connector (L0)**

```
Agent plugins   plugins/agent-plugins/<name>/agents/<name>.md
                   ↓ may reference
Skills          plugins/vertical-plugins/a-share-analysis/skills/<name>/SKILL.md
                   ↓ may call
MCP Servers     mcp-servers/<name>/server.py  (@mcp.tool() functions)
```

Boundary rules enforced by `scripts/check.py`:
- **R1**: MCP servers must not import Agent or Skill code
- **R2**: Skills must not reference Agent code
- **R3**: Agents may reference Skills but never modify Skill source files
- **R4**: MCP servers are self-contained — no cross-server imports
- **R5**: `internal-store` is the only shared data layer

6 agents: `stock-screener`, `equity-researcher`, `factor-analyst`, `backtester`, `portfolio-manager`, `market-monitor`

7 skills: `factor-screen`, `financial-analysis`, `factor-research`, `backtest-engine`, `portfolio-optimize`, `market-breadth`, `xlsx-author`

## Development Commands

```bash
# Environment verification
python scripts/check.py
python scripts/validate.py                    # Validate plugin/skill structure
python scripts/sync-agent-skills.py            # Sync skills into agent dirs
python scripts/sync-agent-skills.py --check    # Check sync status

# Start MCP servers
uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# Lint and format
ruff check .
ruff format .

# Test
pytest                    # Unit tests
pytest -m integration     # Integration tests (MCP servers must be running)
pytest -m e2e             # End-to-end tests (uses fixture data)
pytest tests/test_foo.py  # Single test file
pytest -x                 # Stop on first failure
pytest --cov=mcp_servers  # Coverage report
```

## Plugin Conventions

- Plugin metadata: `.claude-plugin/plugin.json` (name, version, description)
- Agent definitions: `agents/<name>.md` with YAML frontmatter (`name`, `description`, `tools`)
- Skill definitions: `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description` with trigger phrases)
- Commands: `commands/*.md` with YAML frontmatter (`description`, `argument-hint`)
- Plugin registry: `.claude-plugin/marketplace.json`
- MCP config: `.mcp.json` (type: "http")

Slash commands: `/screen`, `/research`, `/factor`, `/backtest`, `/optimize`, `/market`

## MCP Server Patterns

All servers use FastMCP (`mcp.server.fastmcp`), export ASGI app via `mcp.streamable_http_app()`, and follow the same patterns:

```python
@mcp.tool()
def tool_name(param: str) -> list[dict]:
    """Docstring is mandatory — becomes tool description for agents."""
    try:
        df = external_api_call(param)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "tool_name", "params": {"param": param}}]
```

Key rules:
- One `@mcp.tool()` per external API function
- Type hints on all parameters; default values for optional ones
- Return `list[dict]` via `df_to_json()` (max 5000 rows, NaN → "NaN" string)
- Never raise unhandled exceptions — catch and return error dicts
- `df_to_json()` helper converts DataFrames consistently

Ports: AKShare 8000, Tushare 8001, Internal Store 8002

## Coding Standards

- **ruff**: line length 120, double quotes, 4-space indent
- **Naming**: kebab-case dirs, snake_case Python, PascalCase classes
- **Stock codes**: always 6-digit strings (leading zeros matter). Tushare codes include suffix (`000001.SZ`), AKShare codes are bare (`000001`)
- **Dates**: `YYYYMMDD` strings for API calls, convert to `datetime` only for calculations
- **NaN**: use pandas NaN-aware methods, never let NaN silently propagate
- **No `print()`** in production code — use `logging`
- **Commits**: conventional commits with squash-merge (`feat:`, `fix:`, `chore:`, etc.)
- **Tests**: co-located `test_*.py`, table-driven with `@pytest.mark.parametrize`

## A-Share Market Constraints

- **T+1**: stocks bought today cannot be sold until tomorrow. Backtest label: `Close(T+2) / Open(T+1) - 1`
- **Board price limits**: main ±10%, ChiNext/STAR ±20%, BSE ±30%, ST ±5%
- **Transaction costs**: commission 0.025% each side, stamp duty 0.05% sell-only, slippage ~0.05%
- **Lot size**: 100 shares minimum, round down when buying
- **Industry**: Shenwan Level 1 (31 sectors)
- **Exclusions**: ST/*ST, suspended, listed < 1 year, delisted, limit-up/limit-down
- **Factor preprocessing**: MAD Winsorization (3σ) → ZScore → [Optional] Industry + Cap Neutralization
- **Market calendar**: use A-share trading calendar (Tushare `exchange_cal`) for backtests

## Data Source Priority

Tushare first (high quality, requires `TUSHARE_TOKEN`), AKShare second (free, realtime), user-provided data last. Never web search.

## Before Working

1. Run `python scripts/check.py` to verify environment
2. Ensure MCP servers are running
3. Check `TUSHARE_TOKEN` is set in `.env`

## Contributing

See `contributing/` for detailed guidelines on architecture, coding standards, testing, MCP server development, playbooks, and A-share rules.
