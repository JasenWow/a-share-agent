# AKShare MCP Server

A-share data connector based on AKShare.

## Tools

| Tool Name | Upstream Function | Description | Key Parameters |
|-----------|-------------------|-------------|----------------|
| `stock_zh_a_spot` | `ak.stock_zh_a_spot_em()` | Realtime quotes | symbol (optional) |
| `stock_zh_a_hist` | `ak.stock_zh_a_hist()` | Historical OHLCV | symbol, period, start_date, end_date, adjust |
| `stock_financial_abstract` | `ak.stock_financial_abstract_ths()` | Financial summary | symbol, indicator |
| `stock_financial_report_sina` | `ak.stock_financial_report_sina()` | Financial statements | stock, symbol, type |
| `stock_rank_cxg_thsh` | `ak.stock_rank_cxg_thsh()` | Shenwan industry stocks | indicator |
| `stock_hsgt_north_net_flow_in_em` | `ak.stock_hsgt_north_net_flow_in_em()` | Northbound capital flow | — |
| `stock_lhb_detail_em` | `ak.stock_lhb_detail_em()` | Dragon-tiger list | start_date, end_date |
| `index_stock_cons` | `ak.index_stock_cons_csindex()` | Index constituents | symbol |
| `stock_zh_index_daily` | `ak.stock_zh_index_daily()` | Index daily OHLCV | symbol, start_date, end_date |

## Running

```bash
uvicorn server:mcp_app --host 0.0.0.0 --port 8000
```

## Testing

```bash
pytest test_server.py -v
```
