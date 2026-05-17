# Market Data Plugin

**Scope:** Core market data — factor screening, factor research, portfolio optimization.

## Structure

```
plugins/vertical-plugins/market-data/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   ├── factor-screen/
│   ├── factor-research/
│   └── portfolio-optimize/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `factor-screen` | Multi-factor stock screening |
| `factor-research` | Factor validation and IC analysis |
| `portfolio-optimize` | Portfolio construction and optimization |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills