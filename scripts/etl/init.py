"""一次性初始化：建目录、meta.db、catalog/jobs 表、DuckDB 视图、注册 catalog。

Usage: uv run python -m scripts.etl.init
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 `from common.X` 和 `from ods.X` 在 python -m 下可用
_ETL_ROOT = str(Path(__file__).resolve().parent)
if _ETL_ROOT not in sys.path:
    sys.path.insert(0, _ETL_ROOT)

import duckdb  # noqa: E402

from common.config import (  # noqa: E402
    WAREHOUSE_ROOT,
    ODS_ROOT,
    META_DB_PATH,
    ensure_dirs,
)
from common.catalog import init_catalog, register  # noqa: E402
from common.jobs import init_jobs_table  # noqa: E402
from ods.equity_daily import CATALOG_ENTRY as EQUITY_DAILY_CAT  # noqa: E402
from ods.index_constituents import CATALOG_ENTRY as INDEX_CAT  # noqa: E402
from ods.financial_income import CATALOG_ENTRY as INCOME_CAT  # noqa: E402
from ods.factor_experiments import CATALOG_ENTRY as FACTOR_EXP_CAT  # noqa: E402
from ods.backtest_runs import CATALOG_ENTRY as BACKTEST_CAT  # noqa: E402
from ods.strategy_hypotheses import CATALOG_ENTRY as HYPOTH_CAT  # noqa: E402

# 所有已实现的 domain catalog（init 时注册）
_ALL_CATALOGS = [
    EQUITY_DAILY_CAT,
    INDEX_CAT,
    INCOME_CAT,
    FACTOR_EXP_CAT,
    BACKTEST_CAT,
    HYPOTH_CAT,
]

# 所有 ODS 视图定义（domain → hive 路径 glob）
_ODS_VIEWS = {
    "ods_equity_daily": "equity_daily/dt=*/part-*.parquet",
    "ods_index_constituents": "index_constituents/dt=*/part-*.parquet",
    "ods_financial_income": "financial_income/period=*/part-*.parquet",
    "ods_factor_experiments": "factor_experiments/dt=*/part-*.parquet",
    "ods_backtest_runs": "backtest_runs/dt=*/part-*.parquet",
    "ods_strategy_hypotheses": "strategy_hypotheses/dt=*/part-*.parquet",
}


def create_views(conn: duckdb.DuckDBPyConnection) -> None:
    """为每个已实现的 ODS 表建视图。

    首次运行可能无 parquet 文件，此时建一个空视图（schema 来自 catalog），
    后续 ETL 写入 parquet 后，视图自动指向真实数据（视图是懒求值）。
    需要重新跑 init 刷新视图，或直接查询 parquet glob。
    """

    # 各 domain 的空 schema（与 CATALOG_ENTRY 对齐，DuckDB 类型名）
    empty_schemas = {
        "ods_equity_daily": {
            "trade_date": "VARCHAR",
            "code": "VARCHAR",
            "exchange": "VARCHAR",
            "open": "DOUBLE",
            "high": "DOUBLE",
            "low": "DOUBLE",
            "close": "DOUBLE",
            "volume": "DOUBLE",
            "amount": "DOUBLE",
            "pct_chg": "DOUBLE",
        },
        "ods_index_constituents": {
            "index_code": "VARCHAR",
            "trade_date": "VARCHAR",
            "code": "VARCHAR",
            "exchange": "VARCHAR",
            "weight": "DOUBLE",
        },
        "ods_financial_income": {
            "code": "VARCHAR",
            "exchange": "VARCHAR",
            "ann_date": "VARCHAR",
            "end_date": "VARCHAR",
            "period": "VARCHAR",
            "update_flag": "VARCHAR",
            "revenue": "DOUBLE",
            "oper_profit": "DOUBLE",
            "n_income": "DOUBLE",
            "n_income_attr_p": "DOUBLE",
        },
        "ods_factor_experiments": {
            "snapshot_date": "VARCHAR",
            "factor_id": "INTEGER",
            "name": "VARCHAR",
            "expression": "VARCHAR",
            "operators": "VARCHAR",
            "data_fields": "VARCHAR",
            "ic": "DOUBLE",
            "icir": "DOUBLE",
            "turnover": "DOUBLE",
            "sharpe": "DOUBLE",
            "max_drawdown": "DOUBLE",
            "universe": "VARCHAR",
            "period": "VARCHAR",
            "status": "VARCHAR",
            "source_experiment_id": "INTEGER",
            "created_at": "VARCHAR",
        },
        "ods_backtest_runs": {
            "snapshot_date": "VARCHAR",
            "run_id": "INTEGER",
            "name": "VARCHAR",
            "strategy": "VARCHAR",
            "start_date": "VARCHAR",
            "end_date": "VARCHAR",
            "sharpe": "DOUBLE",
            "max_drawdown": "DOUBLE",
            "annual_return": "DOUBLE",
            "created_at": "VARCHAR",
        },
        "ods_strategy_hypotheses": {
            "snapshot_date": "VARCHAR",
            "experiment_id": "INTEGER",
            "name": "VARCHAR",
            "strategy_json": "VARCHAR",
            "params_json": "VARCHAR",
            "result_json": "VARCHAR",
            "created_at": "VARCHAR",
        },
    }

    for view_name, glob in _ODS_VIEWS.items():
        parquet_path = str(ODS_ROOT / glob)
        try:
            conn.execute(
                f"""CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM read_parquet(
                        '{parquet_path}', hive_partitioning=true
                    )"""
            )
            print(f"  VIEW: {view_name} (live)")
        except Exception:
            # 首次无 parquet：用 VALUES 建带 schema 的空视图占位
            cols = list(empty_schemas[view_name].items())
            # 构造一个全 NULL 的单行 cast，再过滤掉，得到带 schema 的 0 行视图
            cast_cols = ", ".join(f"CAST(NULL AS {v}) AS {k}" for k, v in cols)
            conn.execute(
                f"""CREATE OR REPLACE VIEW {view_name} AS
                    SELECT {cast_cols} WHERE 1=0"""
            )
            print(f"  VIEW: {view_name} (empty placeholder, re-run init after ETL)")


def main() -> int:
    print("Initializing data warehouse...")
    print(f"  WAREHOUSE_ROOT: {WAREHOUSE_ROOT}")

    # 1. 目录
    ensure_dirs()
    print("  dirs ready: warehouse/ ods/ _logs/")

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

    # 5. 视图
    create_views(conn)

    conn.close()
    print("\n✓ Warehouse initialized. Run ETL: uv run python -m scripts.etl.runner equity_daily --date <YYYYMMDD>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
