# Simulation Plugin

**Scope:** Trading simulation — simulator, experiment tracking, evolution loop, script generation, agent modification.

## Structure

```
plugins/vertical-plugins/simulation/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata + skill list
├── .mcp.json               # MCP server config
├── skills/                  # Skills
│   ├── trading-simulator/   # A-share trading sandbox
│   ├── experiment-tracker/  # Experiment recording via internal-store
│   ├── evolution-loop/      # Iteration control, doom loop, hypothesis generation
│   ├── script-generator/    # Auto-generate factor/strategy Python scripts
│   ├── agent-modifier/      # Modify agent definitions (Phase 3)
│   ├── mcp-tool-adder/      # Add MCP tools to internal-store (Phase 3)
│   └── next-day-predict/    # Next-day prediction skill
└── commands/               # Slash commands
```

## Skills

| Skill | Purpose |
|-------|---------|
| `trading-simulator` | A-share trading sandbox with T+1, price limits, costs |
| `experiment-tracker` | Experiment recording and history |
| `evolution-loop` | Iteration control, doom loop detection, hypothesis generation |
| `script-generator` | Generate and validate factor/strategy Python scripts |
| `agent-modifier` | Modify agent plugin definitions (self-mod prevention) |
| `mcp-tool-adder` | Add new MCP tools to internal-store (R6 enforced) |
| `next-day-predict` | Next-day prediction skill |

## ANTI-PATTERNS

- Skills must not reference Agent code (R2)
- Skill scripts must not import from `mcp-servers/`, `plugins/agent-plugins/`, or other skills