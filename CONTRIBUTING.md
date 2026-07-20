# Contributing to aquan

> Engineering guide for human contributors and AI agents. See `docs/draft/` for detailed references and `RESTRUCTURE-PLAN.md` for the migration history.

## Quick setup

```bash
# Python side (all Python under python/)
cd python
uv sync                                # installs aquan + etl + dev deps
uv run pytest                          # full Python test suite
# Start MCP servers (each in its own terminal):
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000 &
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001 &
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002 &

# TS side (from repo root)
bun install
bun run dev                            # @aquan/server (3001) + @aquan/web (3000)

# Repo-level check (from repo root, not python/)
cp .env.example .env && $EDITOR .env   # add TUSHARE_TOKEN
python scripts/check.py                # must pass before any work
```

## Branching

- **PRs target `develop`** — never `main`
- Branch: `feat/short-desc`, `fix/issue-N`, `refactor/...`, `docs/...`
- One logical change per branch

## Commit Messages

Format: `<type>: description (#PR)`

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `ci`, `perf`

Example: `feat: add northbound flow MCP tool (#42)`

## Code Quality

Python side (from `python/`):

```bash
cd python
uv run ruff check . && uv run ruff format .  # Lint + format
uv run pytest                                 # full Python test suite
uv run pytest -m "integration"                # Integration (servers must run)
```

TS side (from repo root):

```bash
bun run typecheck        # tsc --noEmit across all packages
bun run test             # bun test across all packages
bun run dep-check        # dependency-cruiser boundary rules
```

**Rules (zero tolerance)**:
- `E501` — line > 120 chars
- `F401` / `F841` — unused import / variable
- `B006` — mutable default arg (`def f(x=[])` → `def f(x=None)`)
- `T201` — `print()` in production → use `logging`
- Bare `except` — always catch specific exception

**A-share specifics**:
- Stock codes are **6-digit strings** — `000001`, never `1`
- Dates are `YYYYMMDD` strings
- NaN → `"NaN"` string in JSON output

## Architecture

Four-layer, **downward-only** dependency:

```
L3  meta-strategist     /evolve     Autonomous strategy exploration
L2  equity-researcher   /screen     Stock screening + research
    strategy-analyst    /factor     Factor + strategy + backtest
    portfolio-manager   /optimize   Portfolio optimization
    market-monitor      /market     Market monitoring
L1  market-data                      Data fetch, factor compute, preprocess
    equity-research                   Financials, valuation
    trading-strategy                  Backtest, signals, risk control
    simulation                        Trading simulator, experiments
    market-monitor                    Breadth, northbound
L0  aquan-akshare-server (8000)         Real-time quotes
    aquan-tushare-server (8001)         Historical + financials
    aquan-internal-store-server (8002)  Cache + experiments + memory
    aquan-qlib-server (8003)            Qlib quant engine
```

All L0 servers live under `python/mcp-servers/` (uv workspace members, package names `aquan-*-server`).

## Boundary Rules (enforced by `scripts/check.py`)

| Rule | Statement |
|------|-----------|
| **R1** | MCP servers (`python/mcp-servers/`) must not import Agent or Skill code |
| **R2** | Skills must not import or reference Agent code |
| **R3** | Agents may reference Skills but **never modify** Skill source files |
| **R4** | Each MCP server is self-contained — no cross-server imports |
| **R5** | `internal-store` is the only shared data layer |
| **R6** | MCP servers contain only data access — no domain/business logic |

## Directory Patterns

```
agent-plugins/<name>/
├── AGENT.md          # Persona → Deliverables → Workflow → Guardrails
├── system-prompt.md  # Claude system prompt
└── plugin.json       # Metadata, skills, commands, MCP deps

skills/<name>/
├── SKILL.md          # Trigger, inputs, outputs, steps
├── prompt.md         # Execution prompt template
└── scripts/          # Standalone Python (invoked via uv run)

mcp-servers/<name>/               # python/mcp-servers/<name>/
├── server.py                     # FastMCP @mcp.tool() functions
├── pyproject.toml                # Dependencies (workspace member: name = "aquan-<name>-server")
└── test_server.py                # Co-located tests
```

## MCP Tool Pattern

```python
@mcp.tool()
def tool_name(param1: str, param2: str = "default") -> list[dict]:
    """One-line description of what this tool returns."""
    try:
        df = external_api_call(param1)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "tool_name"}]
```

Rules:
- Return `list[dict]` — use `df_to_json(df)` helper
- Mandatory `max_rows` (default 5000) — prevent memory issues
- NaN → `"NaN"` string
- Never raise unhandled exceptions — catch and return error dict

## A-Share Rules

| Rule | Value |
|------|-------|
| T+1 | Bought today → sellable tomorrow |
| Commission | 0.025% each side |
| Stamp duty | 0.05% sell-only |
| Slippage | ~0.05% one-way |
| Lot size | 100 shares minimum |
| Main board limit | ±10% |
| ChiNext/STAR limit | ±20% |

**Exclusions** (always filter unless user overrides): ST/\*ST, suspended, newly listed (<1yr), limit-up/down stocks.

## Before Submitting PR

- [ ] `scripts/check.py` passes
- [ ] `ruff check . && ruff format .` clean
- [ ] `pytest` passes
- [ ] `plugin.json` updated if skills/commands changed
- [ ] `scripts/sync-agent-skills.py --check` reports no drift

## Detailed References

All detailed docs moved to `docs/draft/`:
- `docs/draft/architecture.md` — full tech stack, Meta-Agent, trading simulator, memory store
- `docs/draft/coding-standards.md` — naming conventions, import organization, PR checklist
- `docs/draft/testing.md` — pytest patterns, MCP integration, E2E, coverage targets
- `docs/draft/mcp-servers.md` — FastMCP patterns, caching, adding tools/servers
- `docs/draft/playbooks.md` — step-by-step: add skill, agent, MCP tool, slash command, factor
- `docs/draft/a-share-rules.md` — full market rules, factor preprocessing, label construction
- `docs/draft/notebooks.md` — Jupyter conventions