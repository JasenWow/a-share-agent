# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-10
**Commit:** 604f326
**Branch:** main

## OVERVIEW

A-share quantitative analysis Agent system. Python 3.10+, FastMCP data connectors, markdown-based plugin architecture (no Python packages for agents/skills). Three-layer downward dependency: Agent (L2) → Skill (L1) → Connector (L0).

## STRUCTURE

```
a-share-agents/
├── mcp-servers/            # 4 FastMCP servers (the only Python packages)
│   ├── akshare-server/     # Realtime data (port 8000)
│   ├── tushare-server/    # Historical data (port 8001)
│   ├── internal-store/     # Cache layer (port 8002)
│   └── bilibili-server/
├── plugins/                # Markdown-based plugins (NOT Python packages)
│   ├── agent-plugins/      # 6 agents: stock-screener, equity-researcher, factor-analyst, backtester, portfolio-manager, market-monitor
│   └── vertical-plugins/   # 7 skills + 6 commands for a-share-analysis
├── scripts/                # Dev tooling: check.py, validate.py, sync-agent-skills.py
├── contributing/           # Full engineering guidelines
├── docs/                   # Design documents (Chinese)
├── managed-agent-cookbooks/
└── tests/fixtures/         # Test fixtures only (no test_*.py at root)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add MCP tool | `mcp-servers/<name>/server.py` | Add `@mcp.tool()` function, follow pattern |
| Add agent | `plugins/agent-plugins/<name>/agents/` | Create `.md` with YAML frontmatter |
| Add skill | `plugins/vertical-plugins/a-share-analysis/skills/<name>/` | `SKILL.md` with trigger phrases |
| Add command | `plugins/vertical-plugins/a-share-analysis/commands/` | `.md` with YAML frontmatter |
| A-share market rules | `contributing/a-share-rules.md` | T+1, price limits, costs, exclusions |
| Coding standards | `contributing/coding-standards.md` | ruff 120, double quotes, naming |
| Verify env | `python scripts/check.py` | Must pass before any work |
| Validate structure | `python scripts/validate.py` | Plugin/skill manifest validation |
| Sync skills | `python scripts/sync-agent-skills.py` | Sync skills into agent dirs |

## ANTI-PATTERNS (THIS PROJECT)

- **No `__init__.py`** — not a standard Python package; don't add them
- **No root `pyproject.toml`** — each MCP server has its own
- **Agents/skills are `.md` files** — never Python packages; don't create Python modules at plugin layer
- **Never web search** for financial data — use Tushare → AKShare → user-provided only
- **Stock codes always 6-digit strings** — `000001.SZ` not `1`, `000001` not `1`
- **Never same-day round-trip** — T+1 is hard constraint
- **Never return `None`** from MCP tools — return `[]` or error dict
- **Never raise unhandled exceptions** in MCP tools — catch and return error dicts
- **Never modify Skill source files from an Agent** (R3 boundary)
- **No `print()` in production** — use `logging`

## UNIQUE STYLES

- **Markdown plugin system**: `.claude-plugin/plugin.json` metadata + YAML frontmatter in `.md` files
- **Per-server `pyproject.toml`**: Decentralized dependency management
- **3 independent uvicorn processes**: No unified entry point; manual startup documented in README
- **All analysis output in Chinese** with English technical terms

## COMMANDS

```bash
# Environment
python scripts/check.py
python scripts/validate.py
python scripts/sync-agent-skills.py --check

# Start MCP servers
uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# Lint and format (rules in contributing/coding-standards.md)
ruff check .
ruff format .

# Test
pytest tests/                    # Unit (co-located with servers: mcp-servers/*/test_server.py)
pytest -m integration             # Integration (servers must be running)
pytest -m e2e                     # E2E (fixture data)
```

## NOTES

- 4 MCP servers, 6 agents, 7 skills, 6 commands
- Boundary rules enforced by `scripts/check.py` (R1–R5)
- No `requirements.txt` at root; each server declares deps in its own `pyproject.toml`
- No GitHub Actions CI, no Docker — manual operation only
- Max depth: 5 (contributing/, docs/, mcp-servers/, plugins/)