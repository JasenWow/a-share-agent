# Contributing Guidelines

**Scope:** Engineering guidelines for this project — not a Python package, not a traditional monorepo.

## FILES

| File | Content |
|------|---------|
| `coding-standards.md` | ruff rules (120 char, double quotes, 4-space), naming, commits, PR checklist |
| `a-share-rules.md` | T+1, price limits, transaction costs, exclusion rules, factor preprocessing |
| `architecture.md` | Tech stack, three-layer architecture (R1–R5), data flow, catalog |
| `testing.md` | pytest conventions, integration/E2E testing, coverage targets |
| `mcp-servers.md` | FastMCP patterns, tool patterns, caching, adding tools/servers |
| `playbooks.md` | Step-by-step: add skill, agent, MCP tool, or slash command |
| `README.md` | This directory's index |

## KEY RULES

| Rule | Source |
|------|--------|
| `python scripts/check.py` must pass before any work | R0 |
| Boundary R1: MCP servers must not import Agent/Skill code | `scripts/check.py` |
| Boundary R2: Skills must not reference Agent code | `scripts/check.py` |
| Boundary R3: Agents may reference Skills but **never modify** Skill source files | `scripts/check.py` |
| Boundary R4: MCP servers are self-contained — no cross-server imports | `scripts/check.py` |
| Boundary R5: `internal-store` is the only shared data layer | `scripts/check.py` |

## CONVENTIONS (DEVIATIONS FROM STANDARD)

- No `__init__.py` anywhere — not a standard Python package
- No root `pyproject.toml` — each MCP server has its own
- Agents/skills are `.md` files — never Python packages
- ruff rules defined in `coding-standards.md` but NOT enforced by actual config file (no `.ruff.toml`)
- Tests co-located with servers as `test_server.py`, not `tests/test_*.py`
- `tests/fixtures/` is the only root-level tests directory — contains fixture data only

## MCP SERVER PATTERN

Every MCP server directory must contain:
```
mcp-servers/<name>/
├── server.py      # FastMCP app, @mcp.tool() functions
├── pyproject.toml # dependencies
└── README.md      # tool documentation
```

Entry point: `uvicorn mcp-servers.<name>.server:mcp_app --port XXXX`