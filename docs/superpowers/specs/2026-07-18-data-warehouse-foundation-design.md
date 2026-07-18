# 数据仓地基 + 数据采集 ETL 设计

**日期**: 2026-07-18
**状态**: Approved（待 spec review）
**作者**: jasenwood + ZCode
**关联**: 这是"数仓 + 语义层 + Meta-Agent"大架构的**第一个子项目**。后续 dbt 建模、语义层、Meta-Agent 各自走独立 spec。

---

## 0. 背景与动机

### 0.1 问题诊断

当前项目（A-Share Agents）有完整的 agent/skill/MCP 架构，但**数据是"流过即逝"的**：

- Tushare/AKShare 拉的数据只在单次工具调用内存中存在，无沉淀
- `internal-store` 的 `cache_entries` 表存在但**从未被写入**（死代码）
- 因子评估（IC/ICIR）、回测指标（Sharpe/MaxDD）分散在各 skill 的 scripts，无统一 sink
- 无法回答"动量因子在中证 500 上过去 3 年的 IC 衰减"这类**跨实验 OLAP 问题**
- meta-strategist 自演化闭环的"读历史最佳"无可靠数据源

### 0.2 目标

建立**数据仓地基**，让原始数据沉淀下来，为后续的：

1. dbt 建模（DWD/DWS/ADS）
2. 语义层（指标统一定义）
3. Meta-Agent（自然语言探索分析）

提供数据基础。**本期只做 ODS 层 + 数据采集 ETL**，不做建模、不做语义层、不做 Agent。

### 0.3 非目标（明确不做）

- ❌ dbt 项目（DWD/DWS/ADS 建模）—— 后续 spec
- ❌ 语义层（Cube.dev / dbt SL）—— 后续 spec
- ❌ Meta-Agent —— 后续 spec
- ❌ 因子/回测实验数据入仓 —— 另一条 ETL 线，后续 spec
- ❌ 数据权限 / 多租户
- ❌ PGlite / pgboss（见 §6 决策记录）

---

## 1. 整体架构

### 1.1 定位

数仓作为**新的平行子系统**，不侵入现有 MCP/Skill/Agent：

```
┌──────────────────────────────────────────────────────┐
│ 现有层（完全不动）                                       │
│  L0 MCP Servers (akshare/tushare/qlib/internal-store)  │
│  L1 Skills / L2 Agents / L3 Meta-strategist            │
└──────────────────────────────────────────────────────┘
              ↑ 实时查询               ↓ 仅读取（未来）
┌──────────────────────────────────────────────────────┐
│ 新增层：数仓                                            │
│  scripts/etl/  ──HTTP──→  MCP Servers（取数）           │
│       ↓                                                │
│  DuckDB (meta.db)  ←  Parquet (data/warehouse/ods/)    │
│       ↓ JobService 抽象                                │
│  etl_jobs 表（任务队列）                                 │
└──────────────────────────────────────────────────────┘
              ↓ 未来 spec 读取
       dbt → 语义层 → Meta-Agent
```

### 1.2 范围边界

**做**：
- ODS 层物理落地（DuckDB + Parquet 分区表）
- 5 个数据域的 ETL 脚本
- 数据目录（catalog）+ 血缘字段预留
- 轻量任务队列（DuckDB jobs 表 + JobService 抽象）
- 数据质量检查 + report 子命令

**不做**：见 §0.3

### 1.3 设计原则

1. **贴源最小加工**：ODS 层只做 snake_case 重命名 + 类型转换，不做业务逻辑（不复权、不去停牌）
2. **幂等可重跑**：同一 `dt` 重跑覆盖，不产生重复
3. **数据源单一入口**：ETL 通过 MCP server HTTP 接口取数，保证与 agent 数据口径一致
4. **小步快跑**：5 个域分 P0/P1/P2 优先级独立交付
5. **可演进**：JobService 抽象接口，未来可从 DuckDB jobs 表升级到 pgboss

---

## 2. ODS Schema 设计

### 2.1 数据域划分

| 数据域 | ODS 表名 | 数据源 MCP 工具 | 更新频率 | 优先级 |
|---|---|---|---|---|
| 股票行情 | `ods_equity_daily` | `stock_zh_a_hist` / `daily` | 日（收盘后） | P0 |
| 指数成分 | `ods_index_constituents` | `index_stock_cons` / `index_weight` | 月（按月快照，捕捉成分调整） | P0 |
| 财务报表（利润） | `ods_financial_income` | `income` / `stock_financial_abstract` | 季 | P1 |
| 财务报表（资产负债） | `ods_financial_balance` | `balancesheet` | 季 | P1 |
| 财务报表（现金流） | `ods_financial_cashflow` | `cashflow` | 季 | P1 |
| 财务指标 | `ods_financial_indicator` | `fina_indicator` | 季 | P1 |
| 北向资金 | `ods_northbound_flow` | `stock_hsgt_north_net_flow_in_em` | 日 | P1 |
| 龙虎榜 | `ods_dragon_tiger` | `stock_lhb_detail_em` | 日 | P2 |
| 实时快照 | `ods_equity_spot`（可选） | `stock_zh_a_spot` | 盘中 | P2 |

### 2.2 物理存储模型

```
data/warehouse/
├── ods/                                    # ODS 层 Parquet 文件
│   ├── equity_daily/
│   │   └── dt=2026-07-17/
│   │       └── part-0.parquet              # 当日全市场日线
│   ├── index_constituents/
│   │   └── dt=2026-07/                     # 月度分区
│   ├── financial_income/
│   │   └── period=2024Q4/                  # 财报期分区
│   ├── northbound_flow/
│   │   └── dt=2026-07-17/
│   └── dragon_tiger/
│       └── dt=2026-07-17/
├── meta.db                                 # DuckDB 元数据库
├── _logs/                                  # ETL 运行日志（JSON）
└── (dbt 项目目录留给后续 spec)
```

**分区策略**：
- 日频表：`dt=YYYY-MM-DD`（equity_daily / northbound_flow / dragon_tiger / equity_spot）
- 月频表：`dt=YYYY-MM`（index_constituents，按月快照保留调整历史）
- 财报表：`period=YYYYQn`（financial_*，同财报期会修订，保留多版本）

### 2.3 通用 schema 约定

**业务字段**：最小标准化（snake_case + 类型转换）

**元数据字段**（每张 ODS 表都有，`__` 前缀避免与业务字段冲突）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `__source` | str | 数据源（"tushare" / "akshare"） |
| `__source_tool` | str | MCP 工具名（"daily" / "stock_zh_a_hist"） |
| `__fetched_at` | str | 拉取时间 ISO8601 带时区 |
| `__params_hash` | str | MCP 调用参数的 sha256（追溯用） |
| `__etl_run_id` | str | ETL 运行实例 ID（如 `20260717_170003_equity_daily`） |

### 2.4 `ods_equity_daily` schema（示例）

业务字段：
```
trade_date   str    YYYYMMDD 格式（保留原格式，避免时区问题）
code         str    6 位裸码（"600519"）
exchange     str    交易所（"SH" / "SZ" / "BJ"）
name         str    股票名称
open         float  开盘价
high         float  最高价
low          float  最低价
close        float  收盘价
volume       int    成交量（股）
amount       float  成交额（元）
pct_chg      float  涨跌幅（%）
```

加 5 个元数据字段（§2.3）。

**股票代码统一规则**：裸码 + exchange 字段。tushare 的 `600519.SH` 在 transform 时拆为 `code="600519"` + `exchange="SH"`。akshare 的 `600519` 直接用，exchange 从代码前缀派生（6→SH, 0/3→SZ, 8→BJ）。

### 2.5 DuckDB 视图层

DuckDB 不复制数据，只建视图指向 Parquet：

```sql
CREATE OR REPLACE VIEW ods_equity_daily AS
SELECT * FROM read_parquet(
    'data/warehouse/ods/equity_daily/dt=*/part-*.parquet',
    hive_partitioning = true
);
-- 每个 ODS 表一个视图
```

查询时 DuckDB 自动下推分区裁剪。

### 2.6 catalog 表（数据字典）

```sql
CREATE TABLE ods_catalog (
    table_name      TEXT PRIMARY KEY,
    domain          TEXT,
    source_mcp      TEXT,
    source_tool     TEXT,
    partition_col   TEXT,
    partition_grain TEXT,                  -- daily/monthly/quarterly
    schema_json     TEXT,                  -- 业务字段 schema
    description     TEXT,
    owner           TEXT,
    created_at      TEXT,
    updated_at      TEXT
);
```

### 2.7 血缘字段（为多层 DAG 预留）

本期不做完整血缘图，但 ODS 层每条记录都带 `__source` + `__source_tool` + `__params_hash`，可追溯至 MCP 调用参数。完整 DAG（ODS → DWD → DWS）在后续 dbt spec 中用 dbt 的 `ref()` 实现。

---

## 3. ETL 管道设计

### 3.1 目录结构

```
scripts/etl/
├── __init__.py
├── README.md
├── common/
│   ├── __init__.py
│   ├── mcp_client.py             # MCP HTTP 客户端（封装 tools/call）
│   ├── parquet_writer.py         # 幂等写 Parquet（分区原子覆盖）
│   ├── catalog.py                # ods_catalog 表 CRUD
│   ├── quality.py                # 数据质量检查
│   ├── meta_fields.py            # __source/__fetched_at 等元数据注入
│   └── jobs.py                   # JobService 抽象 + DuckDB 实现
├── ods/
│   ├── __init__.py
│   ├── equity_daily.py           # P0
│   ├── index_constituents.py     # P0
│   ├── financial_income.py       # P1
│   ├── financial_balance.py      # P1
│   ├── financial_cashflow.py     # P1
│   ├── financial_indicator.py    # P1
│   ├── northbound_flow.py        # P1
│   ├── dragon_tiger.py           # P2
│   └── equity_spot.py            # P2（可选）
├── runner.py                     # 统一调度入口
├── report.py                     # report 子命令
├── init.py                       # 一次性初始化
└── tests/
    ├── test_mcp_client.py
    ├── test_parquet_writer.py
    ├── test_quality.py
    └── test_equity_daily.py
```

### 3.2 ETL 脚本五段式契约

每个 `ods/<domain>.py` 实现统一契约：

```python
DOMAIN = "equity_daily"
PARTITION_COL = "dt"
PARTITION_GRAIN = "daily"
SOURCE_MCP = "tushare"
FALLBACK_MCP = "akshare"

def extract(date: str, source: str = SOURCE_MCP) -> list[dict]:
    """从 MCP HTTP 拉原始数据。"""
    tool = "daily" if source == "tushare" else "stock_zh_a_hist"
    params = {"trade_date": date} if source == "tushare" else {"date": date}
    return mcp_client.call(source, tool, params)

def transform(rows: list[dict], date: str) -> list[dict]:
    """最小标准化：列名 snake_case、类型转换、代码裸码化、加元数据。"""

def load(rows: list[dict], date: str) -> dict:
    """幂等写入 Parquet 分区（原子覆盖）。"""

def check_quality(rows: list[dict], date: str) -> QualityReport:
    """数据质量检查。"""

def run(date: str, source: str = SOURCE_MCP) -> dict:
    """端到端：extract → transform → check → load。返回运行报告。"""
```

**五段式的好处**：可单测 transform（不依赖 MCP）、可单测 quality（不依赖 IO）。

### 3.3 runner.py 统一入口

```bash
# 初始化
uv run python -m scripts.etl.init

# 单域单日
uv run python -m scripts.etl.runner equity_daily --date 2026-07-17

# 单域补数据（历史回填，走 --direct-sdk 加速）
uv run python -m scripts.etl.runner equity_daily --start 2015-01-01 --end 2026-07-17 --direct-sdk

# 多域（P0 全跑）
uv run python -m scripts.etl.runner --priority P0 --date 2026-07-17

# 全量
uv run python -m scripts.etl.runner --all --date 2026-07-17
```

