# Market Monitor Plugin

**Scope:** Market monitoring — breadth, northbound flow, next-day prediction.

## Structure

```
plugins/vertical-plugins/market-monitor/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   ├── market-breadth/
│   ├── next-day-predict/
│   └── northbound-monitor/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `market-breadth` | Market breadth indicators |
| `next-day-predict` | Next-day stock prediction |
| `northbound-monitor` | Northbound capital monitoring |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills