---
name: factor-screen
description: |
  Multi-factor stock screening for A-share market. Filter and rank stocks
  based on fundamental factors (PE, PB, ROE, revenue growth, etc.) with
  proper A-share exclusions and factor preprocessing.

  Triggers: "筛选低估值股票", "find high ROE stocks", "帮我选股",
  "screener", "factor screen", "选股", "筛选"
---

# Multi-Factor Stock Screening

## CRITICAL: A-Share Exclusion Rules (READ FIRST)

**ALWAYS apply these exclusions BEFORE any factor calculation:**

1. **EXCLUDE ST/*ST stocks** — check stock name contains "ST"
2. **EXCLUDE suspended stocks** — check trading status
3. **EXCLUDE stocks listed < 252 trading days (1 year)** — use listing date
4. **EXCLUDE delisted stocks** — check delist status
5. **EXCLUDE stocks with price > board price limit** — avoid buy limit orders

**Why:** ST stocks have distorted financials; suspended stocks cannot trade;
newly listed stocks lack historical data; delisted stocks cause survivorship bias.

---

## Overview

This skill performs institutional-grade multi-factor stock screening
adapted for A-share market characteristics. Output is a ranked stock list
with factor values in both Markdown table and Excel format.

**Core Philosophy:** "Filter first, rank second, verify always."

---

## Data Source Priority

1. **FIRST: Tushare MCP** — highest quality, well-structured financial data
2. **SECOND: AKShare MCP** — broader coverage, real-time quotes
3. **LAST: Require user to provide data file** — only if MCPs unavailable
4. **NEVER use web search for financial data** — unreliable, no audit trail

---

## Workflow

### Step 1: Parse Screening Conditions

Extract from user input:
- Target universe (全A / 沪深300成分 / 中证500成分 / 创业板 / 科创板)
- Factor conditions (PE < X, ROE > Y, revenue_growth > Z, etc.)
- Sorting preference (composite score / single factor)
- Output format (Markdown / Excel / both)

### Step 2: Build Stock Universe

1. Fetch stock list from MCP data source
2. Apply exclusion rules (ST, suspended, <1yr listed, delisted)
3. Filter by target universe (index constituents if specified)
4. Result: clean stock universe for factor calculation

### Step 3: Fetch Factor Data

Fetch raw data for each requested factor:

| Factor | Data Source | Fields |
|--------|-----------|--------|
| PE (市盈率) | Tushare fina_indicator | pe_ttm |
| PB (市净率) | Tushare fina_indicator | pb |
| ROE (净资产收益率) | Tushare fina_indicator | roe |
| ROA (总资产收益率) | Tushare fina_indicator | roa |
| 营收增长率 | Tushare fina_indicator | or_yoy |
| 净利润增长率 | Tushare fina_indicator | netprofit_yoy |
| 股息率 | AKShare dividend | dy |
| 市值 | AKShare real-time | total_mv |
| 换手率 | Tushare daily | turnover_rate |
| 行业 | Tushare stock_basic | industry (申万一级) |

### Step 4: Factor Preprocessing

Apply standard preprocessing pipeline:

```
Raw Factor → MAD Winsorization (3σ) → ZScore Standardization → (Optional) Industry+Cap Neutralization
```

**MAD Winsorization:**
- Median = median(factor_values)
- MAD = median(|factor_values - Median|)
- Clip to [Median - 3*MAD*1.4826, Median + 3*MAD*1.4826]

**ZScore:**
- factor_zscore = (factor - mean) / std

**Industry+Cap Neutralization (optional):**
- Run cross-sectional regression: factor ~ log(market_cap) + industry_dummies
- Use residuals as neutralized factor

### Step 5: Composite Scoring

If multiple factors requested:
- Equal-weight ZScore composite (default)
- OR user-specified weights
- Score = Σ(weight_i × zscore_i)

### Step 6: Rank and Filter

1. Apply user-specified thresholds (e.g., PE < 20, ROE > 15%)
2. Rank by composite score (descending)
3. Return top N (default 50, configurable)

### Step 7: Format Output

**Markdown Table:**
```
| 排名 | 代码 | 名称 | 行业 | PE(TTM) | PB | ROE | 营收增长 | 综合得分 |
|------|------|------|------|---------|-----|------|---------|---------|
| 1 | 000001 | 平安银行 | 银行 | 5.2 | 0.6 | 12.5% | 8.3% | 2.34 |
```

**Excel Output:**
- Sheet 1: 筛选结果 (ranked list with all factors)
- Sheet 2: 因子分布 (factor distribution statistics: mean, median, std, skew)
- Sheet 3: 行业分布 (industry breakdown)
- File: `./out/screen_<date>.xlsx`

---

## Common Mistakes

| Mistake | Correct Approach |
|-----------|-------------------|
| Using current index constituents for historical backtest | Use point-in-time constituents |
| Ignoring ST stocks that later recovered | Exclude from screening but track separately |
| ZScore without winsorization first | Always winsorize BEFORE standardizing |
| Applying PE filter on negative-earnings stocks | Handle negative PE: set to NaN or use absolute PE |
| Using total market cap without log transform | Always use log(market_cap) for neutralization |
| Forgetting T+1 constraint in turnover calculation | Portfolio changes execute at T+1 open |

---

## Quality Checklist

- [ ] All exclusion rules applied (ST, suspended, <1yr, delisted)
- [ ] Factor preprocessing: winsorization → zscore (in this order)
- [ ] Every hardcoded threshold has user confirmation or clear default
- [ ] Output includes data source citation for each factor
- [ ] No [UNSOURCED] data in final output
- [ ] Excel file follows color coding: blue=inputs, black=formulas