runner 职责：
- 解析参数、构造 ETL 任务列表
- 顺序执行（简单可靠，避免并发写冲突）
- 调用 JobService 记录每个任务的状态/重试/历史
- 任一域失败不阻塞其他域（隔离故障）

### 3.4 `--direct-sdk` 逃生开关

默认走 MCP HTTP（口径统一），但**历史回填**场景允许 `--direct-sdk` 绕过 MCP 直接调 SDK（`uv run python -m scripts.etl.runner equity_daily --start 2015-01-01 --direct-sdk`）。

理由：拉 10 年全市场历史数据时，HTTP 逐调用开销累积显著。日常 ETL 不用此开关。

**约束**：`--direct-sdk` 模式下，transform 阶段强制注入 `__source_tool="direct_sdk"` 标记，便于追溯（知道这批数据绕过了 MCP）。

### 3.5 幂等保证

`parquet_writer.write(mode="overwrite")`：
1. 写到临时文件 `part-0.parquet.tmp`
2. 校验行数 > 0
3. 原子替换：`os.replace(tmp, target)`
4. 同分区同日重跑直接覆盖

### 3.6 错误处理

- MCP 调用失败：`mcp_client.call` 内置 3 次指数退避重试（应对 tushare 限流）
- 数据质量阻断：blocking issue → 不写 Parquet，返回 `quality_failed`，JobService 记录
- 非阻断 issue（如某字段空值率高）→ 照写，记入 catalog 的 `quality_flags`

---

## 4. 任务队列与调度

### 4.1 JobService 抽象

定义 Python Protocol，业务代码不感知队列实现：

```python
# scripts/etl/common/jobs.py
from typing import Protocol

class JobService(Protocol):
    def submit(self, job: JobSpec) -> str: ...
    def claim(self, worker_id: str) -> Job | None: ...
    def complete(self, job_id: str, result: dict) -> None: ...
    def fail(self, job_id: str, error: str, retry: bool = True) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def list(self, status: str | None = None, limit: int = 100) -> list[Job]: ...
```

### 4.2 本期实现：DuckDBJobService

在 `meta.db` 中建 `etl_jobs` 表：

```sql
CREATE TABLE etl_jobs (
    id              TEXT PRIMARY KEY,           -- uuid
    domain          TEXT NOT NULL,              -- equity_daily / ...
    params_json     TEXT NOT NULL,              -- {"date": "20260717", "source": "tushare"}
    status          TEXT NOT NULL,              -- pending/running/completed/failed
    worker_id       TEXT,
    attempts        INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 3,
    result_json     TEXT,                       -- ETL 运行报告
    error           TEXT,
    created_at      TEXT NOT NULL,
    claimed_at      TEXT,
    finished_at     TEXT,
    -- 索引
    -- (status, created_at) 用于 claim 查询
);
CREATE INDEX idx_jobs_status ON etl_jobs(status, created_at);
```

**claim 实现**（利用 DuckDB 事务）：
```python
def claim(self, worker_id: str) -> Job | None:
    conn = self._conn
    conn.execute("BEGIN TRANSACTION")
    try:
        row = conn.execute("""
            SELECT id FROM etl_jobs
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT 1
        """).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None
        conn.execute("""
            UPDATE etl_jobs
            SET status = 'running', worker_id = ?, claimed_at = ?, attempts = attempts + 1
            WHERE id = ? AND status = 'pending'
        """, [worker_id, now_iso(), row[0]])
        conn.execute("COMMIT")
        return self.get(row[0])
    except:
        conn.execute("ROLLBACK")
        raise
```

### 4.3 满足的需求映射

| 用户需求 | 实现方式 |
|---|---|
| 可靠重试 + 执行历史 | `attempts` / `max_attempts` / `result_json` / `error` 字段 + 失败时 `status` 回到 pending |
| 多任务并发 | 多个 worker 进程并发 `claim()`，DuckDB 事务保证不重复领取 |
| 可视化任务状态 | `report.py --jobs` 子命令 + 未来 Web UI 读取 `etl_jobs` 表 |
| 未来外部提交任务 | 外部进程调 `JobService.submit()` 即可，接口已抽象 |

