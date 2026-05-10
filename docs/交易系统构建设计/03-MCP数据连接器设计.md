# MCP 数据连接器设计

> 本文档设计 A 股量化分析 Agent 系统的 MCP（Model Context Protocol）数据连接器层。
> 连接器负责将 AKShare、Tushare 等数据源封装为标准 MCP Server，供 Agent 统一调用。

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   Agent Layer                        │
│  (stock-screener, factor-analyst, backtester, ...)  │
└──────────────┬──────────────┬───────────────────────┘
               │              │
        MCP (HTTP)      MCP (HTTP)
               │              │
┌──────────────▼──────┐ ┌─────▼──────────────┐
│  AKShare MCP Server │ │ Tushare MCP Server │
│  localhost:8000     │ │ localhost:8001     │
│  (免费/实时)        │ │ (Token/历史)       │
└──────┬──────────────┘ └─────┬──────────────┘
       │                      │
┌──────▼──────────────────────▼──────┐
│       Internal Data Store          │
│  SQLite + Parquet (本地缓存)       │
└────────────────────────────────────┘
```

核心设计原则：
- **每个数据源一个 MCP Server**，独立部署、独立升级
- **HTTP transport**，遵循 `type: "http"` 配置模式（与 financial-services 插件一致）
- **本地缓存优先**，减少 API 调用，加速回测
- **统一错误处理**，数据源不可用时自动降级到缓存

---

## 2. AKShare MCP Server

### 2.1 概述

AKShare 是一个开源的金融数据接口库，覆盖 A 股实时行情、历史数据、财务报表、资金流向等。
MCP Server 将 AKShare 的 Python API 封装为 MCP Tools，供 Agent 通过标准协议调用。

- **Server URL**: `http://localhost:8000/mcp`
- **Transport**: Streamable HTTP
- **依赖**: `akshare`, `mcp`, `pandas`, `fastapi`

### 2.2 工具清单

| Tool Name | AKShare 函数 | 说明 | 关键参数 |
|-----------|-------------|------|---------|
| `stock_zh_a_spot` | `ak.stock_zh_a_spot_em()` | A 股实时行情 | symbol (可选) |
| `stock_zh_a_hist` | `ak.stock_zh_a_hist()` | 历史 OHLCV | symbol, period, start_date, end_date, adjust |
| `stock_financial_abstract` | `ak.stock_financial_abstract_ths()` | 财务摘要 | symbol, indicator |
| `stock_financial_report_sina` | `ak.stock_financial_report_sina()` | 详细财务报表 | stock, symbol, type |
| `stock_rank_cxg_thsh` | `ak.stock_rank_cxg_thsh()` | 申万行业成分股 | indicator, industry_code |
| `stock_hsgt_north_net_flow_in_em` | `ak.stock_hsgt_north_net_flow_in_em()` | 北向资金净流入 | 无 (返回历史序列) |
| `stock_lhb_detail_em` | `ak.stock_lhb_detail_em()` | 龙虎榜明细 | start_date, end_date |
| `index_stock_cons` | `ak.index_stock_cons_csindex()` | 指数成分股 | symbol (指数代码) |
| `stock_zh_index_daily` | `ak.stock_zh_index_daily()` | 指数日线行情 | symbol, start_date, end_date |

### 2.3 Python 实现草图

