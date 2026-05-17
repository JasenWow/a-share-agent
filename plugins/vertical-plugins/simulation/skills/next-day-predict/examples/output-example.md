# Next-Day Prediction Output Example

## Report Output

```markdown
# 次日预测报告 - 2026-05-09

| 股票代码 | 当前价 | 预测涨跌幅 | 置信度 | 信号 |
|---------|--------|-----------|--------|------|
| 000001 | 12.50 | +1.8% | 0.72 | 买入信号 |
| 600519 | 1850.00 | +0.5% | 0.65 | 持仓 |
| 300750 | 280.00 | null | - | 涨停排除 |

准确率追踪: MAE=1.2%, 方向准确率=68%
误差模式: 近5日对小盘股存在系统性高估
```

## Prediction Details

| Stock | Indicators | Reasoning |
|-------|------------|-----------|
| 000001 | RSI=58, MACD hist=+0.12, MA5>MA10>MA20 | Bullish alignment, positive momentum, confidence 0.72 |
| 600519 | RSI=45, MACD hist=+0.05, vol_ratio=0.8 | Neutral indicators, moderate volume, confidence 0.65 |
| 300750 | 涨跌幅度=+20%, limit-up detected | 涨停排除，无法买入 |

## Stored Prediction Records

After execution, predictions are stored via `store_prediction`:
- 000001: predicted_pct=1.8, confidence=0.72
- 600519: predicted_pct=0.5, confidence=0.65
- 300750: null (exclusion reason: "涨停排除")