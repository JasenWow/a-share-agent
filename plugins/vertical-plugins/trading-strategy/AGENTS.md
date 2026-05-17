# Trading Strategy Plugin

**Scope:** Trading strategy — backtesting engine and Excel report generation.

## Structure

```
plugins/vertical-plugins/trading-strategy/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   ├── backtest-engine/
│   └── xlsx-author/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `backtest-engine` | Strategy backtesting with A-share constraints |
| `xlsx-author` | Excel file generation |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills