"""ODS ETL: 回测运行（回测结果快照）。

数据源：internal-store list_backtest_results
分区：dt=YYYY-MM-DD（快照分区）

internal-store backtest_results 列：
  id, name, strategy, start_date, end_date, sharpe, max_drawdown,
  annual_return, created_at
"""

from __future__ import annotations

from datetime import datetime, timezone

from common import mcp_client
from common.meta_fields import inject
from common.meta_fields import params_hash as compute_hash
from common.parquet_writer import write as write_parquet
from common.quality import run_checks, min_row_count, no_null_in

DOMAIN = "backtest_runs"
PARTITION_COL = "dt"
PARTITION_GRAIN = "snapshot"
SOURCE_MCP = "internal-store"

MIN_ROWS = 1


def extract(date: str) -> list[dict]:
    """date 仅作为分区标签。"""
    return mcp_client.call(SOURCE_MCP, "list_backtest_results", {"limit": 500})


def transform(rows: list[dict], date: str) -> list[dict]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{date}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash() or compute_hash({"limit": 500})

    result = []
    for r in rows:
        if "error" in r:
            continue
        result.append(
            {
                "snapshot_date": date,
                "run_id": int(r.get("id", 0) or 0),
                "name": str(r.get("name", "")),
                "strategy": str(r.get("strategy", "")),
                "start_date": str(r.get("start_date", "")),
                "end_date": str(r.get("end_date", "")),
                "sharpe": float(r.get("sharpe", 0) or 0),
                "max_drawdown": float(r.get("max_drawdown", 0) or 0),
                "annual_return": float(r.get("annual_return", 0) or 0),
                "created_at": str(r.get("created_at", "")),
                **inject(
                    source=SOURCE_MCP,
                    source_tool="list_backtest_results",
                    fetched_at=fetched_at,
                    params_hash=p_hash,
                    etl_run_id=etl_run_id,
                ),
            }
        )
    return result


def check_quality(rows: list[dict], date: str):
    return run_checks(
        DOMAIN,
        rows,
        date,
        [
            min_row_count(MIN_ROWS),
            no_null_in(["name", "strategy"]),
        ],
    )


def _format_partition(date: str) -> str:
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}"


def load(rows: list[dict], date: str, ods_root=None) -> dict:
    return write_parquet(
        domain=DOMAIN,
        partition_col=PARTITION_COL,
        partition_val=_format_partition(date),
        rows=rows,
        mode="overwrite",
        ods_root=ods_root,
    )


def run(date: str = "", ods_root=None) -> dict:
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    raw = extract(date)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {
            "status": "extract_failed",
            "domain": DOMAIN,
            "date": date,
            "error": raw[0].get("error") if raw else "empty",
        }
    clean = transform(raw, date)
    report = check_quality(clean, date)
    if report.has_blocking():
        return {
            "status": "quality_failed",
            "domain": DOMAIN,
            "date": date,
            "issues": report.to_list(),
        }
    load_result = load(clean, date, ods_root=ods_root)
    return {
        "status": "ok",
        "domain": DOMAIN,
        "date": date,
        "rows": len(clean),
        "load": load_result,
        "issues": report.to_list(),
    }


CATALOG_ENTRY = {
    "table_name": "ods_backtest_runs",
    "domain": "experiments",
    "source_mcp": SOURCE_MCP,
    "source_tool": "list_backtest_results",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"snapshot_date":"str","run_id":"int","name":"str","strategy":"str","start_date":"str","end_date":"str","sharpe":"float","max_drawdown":"float","annual_return":"float","created_at":"str"}',
    "description": "回测运行结果快照（按日分区）",
    "owner": "etl",
}
