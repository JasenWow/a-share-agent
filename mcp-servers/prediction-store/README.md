# Prediction Store MCP Server

Stock prediction persistence and accuracy tracking for A-share quantitative analysis.

## Running

```bash
uvicorn server:mcp_app --host 0.0.0.0 --port 8003
```

## Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `manage_watchlist` | Add, remove, or list watchlist stocks | `action` (add/remove/list), `stock_codes` (list of 6-digit codes) |
| `store_prediction` | Store or update a prediction | `stock_code`, `signal_date` (YYYYMMDD), `predicted_pct`, `confidence`, `features_summary` |
| `get_predictions` | Query prediction records | `stock_code`, `signal_date`, `limit` (default 30, max 500) |
| `record_actual` | Record actual % change, auto-computes error | `stock_code`, `signal_date`, `actual_pct` |
| `batch_record_actual` | Batch record actuals for multiple stocks | `signal_date`, `actuals_list` (list of dicts) |
| `get_accuracy_report` | Compute MAE, hit rate, bias metrics | `stock_code` (optional), `days` (default 30, max 365) |
| `get_error_analysis` | Analyze error patterns by stock, direction, magnitude | `days` (default 30, max 365) |
| `get_next_trading_day` | Get next trading day using Chinese calendar | `from_date` (YYYYMMDD, default today) |

## Database Schema

### predictions
| Column | Type | Description |
|--------|------|-------------|
| stock_code | TEXT | 6-digit stock code |
| signal_date | TEXT | YYYYMMDD |
| predicted_pct | REAL | Predicted % change |
| confidence | REAL | 0-1 confidence level |
| features_summary | TEXT | JSON of technical indicators |
| actual_pct | REAL | Recorded actual % change |
| error | REAL | actual_pct - predicted_pct |
| version | INTEGER | Upsert version counter |
| baseline | INTEGER | Cold-start flag |
| created_at | TEXT | Creation timestamp |
| verified_at | TEXT | When actual was recorded |

### watchlist
| Column | Type | Description |
|--------|------|-------------|
| stock_code | TEXT | 6-digit stock code |
| stock_name | TEXT | Optional display name |
| added_at | TEXT | Addition timestamp |
| is_active | INTEGER | 1=active, 0=removed |

### trading_calendar
| Column | Type | Description |
|--------|------|-------------|
| trade_date | TEXT | YYYYMMDD |
| is_trading_day | INTEGER | 1=trading, 0=holiday |

## Return Format

All tools return `list[dict]`. On error:
```python
[{"error": "error message", "tool": "tool_name", "params": {...}}]
```