```python
# mcp-servers/akshare-server/server.py
"""
AKShare MCP Server — A 股数据连接器
运行: uvicorn server:mcp_app --host 0.0.0.0 --port 8000
"""

from mcp.server.fastmcp import FastMCP
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

# --- Server Setup ---
mcp = FastMCP(
    name="akshare-a-share",
    version="0.1.0",
    description="A 股数据 MCP Server，基于 AKShare"
)

# --- Helper ---
def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    """将 DataFrame 转为 JSON 序列化的 dict list，截断超长结果"""
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")

# --- Tools ---

@mcp.tool()
def stock_zh_a_spot(symbol: str | None = None) -> list[dict]:
    """
    获取 A 股实时行情快照。
    可选按股票代码过滤。返回全部 A 股最新价、涨跌幅、成交量等。
    """
    df = ak.stock_zh_a_spot_em()
    if symbol:
        df = df[df["代码"] == symbol]
    return df_to_json(df, max_rows=10000)


@mcp.tool()
def stock_zh_a_hist(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> list[dict]:
    """
    获取单只 A 股历史 OHLCV 数据。

    参数:
        symbol:    股票代码，如 "000001"
        period:    周期 "daily" / "weekly" / "monthly"
        start_date: 起始日期 "YYYYMMDD"，默认一年前
        end_date:   截止日期 "YYYYMMDD"，默认今天
        adjust:    复权类型 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    return df_to_json(df)


@mcp.tool()
def stock_financial_abstract(symbol: str, indicator: str = "按年度") -> list[dict]:
    """
    获取股票财务摘要（同花顺来源）。

    参数:
        symbol:   股票代码，如 "000001"
        indicator: "按年度" / "按单季度"
    """
    df = ak.stock_financial_abstract_ths(symbol=symbol, indicator=indicator)
    return df_to_json(df)


@mcp.tool()
def stock_financial_report_sina(
    stock: str,
    symbol: str = "利润表",
    type: str = "年报",
) -> list[dict]:
    """
    获取新浪财经详细财务报表。

    参数:
        stock:  股票代码 "sh600000" 或 "sz000001"
        symbol: 报表类型 "利润表" / "资产负债表" / "现金流量表"
        type:   报告类型 "年报" / "中报" / "一季报" / "三季报"
    """
    df = ak.stock_financial_report_sina(stock=stock, symbol=symbol)
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def stock_rank_cxg_thsh(indicator: str = "成分股") -> list[dict]:
    """
    获取申万行业分类成分股列表。
    """
    df = ak.stock_rank_cxg_thsh(indicator=indicator)
    return df_to_json(df, max_rows=5000)


@mcp.tool()
def stock_hsgt_north_net_flow_in_em() -> list[dict]:
    """
    获取北向资金（沪深港通）净流入历史数据。
    返回日期、净买入额、累计净买入等字段。
    """
    df = ak.stock_hsgt_north_net_flow_in_em(indicator="北上")
    return df_to_json(df, max_rows=10000)


@mcp.tool()
def stock_lhb_detail_em(
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    获取东方财富龙虎榜明细数据。

    参数:
        start_date: 起始日期 "YYYYMMDD"
        end_date:   截止日期 "YYYYMMDD"
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
    return df_to_json(df)


@mcp.tool()
def index_stock_cons(symbol: str = "000300") -> list[dict]:
    """
    获取指数成分股列表。

    参数:
        symbol: 指数代码，如 "000300"(沪深300) / "000905"(中证500)
    """
    df = ak.index_stock_cons_csindex(symbol=symbol)
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def stock_zh_index_daily(
    symbol: str = "sh000300",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    获取指数日线行情。

    参数:
        symbol:     指数代码，带前缀 "sh"/"sz"
        start_date: 起始日期 "YYYYMMDD"
        end_date:   截止日期 "YYYYMMDD"
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    df = ak.stock_zh_index_daily(symbol=symbol)
    # 日期过滤
    df["date"] = pd.to_datetime(df["date"])
    df = df[
        (df["date"] >= start_date) & (df["date"] <= end_date)
    ]
    return df_to_json(df)


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)
```

### 2.4 依赖文件 (pyproject.toml)

```toml
# mcp-servers/akshare-server/pyproject.toml
[project]
name = "akshare-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "akshare>=1.14",
    "mcp>=1.0",
    "pandas>=2.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]

[project.scripts]
akshare-mcp = "server:main"
```

---

## 3. Tushare MCP Server

### 3.1 概述

Tushare 是国内广泛使用的量化数据平台，提供高质量的 A 股历史数据和财务数据。
与 AKShare 的差异：
- 需要注册获取 Token
- 数据质量更高，适合回测和因子研究
- 提供指数成分权重（point-in-time），避免前视偏差

- **Server URL**: `http://localhost:8001/mcp`
- **Transport**: Streamable HTTP
- **认证**: Token-based（环境变量 `TUSHARE_TOKEN`）

### 3.2 工具清单

