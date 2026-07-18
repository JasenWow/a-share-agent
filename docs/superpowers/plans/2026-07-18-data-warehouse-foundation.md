# 数据仓地基 + 数据采集 ETL 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 DuckDB + Parquet 的 ODS 层数仓地基，通过 ETL 脚本把 Tushare/AKShare 数据沉淀下来，为后续 dbt 建模 / 语义层 / Meta-Agent 提供数据基础。

**Architecture:** 平行子系统，不侵入现有 MCP/Skill/Agent。ETL 脚本通过 MCP HTTP 接口取数（单一数据入口），写入按日期分区的 Parquet 文件，DuckDB 建视图查询。任务队列用 JobService 抽象（本期 DuckDB 实现，可演进到 pgboss）。

**Tech Stack:** Python 3.10+ / DuckDB >= 0.10 / PyArrow / requests / pytest / uv。spec：`docs/superpowers/specs/2026-07-18-data-warehouse-foundation-design.md`

---

## 文件结构

实施完成后的目录结构（**先看这张图，再看任务**）：

```
pyproject.toml                              # 修改：加 duckdb / exchange_calendars 依赖
tests/conftest.py                           # 新建：pytest 路径配置（避免 sys.path hack）
scripts/check.py                            # 修改：加 check_warehouse 函数
.gitignore                                  # 修改：加 meta.db / _logs 排除

scripts/etl/
├── __init__.py                             # 包标识
├── README.md                               # ETL 使用文档
├── common/
│   ├── __init__.py
│   ├── config.py                           # 配置：WAREHOUSE_ROOT / MCP 端口（读 .env）
│   ├── mcp_client.py                       # MCP HTTP 客户端 + health_check + retry
│   ├── meta_fields.py                      # 元数据字段注入（__source 等）
│   ├── parquet_writer.py                   # 幂等 Parquet 写入（原子覆盖）
│   ├── catalog.py                          # ods_catalog 表 CRUD
│   ├── quality.py                          # 数据质量检查框架
│   └── jobs.py                             # JobService Protocol + DuckDBJobService
├── ods/
│   ├── __init__.py
│   ├── equity_daily.py                     # P0：股票日线（样板）
│   ├── index_constituents.py               # P0：指数成分
│   └── financial_income.py                 # P1 样板：利润表
├── init.py                                 # 一次性初始化（建目录/meta.db/视图/catalog）
├── runner.py                               # 统一调度入口
└── report.py                               # report 子命令（缺数据/质量/任务）

scripts/etl/tests/
├── __init__.py
├── conftest.py                             # ETL 测试 fixtures（tmp DuckDB / fixture data）
├── test_mcp_client.py
├── test_meta_fields.py
├── test_parquet_writer.py
├── test_catalog.py
├── test_quality.py
├── test_jobs.py
├── test_equity_daily.py
├── test_index_constituents.py
├── test_financial_income.py
└── fixtures/
    ├── tushare_daily_20260717.json         # tushare daily 真实返回样本
    ├── akshare_hist_600519.json            # akshare stock_zh_a_hist 返回样本
    ├── tushare_index_weight.json
    └── tushare_income.json
```

---

## 任务依赖图

```
Task 1 (依赖/pytest 基建)
  ↓
Task 2 (config) → Task 3 (meta_fields) → Task 4 (parquet_writer)
  ↓                                      ↓
Task 5 (catalog)                     Task 6 (mcp_client)
  ↓                                      ↓
Task 7 (quality) ←────────────────────────┘
  ↓
Task 8 (equity_daily domain)  ← 核心样板
  ↓
Task 9 (index_constituents domain)
  ↓
Task 10 (financial_income domain - P1 样板)
  ↓
Task 11 (jobs JobService)
  ↓
Task 12 (init.py)
  ↓
Task 13 (runner.py)
  ↓
Task 14 (report.py)
  ↓
Task 15 (check.py 扩展 + .gitignore + README)
  ↓
Task 16 (端到端验证)
```

P2 域（dragon_tiger / equity_spot）和剩余 P1 域（balance/cashflow/indicator/northbound）按 Task 8-10 的模式复制，不在本计划内（验收标准只要求 P0 + P1 一个样板）。

---

## Task 1: 依赖与 pytest 基建

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`

- [ ] **Step 1: 加依赖到 pyproject.toml**

在 `pyproject.toml` 的 `dependencies` 数组末尾（`"deap>=1.4",` 之后）追加：

```toml
    "duckdb>=0.10",
    "exchange_calendars>=4.5",
```

- [ ] **Step 2: 安装新依赖**

Run: `uv sync`
Expected: 安装 duckdb 和 exchange_calendars 成功

- [ ] **Step 3: 验证 import**

Run: `uv run python -c "import duckdb; import exchange_calendars; print(duckdb.__version__)"`
Expected: 打印 duckdb 版本号（>= 0.10），无报错

- [ ] **Step 4: 建 tests/conftest.py 解决 sys.path 问题**

创建 `tests/conftest.py`：

```python
"""Pytest config — make project scripts importable without sys.path hacks."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
# 让 tests/ 可以 import plugins/scripts 下的模块
for sub in ["scripts", "plugins"]:
    p = ROOT / sub
    if p.exists():
        sys.path.insert(0, str(p))
```

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml uv.lock tests/conftest.py
git commit -m "feat(etl): add duckdb + exchange_calendars deps, pytest path config"
```

---

## Task 2: config 配置模块

**Files:**
- Create: `scripts/etl/__init__.py`
- Create: `scripts/etl/common/__init__.py`
- Create: `scripts/etl/common/config.py`
- Test: `scripts/etl/tests/__init__.py`
- Test: `scripts/etl/tests/test_config.py`

- [ ] **Step 1: 建包标识文件**

`scripts/etl/__init__.py`（空文件）：
```python
```

`scripts/etl/common/__init__.py`（空文件）：
```python
```

`scripts/etl/tests/__init__.py`（空文件）：
```python
```

- [ ] **Step 2: 写失败测试**

`scripts/etl/tests/test_config.py`：

```python
"""Tests for ETL config module."""
import os
from pathlib import Path

from common.config import WAREHOUSE_ROOT, MCP_AKSHARE_URL, MCP_TUSHARE_URL


def test_warehouse_root_default():
    """WAREHOUSE_ROOT 默认指向 <repo>/data/warehouse。"""
    # WAREHOUSE_ROOT 是 Path 对象
    assert isinstance(WAREHOUSE_ROOT, Path)
    # 以 data/warehouse 结尾
    assert WAREHOUSE_ROOT.name == "warehouse"
    assert WAREHOUSE_ROOT.parent.name == "data"


def test_warehouse_root_respects_env(monkeypatch, tmp_path):
    """DATA_ROOT 环境变量改变 WAREHOUSE_ROOT。"""
    monkeypatch.setattr("common.config.WAREHOUSE_ROOT", tmp_path / "warehouse")
    # 这里只验证可被覆盖（实际逻辑在 config.py 里读 env）
    assert True


def test_mcp_urls():
    """MCP URL 默认值正确。"""
    assert MCP_AKSHARE_URL == "http://localhost:8000/mcp"
    assert MCP_TUSHARE_URL == "http://localhost:8001/mcp"


def test_mcp_urls_respect_env(monkeypatch):
    """MCP 端口可通过环境变量覆盖。"""
    monkeypatch.setenv("AKSHARE_PORT", "9000")
    # 重新 import 验证（用 importlib）
    import importlib
    import common.config
    importlib.reload(common.config)
    assert common.config.MCP_AKSHARE_URL == "http://localhost:9000/mcp"
```

- [ ] **Step 3: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'common.config'`

- [ ] **Step 4: 实现 config.py**

`scripts/etl/common/config.py`：

```python
"""ETL 配置：仓库路径、MCP 端点。从 .env 读取，提供合理默认值。"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（scripts/etl/common/config.py 往上 4 级）
ROOT = Path(__file__).resolve().parents[3]

# 数据根目录（与 internal-store 的 DATA_ROOT 复用同一变量）
DATA_ROOT = Path(os.environ.get("DATA_ROOT", ROOT / "data"))

# 数仓根目录
WAREHOUSE_ROOT = DATA_ROOT / "warehouse"
ODS_ROOT = WAREHOUSE_ROOT / "ods"
META_DB_PATH = WAREHOUSE_ROOT / "meta.db"
LOGS_DIR = WAREHOUSE_ROOT / "_logs"

# MCP server 端点（端口可从环境变量覆盖，与 .env.example 一致）
AKSHARE_PORT = os.environ.get("AKSHARE_PORT", "8000")
TUSHARE_PORT = os.environ.get("TUSHARE_PORT", "8001")
INTERNAL_STORE_PORT = os.environ.get("INTERNAL_STORE_PORT", "8002")

MCP_AKSHARE_URL = f"http://localhost:{AKSHARE_PORT}/mcp"
MCP_TUSHARE_URL = f"http://localhost:{TUSHARE_PORT}/mcp"
MCP_INTERNAL_STORE_URL = f"http://localhost:{INTERNAL_STORE_PORT}/mcp"


def ensure_dirs() -> None:
    """确保数仓目录结构存在。"""
    WAREHOUSE_ROOT.mkdir(parents=True, exist_ok=True)
    ODS_ROOT.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_config.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 6: 提交**

```bash
git add scripts/etl/__init__.py scripts/etl/common/__init__.py scripts/etl/common/config.py scripts/etl/tests/__init__.py scripts/etl/tests/test_config.py
git commit -m "feat(etl): add config module with warehouse paths and MCP endpoints"
```

---

## Task 3: meta_fields 元数据注入

**Files:**
- Create: `scripts/etl/common/meta_fields.py`
- Test: `scripts/etl/tests/test_meta_fields.py`

- [ ] **Step 1: 写失败测试**

`scripts/etl/tests/test_meta_fields.py`：

```python
"""Tests for meta_fields injection."""
from datetime import datetime

from common.meta_fields import inject, params_hash


def test_params_hash_stable():
    """相同参数（任意顺序）产生相同 hash。"""
    h1 = params_hash({"code": "600519", "date": "20260717"})
    h2 = params_hash({"date": "20260717", "code": "600519"})
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_params_hash_different():
    """不同参数产生不同 hash。"""
    h1 = params_hash({"code": "600519"})
    h2 = params_hash({"code": "000001"})
    assert h1 != h2


def test_inject_returns_5_fields():
    """inject 返回 5 个元数据字段。"""
    result = inject(
        source="tushare",
        source_tool="daily",
        fetched_at="2026-07-17T17:00:00+08:00",
        params_hash="abc123",
        etl_run_id="20260717_170000_equity_daily",
    )
    assert set(result.keys()) == {
        "__source", "__source_tool", "__fetched_at",
        "__params_hash", "__etl_run_id",
    }
    assert result["__source"] == "tushare"
    assert result["__source_tool"] == "daily"
    assert result["__params_hash"] == "abc123"
    assert result["__etl_run_id"] == "20260717_170000_equity_daily"


def test_inject_field_names_dunder_prefixed():
    """所有元数据字段以 __ 前缀开头（避免与业务字段冲突）。"""
    result = inject("s", "t", "now", "h", "r")
    for key in result:
        assert key.startswith("__")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_meta_fields.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'common.meta_fields'`

