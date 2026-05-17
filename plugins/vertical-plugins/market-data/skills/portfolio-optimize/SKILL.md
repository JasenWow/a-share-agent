---
name: portfolio-optimize
description: |
  Portfolio optimization with multiple methods (MVO, HRP, Risk Parity, TopkDropout),
  position sizing, and risk monitoring for A-share portfolios.

  Triggers: "优化组合", "portfolio optimization", "调仓建议",
  "风控检查", "rebalance", "仓位管理"
---

# Portfolio Optimization and Risk Management

## Workflow

### Step 1: Assess Current Portfolio

If user has existing portfolio:
1. Fetch current holdings and weights
2. Calculate current risk metrics (volatility, CVaR, sector exposure)
3. Compare against benchmark weights
4. Identify concentration risks

### Step 2: Generate Optimized Weights

Available methods:

| Method | When to Use | Required Inputs |
|--------|-----------|----------------|
| TopkDropout | Baseline, simple | Predicted scores only |
| MVO | Precise optimization | Expected returns + covariance |
| HRP | Robust, no return forecast | Covariance only |
| Risk Parity | Equal risk contribution | Covariance only |
| Black-Litterman | Have market views | Market cap weights + views |

**Default constraints:**
- Max single position: 10%
- Sector deviation vs benchmark: ±5%
- Min position: 1% (avoid fragmentation)
- Lot size: round to 100 shares

### Step 3: Position Sizing

- Default: Fractional Kelly (0.25x) based on strategy Sharpe
- Alternative: Risk budgeting (equal risk contribution)
- Apply T+1 constraint: cannot sell today's purchases

### Step 4: Risk Assessment

Calculate:
- **CVaR (95%)** — expected loss beyond VaR
- **Sector/factor exposure** — vs 沪深300 benchmark
- **Correlation matrix** — check for concentration
- **Stress scenarios** — apply -10%, -20%, -30% market shock
- **Liquidity score** — avg daily volume vs position size

### Step 5: Generate Rebalancing Orders

Output trade list:
```
| 动作 | 代码 | 名称 | 当前权重 | 目标权重 | 调整数量 | 预估成本 |
|------|------|------|---------|---------|---------|---------|
| 买入 | 600519 | 贵州茅台 | 5% | 8% | +300股 | ¥XXX |
| 卖出 | 000001 | 平安银行 | 8% | 5% | -3000股 | ¥XXX |
```

Include: estimated transaction costs, market impact warning for large orders.

### Step 6: Output

**Markdown Report:**
- Current vs optimized portfolio comparison
- Risk metrics dashboard
- Trade list with estimated costs
- Risk warnings

**Excel File:**
- Sheet 1: 当前组合 (current holdings)
- Sheet 2: 优化组合 (optimized weights)
- Sheet 3: 风险指标 (risk metrics)
- Sheet 4: 交易清单 (trade list)
- File: `./out/portfolio_<date>.xlsx`
