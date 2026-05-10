# A-Share Analysis Plugin

**Scope:** The skills + commands layer. Markdown-based, not Python packages.

## STRUCTURE

```
plugins/vertical-plugins/a-share-analysis/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata
├── .mcp.json               # MCP config (type: http)
├── skills/                  # 7 skills (each is a directory with SKILL.md)
│   ├── factor-screen/
│   ├── financial-analysis/
│   ├── factor-research/
│   ├── backtest-engine/
│   ├── portfolio-optimize/
│   ├── market-breadth/
│   └── xlsx-author/
├── commands/               # 6 slash commands (each is a .md file)
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
- Skills are `.md` files — never Python modules at this layer
- Never web search for financial data

## CONVENTIONS

- Each skill dir has: `SKILL.md` (required), `prompt.md` (recommended), `examples/` (recommended)
- Skill validation: `python scripts/validate.py`
- Sync to agents: `python scripts/sync-agent-skills.py`