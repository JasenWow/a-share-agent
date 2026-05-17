---
name: backtest-engine
description: |
  Strategy backtesting with A-share market constraints. T+1 settlement,
  tiered transaction costs, board-specific price limits, and
  survivorship bias prevention.

  Triggers: "回测策略", "backtest", "测试这个策略", "run backtest",
  "策略表现"
---

# Strategy Backtesting Engine

## CRITICAL: A-Share Backtest Constraints

1. **T+1 Settlement**: Buy today → can only sell tomorrow
   - Position changes execute at NEXT DAY open price
   - Label: signal T → trade T+1 → return realized T+2

2. **Transaction Costs (2026)**:
   - Commission: 0.025% per side (assume 万2.5 full-commission)
   - Stamp duty: 0.05% sell only
   - Slippage: 0.1% large-cap, 0.2% small-cap
   - **Total round-trip: ~0.20% (large-cap) to ~0.40% (small-cap)**

3. **Board Price Limits**:
   - Main board: ±10%
   - ChiNext (创业板 300xxx): ±20%
   - STAR Market (科创板 688xxx): ±20%
   - BSE (北交所 8xxxxx): ±30%
   - ST/*ST: ±5%

4. **Lot Size**: 100 shares minimum (1 lot)
   - Round all orders to nearest 100

5. **Survivorship Bias**:
   - MUST use point-in-time universe (include delisted stocks)
   - On delist date: assume 30-55% loss
   - Use historical index constituents, not current

---

## Workflow

### Step 1: Parse Strategy Definition

Extract from user input:
- Signal generation logic (factor-based, rule-based, ML-based)
- Universe definition
- Rebalancing frequency (daily / weekly / monthly)
- Position sizing method (equal-weight / score-weighted / risk-parity)
- Number of holdings (top-K)

### Step 2: Prepare Data

1. Fetch historical data via MCP (OHLCV, factors, constituents)
2. Merge with point-in-time constituent data
3. Apply exclusion rules (ST, suspended, <1yr listed)
4. Verify no look-ahead bias in data preparation

### Step 3: Generate Signals

For each rebalancing date:
1. Calculate factor/signal values using ONLY data available up to that date
2. Rank stocks by signal
3. Select top-K stocks
4. Determine target weights

### Step 4: Simulate Trading

For each trading day:
1. Check for rebalancing signal
2. If rebalancing:
   - Sell current positions (apply sell costs)
   - Buy new positions at T+1 open price (apply buy costs)
   - Apply lot size rounding
3. Check board price limits (no order beyond limit)
4. Update positions and cash
5. Calculate daily P&L

### Step 5: Calculate Performance Metrics

| Metric | Formula | Threshold |
|--------|---------|-----------|
| Annualized Return | geometric mean of daily returns | — |
| Sharpe Ratio | √252 × mean(daily) / std(daily) | ≥ 1.0 |
| Max Drawdown | max(peak - trough) / peak | ≤ 20% |
| Calmar Ratio | Return / MaxDD | ≥ 0.5 |
| IC | corr(signal, forward_return) | ≥ 0.03 |
| ICIR | mean(IC) / std(IC) | ≥ 0.5 |
| Turnover | avg daily portfolio change | — |
| Win Rate | % of positive return days | ≥ 52% |

### Step 6: Benchmark Comparison

Compare against:
- 沪深300 (large-cap benchmark)
- 中证500 (mid-cap benchmark)
- 中证1000 (small-cap benchmark)
- Show excess return, tracking error, information ratio

### Step 7: Output

**Markdown Report:**
- Strategy summary
- Performance metrics table
- Drawdown analysis
- Benchmark comparison
- Year-by-year breakdown
- Risk warnings

**Excel File:**
- Sheet 1: 净值曲线 (NAV series: strategy + benchmarks)
- Sheet 2: 持仓明细 (position history)
- Sheet 3: 绩效指标 (performance metrics)
- Sheet 4: 年度分解 (annual breakdown)
- File: `./out/backtest_<strategy>_<date>.xlsx`