| Tool Name | Tushare 接口 | 说明 | 关键参数 |
|-----------|-------------|------|---------|
| `daily` | `pro.daily()` | 日线 OHLCV | ts_code, start_date, end_date |
| `income` | `pro.income()` | 利润表 | ts_code, period, report_type |
| `balancesheet` | `pro.balancesheet()` | 资产负债表 | ts_code, period |
| `cashflow` | `pro.cashflow()` | 现金流量表 | ts_code, period |
| `fina_indicator` | `pro.fina_indicator()` | 财务指标 | ts_code, period |
| `index_weight` | `pro.index_weight()` | 指数成分权重（时点） | index_code, start_date, end_date |
| `concept_detail` | `pro.concept_detail()` | 概念板块成分股 | id (概念代码) |

### 3.3 Python 实现草图

```python
# mcp-servers/tushare-server/server.py
"""
Tushare MCP Server — A 股高质量数据连接器
运行: TUSHARE_TOKEN=xxx uvicorn server:mcp_app --host 0.0.0.0 --port 8001
"""

import os
from mcp.server.fastmcp import FastMCP
import tushare as ts
import pandas as pd

# --- Auth ---
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
if not TUSHARE_TOKEN:
    raise ValueError("TUSHARE_TOKEN 环境变量未设置")

pro = ts.pro_api(TUSHARE_TOKEN)

mcp = FastMCP(
    name="tushare-a-share",
    version="0.1.0",
    description="A 股高质量数据 MCP Server，基于 Tushare Pro"
)

def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")


@mcp.tool()
def daily(
    ts_code: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 5000,
) -> list[dict]:
    """
    获取 A 股日线行情 (OHLCV)。

    参数:
        ts_code:     股票代码 "000001.SZ"，为空则返回全市场
        start_date:  起始日期 "YYYYMMDD"
        end_date:    截止日期 "YYYYMMDD"
    """
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return df_to_json(df, max_rows=limit)


@mcp.tool()
def income(
    ts_code: str,
    period: str = "",
    report_type: int = 1,
) -> list[dict]:
    """
    获取利润表数据。

    参数:
        ts_code:      股票代码 "000001.SZ"
        period:       报告期 "20240331"
        report_type:  1=合并 2=单季
    """
    df = pro.income(
        ts_code=ts_code,
        period=period,
        report_type=report_type,
    )
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def balancesheet(ts_code: str, period: str = "") -> list[dict]:
    """
    获取资产负债表数据。

    参数:
        ts_code:  股票代码 "000001.SZ"
        period:   报告期 "20240331"
    """
    df = pro.balancesheet(ts_code=ts_code, period=period)
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def cashflow(ts_code: str, period: str = "") -> list[dict]:
    """
    获取现金流量表数据。

    参数:
        ts_code:  股票代码 "000001.SZ"
        period:   报告期 "20240331"
    """
    df = pro.cashflow(ts_code=ts_code, period=period)
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def fina_indicator(ts_code: str, period: str = "") -> list[dict]:
    """
    获取财务指标（ROE、毛利率、净利率等）。

    参数:
        ts_code:  股票代码 "000001.SZ"
        period:   报告期 "20240331"
    """
    df = pro.fina_indicator(ts_code=ts_code, period=period)
    return df_to_json(df, max_rows=2000)


@mcp.tool()
def index_weight(
    index_code: str = "399300.SZ",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    获取指数成分股权重（point-in-time，避免前视偏差）。

    参数:
        index_code:  指数代码 "399300.SZ"(沪深300)
        start_date:  起始日期 "YYYYMMDD"
        end_date:    截止日期 "YYYYMMDD"
    """
    df = pro.index_weight(
        index_code=index_code,
        start_date=start_date,
        end_date=end_date,
    )
    return df_to_json(df, max_rows=10000)


@mcp.tool()
def concept_detail(id: str = "") -> list[dict]:
    """
    获取概念板块成分股。

    参数:
        id: 概念代码（为空返回所有概念列表）
    """
    df = pro.concept_detail(id=id)
    return df_to_json(df, max_rows=5000)


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8001)
```

---

## 4. Internal Data Store

### 4.1 架构

本地数据存储层用于缓存 MCP Server 返回的数据，避免重复请求，并保存回测结果和组合状态。

