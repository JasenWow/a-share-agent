# Coding Standards

> Mechanical rules enforced by `ruff` and commit conventions enforced by review. These should rarely require human judgment — if a change trips a linter, fix the code, don't silence the linter.

## ruff (format + lint)

Config: `ruff.toml` or `pyproject.toml [tool.ruff]`. Runs via `ruff check .` and `ruff format .`.

### Formatting

- **Line length**: 120 characters
- **Quote style**: double quotes
- **Indentation**: 4 spaces
- Run `ruff format .` before committing — no manual formatting debates.

### Key Lint Rules

| Rule | Code | Threshold | Typical trigger |
|------|------|-----------|-----------------|
| Line too long | `E501` | 120 chars | Long URL, long dict literal |
| Unused import | `F401` | zero tolerance | Leftover from refactoring |
| Unused variable | `F841` | zero tolerance | Dead code |
| Bare `except` | `E722` | never allowed | `except:` without exception type |
| Mutable default argument | `B006` | never allowed | `def f(x=[])` |
| Duplicate key in dict | `F601` | zero tolerance | Copy-paste error |
| `print()` in production | `T201` | disallowed | Use `logging` instead |

### Error Cheatsheet

| Error | Typical trigger | Fix direction |
|-------|-----------------|---------------|
| `E501: line too long` | Long URL or call chain | Extract to variable; parenthesized break |
| `F401: unused import` | Leftover import | Remove it |
| `B006: mutable default` | `def f(x=[])` | Change to `def f(x=None): x = x or []` |
| `T201: print found` | Debugging leftover | Replace with `logging.debug()` |

## Import Organization

`ruff` enforces import grouping via `isort`-compatible rules. Imports are organized as:

1. **Standard library** — `os`, `json`, `datetime`, ...
2. **Third-party** — `pandas`, `akshare`, `mcp`, `fastapi`, ...
3. **Local** — project-internal imports

Blank line between each group. No relative imports outside of `mcp-servers/` subpackages.

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Directory | `kebab-case` | `stock-screener/`, `factor-screen/` |
| Python file | `snake_case` | `sync_agent_skills.py`, `server.py` |
| Python class | `PascalCase` | `AgentOrchestrator`, `CacheEntry` |
| Python function/variable | `snake_case` | `fetch_daily_data()`, `max_rows` |
| MCP tool name | `snake_case` | `stock_zh_a_spot`, `fina_indicator` |
| JSON config | `kebab-case` | `plugin.json`, `screen.json` |
| Markdown file | `UPPERCASE.md` or `kebab-case.md` | `SKILL.md`, `system-prompt.md` |
| Parquet file | `{code}.parquet` | `000001.parquet` |

## File Structure Rules

### Agent Plugin

Every agent plugin directory MUST contain:

```
agent-plugins/<agent-name>/
├── AGENT.md              # Required: persona, deliverables, workflow, guardrails
├── system-prompt.md      # Required: Claude system prompt
└── plugin.json           # Required: metadata, skills, commands, MCP deps
```

### Skill Directory

Every skill directory MUST contain:

```
skills/<skill-name>/
├── SKILL.md              # Required: trigger conditions, inputs, outputs, steps
├── prompt.md             # Recommended: execution prompt template
└── examples/             # Recommended: input/output examples
```

### MCP Server

Every MCP server directory MUST contain:

```
mcp-servers/<name>/
├── server.py             # Required: FastMCP tool definitions
├── pyproject.toml        # Required: dependencies
└── README.md             # Required: tool documentation
```

## Commit Convention

Conventional commits with squash-merge — **one commit per PR**.

- Prefixes: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `ci:`, `perf:`.
- Format: `<type>: <description> (#PR)`
- Every commit must include the PR reference `(#NNN)`.
- Example: `feat: add northbound capital flow MCP tool (#42)`

## Pull Request Checklist

Before requesting review:

- [ ] `python scripts/check.py` passes with no issues
- [ ] `ruff check .` and `ruff format .` produce no changes
- [ ] `pytest` passes (unit tests)
- [ ] MCP servers start without errors (if server code changed)
- [ ] Agent/skill runs end-to-end (if agent or skill code changed)
- [ ] `plugin.json` updated if skills/commands were added or removed
- [ ] `python scripts/sync-agent-skills.py --check` reports no drift

## A-Share Specific Rules

When writing Python code that handles A-share data:

1. **Stock codes are 6-digit strings** — always use string type, never int. Leading zeros matter (`000001` ≠ `1`).
2. **Tushare codes include suffix** — `000001.SZ`, `600519.SH`. AKShare codes are bare 6-digit. Always convert explicitly.
3. **Dates are `YYYYMMDD` strings** — both AKShare and Tushare use this format. Convert to `datetime` only for calculations, convert back for API calls.
4. **NaN handling** — financial data frequently contains NaN. Use `pandas` NaN-aware methods (`fillna`, `dropna`, `isna`). Never let NaN silently propagate into calculations.
5. **No hardcoded credentials** — Tushare tokens come from environment variables, never from config files or source code.
