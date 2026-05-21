# Equity Research Plugin

**Scope:** Fundamental equity research — financial analysis, valuation.

## Structure

```
plugins/vertical-plugins/equity-research/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   ├── financial-analysis/
│   └── stock-pool/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `financial-analysis` | Deep financial analysis and valuation |
| `stock-pool` | 主题股票池构建：价值链分析、标的发现、量化初筛 |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills