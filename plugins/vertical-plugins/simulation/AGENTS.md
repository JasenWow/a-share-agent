# Simulation Plugin

**Scope:** Trading simulation — simulator, experiment tracking, evolution loop.

## Structure

```
plugins/vertical-plugins/simulation/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills (Phase 2+)
│   ├── trading-simulator/
│   ├── experiment-tracker/
│   └── evolution-loop/
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `trading-simulator` | A-share trading sandbox |
| `experiment-tracker` | Experiment recording |
| `evolution-loop` | Iteration control and doom loop detection |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills