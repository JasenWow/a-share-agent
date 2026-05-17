---
name: trading-simulator
description: |
  A-share trading simulator sandbox with T+1 settlement enforcement.
  Triggers: "simulation", "backtest", "trading simulator", "模拟交易", "回测"
---

# Trading Simulator

## Overview

A-share market trading simulator with full T+1 settlement enforcement, board price limits, transaction cost modeling, and lot size validation. Used by agents to validate trading strategies before live deployment.

**Core Philosophy:** "Simulate first, trade second — catch rule violations in sandbox before they cost money."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| initial_capital | float | Yes | Starting capital in CNY |
| signals | list[dict] | Yes | List of trade signals |
| start_date | str | Yes | YYYYMMDD |
| end_date | str | Yes | YYYYMMDD |

---

## Output

| Field | Type | Description |
|-------|------|-------------|
| final_capital | float | Ending portfolio value |
| total_return_pct | float | Return percentage |
| trade_count | int | Number of executed trades |
| trades | list[dict] | Detailed trade records |
| portfolio_history | list[dict] | Daily portfolio values |

---

## A-Share Rules Enforced

| Rule | Implementation |
|------|---------------|
| T+1 settlement | Shares bought day T can only be sold from day T+1 |
| Board price limits | Main ±10%, ChiNext/STAR ±20%, BSE ±30%, ST ±5% |
| Lot size | Minimum 100 shares, round down |
| Commission | 0.025% per side |
| Stamp duty | 0.05% sell-only |
| Slippage | 0.05% one-way default |

---

## Usage

```bash
uv run python plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/run_simulation.py \
  --capital 1000000 \
  --start 20240101 \
  --end 20241231 \
  --config signals.json \
  --output results.json
```

---

## Quality Checklist

- [ ] All trades pass T+1 check
- [ ] Board limit violations rejected
- [ ] Lot size rounding applied
- [ ] Transaction costs deducted
- [ ] Realized P&L matches expectation
- [ ] Portfolio history complete