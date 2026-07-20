# ETL: 数据仓 ODS 层采集

把 Tushare/AKShare 数据通过 MCP HTTP 接口拉取，落到 DuckDB + Parquet 的 ODS 层。
详细设计见 `docs/superpowers/specs/2026-07-18-data-warehouse-foundation-design.md`。

## 快速开始

```bash
# 1. 初始化数仓结构
uv run python -m scripts.etl.init

# 2. 确保 MCP server 运行
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000 &
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001 &

# 3. 跑 P0 域（当日）
uv run python -m scripts.etl.runner --priority P0 --date 20260717
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `python -m scripts.etl.init` | 初始化数仓（建目录、meta.db、视图、catalog） |
| `python -m scripts.etl.runner <domain> --date YYYYMMDD` | 单域单日 |
| `python -m scripts.etl.runner <domain> --start ... --end ...` | 单域日期范围（按交易日） |
| `python -m scripts.etl.runner --priority P0 --date ...` | 按 P0/P1/P2 批量 |
| `python -m scripts.etl.runner --all --date ...` | 所有已注册 domain |
| `python -m scripts.etl.report --missing-dates` | 查某 domain 缺失的交易日 |
| `python -m scripts.etl.report --jobs --status failed` | 查失败任务 |

## 已实现的数据域

| Domain | 优先级 | 数据源 | 分区 |
|--------|--------|--------|------|
| equity_daily | P0 | tushare `daily` | dt=YYYY-MM-DD |
| index_constituents | P0 | tushare `index_weight` | dt=YYYY-MM |
| financial_income | P1 | tushare `income` | period=YYYYQn |

P2 域（dragon_tiger / equity_spot）和剩余 P1（balance/cashflow/indicator/northbound）
按现有 domain 模式复制即可，见下方"添加新 domain"。

## 五段式 ETL 契约

每个 `ods/<domain>.py` 实现统一契约（让 runner 能统一调度，让测试能逐段验证）：

```python
DOMAIN = "equity_daily"
PARTITION_COL = "dt"
SOURCE_MCP = "tushare"

def extract(date: str, source: str = SOURCE_MCP) -> list[dict]: ...   # 从 MCP 拉
def transform(rows: list[dict], date: str) -> list[dict]: ...        # 最小标准化 + 元数据
def check_quality(rows: list[dict], date: str) -> QualityReport: ... # 阻断/告警
def load(rows: list[dict], date: str) -> dict: ...                   # 幂等写 Parquet
def run(date: str, **kwargs) -> dict: ...                            # 端到端编排

CATALOG_ENTRY = {...}  # 供 init.py 注册到 ods_catalog
```

## 添加新 domain

1. 复制 `ods/equity_daily.py` 为模板，改 DOMAIN / SOURCE_MCP / 字段映射
2. 加 fixture：`tests/fixtures/<source>_<name>.json`（真实返回样本）
3. 写测试：`tests/test_<domain>.py`（仿照 test_equity_daily.py）
4. 在 `runner.py` 的 `_DOMAIN_REGISTRY` 注册
5. 在 `init.py` 的 `_ALL_CATALOGS` 和 `_ODS_VIEWS` 注册

## 查询数据

```python
import duckdb
conn = duckdb.connect("data/warehouse/meta.db")
df = conn.execute("""
    SELECT code, close FROM ods_equity_daily
    WHERE dt = '2026-07-17' AND close > 100
""").fetchdf()
```

## 任务队列（JobService）

`common/jobs.py` 定义 `JobService` Protocol，本期实现 `DuckDBJobService`（存 `etl_jobs` 表）。
未来要支持外部提交任务 / 多 worker 时，新增 `PGBossJobService` 实现同一 Protocol，
业务代码（runner / 未来 Meta-Agent）无需改动。

`report --jobs` 子命令查任务历史；`report --status failed` 查失败。

## 设计边界（与现有系统）

- **不侵入** MCP/Skill/Agent：ETL 通过 MCP HTTP 取数，不修改 server
- **internal-store 不动**：internal-store 是运行时层，数仓是分析层，两者平行
- **数据源单一入口**：日常 ETL 走 MCP HTTP；历史回填预留 `--direct-sdk`（当前 no-op）

## 测试

```bash
# 单元测试（默认不连 MCP server，用 mock）
uv run pytest scripts/etl/tests/ -v

# 集成测试（需要 MCP server 运行 + TUSHARE_TOKEN）
uv run pytest scripts/etl/tests/ -v -m integration
```
