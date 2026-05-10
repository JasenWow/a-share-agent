---
name: factor-research
description: |
  Factor research and validation for A-share market. Construct factors,
  calculate IC/ICIR, perform neutralization, and run walk-forward testing.

  Triggers: "研究因子", "factor IC", "因子测试", "factor analysis",
  "验证因子有效性", "factor validation"
---

# Factor Research and Validation

## CRITICAL: Look-Ahead Bias Prevention

- NEVER use future data for factor construction at any point
- T+1 labeling: Signal at T close → Trade at T+1 open → Return realized at T+2 close
- Label formula: `Label = Ref($close, -2) / Ref($close, -1) - 1`
- Winsorization/ZScore MUST use only training-period data for fit
- Point-in-time constituents only — never use current index members for historical periods

---

## Workflow

### Step 1: Define Factor

Parse user input for:
- Factor formula or description
- Universe (全A / 沪深300 / etc.)
- Time period
- Frequency (daily / weekly / monthly)

### Step 2: Construct Factor

Build factor values cross-sectionally:
1. Fetch required raw data via MCP
2. Apply factor formula to each stock at each time point
3. Handle missing values (set to NaN, do NOT forward-fill for factor values)

### Step 3: Factor Preprocessing

Standard pipeline (per cross-section):
```
Raw → MAD Winsorization (3σ) → ZScore → [Optional] Neutralization
```

Neutralization options:
- Industry only: `factor ~ industry_dummies` → residuals
- Industry + Cap: `factor ~ log(cap) + industry_dummies` → residuals
- Default: Industry (申万一级) + log(流通市值)

### Step 4: IC Analysis

Calculate for each period:
- **IC** = Pearson_corr(factor_values, forward_returns)
- **Rank IC** = Spearman_corr(factor_values, forward_returns)

Aggregate:
- Mean IC, Std IC
- **ICIR** = Mean_IC / Std_IC
- IC > 0 ratio (positive hit rate)

| Threshold | Interpretation |
|-----------|---------------|
| ICIR > 0.5 | Good factor |
| ICIR > 1.0 | Strong factor |
| ICIR < 0.3 | Weak, may not survive costs |
| IC > 0 ratio < 50% | Inconsistent direction |

### Step 5: Walk-Forward Validation

Standard configuration:
- Training window: 5 years (~1250 trading days)
- Validation window: 1 year
- Test window: 1 year
- Step: 1 year

For each fold:
1. Fit preprocessing on training data only
2. Apply to validation/test data
3. Calculate IC/ICIR on test window
4. Track decay over time

### Step 6: Factor Correlation

If comparing multiple factors:
- Calculate pairwise Rank IC between factors
- Flag pairs with |corr| > 0.6 as highly correlated
- Recommend diversified factor selection

### Step 7: Factor Scorecard

Generate PASS/FAIL assessment:

| Criterion | Threshold | Result |
|-----------|-----------|--------|
| Mean IC | > 0.03 | PASS/FAIL |
| ICIR | > 0.5 | PASS/FAIL |
| IC > 0 ratio | > 52% | PASS/FAIL |
| Turnover | < 50% | PASS/FAIL |
| Monotonicity | Quantile spread > 2% | PASS/FAIL |
| Stability | No decade with negative ICIR | PASS/FAIL |

### Step 8: Output

**Markdown Report:**
- Factor definition and construction logic
- IC/ICIR time series summary
- Walk-forward results table
- Factor scorecard
- Recommendations (NOT investment advice)

**Excel File:**
- Sheet 1: 因子值 (factor values matrix: stocks × dates)
- Sheet 2: IC序列 (IC time series)
- Sheet 3: 分层回测 (quantile portfolio returns)
- Sheet 4: 评分卡 (scorecard)
- File: `./out/factor_<name>_<date>.xlsx`
