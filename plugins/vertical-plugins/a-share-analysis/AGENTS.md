# A-Share Analysis Plugin

**Scope:** The skills + commands layer. Skills contain domain knowledge (Markdown) and executable domain logic (Python scripts).

## STRUCTURE

```
plugins/vertical-plugins/a-share-analysis/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata
├── .mcp.json               # MCP config (type: http)
├── skills/                  # Skills (each is a directory)
│   ├── factor-screen/
│   │   ├── SKILL.md         # Domain instructions
│   │   ├── prompt.md        # Execution prompt (recommended)
│   │   ├── scripts/         # Executable Python (optional)
│   │   ├── references/      # Formulas, thresholds (optional)
│   │   └── examples/        # I/O samples (recommended)
│   ├── financial-analysis/
│   ├── factor-research/
│   ├── backtest-engine/
│   ├── portfolio-optimize/
│   ├── market-breadth/
│   ├── xlsx-author/
│   ├── next-day-predict/
│   └── northbound-monitor/
├── commands/               # Slash commands (each is a .md file)
│   ├── screen.md
│   ├── research.md
│   ├── factor.md
│   ├── backtest.md
│   ├── optimize.md
│   └── market.md
└── hooks/
```

## SKILLS

| Skill | Trigger Phrases | Purpose |
|-------|-----------------|---------|
| `factor-screen` | `/screen`, "screen stocks", "multi-factor" | Stock screening |
| `financial-analysis` | `/research`, "financial analysis", "deep dive" | Single-stock research |
| `factor-research` | `/factor`, "factor research", "validate factor" | Factor validation |
| `backtest-engine` | `/backtest`, "backtest strategy", "backtest" | Strategy backtesting |
| `portfolio-optimize` | `/optimize`, "portfolio optimization", "HRP" | Portfolio optimization |
| `market-breadth` | `/market`, "market breadth", "northbound" | Market monitoring |
| `xlsx-author` | "write xlsx", "to Excel", "export" | Excel file generation |

## COMMANDS

`/screen`, `/research`, `/factor`, `/backtest`, `/optimize`, `/market` — each maps to an agent.

## ANTI-PATTERNS

- **Never** modify Skill source files from an Agent (R3)
- Skills must not reference Agent code (R2)
- Skill scripts must not import code from `mcp-servers/`, `plugins/agent-plugins/`, or other skills
- Never web search for financial data

## CONVENTIONS

- Each skill dir has: `SKILL.md` (required), `prompt.md` (recommended), `scripts/` (if domain logic exists), `references/` (if lookup data exists), `examples/` (recommended)
- Skill scripts are invoked via `uv run python skills/<name>/scripts/<script>.py`
- Skill validation: `python scripts/validate.py`
- Sync to agents: `python scripts/sync-agent-skills.py`