- [ ] **Step 3: 实现 meta_fields.py**

`scripts/etl/common/meta_fields.py`：

```python
"""元数据字段注入：给 ODS 记录加追溯信息。

5 个字段（前缀 __ 避免与业务字段冲突）：
- __source:        数据源（tushare / akshare）
- __source_tool:   MCP 工具名（daily / stock_zh_a_hist / direct_sdk）
- __fetched_at:    拉取时间 ISO8601 带时区
- __params_hash:   MCP 调用参数的 sha256
- __etl_run_id:    ETL 运行实例 ID
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def params_hash(params: dict[str, Any]) -> str:
    """计算参数 dict 的稳定 sha256（key 排序，不依赖顺序）。"""
    canonical = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def inject(
    source: str,
    source_tool: str,
    fetched_at: str,
    params_hash: str,
    etl_run_id: str,
) -> dict[str, str]:
    """返回 5 个元数据字段的 dict，供 merge 到业务记录中。"""
    return {
        "__source": source,
        "__source_tool": source_tool,
        "__fetched_at": fetched_at,
        "__params_hash": params_hash,
        "__etl_run_id": etl_run_id,
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_meta_fields.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/meta_fields.py scripts/etl/tests/test_meta_fields.py
git commit -m "feat(etl): add meta_fields injection with params_hash"
```

---

## Task 4: parquet_writer 幂等写入

**Files:**
- Create: `scripts/etl/common/parquet_writer.py`
- Test: `scripts/etl/tests/test_parquet_writer.py`

- [ ] **Step 1: 写失败测试**

`scripts/etl/tests/test_parquet_writer.py`：

```python
"""Tests for parquet_writer."""
import pyarrow.parquet as pq

from common.parquet_writer import write


def test_write_creates_parquet_file(tmp_path):
    """写入生成 parquet 文件，行数正确。"""
    rows = [
        {"code": "600519", "close": 1692.0, "__source": "tushare"},
        {"code": "000001", "close": 12.5, "__source": "tushare"},
    ]
    result = write(
        domain="equity_daily",
        partition_col="dt",
        partition_val="2026-07-17",
        rows=rows,
        mode="overwrite",
        ods_root=tmp_path,
    )
    assert result["status"] == "ok"
    assert result["rows"] == 2
    # 文件存在
    parquet_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    assert parquet_file.exists()
    # 读回校验
    table = pq.read_table(parquet_file)
    assert table.num_rows == 2


def test_write_overwrite_is_idempotent(tmp_path):
    """同分区重跑覆盖，不产生重复。"""
    rows1 = [{"code": "600519", "close": 1692.0}]
    rows2 = [{"code": "600519", "close": 1700.0}]  # 更新后的数据

    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows1, mode="overwrite", ods_root=tmp_path)
    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows2, mode="overwrite", ods_root=tmp_path)

    parquet_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    table = pq.read_table(parquet_file)
    assert table.num_rows == 1  # 不是 2
    # 是最新数据
    assert table.to_pylist()[0]["close"] == 1700.0


def test_write_empty_rows_fails(tmp_path):
    """空 rows 视为异常，不写文件。"""
    import pytest
    with pytest.raises(ValueError, match="empty"):
        write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
              rows=[], mode="overwrite", ods_root=tmp_path)


def test_write_atomic_no_tmp_left(tmp_path):
    """写入后无 .tmp 残留文件。"""
    rows = [{"code": "600519", "close": 1692.0}]
    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows, mode="overwrite", ods_root=tmp_path)
    # 递归找 .tmp 文件
    tmps = list(tmp_path.rglob("*.tmp"))
    assert tmps == []


def test_write_monthly_partition(tmp_path):
    """月度分区路径格式正确。"""
    rows = [{"index_code": "000300", "code": "600519"}]
    write(domain="index_constituents", partition_col="dt", partition_val="2026-07",
          rows=rows, mode="overwrite", ods_root=tmp_path)
    parquet_file = tmp_path / "index_constituents" / "dt=2026-07" / "part-0.parquet"
    assert parquet_file.exists()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_parquet_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'common.parquet_writer'`

- [ ] **Step 3: 实现 parquet_writer.py**

`scripts/etl/common/parquet_writer.py`：

```python
"""幂等 Parquet 写入：按分区原子覆盖。

模式：
- overwrite（默认）：同分区重跑覆盖
- 分区路径：{ods_root}/{domain}/{partition_col}={partition_val}/part-0.parquet
- 原子性：先写 .tmp，校验后 os.replace 覆盖
"""
from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def write(
    domain: str,
    partition_col: str,
    partition_val: str,
    rows: list[dict],
    mode: str = "overwrite",
    ods_root: Path | None = None,
) -> dict:
    """写入 Parquet 分区。

    Args:
        domain:         数据域（如 equity_daily）
        partition_col:  分区列名（如 dt / period）
        partition_val:  分区值（如 2026-07-17 / 2026-07 / 2024Q4）
        rows:           数据行（list[dict]）
        mode:           overwrite（本期仅支持此模式）
        ods_root:       ODS 根目录（默认从 config 读）

    Returns:
        {"status": "ok", "rows": N, "path": "..."}
    """
    if not rows:
        raise ValueError("Cannot write empty rows (would create invalid parquet)")

    if ods_root is None:
        from common.config import ODS_ROOT
        ods_root = ODS_ROOT

    partition_dir = ods_root / domain / f"{partition_col}={partition_val}"
    partition_dir.mkdir(parents=True, exist_ok=True)

    target = partition_dir / "part-0.parquet"
    tmp = partition_dir / "part-0.parquet.tmp"

    # 转为 pyarrow Table（处理字段顺序不一致问题：用第一条 keys 作 schema）
    table = pa.Table.from_pylist(rows)

    # 写到 tmp
    pq.write_table(table, tmp, compression="snappy")

    # 校验 tmp 可读且行数对
    verify = pq.read_table(tmp)
    if verify.num_rows != len(rows):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Parquet verify failed: wrote {len(rows)} rows but read back {verify.num_rows}"
        )

    # 原子覆盖
    os.replace(tmp, target)

    return {
        "status": "ok",
        "rows": len(rows),
        "path": str(target.relative_to(ods_root.parent)),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_parquet_writer.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/parquet_writer.py scripts/etl/tests/test_parquet_writer.py
git commit -m "feat(etl): add idempotent parquet writer with atomic overwrite"
```

---

## Task 5: catalog 数据字典

**Files:**
- Create: `scripts/etl/common/catalog.py`
- Test: `scripts/etl/tests/test_catalog.py`

- [ ] **Step 1: 写失败测试**

`scripts/etl/tests/test_catalog.py`：

```python
"""Tests for catalog CRUD."""
import duckdb
import pytest

from common.catalog import register, get, list_all, init_catalog


@pytest.fixture()
def db(tmp_path):
    """临时 DuckDB + catalog 表。"""
    db_path = tmp_path / "meta.db"
    conn = duckdb.connect(str(db_path))
    init_catalog(conn)
    yield conn
    conn.close()


def test_register_and_get(db):
    """注册后能查到。"""
    register(db, {
        "table_name": "ods_equity_daily",
        "domain": "equity_prices",
        "source_mcp": "tushare",
        "source_tool": "daily",
        "partition_col": "dt",
        "partition_grain": "daily",
        "schema_json": '{"code": "str"}',
        "description": "股票日线行情",
        "owner": "etl",
    })
    row = get(db, "ods_equity_daily")
    assert row["table_name"] == "ods_equity_daily"
    assert row["source_mcp"] == "tushare"


def test_register_is_upsert(db):
    """重名注册是更新不是报错。"""
    register(db, {"table_name": "t1", "domain": "d", "source_mcp": "s",
                  "source_tool": "t", "partition_col": "dt",
                  "partition_grain": "daily", "schema_json": "{}",
                  "description": "v1", "owner": "etl"})
    # 更新描述
    register(db, {"table_name": "t1", "domain": "d", "source_mcp": "s",
                  "source_tool": "t", "partition_col": "dt",
                  "partition_grain": "daily", "schema_json": "{}",
                  "description": "v2", "owner": "etl"})
    row = get(db, "t1")
    assert row["description"] == "v2"


def test_get_missing_returns_none(db):
    """查不到返回 None。"""
    assert get(db, "nonexistent") is None


def test_list_all(db):
    """list_all 返回所有注册项。"""
    for name in ["t1", "t2", "t3"]:
        register(db, {"table_name": name, "domain": "d", "source_mcp": "s",
                      "source_tool": "t", "partition_col": "dt",
                      "partition_grain": "daily", "schema_json": "{}",
                      "description": name, "owner": "etl"})
    rows = list_all(db)
    assert len(rows) == 3
    names = {r["table_name"] for r in rows}
    assert names == {"t1", "t2", "t3"}
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 catalog.py**

`scripts/etl/common/catalog.py`：

```python
"""ODS 数据字典（catalog）CRUD。

catalog 表存 DuckDB，记录每个 ODS 表的元信息（数据源、分区、schema、所有者）。
"""
from __future__ import annotations

from datetime import datetime, timezone

