---
name: factor-mining
description: |
  Industry-driven factor mining: discover effective quantitative signals for
  a specific industry stock pool, rank stocks, and evaluate portfolios.

  Triggers: "挖掘因子", "mine factors", "factor mining", "自动因子发现",
  "discover alpha", "find new factors", "因子挖掘", "产业选股"
---

# Factor Mining — 产业驱动的量化选股

## Overview

Two core scenarios:

1. **产业选股**: On a specific industry stock pool, automatically discover
   what quantitative signals best predict outperformance, then rank stocks.
2. **持仓评估**: Score user's holdings using industry-specific factors,
   diagnose health and concentration risk.

**Core Philosophy:** "Not universal factor mining — discover what works for *this* industry."

---

## Input

### Mining Mode

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| codes | list[str] | Yes | Stock codes for the pool (from stock-pool skill) |
| direction | str | Yes | Preset direction: 低波动/动量趋势/量价关系/均值回归/综合探索 |
| start_date | str | No | Historical start date (default: 1 year ago) |
| end_date | str | No | Historical end date (default: today) |

### Evaluation Mode

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| holdings | list[dict] | Yes | List of {code, shares/weight} |

---

## Tool Dependencies

| Tool | Purpose |
|------|---------|
| AKShare MCP (8000) | OHLCV data for custom stock pools |
| Tushare MCP (8001) | Supplementary data |
| Internal-store MCP (8002) | Factor library (register, list, deprecate) |
| Qlib MCP (8003) | Universe-based data (fallback) |

---

## Workflow

### Mining Mode

#### Step 1: Receive Stock Pool + Direction

- Stock pool comes from stock-pool skill or user input
- User selects direction (or provides natural language description)
- System maps direction to search parameters (fields, operators, windows)

#### Step 2: Fetch Data

- Fetch daily OHLCV for all stocks in the pool via AKShare/Tushare MCP
- Align to (T, N) ndarray format
- Compute forward returns

#### Step 3: Template Search (Layer 2)

- Enumerate all factor template × field × window combinations
- Evaluate each candidate's IC/ICIR on the pool's historical data
- Keep top-N candidates (default 20)

Templates by category:
- **Trend**: price/MA ratio, normalized momentum
- **Momentum**: absolute momentum, up-day fraction
- **Volatility**: low volatility, volatility-adjusted level
- **Volume-Price**: price-volume correlation, price-to-volume ratio
- **Mean Reversion**: z-score reversion, deviation reversal
- **Strength**: distance from high, distance from low

#### Step 4: GP Refinement (Layer 3)

- Use top template results as seed population
- DEAP genetic programming evolves around seeds
- Crossover + mutation explores nearby expressions
- Returns refined factors with better fitness

#### Step 5: Register Factors

- Register validated factors (IC > 0.02, ICIR > 0) to factor_library
- Record: expression, IC, ICIR, turnover, industry, date

#### Step 6: Rank Stocks + Generate Report

- Score each stock using discovered factors (weighted by ICIR)
- Classify signals: 强势延续 / 信号转强 / 强势但转弱 / 弱势
- Output Markdown ranking report

### Evaluation Mode

#### Step 1: Receive Holdings

- User provides stock code list

#### Step 2: Score Holdings

- Load active factors for relevant industries
- Score each holding using factor values
- Assess: health (strong/healthy/weakening/recovering/weak)

#### Step 3: Portfolio Diagnostics

- Concentration risk
- Average score
- Signal distribution

#### Step 4: Generate Report

- Per-holding details table
- Portfolio-level diagnostics
- Factor context

---

## Output

### Mining Report (Markdown)

```markdown
# 产业因子挖掘报告

**方向:** 动量趋势
**标的池:** 42 只股票

## 因子列表 (Top 10)
| # | 因子表达式 | IC | ICIR | 换手率 | 适应度 |
...

## 标的排名
| 排名 | 代码 | 综合评分 | 动量信号 | 信号分类 |
...

### 🔥 近期强势
- 300124.SZ — 评分 1.234

### 📈 信号转强（关注）
- 002472.SZ — 动量 0.456
```

### Portfolio Report (Markdown)

```markdown
# 持仓评估报告

## 组合诊断
- 平均评分: 0.345
- 集中度: 适中

## 持仓详情
| 代码 | 排名 | 综合评分 | 健康度 |
...
```

---

## Guardrails

1. **Small sample awareness** — industry pools may have 20-80 stocks; use lower IC thresholds (0.02 vs 0.03)
2. **Never use future data** — forward returns are point-in-time
3. **Factor lifecycle** — track IC over time, deprecate stale factors
4. **Report disclaimer** — all reports state "not investment advice"
5. **Data source priority** — AKShare > Tushare > user-provided; never web search

---

## Quality Checklist

- [ ] Stock pool has at least 10 stocks
- [ ] Historical data covers at least 250 trading days
- [ ] Template search completed with meaningful IC results
- [ ] GP refinement did not crash (fallback to template-only is OK)
- [ ] Top factors registered to factor_library
- [ ] Ranking report generated with signal classification
