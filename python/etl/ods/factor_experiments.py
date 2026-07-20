"""ODS ETL: 因子实验（因子库快照）。

数据源：internal-store list_factors
分区：dt=YYYY-MM-DD（快照分区，每次拉取整个因子库）

internal-store 的 list_factors(status="all") 返回全量因子库（无日期参数），
因此采用**快照分区**：每次拉取整个因子库作为一个日期分区的快照。

五段式契约：extract → transform → check_quality → load → run
"""

from __future__ import annotations

from datetime import datetime, timezone

from aquan.utils import http as mcp_client
from etl.meta_fields import inject
from aquan.utils.hashing import params_hash as compute_hash
from aquan.utils.io import write as write_parquet
from etl.quality import run_checks, min_row_count, no_null_in

DOMAIN = "factor_experiments"
PARTITION_COL = "dt"
PARTITION_GRAIN = "snapshot"
SOURCE_MCP = "internal-store"

MIN_ROWS = 1  # 因子库可能为空（首次），不强制；但若有数据至少 1 行


def extract(date: str) -> list[dict]:
    """拉取整个因子库快照。date 仅作为分区标签，不参与源端过滤。"""
    return mcp_client.call(SOURCE_MCP, "list_factors", {"status": "all"})


def transform(rows: list[dict], date: str) -> list[dict]:
    """标准化字段 + 元数据注入。

    internal-store factor_library 列：
      id, name, expression, hypothesis, operators, data_fields,
      ic, icir, turnover, sharpe, max_drawdown, universe, period,
      walk_forward, status, source_experiment_id, created_at
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    etl_run_id = f"{date}_{datetime.now().strftime('%H%M%S')}_{DOMAIN}"
    p_hash = mcp_client.get_last_params_hash() or compute_hash({"status": "all"})

    result = []
    for r in rows:
        if "error" in r:
            continue
        result.append(
            {
                "snapshot_date": date,
                "factor_id": int(r.get("id", 0) or 0),
                "name": str(r.get("name", "")),
                "expression": str(r.get("expression", "")),
                "operators": str(r.get("operators", "")),
                "data_fields": str(r.get("data_fields", "")),
                "ic": float(r.get("ic", 0) or 0),
                "icir": float(r.get("icir", 0) or 0),
                "turnover": float(r.get("turnover", 0) or 0),
                "sharpe": float(r.get("sharpe", 0) or 0),
                "max_drawdown": float(r.get("max_drawdown", 0) or 0),
                "universe": str(r.get("universe", "")),
                "period": str(r.get("period", "")),
                "status": str(r.get("status", "")),
                "source_experiment_id": int(r.get("source_experiment_id", 0) or 0),
                "created_at": str(r.get("created_at", "")),
                **inject(
                    source=SOURCE_MCP,
                    source_tool="list_factors",
                    fetched_at=fetched_at,
                    params_hash=p_hash,
                    etl_run_id=etl_run_id,
                ),
            }
        )
    return result


def check_quality(rows: list[dict], date: str):
    """因子库可能为空（首跑），不强制 min_row_count 高阈值。"""
    return run_checks(
        DOMAIN,
        rows,
        date,
        [
            min_row_count(MIN_ROWS),
            no_null_in(["name", "expression"]),
        ],
    )


def _format_partition(date: str) -> str:
    """YYYYMMDD → YYYY-MM-DD（hive 分区格式）。"""
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
    """端到端。date 默认今天（快照分区）。"""
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
    "table_name": "ods_factor_experiments",
    "domain": "experiments",
    "source_mcp": SOURCE_MCP,
    "source_tool": "list_factors",
    "partition_col": PARTITION_COL,
    "partition_grain": PARTITION_GRAIN,
    "schema_json": '{"snapshot_date":"str","factor_id":"int","name":"str","expression":"str","operators":"str","data_fields":"str","ic":"float","icir":"float","turnover":"float","sharpe":"float","max_drawdown":"float","universe":"str","period":"str","status":"str","source_experiment_id":"int","created_at":"str"}',
    "description": "因子库快照（按日分区，每次拉取整个 factor_library）",
    "owner": "etl",
}
