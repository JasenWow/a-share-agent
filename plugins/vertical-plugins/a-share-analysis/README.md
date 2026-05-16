# A-Share Analysis Plugin

A-share quantitative analysis skills and commands for Claude Code.

## Skills

| Skill | Description | Command |
|-------|-------------|---------|
| factor-screen | Multi-factor stock screening | `/screen` |
| financial-analysis | Deep financial analysis | `/research` |
| factor-research | Factor research and validation | `/factor` |
| backtest-engine | Strategy backtesting | `/backtest` |
| portfolio-optimize | Portfolio optimization | `/optimize` |
| market-breadth | Market breadth monitoring | `/market` |
| xlsx-author | Excel file generation | — |
| next-day-predict | Next-day stock prediction | `/predict` |
| northbound-monitor | Northbound capital monitoring | — |

## Skill Structure

Each skill directory follows this layout:

```
skills/<name>/
├── SKILL.md          # Required: domain instructions + workflow
├── prompt.md         # Recommended: execution prompt template
├── scripts/          # Optional: executable Python domain logic
├── references/       # Optional: formulas, thresholds, lookup tables
└── examples/         # Recommended: input/output samples
```

## MCP Connectors

- **AKShare** (localhost:8000) — Realtime quotes, historical data
- **Tushare** (localhost:8001) — High-quality financial data

## A-Share Constraints

All skills enforce A-share market rules:
- T+1 settlement
- Board price limits (±10%/±20%/±30%)
- ST/*ST exclusion
- 100-share lot size
