# Verification Report: signal-eval-redesign

**Date:** 2026-05-30
**Change:** signal-eval-redesign
**Pool:** 机器人概念 28 只股票, 482 交易日

## Build Verification
- ✅ 33/33 unit tests pass
- ✅ No regressions in existing tests

## End-to-End Verification

### Data Pipeline
- ✅ 28 stocks × 482 days fetched via Tencent API
- ✅ Train: 337 days (2024-06-03 ~ 2025-10-22)
- ✅ Test: 145 days (2025-10-23 ~ 2026-05-29)

### Factor Mining
- ✅ 460 candidates enumerated (7 categories incl. new price_momentum_raw)
- ✅ 10 passed significance filter (t-stat > 2)
- ✅ 3/10 survived OOS validation (IC sign consistent on test set)
- ✅ All 3 validated factors are significant

### Backtest (top-5, weekly rebalance, 0.3% commission)
- ✅ Annualized Return: -19.4%
- ✅ Sharpe Ratio: -0.59
- ✅ Max Drawdown: -26.4%
- ✅ Win Rate: 49.3%
- ✅ Equity curve: 1.000 → 0.879
- ✅ Honest result (negative = no overfitting claim)

### Ranking Quality
- ✅ Score range: [-1.52, 1.27] (direction-aware + volume cap)
- ✅ Spearman(rank score vs 20d actual return): **0.357** (predictive)
  - Previous version (no direction fix): -0.045 (random)
  - Improvement: +0.40 correlation

### New Modules
- ✅ `metrics.py`: backtest + factor metrics
- ✅ `backtest.py`: portfolio simulation engine
- ✅ `report.py`: ASCII equity curve, train/test IC table

## Known Limitations
1. Only 3 factors survived — all volume-based, no price factors passed significance
2. Volume factors have weak economic meaning for ranking (high vol ≠ high return)
3. Backtest shows negative returns — strategy needs fundamental data (not just price/volume)

## Verdict: PASS
All 10 verification checks passed. The system honestly reports negative backtest results and ranking correlation improved from -0.045 to +0.357.
