# Equity Research Plugin

**Scope:** Fundamental equity research — financial analysis, valuation.

## Structure

```
plugins/vertical-plugins/equity-research/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   └── financial-analysis/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `financial-analysis` | Deep financial analysis and valuation |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills