# Tushare MCP Server

A-share high-quality data connector based on Tushare Pro.

## Setup

```bash
export TUSHARE_TOKEN=your_token_here
```

## Tools

| Tool Name | Tushare Function | Description | Key Parameters |
|-----------|-----------------|-------------|----------------|
| `daily` | `pro.daily()` | Daily OHLCV | ts_code, start_date, end_date |
| `income` | `pro.income()` | Income statement | ts_code, period, report_type |
| `balancesheet` | `pro.balancesheet()` | Balance sheet | ts_code, period |
| `cashflow` | `pro.cashflow()` | Cash flow statement | ts_code, period |
| `fina_indicator` | `pro.fina_indicator()` | Financial indicators | ts_code, period |
| `index_weight` | `pro.index_weight()` | Index constituent weights (PIT) | index_code, start_date, end_date |
| `concept_detail` | `pro.concept_detail()` | Concept sector stocks | id |

## Running

```bash
TUSHARE_TOKEN=xxx uvicorn server:mcp_app --host 0.0.0.0 --port 8001
```