### 4.4 调度（Phase 1 简单方案）

```bash
# crontab 每个交易日 17:00 跑 P0
0 17 * * 1-5 cd /path/to/a-share-agents && uv run python -m scripts.etl.runner --priority P0 --date $(date +%Y%m%d)
```

用 `exchange_calendars` 库判断是否交易日，避免节假日空跑。

不引入 Airflow/Prefect（YAGNI）。当 ETL 任务 >20 个、依赖关系复杂时（未来 spec）再升级。

### 4.5 report 子命令

```bash
# 看哪些 ODS 表、哪些日期缺数据
uv run python -m scripts.etl.report --missing-dates --domain equity_daily --last 30d

# 看数据质量趋势
uv run python -m scripts.etl.report --quality-trend --domain equity_daily

# 看队列任务历史
uv run python -m scripts.etl.report --jobs --status failed --last 7d

# 补数据
uv run python -m scripts.etl.runner equity_daily --start 20260715 --end 20260717
```

---

## 5. 与现有系统集成

### 5.1 不动现有架构

数仓作为平行子系统，不侵入 MCP/Skill/Agent：

| 层 | 是否改动 | 说明 |
|---|---|---|
| MCP Servers | ❌ 不动 | 继续承担实时查询职责，ETL 通过 HTTP 调用 |
| Skills | ❌ 不动 | 未来 spec 通过 dbt model 读取数仓 |
| Agents | ❌ 不动 | 未来 Meta-Agent 消费语义层 |
| internal-store | ❌ 不动 | 继续承担运行时状态 |

### 5.2 internal-store 与数仓的职责划分

- `internal-store` = **运行时**（实验进行中、因子库、portfolio）—— 行式、低延迟、读写并发
- `data/warehouse` = **分析时**（历史沉淀、跨实验 OLAP）—— 列式、批量、读多写少

两者未来通过 dbt model 桥接（把 internal-store 的 `factor_library` 拉到数仓做 OLAP），但**本期不集成**。

### 5.3 .gitignore 更新

```gitignore
# 新增：数仓运行时产物（Parquet 文件已被 data/ 覆盖）
data/warehouse/meta.db
data/warehouse/meta.db.wal
data/warehouse/_logs/
```

只保留 Parquet 文件和 DDL SQL 入 git（如需要）。db 文件不入。

### 5.4 check.py 扩展

在 `scripts/check.py` 加一项检查（不破坏现有 R1-R6）：

```python
def check_warehouse() -> list[str]:
    """Check warehouse structure."""
    issues = []
    wh = ROOT / "data" / "warehouse"
    if not wh.exists():
        issues.append(f"INFO: {wh} not initialized (run `python -m scripts.etl.init`)")
    else:
        # 检查 catalog 表是否注册了所有声明的 ODS 域
        # 检查 DuckDB 视图是否齐全
        pass
    return issues
```

### 5.5 依赖更新

`pyproject.toml` 新增：
```toml
dependencies = [
    # ... 现有
    "duckdb>=0.10",
    "pyarrow>=14.0",      # 已有
    "exchange_calendars>=4.5",  # 交易日历
    # dbt 留到后续 spec 加（dbt-duckdb）
]
```

### 5.6 MCP server 依赖管理

ETL 默认走 MCP HTTP，启动前置：
- `mcp_client.health_check()` ping 三个 server 的 `data_source_health`，不通则报错退出
- `.env` 统一管理：MCP server 端口、TUSHARE_TOKEN 在 ETL 侧也读取同一份

---

## 6. 决策记录（关键选型理由）

### 6.1 为何选 DuckDB + Parquet 而非 Postgres / PGlite

**讨论过程**：用户最初倾向 PGlite（想要 PG 功能 + 零运维），并希望用 pgboss 做队列。

