---
comet_change: signal-eval-redesign
role: technical-design
canonical_spec: openspec
---

# Design Doc: 因子挖掘完整评估体系

> Full design in `openspec/changes/signal-eval-redesign/design.md`

## Status: active

## Summary

Build a complete evaluation loop: factor mining → ranking → backtesting → metrics.

### New modules
- `backtest.py` — portfolio backtest engine (top-N long, weekly rebalance)
- `metrics.py` — evaluation metrics (annualized return, Sharpe, max drawdown, win rate, IR, t-stat)

### Key fixes
- `fitness.py` — statistical significance filter (t-stat > 2)
- `ranker.py` — direction-aware zscore (flip for negative-IC factors) + volume factor weight cap
- `run_mining.py` — 70/30 train/test split, OOS IC validation

### Report
- `report.py` — backtest performance, train/test IC comparison, ASCII equity curve, actual price changes

## Tasks

T1-T8 in `openspec/changes/signal-eval-redesign/tasks.md`