```
data/
├── cache/
│   ├── akshare/          # AKShare 缓存
│   │   ├── daily/        # 日线 Parquet 文件
│   │   │   ├── 000001.parquet
│   │   │   └── 600519.parquet
│   │   ├── financial/    # 财务数据
│   │   └── index/        # 指数数据
│   ├── tushare/          # Tushare 缓存
│   │   ├── daily/
│   │   ├── financial/
│   │   └── index_weight/
│   └── meta.db           # SQLite 元数据库
├── backtest/
│   ├── results/          # 回测结果 Parquet
│   └── portfolios/       # 组合状态 JSON
└── logs/
    └── mcp-servers.log
```

### 4.2 SQLite 元数据库 Schema

```sql
-- 缓存追踪表
CREATE TABLE IF NOT EXISTS cache_entries (
    source      TEXT NOT NULL,       -- 'akshare' | 'tushare'
    tool_name   TEXT NOT NULL,       -- MCP tool name
    params_hash TEXT NOT NULL,       -- SHA256 of params JSON
    file_path   TEXT NOT NULL,       -- 相对路径
    fetched_at  TEXT NOT NULL,       -- ISO timestamp
    expires_at  TEXT NOT NULL,       -- 过期时间
    row_count   INTEGER DEFAULT 0,
    PRIMARY KEY (source, tool_name, params_hash)
);

-- 回测结果索引
CREATE TABLE IF NOT EXISTS backtest_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    strategy    TEXT NOT NULL,       -- 策略描述
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    sharpe      REAL,
    max_drawdown REAL,
    annual_return REAL,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 组合状态
CREATE TABLE IF NOT EXISTS portfolio_state (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    holdings    TEXT NOT NULL,       -- JSON: [{ts_code, weight, shares}]
    cash        REAL DEFAULT 0,
    updated_at  TEXT DEFAULT (datetime('now'))
);
```

### 4.3 缓存策略

| 数据类型 | 缓存时长 | 存储格式 | 说明 |
|---------|---------|---------|------|
| 实时行情 | 不缓存 | — | 每次实时获取 |
| 日线行情 | 1 天 | Parquet | 按股票代码分文件 |
| 财务报表 | 90 天 | Parquet | 季度更新 |
| 指数成分 | 30 天 | Parquet | 半年调整 |
| 北向资金 | 1 天 | Parquet | 日频更新 |
| 回测结果 | 永久 | Parquet + SQLite | 带索引 |

---

## 5. .mcp.json 配置

### 5.1 项目级 .mcp.json

将以下文件放置在项目根目录 `a-share-agents/.mcp.json`：

```json
{
  "mcpServers": {
    "akshare": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "description": "AKShare A 股数据 — 实时行情、历史 OHLCV、财务报表、北向资金、龙虎榜"
    },
    "tushare": {
      "type": "http",
      "url": "http://localhost:8001/mcp",
      "description": "Tushare Pro A 股数据 — 高质量历史数据、财务报表、指数权重、概念板块",
      "env": {
        "TUSHARE_TOKEN": "${TUSHARE_TOKEN}"
      }
    },
    "internal-store": {
      "type": "http",
      "url": "http://localhost:8002/mcp",
      "description": "本地数据存储 — 缓存查询、回测结果管理、组合状态持久化"
    }
  }
}
```

### 5.2 插件级 .mcp.json (vertical plugin)

放置在 `plugins/vertical-plugins/a-share-analysis/.mcp.json`：

```json
{
  "mcpServers": {
    "akshare": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "description": "AKShare A 股数据连接器"
    },
    "tushare": {
      "type": "http",
      "url": "http://localhost:8001/mcp",
      "description": "Tushare Pro A 股数据连接器",
      "env": {
        "TUSHARE_TOKEN": "${TUSHARE_TOKEN}"
      }
    }
  }
}
```

---

## 6. Internal Store MCP Server（可选）

为缓存层和回测结果提供 MCP 接口，使 Agent 可以直接查询本地数据。