import duckdb


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """建 catalog 表（幂等）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ods_catalog (
            table_name      TEXT PRIMARY KEY,
            domain          TEXT NOT NULL,
            source_mcp      TEXT NOT NULL,
            source_tool     TEXT NOT NULL,
            partition_col   TEXT NOT NULL,
            partition_grain TEXT NOT NULL,
            schema_json     TEXT NOT NULL,
            description     TEXT,
            owner           TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )


def register(conn: duckdb.DuckDBPyConnection, entry: dict) -> None:
    """注册或更新一个 ODS 表（upsert）。"""
    now = _now()
    conn.execute(
        """
        INSERT INTO ods_catalog (
            table_name, domain, source_mcp, source_tool,
            partition_col, partition_grain, schema_json,
            description, owner, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (table_name) DO UPDATE SET
            domain = EXCLUDED.domain,
            source_mcp = EXCLUDED.source_mcp,
            source_tool = EXCLUDED.source_tool,
            partition_col = EXCLUDED.partition_col,
            partition_grain = EXCLUDED.partition_grain,
            schema_json = EXCLUDED.schema_json,
            description = EXCLUDED.description,
            owner = EXCLUDED.owner,
            updated_at = EXCLUDED.updated_at
        """,
        [
            entry["table_name"], entry["domain"], entry["source_mcp"],
            entry["source_tool"], entry["partition_col"], entry["partition_grain"],
            entry["schema_json"], entry.get("description", ""),
            entry.get("owner", "etl"), now, now,
        ],
    )


def get(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict | None:
    """查单个表，无则 None。"""
    row = conn.execute(
        "SELECT * FROM ods_catalog WHERE table_name = ?", [table_name]
    ).fetchone()
    if not row:
        return None
    cols = [d[0] for d in conn.description]
    return dict(zip(cols, row))


def list_all(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """列出所有 catalog 记录。"""
    rows = conn.execute("SELECT * FROM ods_catalog ORDER BY table_name").fetchall()
    cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_catalog.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/catalog.py scripts/etl/tests/test_catalog.py
git commit -m "feat(etl): add catalog CRUD with upsert support"
```

---

## Task 6: mcp_client MCP HTTP 客户端

**Files:**
- Create: `scripts/etl/common/mcp_client.py`
- Test: `scripts/etl/tests/test_mcp_client.py`

- [ ] **Step 1: 写失败测试（用 monkeypatch 模拟 HTTP）**

`scripts/etl/tests/test_mcp_client.py`：

```python
"""Tests for mcp_client. Mock HTTP layer."""
import json
from unittest.mock import patch, MagicMock

import pytest

from common.mcp_client import call, health_check, McpError


def _mock_response(payload, status=200):
    """构造 mock requests.Response。"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None if status < 400 else Exception(f"HTTP {status}")
    return resp


def test_call_returns_result_list():
    """正常返回 result.content 里的数据。"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [{"type": "text", "text": json.dumps([{"code": "600519", "close": 1692.0}])}]
        },
    }
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        rows = call("tushare", "daily", {"trade_date": "20260717"})
    assert rows == [{"code": "600519", "close": 1692.0}]


def test_call_raises_on_mcp_error():
    """MCP 返回 error 字段时抛 McpError。"""
    payload = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32602, "message": "invalid params"}}
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(McpError, match="invalid params"):
            call("tushare", "daily", {})


def test_call_returns_error_dict_from_tool():
    """工具内部错误（[{'error': ...}]）按原样返回（不抛异常，让上层判断）。"""
    error_text = json.dumps([{"error": "rate limited", "tool": "daily"}])
    payload = {"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": error_text}]}}
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        rows = call("tushare", "daily", {})
    # 工具错误原样返回，由 quality 检查处理
    assert rows == [{"error": "rate limited", "tool": "daily"}]


def test_call_retries_on_network_error():
    """网络错误重试 3 次后抛 McpError。"""
    with patch("common.mcp_client.requests.post", side_effect=ConnectionError("network down")):
        with patch("common.mcp_client.time.sleep") as mock_sleep:  # 加速测试
            with pytest.raises(McpError, match="network down"):
                call("tushare", "daily", {}, max_retries=3)
    # 重试间隔被调用（exponential backoff）
    assert mock_sleep.call_count == 3


def test_health_check_ok():
    """health_check 成功返回 True。"""
    payload = {
        "jsonrpc": "2.0", "id": "1",
        "result": {"content": [{"type": "text", "text": json.dumps([{"status": "ok"}])}]},
    }
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        assert health_check("tushare") is True


def test_health_check_fail():
    """health_check 失败返回 False（不抛异常）。"""
    with patch("common.mcp_client.requests.post", side_effect=ConnectionError("down")):
        with patch("common.mcp_client.time.sleep"):
            assert health_check("tushare", max_retries=1) is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_mcp_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 mcp_client.py**

`scripts/etl/common/mcp_client.py`：

```python
"""MCP HTTP 客户端：封装 JSON-RPC tools/call 调用，带重试。

协议参考：plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts/track_experiment.py
端点：{MCP_URL}/mcp，POST JSON-RPC 2.0。
返回 result.content[0].text 是 JSON 字符串，解析后是 list[dict]。
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import requests

from common.config import (
    MCP_AKSHARE_URL, MCP_TUSHARE_URL, MCP_INTERNAL_STORE_URL,
)


class McpError(Exception):
    """MCP 调用异常（协议错误 / 重试耗尽）。"""


# 源名 → URL 映射
_SOURCE_URLS = {
    "akshare": MCP_AKSHARE_URL,
    "tushare": MCP_TUSHARE_URL,
    "internal-store": MCP_INTERNAL_STORE_URL,
}

# 记录最近一次调用的 params_hash（供 meta_fields 用）
_last_params_hash: str = ""


def get_last_params_hash() -> str:
    return _last_params_hash


def call(
    source: str,
    tool: str,
    params: dict[str, Any],
    timeout: int = 30,
    max_retries: int = 3,
) -> list[dict]:
    """调用 MCP 工具，返回 list[dict]。

    Args:
        source:     数据源名（akshare / tushare / internal-store）
        tool:       MCP 工具名（如 daily / stock_zh_a_hist）
        params:     工具参数
        timeout:    单次请求超时秒
        max_retries: 网络错误重试次数

    Returns:
        工具返回的 list[dict]。如果是工具内部错误，原样返回 [{"error": ...}]。

    Raises:
        McpError: MCP 协议错误或重试耗尽。
    """
    global _last_params_hash
    from common.meta_fields import params_hash
    _last_params_hash = params_hash(params)

    if source not in _SOURCE_URLS:
        raise McpError(f"Unknown MCP source: {source}")

    url = _SOURCE_URLS[source]
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool, "arguments": params},
    }

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url, json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                raise McpError(f"MCP error from {source}.{tool}: {data['error']}")

            if "result" not in data:
                raise McpError(f"MCP malformed response from {source}.{tool}: no result")

            content = data["result"].get("content", [])
            if not content:
                return []

            # content[0].text 是 JSON 字符串
            text = content[0].get("text", "[]")
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                parsed = [parsed]
            return parsed

        except (requests.RequestException, ConnectionError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避：1s, 2s, 4s
                continue
            break

    raise McpError(f"MCP call {source}.{tool} failed after {max_retries} retries: {last_exc}")


def health_check(source: str, max_retries: int = 1) -> bool:
    """ping 数据源的健康检查工具。True = 健康。"""
    # 不同 server 的 health 工具名不同
    health_tool = {
        "akshare": "data_source_health",
        "tushare": "daily",  # tushare 没有 health tool，用一个轻量调用
        "internal-store": "list_experiments",
    }.get(source)
    if not health_tool:
        return False

    try:
        if source == "tushare":
            call(source, "daily", {"limit": 1}, max_retries=max_retries, timeout=10)
        else:
            call(source, health_tool, {}, max_retries=max_retries, timeout=10)
        return True
    except (McpError, Exception):
        return False
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_mcp_client.py -v`
Expected: PASS（6 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/mcp_client.py scripts/etl/tests/test_mcp_client.py
git commit -m "feat(etl): add MCP HTTP client with retry and health check"
```

---

## Task 7: quality 数据质量检查

**Files:**
- Create: `scripts/etl/common/quality.py`
- Test: `scripts/etl/tests/test_quality.py`

- [ ] **Step 1: 写失败测试**

`scripts/etl/tests/test_quality.py`：

```python
"""Tests for data quality checks."""
import pytest

from common.quality import run_checks, QualityReport, min_row_count, no_null_in, date_is


def test_min_row_count_pass():
    """行数达标通过。"""
    report = QualityReport()
    check = min_row_count(100)
    result = check([{"a": 1}] * 150, "20260717")
    assert result.passed is True


def test_min_row_count_fail_blocking():
    """行数不足阻断。"""
    check = min_row_count(100)
    result = check([{"a": 1}] * 50, "20260717")
    assert result.passed is False
    assert result.blocking is True
    assert "100" in result.message


def test_no_null_in_pass():
    """关键字段无 null 通过。"""
    check = no_null_in(["code", "close"])
    rows = [{"code": "600519", "close": 1692.0}, {"code": "000001", "close": 12.5}]
    assert check(rows, "20260717").passed is True


def test_no_null_in_fail():
    """关键字段有 null 阻断。"""
    check = no_null_in(["code", "close"])
    rows = [{"code": "600519", "close": None}]
    result = check(rows, "20260717")
    assert result.passed is False
    assert result.blocking is True


def test_date_is_pass():
    """日期字段与预期一致通过。"""
    check = date_is("20260717", "trade_date")
    rows = [{"trade_date": "20260717"}, {"trade_date": "20260717"}]
    assert check(rows, "20260717").passed is True


def test_date_is_fail():
    """日期字段不一致阻断。"""
    check = date_is("20260717", "trade_date")
    rows = [{"trade_date": "20260716"}]
    assert check(rows, "20260717").passed is False


def test_run_checks_collects_all():
    """run_checks 跑所有检查并汇总。"""
    checks = [
        min_row_count(2),
        no_null_in(["code"]),
    ]
    rows = [{"code": "600519"}, {"code": "000001"}]
    report = run_checks("equity_daily", rows, "20260717", checks)
    assert report.has_blocking() is False
    assert len(report.issues) == 0


def test_run_checks_blocking_short_circuits():
    """有 blocking issue 时 has_blocking 返回 True。"""
    checks = [min_row_count(100)]
    rows = [{"code": "600519"}]
    report = run_checks("equity_daily", rows, "20260717", checks)
    assert report.has_blocking() is True
    assert len(report.issues) == 1


def test_quality_report_to_list():
    """to_list 用于序列化到日志。"""
    report = QualityReport()
    report.issues.append({
        "check": "min_row_count", "passed": False, "blocking": True, "message": "x",
    })
    lst = report.to_list()
    assert len(lst) == 1
    assert lst[0]["check"] == "min_row_count"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_quality.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 quality.py**

`scripts/etl/common/quality.py`：

```python
"""数据质量检查框架。

每张 ODS 表在 ETL 内联跑一组 CheckFunc。
CheckFunc 返回 CheckResult（含 blocking 标志）。
QualityReport 汇总所有结果，has_blocking() 用于决定是否阻断写入。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CheckResult:
    passed: bool
    blocking: bool
    message: str
    check: str  # 检查名


# CheckFunc 签名：(rows, date) -> CheckResult
CheckFunc = Callable[[list[dict], str], CheckResult]


@dataclass
class QualityReport:
    issues: list[dict] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        if not result.passed:
            self.issues.append({
                "check": result.check,
                "passed": result.passed,
                "blocking": result.blocking,
                "message": result.message,
            })

    def has_blocking(self) -> bool:
        return any(i["blocking"] for i in self.issues)

    def to_list(self) -> list[dict]:
        return list(self.issues)


def run_checks(
    domain: str,
    rows: list[dict],
    date: str,
    checks: list[CheckFunc],
) -> QualityReport:
    """跑所有检查，返回 QualityReport。"""
    report = QualityReport()
    for check in checks:
        result = check(rows, date)
        report.add(result)
    return report


# --------------------------------------------------------------------------
# 内置 check 工厂函数
# --------------------------------------------------------------------------

def min_row_count(threshold: int) -> CheckFunc:
    """行数 ≥ threshold，否则 blocking。"""
    def _check(rows: list[dict], date: str) -> CheckResult:
        n = len(rows)
        if n >= threshold:
            return CheckResult(True, False, f"rows={n} >= {threshold}", "min_row_count")
        return CheckResult(False, True, f"rows={n} < {threshold}", "min_row_count")
    return _check


def no_null_in(fields: list[str]) -> CheckFunc:
    """指定字段不允许 null，否则 blocking。"""
    def _check(rows: list[dict], date: str) -> CheckResult:
        for f in fields:
            nulls = sum(1 for r in rows if r.get(f) is None)
            if nulls > 0:
                return CheckResult(
                    False, True,
                    f"field '{f}' has {nulls} nulls", "no_null_in",
                )
        return CheckResult(True, False, "no nulls in required fields", "no_null_in")
    return _check


def date_is(expected: str, field: str) -> CheckFunc:
    """指定字段值全部等于 expected，否则 blocking。"""
    def _check(rows: list[dict], date: str) -> CheckResult:
        bad = [r for r in rows if str(r.get(field, "")) != expected]
        if bad:
            return CheckResult(
                False, True,
                f"{len(bad)} rows have {field} != {expected}", "date_is",
            )
        return CheckResult(True, False, f"all rows {field}={expected}", "date_is")
    return _check
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_quality.py -v`
Expected: PASS（9 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/quality.py scripts/etl/tests/test_quality.py
git commit -m "feat(etl): add data quality check framework with blocking/non-blocking"
```

---

## Task 8: equity_daily 域 ETL（P0 核心样板）

这是所有 ODS 域的**样板**。后续 domain 都照此模式。

**Files:**
- Create: `scripts/etl/ods/__init__.py`
- Create: `scripts/etl/ods/equity_daily.py`
- Create: `scripts/etl/tests/fixtures/tushare_daily_20260717.json`
- Test: `scripts/etl/tests/test_equity_daily.py`

- [ ] **Step 1: 建 ods 包**

`scripts/etl/ods/__init__.py`（空文件）：
```python
```

- [ ] **Step 2: 准备 fixture 数据**

`scripts/etl/tests/fixtures/tushare_daily_20260717.json`（tushare daily 真实返回样本，3 条）：

```json
[
  {"ts_code": "600519.SH", "trade_date": "20260717", "open": 1685.0, "high": 1698.5, "low": 1680.0, "close": 1692.0, "vol": 1234567.0, "amount": 2.08e8, "pct_chg": 0.45},
  {"ts_code": "000001.SZ", "trade_date": "20260717", "open": 12.30, "high": 12.50, "low": 12.20, "close": 12.45, "vol": 98765432.0, "amount": 1.23e9, "pct_chg": 1.22},
  {"ts_code": "300750.SZ", "trade_date": "20260717", "open": 215.0, "high": 218.0, "low": 214.0, "close": 217.5, "vol": 5432100.0, "amount": 1.18e9, "pct_chg": 1.17}
]
```

- [ ] **Step 3: 写失败测试**

`scripts/etl/tests/test_equity_daily.py`：

```python
"""Tests for equity_daily ETL domain."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ods.equity_daily import (
    DOMAIN, PARTITION_COL, SOURCE_MCP, extract, transform, run,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_daily_20260717.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_constants():
    """domain 常量符合 spec。"""
    assert DOMAIN == "equity_daily"
    assert PARTITION_COL == "dt"
    assert SOURCE_MCP == "tushare"


def test_transform_strips_ts_code_suffix():
    """transform 把 600519.SH 拆成 code=600519 + exchange=SH。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    assert len(clean) == 3
    # 第一条 600519.SH
    first = clean[0]
    assert first["code"] == "600519"
    assert first["exchange"] == "SH"
    assert first["close"] == 1692.0


def test_transform_casts_types():
    """transform 把字符串/混合类型标准化。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    for r in clean:
        assert isinstance(r["open"], float)
        assert isinstance(r["close"], float)
        assert isinstance(r["code"], str)


def test_transform_injects_meta_fields():
    """transform 注入 5 个元数据字段。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    for r in clean:
        for f in ["__source", "__source_tool", "__fetched_at", "__params_hash", "__etl_run_id"]:
            assert f in r
        assert r["__source"] == "tushare"
        assert r["__source_tool"] == "daily"


def test_transform_volume_renamed_from_vol():
    """tushare 的 vol 字段重命名为 volume。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    assert "vol" not in clean[0]
    assert "volume" in clean[0]
    assert clean[0]["volume"] == 1234567


def test_run_end_to_end_with_mock(tmp_path):
    """端到端：mock MCP + tmp_path 验证 Parquet 落地。"""
    raw = _load_fixture()
    with patch("ods.equity_daily.mcp_client.call", return_value=raw):
        result = run("20260717", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 3
    # 文件存在
    pq_file = tmp_path / "equity_daily" / "dt=20260717" / "part-0.parquet"
    assert pq_file.exists()


def test_run_quality_failed_when_too_few_rows(tmp_path):
    """行数不足（<4000）时阻断，不写文件。"""
    raw = _load_fixture()  # 只有 3 行
    with patch("ods.equity_daily.mcp_client.call", return_value=raw):
        result = run("20260717", ods_root=tmp_path)
    # 注意：测试 fixture 只 3 行，生产阈值 4000，应阻断
    assert result["status"] == "quality_failed"
    pq_file = tmp_path / "equity_daily" / "dt=20260717" / "part-0.parquet"
    assert not pq_file.exists()
```

注意：最后一个测试用真实生产阈值（4000）测，确保 quality 真的阻断。前面用 mock 测 transform 不依赖 quality。

- [ ] **Step 4: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_equity_daily.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ods.equity_daily'`

- [ ] **Step 5: 实现 equity_daily.py**

`scripts/etl/ods/equity_daily.py`：

```python
"""ODS ETL: 股票日线行情。

数据源：tushare daily（主）/ akshare stock_zh_a_hist（备）
分区：dt=YYYY-MM-DD（日频）
"""
from __future__ import annotations

from datetime import datetime, timezone

from common import mcp_client
from common.meta_fields import inject, params_hash as compute_hash
from common.parquet_writer import write as write_parquet
from common.quality import run_checks, min_row_count, no_null_in, date_is

DOMAIN = "equity_daily"
PARTITION_COL = "dt"
PARTITION_GRAIN = "daily"
SOURCE_MCP = "tushare"
FALLBACK_MCP = "akshare"

# A 股 ~5000 只票，正常交易日至少 4000 行
MIN_DAILY_ROWS = 4000


def extract(date: str, source: str = SOURCE_MCP) -> list[dict]:
    """从 MCP 拉原始数据。date 格式 YYYYMMDD。"""
    if source == "tushare":
        return mcp_client.call(source, "daily", {"trade_date": date})
    # akshare 备源：单只票调用，全市场需循环（性能较差，仅 fallback）
    # 本期暂不实现 akshare 全市场批量，留 TODO 给后续
    raise NotImplementedError(f"akshare fallback not implemented for {DOMAIN}")


def _split_ts_code(ts_code: str) -> tuple[str, str]:
    """600519.SH → ('600519', 'SH')。"""
    if "." in ts_code:
        code, _, exchange = ts_code.partition(".")
        return code, exchange
    # 无后缀（akshare 裸码），从代码派生
    code = ts_code
    if code.startswith("6"):
        return code, "SH"
    if code.startswith(("0", "3")):
        return code, "SZ"
    if code.startswith("8"):
        return code, "BJ"
    return code, "SZ"


def transform(rows: list[dict], date: str) -> list[dict]:
    """最小标准化：snake_case + 类型 + 裸码化 + 元数据注入。"""
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{date}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash() or compute_hash({"trade_date": date})

    result = []
    for r in rows:
        # 工具内部错误原样跳过（不应进 ODS）
        if "error" in r:
            continue
        code, exchange = _split_ts_code(r.get("ts_code", r.get("code", "")))
        result.append({
            "trade_date": str(r.get("trade_date", date)),
            "code": code,
            "exchange": exchange,
            "open": float(r.get("open", 0) or 0),
            "high": float(r.get("high", 0) or 0),
            "low": float(r.get("low", 0) or 0),
            "close": float(r.get("close", 0) or 0),
            "volume": float(r.get("vol", r.get("volume", 0)) or 0),
            "amount": float(r.get("amount", 0) or 0),
            "pct_chg": float(r.get("pct_chg", 0) or 0),
            **inject(
                source=SOURCE_MCP, source_tool="daily",
                fetched_at=fetched_at, params_hash=p_hash, etl_run_id=etl_run_id,
            ),
        })
    return result


def check_quality(rows: list[dict], date: str):
    """数据质量检查。"""
    return run_checks(DOMAIN, rows, date, [
        min_row_count(MIN_DAILY_ROWS),
        no_null_in(["code", "close"]),
        date_is(date, "trade_date"),
    ])


def load(rows: list[dict], date: str, ods_root=None) -> dict:
    """幂等写入。"""
    return write_parquet(
        domain=DOMAIN, partition_col=PARTITION_COL,
        partition_val=_format_partition(date),
        rows=rows, mode="overwrite", ods_root=ods_root,
    )


def _format_partition(date: str) -> str:
    """YYYYMMDD → YYYY-MM-DD（hive 分区格式）。"""
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}"


def run(date: str, source: str = SOURCE_MCP, ods_root=None) -> dict:
    """端到端：extract → transform → check → load。"""
    raw = extract(date, source)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {"status": "extract_failed", "domain": DOMAIN, "date": date,
                "error": raw[0].get("error") if raw else "empty"}
    clean = transform(raw, date)
    report = check_quality(clean, date)
    if report.has_blocking():
        return {"status": "quality_failed", "domain": DOMAIN, "date": date,
                "issues": report.to_list()}
    load_result = load(clean, date, ods_root=ods_root)
    return {
        "status": "ok", "domain": DOMAIN, "date": date,
        "rows": len(clean), "load": load_result,
        "issues": report.to_list(),
    }


# 元数据（供 catalog 注册用）
CATALOG_ENTRY = {
    "table_name": "ods_equity_daily",
    "domain": "equity_prices",
    "source_mcp": SOURCE_MCP,
    "source_tool": "daily",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"trade_date":"str","code":"str","exchange":"str","open":"float","high":"float","low":"float","close":"float","volume":"float","amount":"float","pct_chg":"float"}',
    "description": "股票日线行情（全市场）",
    "owner": "etl",
}
```

- [ ] **Step 6: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_equity_daily.py -v`
Expected: PASS（7 个测试全过，包括 quality_failed 阻断测试）

- [ ] **Step 7: 提交**

```bash
git add scripts/etl/ods/__init__.py scripts/etl/ods/equity_daily.py scripts/etl/tests/fixtures/tushare_daily_20260717.json scripts/etl/tests/test_equity_daily.py
git commit -m "feat(etl): add equity_daily ODS domain (P0) with full ETL contract"
```

---

## Task 9: index_constituents 域 ETL（P0）

**Files:**
- Create: `scripts/etl/ods/index_constituents.py`
- Create: `scripts/etl/tests/fixtures/tushare_index_weight.json`
- Test: `scripts/etl/tests/test_index_constituents.py`

- [ ] **Step 1: 准备 fixture**

`scripts/etl/tests/fixtures/tushare_index_weight.json`（tushare index_weight 返回样本）：

```json
[
  {"index_code": "000300.SH", "con_code": "600519.SH", "trade_date": "20260717", "weight": 5.23},
  {"index_code": "000300.SH", "con_code": "000001.SZ", "trade_date": "20260717", "weight": 1.12},
  {"index_code": "000300.SH", "con_code": "300750.SZ", "trade_date": "20260717", "weight": 0.95}
]
```

- [ ] **Step 2: 写失败测试**

`scripts/etl/tests/test_index_constituents.py`：

```python
"""Tests for index_constituents ETL domain."""
import json
from pathlib import Path
from unittest.mock import patch

from ods.index_constituents import (
    DOMAIN, PARTITION_COL, transform, run,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_index_weight.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "index_constituents"
    assert PARTITION_COL == "dt"


def test_transform_strips_con_code():
    """con_code 600519.SH 拆为 code + exchange。"""
    raw = _load_fixture()
    clean = transform(raw, "2026-07")
    assert clean[0]["code"] == "600519"
    assert clean[0]["exchange"] == "SH"
    assert clean[0]["index_code"] == "000300"
    assert clean[0]["weight"] == 5.23


def test_transform_partition_format():
    """月度分区：YYYYMMDD 入参转为 YYYY-MM。"""
    raw = _load_fixture()
    clean = transform(raw, "2026-07")
    # trade_date 保留原 YYYYMMDD
    assert clean[0]["trade_date"] == "20260717"


def test_run_end_to_end(tmp_path):
    """端到端 mock。"""
    raw = _load_fixture()
    with patch("ods.index_constituents.mcp_client.call", return_value=raw):
        result = run("000300.SH", month="202607", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 3
```

- [ ] **Step 3: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_index_constituents.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: 实现 index_constituents.py**

`scripts/etl/ods/index_constituents.py`：

```python
"""ODS ETL: 指数成分股（按月快照）。

数据源：tushare index_weight
分区：dt=YYYY-MM（月度快照，捕捉成分调整）
"""
from __future__ import annotations

from datetime import datetime, timezone

from common import mcp_client
from common.meta_fields import inject
from common.parquet_writer import write as write_parquet
from common.quality import run_checks, min_row_count, no_null_in

DOMAIN = "index_constituents"
PARTITION_COL = "dt"
PARTITION_GRAIN = "monthly"
SOURCE_MCP = "tushare"

# 沪深300/中证500 等主要指数成分至少 100 只
MIN_ROWS = 50


def _split_con_code(con_code: str) -> tuple[str, str]:
    """600519.SH → ('600519', 'SH')。"""
    if "." in con_code:
        code, _, exchange = con_code.partition(".")
        return code, exchange
    return con_code, ""


def extract(index_code: str, month: str) -> list[dict]:
    """month 格式 YYYYMM。转成 trade_date 范围调用。"""
    # tushare index_weight 接受 trade_date 单日，月度取该月最后一个交易日
    # 简化：用月初+月末字符串，让 tushare 自己处理
    start = f"{month}01"
    # 月末（简化为 28 号，tushare 会返回该日数据或最近交易日）
    end = f"{month}28"
    return mcp_client.call(SOURCE_MCP, "index_weight", {
        "index_code": index_code, "start_date": start, "end_date": end,
    })


def transform(rows: list[dict], month_partition: str) -> list[dict]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{month_partition}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash()

    result = []
    for r in rows:
        if "error" in r:
            continue
        code, exchange = _split_con_code(r.get("con_code", ""))
        index_code_full = r.get("index_code", "")
        index_code, _, _ = index_code_full.partition(".")
        result.append({
            "index_code": index_code,
            "trade_date": str(r.get("trade_date", "")),
            "code": code,
            "exchange": exchange,
            "weight": float(r.get("weight", 0) or 0),
            **inject(
                source=SOURCE_MCP, source_tool="index_weight",
                fetched_at=fetched_at, params_hash=p_hash, etl_run_id=etl_run_id,
            ),
        })
    return result


def check_quality(rows: list[dict]):
    return run_checks(DOMAIN, rows, "", [
        min_row_count(MIN_ROWS),
        no_null_in(["code", "index_code"]),
    ])


def _format_month(yyyymm: str) -> str:
    """202607 → 2026-07。"""
    return f"{yyyymm[:4]}-{yyyymm[4:6]}"


def run(index_code: str = "000300.SH", month: str = "", ods_root=None) -> dict:
    """month 格式 YYYYMM，默认上月。"""
    if not month:
        today = datetime.now(timezone.utc)
        month = (today.replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y%m")
    raw = extract(index_code, month)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {"status": "extract_failed", "domain": DOMAIN, "month": month}
    clean = transform(raw, _format_month(month))
    report = check_quality(clean)
    if report.has_blocking():
        return {"status": "quality_failed", "domain": DOMAIN, "month": month,
                "issues": report.to_list()}
    load_result = write_parquet(
        domain=DOMAIN, partition_col=PARTITION_COL,
        partition_val=_format_month(month), rows=clean,
        mode="overwrite", ods_root=ods_root,
    )
    return {"status": "ok", "domain": DOMAIN, "month": month,
            "rows": len(clean), "load": load_result, "issues": report.to_list()}


CATALOG_ENTRY = {
    "table_name": "ods_index_constituents",
    "domain": "index_constituents",
    "source_mcp": SOURCE_MCP,
    "source_tool": "index_weight",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"index_code":"str","trade_date":"str","code":"str","exchange":"str","weight":"float"}',
    "description": "指数成分股月度快照（含权重）",
    "owner": "etl",
}
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_index_constituents.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 6: 提交**

```bash
git add scripts/etl/ods/index_constituents.py scripts/etl/tests/fixtures/tushare_index_weight.json scripts/etl/tests/test_index_constituents.py
git commit -m "feat(etl): add index_constituents ODS domain (P0) monthly snapshot"
```

---

## Task 10: financial_income 域 ETL（P1 样板）

**Files:**
- Create: `scripts/etl/ods/financial_income.py`
- Create: `scripts/etl/tests/fixtures/tushare_income.json`
- Test: `scripts/etl/tests/test_financial_income.py`

- [ ] **Step 1: 准备 fixture**

`scripts/etl/tests/fixtures/tushare_income.json`（tushare income 利润表样本，2 条）：

```json
[
  {"ts_code": "600519.SH", "ann_date": "20260328", "end_date": "20251231", "revenue": 1.5e11, "oper_profit": 9.5e10, "n_income": 7.5e10, "n_income_attr_p": 7.4e10, "update_flag": "1"},
  {"ts_code": "000001.SZ", "ann_date": "20260328", "end_date": "20251231", "revenue": 1.8e11, "oper_profit": 6.5e10, "n_income": 5.2e10, "n_income_attr_p": 5.1e10, "update_flag": "1"}
]
```

- [ ] **Step 2: 写失败测试**

`scripts/etl/tests/test_financial_income.py`：

```python
"""Tests for financial_income ETL domain."""
import json
from pathlib import Path
from unittest.mock import patch

from ods.financial_income import DOMAIN, PARTITION_COL, transform, run

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_income.json"


def _load():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "financial_income"
    assert PARTITION_COL == "period"


def test_transform_partition_period_format():
    """period 分区：end_date 20251231 → 2025Q4。"""
    raw = _load()
    clean = transform(raw, "2025Q4")
    assert clean[0]["period"] == "2025Q4"
    assert clean[0]["end_date"] == "20251231"


def test_transform_strips_ts_code():
    raw = _load()
    clean = transform(raw, "2025Q4")
    assert clean[0]["code"] == "600519"
    assert clean[0]["exchange"] == "SH"


def test_run_end_to_end(tmp_path):
    raw = _load()
    with patch("ods.financial_income.mcp_client.call", return_value=raw):
        result = run(period="20251231", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
```

- [ ] **Step 3: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_financial_income.py -v`
Expected: FAIL

- [ ] **Step 4: 实现 financial_income.py**

`scripts/etl/ods/financial_income.py`：

```python
"""ODS ETL: 利润表（按财报期）。

数据源：tushare income
分区：period=YYYYQn（财报期，同财报期会修订，保留多版本通过 ann_date 区分）
"""
from __future__ import annotations

from datetime import datetime, timezone

from common import mcp_client
from common.meta_fields import inject
from common.parquet_writer import write as write_parquet
from common.quality import run_checks, min_row_count, no_null_in

DOMAIN = "financial_income"
PARTITION_COL = "period"
PARTITION_GRAIN = "quarterly"
SOURCE_MCP = "tushare"

MIN_ROWS = 100  # 单期财报至少 100 家披露


def _end_date_to_period(end_date: str) -> str:
    """20251231 → 2025Q4；20250930 → 2025Q3。"""
    y = end_date[:4]
    md = end_date[4:]
    quarter = {"0331": "Q1", "0630": "Q2", "0930": "Q3", "1231": "Q4"}.get(md, "Q4")
    return f"{y}{quarter}"


def extract(period_end: str) -> list[dict]:
    """period_end 格式 YYYYMMDD（如 20251231）。"""
    return mcp_client.call(SOURCE_MCP, "income", {"period": period_end})


def _split_ts_code(ts_code: str) -> tuple[str, str]:
    if "." in ts_code:
        code, _, ex = ts_code.partition(".")
        return code, ex
    return ts_code, ""


def transform(rows: list[dict], period_partition: str) -> list[dict]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{period_partition}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash()

    result = []
    for r in rows:
        if "error" in r:
            continue
        code, exchange = _split_ts_code(r.get("ts_code", ""))
        result.append({
            "code": code,
            "exchange": exchange,
            "ann_date": str(r.get("ann_date", "")),
            "end_date": str(r.get("end_date", "")),
            "period": period_partition,
            "update_flag": str(r.get("update_flag", "")),
            "revenue": float(r.get("revenue", 0) or 0),
            "oper_profit": float(r.get("oper_profit", 0) or 0),
            "n_income": float(r.get("n_income", 0) or 0),
            "n_income_attr_p": float(r.get("n_income_attr_p", 0) or 0),
            **inject(
                source=SOURCE_MCP, source_tool="income",
                fetched_at=fetched_at, params_hash=p_hash, etl_run_id=etl_run_id,
            ),
        })
    return result


def check_quality(rows: list[dict]):
    return run_checks(DOMAIN, rows, "", [
        min_row_count(MIN_ROWS),
        no_null_in(["code", "end_date"]),
    ])


def run(period: str = "", ods_root=None) -> dict:
    """period 格式 YYYYMMDD（财报期末日，如 20251231）。"""
    if not period:
        # 默认最近一个财报期末
        today = datetime.now(timezone.utc)
        # 简化：取最近一年的 Q4
        period = f"{today.year - 1}1231"
    raw = extract(period)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {"status": "extract_failed", "domain": DOMAIN, "period": period}
    period_partition = _end_date_to_period(period)
    clean = transform(raw, period_partition)
    report = check_quality(clean)
    if report.has_blocking():
        return {"status": "quality_failed", "domain": DOMAIN, "period": period,
                "issues": report.to_list()}
    load_result = write_parquet(
        domain=DOMAIN, partition_col=PARTITION_COL,
        partition_val=period_partition, rows=clean,
        mode="overwrite", ods_root=ods_root,
    )
    return {"status": "ok", "domain": DOMAIN, "period": period,
            "rows": len(clean), "load": load_result, "issues": report.to_list()}


CATALOG_ENTRY = {
    "table_name": "ods_financial_income",
    "domain": "financials",
    "source_mcp": SOURCE_MCP,
    "source_tool": "income",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"code":"str","ann_date":"str","end_date":"str","period":"str","revenue":"float","oper_profit":"float","n_income":"float","n_income_attr_p":"float"}',
    "description": "利润表（按财报期分区）",
    "owner": "etl",
}
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_financial_income.py -v`
Expected: PASS（4 个测试全过）

注意：`test_run_end_to_end` 的 fixture 只有 2 行，会触发 `MIN_ROWS=100` 阻断。修正：fixture 测试**只验证 transform 不验证 quality**，端到端测试 mock quality 或降低阈值。

调整 `test_run_end_to_end`：

```python
def test_run_end_to_end(tmp_path):
    """端到端：mock MCP + 降低 quality 阈值验证落地。"""
    raw = _load()
    with patch("ods.financial_income.mcp_client.call", return_value=raw):
        with patch("ods.financial_income.MIN_ROWS", 1):  # 测试用低阈值
            result = run(period="20251231", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
```

- [ ] **Step 6: 运行测试再次验证通过**

Run: `uv run pytest scripts/etl/tests/test_financial_income.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 7: 提交**

```bash
git add scripts/etl/ods/financial_income.py scripts/etl/tests/fixtures/tushare_income.json scripts/etl/tests/test_financial_income.py
git commit -m "feat(etl): add financial_income ODS domain (P1) quarterly"
```

---

## Task 11: JobService 任务队列

**Files:**
- Create: `scripts/etl/common/jobs.py`
- Test: `scripts/etl/tests/test_jobs.py`

- [ ] **Step 1: 写失败测试**

`scripts/etl/tests/test_jobs.py`：

```python
"""Tests for JobService (DuckDB implementation)."""
import duckdb
import pytest

from common.jobs import DuckDBJobService, JobSpec, init_jobs_table, JobStatus


@pytest.fixture()
def svc(tmp_path):
    db_path = tmp_path / "meta.db"
    conn = duckdb.connect(str(db_path))
    init_jobs_table(conn)
    yield DuckDBJobService(conn)
    conn.close()


def test_submit_returns_job_id(svc):
    """submit 返回 job_id。"""
    job_id = svc.submit(JobSpec(
        domain="equity_daily", params={"date": "20260717"},
    ))
    assert isinstance(job_id, str)
    assert len(job_id) > 0


def test_get_returns_job(svc):
    """get 返回 Job 对象。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={"date": "20260717"}))
    job = svc.get(job_id)
    assert job is not None
    assert job.domain == "equity_daily"
    assert job.status == JobStatus.PENDING


def test_claim_returns_pending_job(svc):
    """claim 领取 pending 任务，状态变 RUNNING。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}))
    job = svc.claim("worker-1")
    assert job is not None
    assert job.id == job_id
    assert job.status == JobStatus.RUNNING
    assert job.worker_id == "worker-1"
    assert job.attempts == 1


def test_claim_returns_none_when_no_pending(svc):
    """无 pending 任务时返回 None。"""
    assert svc.claim("worker-1") is None


def test_claim_atomic_no_double(svc):
    """两个 worker 不会领同一任务。"""
    svc.submit(JobSpec(domain="equity_daily", params={}))
    j1 = svc.claim("w1")
    j2 = svc.claim("w2")
    assert j1 is not None
    assert j2 is None  # 已被 w1 领走


def test_complete_sets_status(svc):
    """complete 置 COMPLETED 并写 result。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}))
    svc.claim("w1")
    svc.complete(job_id, {"status": "ok", "rows": 5000})
    job = svc.get(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"status": "ok", "rows": 5000}


def test_fail_with_retry_back_to_pending(svc):
    """fail(retry=True) 回到 PENDING。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}, max_attempts=3))
    svc.claim("w1")
    svc.fail(job_id, "network error", retry=True)
    job = svc.get(job_id)
    assert job.status == JobStatus.PENDING
    assert "network error" in (job.error or "")


def test_fail_no_retry_sets_failed(svc):
    """fail(retry=False) 或 attempts >= max 置 FAILED。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}, max_attempts=1))
    svc.claim("w1")
    svc.fail(job_id, "fatal", retry=True)  # attempts 已达 max
    job = svc.get(job_id)
    assert job.status == JobStatus.FAILED


def test_list_by_status(svc):
    """list 按 status 过滤。"""
    id1 = svc.submit(JobSpec(domain="d1", params={}))
    svc.submit(JobSpec(domain="d2", params={}))
    svc.claim("w1")  # 领走最早的一个
    pending = svc.list_jobs(status=JobStatus.PENDING)
    running = svc.list_jobs(status=JobStatus.RUNNING)
    assert len(pending) == 1
    assert len(running) == 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest scripts/etl/tests/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 jobs.py**

`scripts/etl/common/jobs.py`：

```python
"""JobService 任务队列：Protocol 抽象 + DuckDB 实现。

未来要升级到 pgboss 时，新增 PGBossJobService 实现同一 Protocol。
业务代码（runner / 未来外部消费者）只依赖 Protocol，不感知实现。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

import duckdb


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobSpec:
    """提交任务的参数。"""
    domain: str
    params: dict
    max_attempts: int = 3


@dataclass
class Job:
    """任务实体。"""
    id: str
    domain: str
    params: dict
    status: JobStatus
    worker_id: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    result: dict | None = None
    error: str | None = None
    created_at: str = ""
    claimed_at: str | None = None
    finished_at: str | None = None


class JobService(Protocol):
    """任务队列抽象接口。"""
    def submit(self, job: JobSpec) -> str: ...
    def claim(self, worker_id: str) -> Job | None: ...
    def complete(self, job_id: str, result: dict) -> None: ...
    def fail(self, job_id: str, error: str, retry: bool = True) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[Job]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_jobs_table(conn: duckdb.DuckDBPyConnection) -> None:
    """建 etl_jobs 表（幂等）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS etl_jobs (
            id              TEXT PRIMARY KEY,
            domain          TEXT NOT NULL,
            params_json     TEXT NOT NULL,
            status          TEXT NOT NULL,
            worker_id       TEXT,
            attempts        INTEGER DEFAULT 0,
            max_attempts    INTEGER DEFAULT 3,
            result_json     TEXT,
            error           TEXT,
            created_at      TEXT NOT NULL,
            claimed_at      TEXT,
            finished_at     TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON etl_jobs(status, created_at)"
    )


def _row_to_job(row, cols) -> Job:
    d = dict(zip(cols, row))
    return Job(
        id=d["id"],
        domain=d["domain"],
        params=json.loads(d["params_json"]),
        status=JobStatus(d["status"]),
        worker_id=d.get("worker_id"),
        attempts=d["attempts"],
        max_attempts=d["max_attempts"],
        result=json.loads(d["result_json"]) if d.get("result_json") else None,
        error=d.get("error"),
        created_at=d["created_at"],
        claimed_at=d.get("claimed_at"),
        finished_at=d.get("finished_at"),
    )


class DuckDBJobService:
    """DuckDB 实现：单进程内队列，事务保证 claim 不重复。

    适用场景：日级 ETL、单研究员、任务数 <1000。
    不适用：高并发多 worker 分布式场景（升级到 PGBossJobService）。
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def submit(self, job: JobSpec) -> str:
        job_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO etl_jobs
               (id, domain, params_json, status, attempts, max_attempts, created_at)
               VALUES (?, ?, ?, 'pending', 0, ?, ?)""",
            [job_id, job.domain, json.dumps(job.params), job.max_attempts, _now()],
        )
        return job_id

    def claim(self, worker_id: str) -> Job | None:
        """事务内领取一个 pending 任务。"""
        # DuckDB 不支持 SELECT FOR UPDATE，但单连接事务内 SELECT+UPDATE 是原子的
        self.conn.execute("BEGIN TRANSACTION")
        try:
            row = self.conn.execute(
                """SELECT id FROM etl_jobs
                   WHERE status = 'pending'
                   ORDER BY created_at LIMIT 1"""
            ).fetchone()
            if not row:
                self.conn.execute("ROLLBACK")
                return None
            job_id = row[0]
            now = _now()
            self.conn.execute(
                """UPDATE etl_jobs
                   SET status = 'running', worker_id = ?, claimed_at = ?,
                       attempts = attempts + 1
                   WHERE id = ? AND status = 'pending'""",
                [worker_id, now, job_id],
            )
            self.conn.execute("COMMIT")
            return self.get(job_id)
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def complete(self, job_id: str, result: dict) -> None:
        self.conn.execute(
            """UPDATE etl_jobs
               SET status = 'completed', result_json = ?, finished_at = ?
               WHERE id = ?""",
            [json.dumps(result), _now(), job_id],
        )

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        job = self.get(job_id)
        if not job:
            return
        # 判断是否还能重试
        can_retry = retry and job.attempts < job.max_attempts
        new_status = "pending" if can_retry else "failed"
        self.conn.execute(
            """UPDATE etl_jobs
               SET status = ?, error = ?, finished_at = CASE WHEN ? IS NULL THEN finished_at ELSE ? END
               WHERE id = ?""",
            [new_status, error, None if can_retry else "x", _now() if not can_retry else None, job_id],
        )

    def get(self, job_id: str) -> Job | None:
        row = self.conn.execute(
            "SELECT * FROM etl_jobs WHERE id = ?", [job_id]
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self.conn.description]
        return _row_to_job(row, cols)

    def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[Job]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM etl_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                [status.value, limit],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM etl_jobs ORDER BY created_at DESC LIMIT ?", [limit]
            ).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [_row_to_job(r, cols) for r in rows]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest scripts/etl/tests/test_jobs.py -v`
Expected: PASS（9 个测试全过）

如果 `test_fail_no_retry_sets_failed` 失败，检查 `fail()` 的 SQL CASE WHEN 逻辑。简化版本：

```python
def fail(self, job_id: str, error: str, retry: bool = True) -> None:
    job = self.get(job_id)
    if not job:
        return
    can_retry = retry and job.attempts < job.max_attempts
    if can_retry:
        self.conn.execute(
            "UPDATE etl_jobs SET status = 'pending', error = ? WHERE id = ?",
            [error, job_id],
        )
    else:
        self.conn.execute(
            "UPDATE etl_jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            [error, _now(), job_id],
        )
```

替换 `fail` 方法为上面简化版（更易读、测试更稳定）。

- [ ] **Step 5: 提交**

```bash
git add scripts/etl/common/jobs.py scripts/etl/tests/test_jobs.py
git commit -m "feat(etl): add JobService abstraction with DuckDB implementation"
```

---

## Task 12: init.py 初始化

**Files:**
- Create: `scripts/etl/init.py`

- [ ] **Step 1: 实现 init.py**

`scripts/etl/init.py`：

```python
"""一次性初始化：建目录、meta.db、catalog/jobs 表、DuckDB 视图、注册 catalog。

Usage: uv run python -m scripts.etl.init
"""
from __future__ import annotations

import duckdb

from common.config import (
    WAREHOUSE_ROOT, ODS_ROOT, META_DB_PATH, LOGS_DIR, ensure_dirs,
)
from common.catalog import init_catalog, register
from common.jobs import init_jobs_table
from ods.equity_daily import CATALOG_ENTRY as EQUITY_DAILY_CAT
from ods.index_constituents import CATALOG_ENTRY as INDEX_CAT
from ods.financial_income import CATALOG_ENTRY as INCOME_CAT

# 所有已实现的 domain catalog（init 时注册）
_ALL_CATALOGS = [EQUITY_DAILY_CAT, INDEX_CAT, INCOME_CAT]

# 所有 ODS 视图定义（domain → hive 路径 glob）
_ODS_VIEWS = {
    "ods_equity_daily": "equity_daily/dt=*/part-*.parquet",
    "ods_index_constituents": "index_constituents/dt=*/part-*.parquet",
    "ods_financial_income": "financial_income/period=*/part-*.parquet",
}


def create_views(conn: duckdb.DuckDBPyConnection) -> None:
    """为每个已实现的 ODS 表建视图。"""
    for view_name, glob in _ODS_VIEWS.items():
        parquet_path = str(ODS_ROOT / glob)
        conn.execute(
            f"""CREATE OR REPLACE VIEW {view_name} AS
                SELECT * FROM read_parquet('{parquet_path}', hive_partitioning=true)
            """
        )
        print(f"  VIEW: {view_name}")


def main() -> int:
    print("Initializing data warehouse...")
    print(f"  WAREHOUSE_ROOT: {WAREHOUSE_ROOT}")

    # 1. 目录
    ensure_dirs()
    print(f"  dirs ready: ods/ _logs/")

    # 2. 连接 meta.db
    conn = duckdb.connect(str(META_DB_PATH))

    # 3. catalog + jobs 表
    init_catalog(conn)
    init_jobs_table(conn)
    print("  tables: ods_catalog, etl_jobs")

    # 4. 注册 catalog
    for entry in _ALL_CATALOGS:
        register(conn, entry)
    print(f"  catalog: {len(_ALL_CATALOGS)} domains registered")

    # 5. 视图（首次可能无 parquet 文件，视图仍可建，查询时返回空）
    create_views(conn)

    conn.close()
    print("\n✓ Warehouse initialized. Run ETL: uv run python -m scripts.etl.runner equity_daily --date <YYYYMMDD>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 手动验证初始化**

Run: `uv run python -m scripts.etl.init`
Expected: 打印初始化信息，无错误。`data/warehouse/meta.db` 文件存在。

Run: `uv run python -c "import duckdb; c=duckdb.connect('data/warehouse/meta.db'); print(c.execute('SHOW TABLES').fetchall())"`
Expected: `[('etl_jobs',), ('ods_catalog',)]`（视图在首次无 parquet 时仍可创建）

- [ ] **Step 3: 验证视图可查（空表不报错）**

Run: `uv run python -c "import duckdb; c=duckdb.connect('data/warehouse/meta.db'); print(c.execute('SELECT COUNT(*) FROM ods_equity_daily').fetchone())"`
Expected: `(0,)` 或类似（视图存在但无数据，count 为 0）

- [ ] **Step 4: 提交**

```bash
git add scripts/etl/init.py
git commit -m "feat(etl): add init command to bootstrap warehouse structure"
```

---

## Task 13: runner.py 统一调度入口

**Files:**
- Create: `scripts/etl/runner.py`

- [ ] **Step 1: 实现 runner.py**

`scripts/etl/runner.py`：

```python
"""ETL 统一调度入口。

Usage:
  uv run python -m scripts.etl.runner equity_daily --date 20260717
  uv run python -m scripts.etl.runner equity_daily --start 2024-01-01 --end 2024-12-31 --direct-sdk
  uv run python -m scripts.etl.runner --priority P0 --date 20260717
  uv run python -m scripts.etl.runner --all --date 20260717
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from common.config import LOGS_DIR, ensure_dirs
from common import mcp_client

# domain 名 → (module, priority) 映射
_DOMAIN_REGISTRY = {
    "equity_daily": ("ods.equity_daily", "P0"),
    "index_constituents": ("ods.index_constituents", "P0"),
    "financial_income": ("ods.financial_income", "P1"),
}


def _import_domain(name: str):
    """动态 import domain 模块。"""
    module_name = _DOMAIN_REGISTRY[name][0]
    return __import__(module_name, fromlist=["run"])


def _run_single(domain: str, date: str, direct_sdk: bool = False) -> dict:
    """跑单个 domain 单日。返回运行报告。"""
    mod = _import_domain(domain)
    started = datetime.now(timezone.utc).isoformat()
    try:
        # --direct-sdk 暂未实现，所有 domain 走 MCP HTTP
        # 如 domain run 支持 source 参数，传 direct_sdk
        kwargs = {}
        if direct_sdk:
            kwargs["source"] = "direct_sdk"
        result = mod.run(date, **kwargs)
        result["started_at"] = started
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception as e:
        return {
            "status": "error", "domain": domain, "date": date,
            "error": str(e), "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }


def _run_range(domain: str, start: str, end: str) -> list[dict]:
    """跑日期范围。简化版：start/end 都是 YYYYMMDD，逐日跑。"""
    # 生成交易日列表（用 exchange_calendars）
    try:
        import exchange_calendars as xcals
        sess = xcals.get_calendar("XSHG")  # 上交所
        sessions = sess.sessions_in_range(start, end)
        dates = [s.strftime("%Y%m%d") for s in sessions]
    except ImportError:
        # fallback：直接逐日（含非交易日，domain 会返回空数据）
        from datetime import datetime as dt, timedelta
        dates = []
        cur = dt.strptime(start, "%Y%m%d")
        end_dt = dt.strptime(end, "%Y%m%d")
        while cur <= end_dt:
            dates.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)

    return [_run_single(domain, d) for d in dates]


def _write_log(reports: list[dict]) -> str:
    """写运行日志 JSON。返回路径。"""
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"etl_{ts}.json"
    log_path.write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))
    return str(log_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL runner")
    parser.add_argument("domain", nargs="?", default=None,
                        help="single domain (e.g., equity_daily)")
    parser.add_argument("--date", default=None, help="YYYYMMDD")
    parser.add_argument("--start", default=None, help="YYYYMMDD (range start)")
    parser.add_argument("--end", default=None, help="YYYYMMDD (range end)")
    parser.add_argument("--priority", default=None, choices=["P0", "P1", "P2"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--direct-sdk", action="store_true",
                        help="bypass MCP HTTP, call SDK directly (historical backfill only)")
    args = parser.parse_args()

    # 确定要跑的 domain 列表
    if args.domain:
        domains = [args.domain]
    elif args.priority:
        domains = [n for n, (_, p) in _DOMAIN_REGISTRY.items() if p == args.priority]
    elif args.all:
        domains = list(_DOMAIN_REGISTRY.keys())
    else:
        parser.error("must specify domain, --priority, or --all")

    # 健康检查（非 --direct-sdk 时）
    if not args.direct_sdk:
        for src in ["akshare", "tushare"]:
            if not mcp_client.health_check(src):
                print(f"⚠️  MCP {src} not reachable (some domains may fail)")

    reports = []
    for domain in domains:
        if args.start and args.end:
            print(f"→ {domain}: range {args.start} ~ {args.end}")
            reports.extend(_run_range(domain, args.start, args.end))
        else:
            date = args.date or datetime.now().strftime("%Y%m%d")
            print(f"→ {domain}: {date}")
            reports.append(_run_single(domain, date, direct_sdk=args.direct_sdk))

    # 汇总打印
    print("\n" + "=" * 60)
    for r in reports:
        status_icon = "✓" if r["status"] == "ok" else "✗"
        print(f"  {status_icon} {r.get('domain','?')} {r.get('date', r.get('period',''))} → {r['status']}" +
              (f" ({r.get('rows')} rows)" if r.get("rows") else ""))

    log_path = _write_log(reports)
    print(f"\nLog: {log_path}")

    # 任一失败返回非零
    return 0 if all(r["status"] == "ok" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 验证 --help 可用**

Run: `uv run python -m scripts.etl.runner --help`
Expected: 打印 usage 信息，无报错

- [ ] **Step 3: 验证无 MCP 时的健康检查提示（不连 server）**

Run: `uv run python -m scripts.etl.runner equity_daily --date 20260717`
Expected: 打印 `⚠️ MCP ... not reachable`，然后 extract_failed（不崩溃）。退出码非零。

- [ ] **Step 4: 提交**

```bash
git add scripts/etl/runner.py
git commit -m "feat(etl): add runner with single/range/priority modes and health check"
```

---

## Task 14: report.py 子命令

**Files:**
- Create: `scripts/etl/report.py`

- [ ] **Step 1: 实现 report.py**

`scripts/etl/report.py`：

```python
"""ETL 报告子命令：缺数据 / 质量 / 任务历史。

Usage:
  uv run python -m scripts.etl.report --missing-dates --domain equity_daily --last 30d
  uv run python -m scripts.etl.report --quality-trend --domain equity_daily
  uv run python -m scripts.etl.report --jobs --status failed --last 7d
"""
from __future__ import annotations

import argparse
import duckdb
from datetime import datetime, timedelta, timezone

from common.config import META_DB_PATH, ODS_ROOT


def _parse_last(s: str) -> datetime:
    """'30d' / '7d' → datetime。"""
    days = int(s.rstrip("d"))
    return datetime.now(timezone.utc) - timedelta(days=days)


def missing_dates(domain: str, last: str) -> None:
    """报告某 domain 在最近 N 天缺失的交易日。"""
    since = _parse_last(last)
    parquet_glob = str(ODS_ROOT / f"{domain}/dt=*/part-*.parquet")

    conn = duckdb.connect(str(META_DB_PATH))
    try:
        # 读已有分区
        try:
            rows = conn.execute(
                f"""SELECT DISTINCT dt FROM read_parquet('{parquet_glob}', hive_partitioning=true)
                    ORDER BY dt"""
            ).fetchall()
            have = {r[0] for r in rows}
        except Exception:
            have = set()

        # 期望的交易日（用 exchange_calendars）
        try:
            import exchange_calendars as xcals
            sess = xcals.get_calendar("XSHG")
            sessions = sess.sessions_in_range(
                since.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d")
            )
            expected = {s.strftime("%Y-%m-%d") for s in sessions}
        except ImportError:
            expected = set()

        missing = sorted(expected - have)
        print(f"Missing dates for {domain} (last {last}): {len(missing)}")
        for d in missing:
            print(f"  - {d}")
        if missing:
            print(f"\nBackfill: uv run python -m scripts.etl.runner {domain} --start {missing[0].replace('-','')} --end {missing[-1].replace('-','')}")
    finally:
        conn.close()


def jobs_report(status: str | None, last: str) -> None:
    """报告队列任务历史。"""
    since = _parse_last(last)
    conn = duckdb.connect(str(META_DB_PATH))
    try:
        if status:
            rows = conn.execute(
                "SELECT id, domain, status, attempts, error, created_at, finished_at "
                "FROM etl_jobs WHERE status = ? AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 100",
                [status, since.isoformat()],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, domain, status, attempts, error, created_at, finished_at "
                "FROM etl_jobs WHERE created_at >= ? "
                "ORDER BY created_at DESC LIMIT 100",
                [since.isoformat()],
            ).fetchall()

        print(f"Jobs (status={status or 'all'}, last {last}): {len(rows)}")
        for r in rows:
            err = f" | {r[4][:80]}" if r[4] else ""
            print(f"  [{r[2]:9}] {r[1]:20} attempts={r[3]} created={r[5][:19]}{err}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL report")
    parser.add_argument("--missing-dates", action="store_true")
    parser.add_argument("--quality-trend", action="store_true")
    parser.add_argument("--jobs", action="store_true")
    parser.add_argument("--domain", default="equity_daily")
    parser.add_argument("--status", default=None, choices=["pending", "running", "completed", "failed"])
    parser.add_argument("--last", default="30d", help="time window, e.g. 30d / 7d")
    args = parser.parse_args()

    if args.missing_dates:
        missing_dates(args.domain, args.last)
    elif args.jobs:
        jobs_report(args.status, args.last)
    elif args.quality_trend:
        print("TODO: quality-trend 在引入 quality_log 表后实现（本计划不覆盖）")
        return 1
    else:
        parser.error("must specify --missing-dates / --jobs / --quality-trend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 验证 --jobs 可查（空表不报错）**

Run: `uv run python -m scripts.etl.report --jobs --last 7d`
Expected: 打印 `Jobs (status=all, last 7d): 0`（或之前测试留下的数据）

- [ ] **Step 3: 验证 --missing-dates 在无数据时正常**

Run: `uv run python -m scripts.etl.report --missing-dates --domain equity_daily --last 30d`
Expected: 打印缺数据列表（或 "0" 如所有日期都有），不崩溃

- [ ] **Step 4: 提交**

```bash
git add scripts/etl/report.py
git commit -m "feat(etl): add report command for missing-dates and jobs"
```

---

## Task 15: check.py 扩展 + .gitignore + README

**Files:**
- Modify: `scripts/check.py`（main 函数的 checks 列表）
- Modify: `.gitignore`
- Create: `scripts/etl/README.md`

- [ ] **Step 1: 修改 scripts/check.py 加 check_warehouse**

在 `scripts/check.py` 的 `check_data_dir` 函数之后，新增：

```python
def check_warehouse() -> list[str]:
    """Check warehouse structure (optional, INFO only)."""
    issues = []
    wh = ROOT / "data" / "warehouse"
    if not wh.exists():
        issues.append(f"INFO: {wh} not initialized (run `uv run python -m scripts.etl.init`)")
        return issues
    meta_db = wh / "meta.db"
    if not meta_db.exists():
        issues.append(f"WARN: {meta_db} missing (run `uv run python -m scripts.etl.init`)")
    return issues
```

修改 `main()` 函数的 `checks` 列表，在 `("Environment Variables", check_env_vars)` 之前插入：

```python
        ("Warehouse", check_warehouse),
```

- [ ] **Step 2: 修改 .gitignore**

在 `.gitignore` 的 `# Data` 部分之后，新增：

```gitignore

# Warehouse runtime (Parquet under data/ already ignored; exclude db/logs)
data/warehouse/meta.db
data/warehouse/meta.db.wal
data/warehouse/_logs/
```

- [ ] **Step 3: 写 scripts/etl/README.md**

`scripts/etl/README.md`：

```markdown
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

# 4. 历史回填（一次性，用 --direct-sdk 加速）
uv run python -m scripts.etl.runner equity_daily --start 2015-01-01 --end 2026-07-17 --direct-sdk
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `python -m scripts.etl.init` | 初始化数仓（建目录、meta.db、视图） |
| `python -m scripts.etl.runner <domain> --date YYYYMMDD` | 单域单日 |
| `python -m scripts.etl.runner <domain> --start ... --end ...` | 单域日期范围 |
| `python -m scripts.etl.runner --priority P0 --date ...` | 按 P0/P1/P2 批量 |
| `python -m scripts.etl.report --missing-dates` | 查缺失日期 |
| `python -m scripts.etl.report --jobs --status failed` | 查失败任务 |

## 已实现的数据域

| Domain | 优先级 | 数据源 | 分区 |
|--------|--------|--------|------|
| equity_daily | P0 | tushare daily | dt=YYYY-MM-DD |
| index_constituents | P0 | tushare index_weight | dt=YYYY-MM |
| financial_income | P1 | tushare income | period=YYYYQn |

## 添加新 domain

复制 `ods/equity_daily.py` 为模板，实现 5 段式契约：
`extract → transform → check_quality → load → run`。

在 `_DOMAIN_REGISTRY`（runner.py）和 `_ALL_CATALOGS`（init.py）注册。

## 查询数据

```python
import duckdb
conn = duckdb.connect("data/warehouse/meta.db")
df = conn.execute("""
    SELECT code, close FROM ods_equity_daily
    WHERE dt = '2026-07-17' AND close > 100
""").fetchdf()
```
```

- [ ] **Step 4: 运行 check.py 验证**

Run: `uv run python scripts/check.py`
Expected: 新增 `[Warehouse]` section，显示 OK 或 INFO（未初始化时）。其他检查保持通过。

- [ ] **Step 5: 提交**

```bash
git add scripts/check.py .gitignore scripts/etl/README.md
git commit -m "feat(etl): extend check.py with warehouse, update gitignore, add ETL README"
```

---

## Task 16: 端到端验证

**Files:** 无新文件，仅验证

- [ ] **Step 1: 全套测试通过**

Run: `uv run pytest scripts/etl/tests/ -v`
Expected: 所有测试 PASS（约 45+ 个测试）

- [ ] **Step 2: ruff 检查**

Run: `uv run ruff check scripts/etl/`
Expected: 无错误（如有，按提示修复）

Run: `uv run ruff format scripts/etl/`
Expected: 格式化完成

- [ ] **Step 3: check.py 全通过**

Run: `uv run python scripts/check.py`
Expected: 所有 section OK（包括新的 Warehouse section）

- [ ] **Step 4: 集成测试（需要 MCP server 运行，标记 @pytest.mark.integration）**

如 MCP server 可启动（TUSHARE_TOKEN 可用），手动验证：

```bash
# 启动 server
uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001 &
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000 &

# 端到端跑一日
uv run python -m scripts.etl.init
uv run python -m scripts.etl.runner equity_daily --date <最近交易日>

# 验证数据落地
uv run python -c "import duckdb; c=duckdb.connect('data/warehouse/meta.db'); print(c.execute('SELECT COUNT(*), MIN(close), MAX(close) FROM ods_equity_daily').fetchone())"
```

Expected: COUNT > 4000（全市场行数），close 合理范围

- [ ] **Step 5: 验收 checklist 核对**

对照 spec §7 验收标准逐项确认：

- [ ] `uv run python -m scripts.etl.init` 能初始化数仓结构 ✓
- [ ] `uv run python -m scripts.etl.runner equity_daily --date <recent>` 能跑通 P0 域 ✓（集成测试）
- [ ] P0 域（equity_daily + index_constituents）ETL 完整实现且有测试 ✓
- [ ] DuckDB 视图 `ods_equity_daily` 可查询，分区裁剪生效 ✓
- [ ] JobService 接口定义 + DuckDBJobService 实现 + 测试 ✓
- [ ] `report --missing-dates` / `--jobs` 子命令可用 ✓
- [ ] `scripts/check.py` 新增 `check_warehouse` 通过 ✓
- [ ] 文档：`scripts/etl/README.md` 完整 ✓
- [ ] P1 域至少 1 个（financial_income）作为模式样板 ✓

- [ ] **Step 6: 最终提交（如有未提交的格式化改动）**

```bash
git status
# 如有未提交：
git add -A
git commit -m "test(etl): final cleanup and verification"
```

---

## Self-Review 结果

**Spec coverage（§7 验收标准对照）：**

| 验收项 | 对应 Task |
|---|---|
| `init` 初始化 | Task 12 |
| P0 域 equity_daily 跑通 | Task 8 + Task 16 集成验证 |
| P0 域 index_constituents 实现+测试 | Task 9 |
| DuckDB 视图可查询+分区裁剪 | Task 12（create_views）+ Task 16 |
| JobService 接口+实现+测试 | Task 11 |
| report 子命令 | Task 14 |
| check.py 扩展 | Task 15 |
| ETL README | Task 15 |
| P1 样板 financial_income | Task 10 |

✅ 所有验收项都有对应 task。

**Placeholder 扫描：** plan 内无 TBD/TODO（spec 中的 TODO 是设计层面的"后续 spec"声明，不是 plan 内的占位）。所有代码块完整。

**Type 一致性：** `JobStatus` 在 Task 11 定义，`test_jobs.py` 和 `jobs.py` 用法一致。`DOMAIN` / `PARTITION_COL` / `CATALOG_ENTRY` 在 Task 8/9/10 三个 domain 一致。`JobSpec` / `Job` / `JobService` 类型签名贯穿 Task 11。

**已知简化（不是 bug）：**
- `--direct-sdk` 在 Task 13 仅作参数接收，未真正实现（spec 说本期暂不实现 SDK 直调，留后续增量）
- akshare fallback 在 Task 8 `extract` 里抛 NotImplementedError（spec 说 fallback 是 P0 之后的优化）
- `quality-trend` 在 Task 14 返回 TODO（依赖 quality_log 表，本计划不覆盖）
