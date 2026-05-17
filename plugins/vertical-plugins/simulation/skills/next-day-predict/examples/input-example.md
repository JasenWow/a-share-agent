# Next-Day Prediction Input Example

## User Request

"帮我预测以下股票明天的涨跌：000001, 600519, 300750"

## Provided Parameters

```
Stock codes: ["000001", "600519", "300750"]
Signal date: 20260509 (optional, default today)
```

## Notes

- Stock codes must be 6-digit strings
- If signal_date is omitted, today's date is used
- User may provide a watchlist via the prediction store instead