```python
# mcp-servers/internal-store/server.py
"""
Internal Data Store MCP Server — 本地数据管理
运行: uvicorn server:mcp_app --host 0.0.0.0 --port 8002
"""

from mcp.server.fastmcp import FastMCP
import sqlite3
import json
import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "./data"))
DB_PATH = DATA_ROOT / "cache" / "meta.db"

mcp = FastMCP(
    name="internal-store",
    version="0.1.0",
    description="本地数据存储 MCP Server — 缓存查询、回测管理"
)


@mcp.tool()
def query_cache(source: str, tool_name: str, params: dict = {}) -> list[dict]:
    """
    查询本地缓存数据。如果缓存未过期，直接返回本地数据；
    否则返回空列表，提示 Agent 需要从数据源重新获取。
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    import hashlib
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True).encode()
    ).hexdigest()

    row = conn.execute(
        "SELECT * FROM cache_entries WHERE source=? AND tool_name=? AND params_hash=?",
        (source, tool_name, params_hash),
    ).fetchone()
    conn.close()

    if not row:
        return [{"status": "cache_miss", "message": "未找到缓存"}]

    # 检查是否过期
    from datetime import datetime
    if row["expires_at"] < datetime.now().isoformat():
        return [{"status": "cache_expired", "message": "缓存已过期"}]

    # 读取 Parquet 文件
    import pandas as pd
    file_path = DATA_ROOT / row["file_path"]
    if file_path.exists():
        df = pd.read_parquet(str(file_path))
        return df.to_dict(orient="records")
    return [{"status": "file_missing", "message": "缓存文件不存在"}]


@mcp.tool()
def list_backtest_results(limit: int = 20) -> list[dict]:
    """列出所有回测结果"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@mcp.tool()
def get_portfolio(name: str = "default") -> dict:
    """获取当前组合状态"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM portfolio_state WHERE name=? ORDER BY updated_at DESC LIMIT 1",
        (name,),
    ).fetchone()
    conn.close()
    if not row:
        return {"status": "not_found", "holdings": [], "cash": 0}
    return {
        "name": row["name"],
        "holdings": json.loads(row["holdings"]),
        "cash": row["cash"],
        "updated_at": row["updated_at"],
    }


mcp_app = mcp.streamable_http_app()
```

---

## 7. 数据流示例

### 7.1 因子筛选流程

```
用户输入: "筛选沪深300中ROE>15%、PE<20的股票"

Agent (factor-analyst) 调用链:
  1. tushare.index_weight(index_code="399300.SZ")
     → 获取沪深300成分股列表 + 权重

  2. tushare.fina_indicator(ts_code="xxx.SZ")
     → 批量获取财务指标

  3. akshare.stock_zh_a_spot()
     → 获取当前 PE/PB

  4. internal-store.query_cache(...)
     → 检查本地缓存

  5. Agent 本地计算:
     → 过滤 ROE > 15% AND PE < 20
     → 输出筛选结果
```

### 7.2 回测流程

```
用户输入: "/backtest 沪深300动量策略 2023-01-01 至 2024-12-31"

Agent (backtester) 调用链:
  1. akshare.stock_zh_a_hist(symbol, start_date, end_date)
     → 获取历史行情

  2. tushare.index_weight(index_code, start_date, end_date)
     → 获取时点成分权重

  3. Agent 本地计算:
     → 构建因子信号
     → 执行回测
     → 计算绩效指标

  4. internal-store 保存回测结果
```

---

## 8. 错误处理与降级策略

```python
# 建议在 Agent system prompt 中注入的降级逻辑

FALLBACK_STRATEGY = """
数据获取降级策略:
1. 优先使用 internal-store 缓存
2. 缓存未命中 → 尝试 AKShare (免费、无限制)
3. AKShare 失败 → 尝试 Tushare (Token、有频次限制)
4. 全部失败 → 返回错误信息，建议用户稍后重试
5. 实时行情不可用 → 使用最近一个交易日的日线数据替代
"""
```

| 错误类型 | 处理方式 |
|---------|---------|
| API 限频 (429) | 退避重试，最多 3 次 |
| 网络超时 | 降级到本地缓存 |
| 数据为空 | 返回空结果 + 警告信息 |
| Token 无效 | 提示用户检查 Tushare Token |
| Server 未启动 | 提示用户运行 MCP Server |

---

## 9. 安全注意事项

- **Tushare Token**: 通过环境变量传入，不硬编码在配置文件中
- **.gitignore**: `data/` 目录不入版本控制
- **API Key 管理**: 敏感信息仅存储在 `.env` 文件中
- **本地 MCP Server**: 仅绑定 `localhost`，不对外暴露
- **数据合规**: 遵守数据源的使用条款，不进行高频爬取
