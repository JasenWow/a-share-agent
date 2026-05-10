---
name: next-day-predict
description: |
  A-share next-day stock price return prediction workflow. Predicts
  next-day returns using technical indicators, recent accuracy trends,
  and error pattern analysis.

  Triggers: "/predict", "prediction", "预测", "明天涨跌", "next day predict",
  "次日预测"
---

# Next-Day Price Return Prediction

## Overview

This skill predicts next-day stock price returns for A-share stocks using
technical indicator analysis combined with prediction accuracy tracking.

**Core Philosophy:** "Technical signals + accuracy feedback = reliable predictions."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| stock_codes | list[str] | Yes | 6-digit stock codes |
| signal_date | str | No | YYYYMMDD (default: today) |

---

## Tool Dependencies

| Tool | Purpose |
|------|---------|
| `mcp__akshare__stock_zh_a_hist` | Historical OHLCV data (qfq, daily) |
| `mcp__akshare__stock_zh_a_spot` | Realtime price quotes |
| `mcp__prediction_store__manage_watchlist` | Get watchlist stocks |
| `mcp__prediction_store__store_prediction` | Store prediction results |
| `mcp__prediction_store__get_predictions` | Query prediction history |
| `mcp__prediction_store__record_actual` | Record actual returns |
| `mcp__prediction_store__get_accuracy_report` | Accuracy metrics (MAE, direction accuracy) |
| `mcp__prediction_store__get_error_analysis` | Error pattern analysis |

---

## Workflow

### Step 1: Get Stock Universe

Call `manage_watchlist(action="list")` to get watchlist stocks.

If user provided `stock_codes`, use those directly instead.

### Step 2: Fetch Historical Data

For each stock, call `stock_zh_a_hist`:
- `symbol`: stock code + ".SH" or ".SZ"
- `period`: "daily"
- `adjust`: "qfq" (forward-adjusted for dividend splits)
- Fetch last 60 trading days

### Step 3: Compute Technical Indicators

For each stock, compute in LLM reasoning:

| Indicator | Formula |
|-----------|---------|
| MA5 | 5-day simple moving average of close |
| MA10 | 10-day simple moving average of close |
| MA20 | 20-day simple moving average of close |
| RSI(14) | 100 - 100/(1 + RS), RS = avg(gain)/avg(loss) over 14 days |
| MACD | DIF = EMA12 - EMA26; DEA = EMA9(DIF); Hist = DIF - DEA |
| Bollinger Bands | Upper = MA20 + 2*std20; Middle = MA20; Lower = MA20 - 2*std20 |
| Volume Ratio | today's volume / 5-day average volume |

### Step 4: Check Recent Accuracy

Call `get_accuracy_report(days=30)` to retrieve:
- MAE (Mean Absolute Error)
- Direction accuracy (% of correct up/down predictions)
- Prediction count

### Step 5: Analyze Error Patterns

Call `get_error_analysis(days=30)` to get:
- Systematic biases (e.g., small-cap overestimation)
- Market regime sensitivity
- Indicator-specific error patterns

### Step 6: Generate Predictions

For each stock, generate:
- `predicted_pct`: predicted change in percent
- `confidence`: probability estimate in [0, 1]

Consider:
- Technical indicator values (MA alignment, RSI overbought/oversold)
- MACD histogram direction and magnitude
- Bollinger Band position
- Volume ratio anomaly
- Recent accuracy trend
- Error pattern corrections

### Step 7: Store Predictions

For each stock, call `store_prediction`:
- `stock_code`: 6-digit code
- `signal_date`: YYYYMMDD
- `predicted_pct`: predicted change percent
- `confidence`: confidence in [0, 1]
- `features_summary`: JSON with key indicator values

### Step 8: Record Actuals for Previous Predictions

Check for unverified predictions from previous signal_date:
- Call `stock_zh_a_spot` to get current price
- Compute `actual_pct = (current_price - prev_close) / prev_close * 100`
- Call `record_actual` to update prediction records

### Step 9: Generate Report

Output markdown with:

**Prediction Table:**
| 股票代码 | 当前价 | 预测涨跌幅 | 置信度 | 信号 |
|---------|--------|-----------|--------|------|
| 000001 | 12.50 | +1.8% | 0.72 | 买入信号 |
| 600519 | 1850.00 | +0.5% | 0.65 | 持仓 |

**Accuracy Summary:**
- MAE over last 30 predictions
- Direction accuracy rate
- Error pattern observations

---

## Guardrails

1. **Never predict on涨停/跌停 stocks** — limit-up/limit-down cannot be traded
2. **Never skip volume=0 check** — suspended stocks have meaningless indicators
3. **Always use adjust="qfq"** — forward-adjusted prices for continuity
4. **Clamp confidence to [0, 1]** — never expose out-of-range confidence
5. **Clamp predicted_pct to [-30, 30]** — A-share daily limit is at most ±30%

---

## Common Mistakes

| Mistake | Why It's Wrong | Correct Approach |
|---------|---------------|------------------|
| 涨跌停未排除 | ±10%/20% 涨跌停无法买入/卖出 | Check 涨跌幅度，排除涨停/跌停股票 |
| 停牌强行预测 | volume=0 时指标无意义 | 检查 volume=0 → skip 预测 |
| 未使用前复权数据 | 存在配股/分红时价格不可比 | use adjust="qfq" |
| 预测非交易日 | 无交易数据 | 使用 get_next_trading_day 确认日期 |
| 置信度超过范围 | LLM 可能输出 >1 | Clamp confidence to [0, 1] |

---

## Quality Checklist

- [ ] Stock code is 6-digit string (with .SH/.SZ suffix when calling MCP)
- [ ] Excluded stocks (ST, suspended, limit-up/down) have null prediction
- [ ] Confidence is in [0, 1]
- [ ] predicted_pct is in [-30, 30]
- [ ] Accuracy trend (MAE) is reported
- [ ] Error patterns are analyzed
- [ ] All predictions stored via `store_prediction`
- [ ] Previous unverified predictions have actuals recorded