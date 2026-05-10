# Internal Store MCP Server

Local data store for caching, backtest results, and portfolio state persistence.

## Tools

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `query_cache` | Query local cache data | source, tool_name, params |
| `list_backtest_results` | List all backtest results | limit |
| `get_portfolio` | Get current portfolio state | name |

## Running

```bash
uvicorn server:mcp_app --host 0.0.0.0 --port 8002
```

## Cache Strategy

| Data Type | TTL | Storage | Rationale |
|-----------|-----|---------|-----------|
| Real-time quotes | No cache | — | Must be fresh |
| Daily OHLCV | 1 day | Parquet (per stock) | Stale after market close |
| Financial statements | 90 days | Parquet | Quarterly updates |
| Index constituents | 30 days | Parquet | Semi-annual rebalancing |
| Northbound flow | 1 day | Parquet | Daily update |
| Backtest results | Permanent | Parquet + SQLite | Never expires