**调研结论**（[PGlite issue #489](https://github.com/electric-sql/pglite/issues/489)、[pg-boss issue #24](https://github.com/timgit/pg-boss/issues/24)）：
- PGlite 是单连接 WASM 嵌入式，pgboss 要求多连接多 worker，**架构上不兼容**
- PGlite 在 OLAP 场景（跨 5000 票 × 10 年聚合）比 DuckDB 慢（WASM 开销 + 行式存储）

**最终决策**：DuckDB + Parquet + 轻量 jobs 表。理由：
1. 用户核心负载是 A 股 OLAP 分析，DuckDB 列式碾压行式 PG 一个数量级
2. 零运维（嵌入式，无需起服务）
3. dbt-duckdb 同样成熟（dbt 官方维护）
4. 队列需求通过 JobService 抽象 + DuckDB jobs 表满足，未来可演进到 pgboss

### 6.2 为何 ETL 走 MCP HTTP 而非直调 SDK

- **口径统一是数仓生命线**：ETL、Agent、未来 Meta-Agent 必须看到同一份数据，MCP 是唯一入口
- HTTP 开销对日级 ETL 可忽略（拉 5000 票是秒级，HTTP ms 级开销微不足道）
- 保留 `--direct-sdk` 仅用于历史回填（10 年批量初始化）

### 6.3 为何 ODS 做"最小标准化"而非"纯贴源"

- 纯贴源（保留中文列名如"开盘"）后续建模需重做一次
- 最小标准化（snake_case + 类型）让后续 dbt model 更顺
- 不做业务加工（不复权、不去停牌）保留"贴源"语义，避免失真

### 6.4 为何本期不集成 internal-store

- internal-store 是运行时层（实验状态），数仓是分析层（历史沉淀）
- 强行同步会增加耦合，违反"小步快跑"
- 未来通过 dbt model 单向拉取（internal-store → 数仓），单向依赖清晰

---

## 7. 验收标准

本期完成的标志：

- [ ] `uv run python -m scripts.etl.init` 能初始化数仓结构
- [ ] `uv run python -m scripts.etl.runner equity_daily --date <recent>` 能跑通 P0 域
- [ ] P0 域（equity_daily + index_constituents）ETL 完整实现且有测试
- [ ] DuckDB 视图 `ods_equity_daily` 可查询，分区裁剪生效
- [ ] JobService 接口定义 + DuckDBJobService 实现 + 测试
- [ ] `report --missing-dates` / `--jobs` 子命令可用
- [ ] `scripts/check.py` 新增 `check_warehouse` 通过
- [ ] 文档：`scripts/etl/README.md` 完整
- [ ] P1 域至少 1 个（建议 financial_income）作为模式样板

P1 其余域、P2 域可作为本 spec 的"后续增量"，不阻塞本 spec 验收。

---

## 8. 后续 spec 规划（不在本期）

1. **dbt 建模**：DWD（明细宽表，如股票日线宽表）/ DWS（汇总，如行业月度收益）/ ADS（应用，如因子评估结果表）
2. **语义层**：dbt Semantic Layer 或 Cube.dev，统一定义 IC/Sharpe/MaxDD 等指标
3. **Meta-Agent**：自然语言 → 语义层查询 → 分析报告
4. **实验数据入仓**：把因子挖掘、回测的实验产物通过另一条 ETL 线入仓
5. **internal-store 同步**：dbt model 单向拉取 factor_library / experiments 到数仓
6. **队列升级**：当真有外部消费者时，JobService 增加 PGBossJobService 实现

---

## 9. 风险与缓解

| 风险 | 概率 | 缓解 |
|---|---|---|
| MCP server HTTP 成为 ETL 瓶颈 | 低 | `--direct-sdk` 逃生开关 |
| DuckDB 并发写冲突（多 worker） | 中 | 事务 + `claim()` 单调领取 |
| 数据源 schema 变更（tushare/akshare 升级） | 中 | transform 层隔离，schema_json 在 catalog 留痕 |
| Parquet 文件数过多（10 年日线 = 2500+ 分区） | 低 | DuckDB 元数据缓存 + 视图分区裁剪 |
| 质量检查规则过严阻断正常 ETL | 中 | 区分 blocking / non-blocking，告警不阻断 |
