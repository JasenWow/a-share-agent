"""ODS ETL: 策略假设实验（experiments 表快照）。

数据源：internal-store list_experiments
分区：dt=YYYY-MM-DD（快照分区）

internal-store experiments 列：
  id, name, strategy (JSON), params (JSON), result (JSON), created_at

strategy/params/result 原样保留 JSON 字符串，下游 dbt 再展开。
"""

from __future__ import annotations

from datetime import datetime, timezone

from aquan.utils import http as mcp_client
from etl.meta_fields import inject
from aquan.utils.hashing import params_hash as compute_hash
from aquan.utils.io import write as write_parquet
from etl.quality import run_checks, min_row_count, no_null_in

DOMAIN = "strategy_hypotheses"
PARTITION_COL = "dt"
PARTITION_GRAIN = "snapshot"
SOURCE_MCP = "internal-store"

MIN_ROWS = 1


def extract(date: str) -> list[dict]:
    """date 仅作为分区标签。"""
    return mcp_client.call(SOURCE_MCP, "list_experiments", {})


def transform(rows: list[dict], date: str) -> list[dict]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{date}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash() or compute_hash({})

    result = []
    for r in rows:
        if "error" in r:
            continue
        result.append(
            {
                "snapshot_date": date,
                "experiment_id": int(r.get("id", 0) or 0),
                "name": str(r.get("name", "")),
                # strategy/params/result 是 JSON 字符串，原样保留供下游 dbt 展开
                "strategy_json": str(r.get("strategy", "") or ""),
                "params_json": str(r.get("params", "") or ""),
                "result_json": str(r.get("result", "") or ""),
                "created_at": str(r.get("created_at", "")),
                **inject(
                    source=SOURCE_MCP,
                    source_tool="list_experiments",
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
            no_null_in(["name"]),
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
    "table_name": "ods_strategy_hypotheses",
    "domain": "experiments",
    "source_mcp": SOURCE_MCP,
    "source_tool": "list_experiments",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"snapshot_date":"str","experiment_id":"int","name":"str","strategy_json":"str","params_json":"str","result_json":"str","created_at":"str"}',
    "description": "策略假设实验快照（按日分区，JSON 字段原样保留）",
    "owner": "etl",
}
