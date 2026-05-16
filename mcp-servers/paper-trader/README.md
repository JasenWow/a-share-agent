# Paper Trader MCP Server

Event-driven A-share backtest simulation engine with web dashboard.

## Start

```bash
# Start with web UI + REST API + MCP (all on port 8004)
uv run uvicorn mcp-servers.paper-trader.server:combined_app --port 8004

# Open dashboard
open http://localhost:8004
```

## Web Dashboard

访问 `http://localhost:8004` 可查看可视化回测结果：

- **净值曲线** — 策略/基准 NAV 对比 + 回撤区域
- **绩效指标** — Sharpe/MaxDD/WinRate 等卡片 + 成本分解饼图 + 月度收益柱状图
- **交易记录** — 可筛选的买卖明细表
- **持仓分析** — 权重分布饼图 + 盈亏柱状图

## REST API

| Endpoint | Description |
|----------|-------------|
| `GET /api/sessions` | 列出所有回测会话 |
| `GET /api/sessions/{id}/status` | 会话状态 |
| `GET /api/sessions/{id}/equity` | 净值曲线数据 |
| `GET /api/sessions/{id}/performance` | 绩效指标 |
| `GET /api/sessions/{id}/trades` | 交易记录 |
| `GET /api/sessions/{id}/positions/latest` | 最新持仓 |

## MCP Tools

| Tool | Description |
|------|-------------|
| `create_session` | 创建回测会话 |
| `list_sessions` | 列出会话 |
| `get_session_status` | 会话状态 + 持仓 |
| `load_bar_data` | 加载 OHLCV 数据 |
| `submit_signal` | 提交买卖信号 |
| `submit_signals_batch` | 批量提交信号 |
| `step_session` | 逐日步进（agent 逐日操作） |
| `get_today_market` | 当前日行情 |
| `run_session` | 批量运行完整回测 |
| `get_equity_curve` | 净值时间序列 |
| `get_trade_log` | 交易明细 |
| `get_positions_snapshot` | 持仓快照 |
| `get_performance` | 绩效指标 |
| `save_results` | 保存到 internal-store |

## A-Share Constraints

- T+1: 买入当日不可卖
- 涨跌停: 主板 ±10%, 创业板/科创板 ±20%, 北交所 ±30%, ST ±5%
- 手数: 100 股整数倍
- 成本: 佣金 0.025%/双向, 印花税 0.05%/卖, 滑点 0.05%/单向
- ST/*ST 和停牌股默认排除

## Architecture

```
server.py          → MCP tools + REST API + Web UI serving
engine.py          → BacktestEngine (event-driven + step-by-step)
models.py          → Data classes
cost_model.py      → Transaction costs + A-share constraints
performance.py     → Performance metrics
web/               → Frontend SPA (HTML + ECharts)
  index.html       → Dashboard layout
  app.js           → SPA logic
schema.sql         → SQLite DDL
```
