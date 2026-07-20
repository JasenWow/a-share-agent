"""ODS ETL: 利润表（按财报期）。

数据源：tushare income
分区：period=YYYYQn（财报期，同财报期会修订，多版本通过 ann_date 区分）
"""

from __future__ import annotations

from datetime import datetime, timezone

from aquan.utils import http as mcp_client
from etl.meta_fields import inject
from aquan.utils.io import write as write_parquet
from etl.quality import run_checks, min_row_count, no_null_in

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
        result.append(
            {
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
                    source=SOURCE_MCP,
                    source_tool="income",
                    fetched_at=fetched_at,
                    params_hash=p_hash,
                    etl_run_id=etl_run_id,
                ),
            }
        )
    return result


def check_quality(rows: list[dict]):
    return run_checks(
        DOMAIN,
        rows,
        "",
        [min_row_count(MIN_ROWS), no_null_in(["code", "end_date"])],
    )


def run(period: str = "", ods_root=None) -> dict:
    """period 格式 YYYYMMDD（财报期末日，如 20251231）。默认最近一年 Q4。"""
    if not period:
        today = datetime.now(timezone.utc)
        period = f"{today.year - 1}1231"
    raw = extract(period)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {
            "status": "extract_failed",
            "domain": DOMAIN,
            "period": period,
            "error": raw[0].get("error") if raw else "empty",
        }
    period_partition = _end_date_to_period(period)
    clean = transform(raw, period_partition)
    report = check_quality(clean)
    if report.has_blocking():
        return {
            "status": "quality_failed",
            "domain": DOMAIN,
            "period": period,
            "issues": report.to_list(),
        }
    load_result = write_parquet(
        domain=DOMAIN,
        partition_col=PARTITION_COL,
        partition_val=period_partition,
        rows=clean,
        mode="overwrite",
        ods_root=ods_root,
    )
    return {
        "status": "ok",
        "domain": DOMAIN,
        "period": period,
        "rows": len(clean),
        "load": load_result,
        "issues": report.to_list(),
    }


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
