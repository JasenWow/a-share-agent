"""ODS ETL: 指数成分股（按月快照）。

数据源：tushare index_weight
分区：dt=YYYY-MM（月度快照，捕捉成分调整）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from common import mcp_client
from common.meta_fields import inject
from common.parquet_writer import write as write_parquet
from common.quality import run_checks, min_row_count, no_null_in

DOMAIN = "index_constituents"
PARTITION_COL = "dt"
PARTITION_GRAIN = "monthly"
SOURCE_MCP = "tushare"

# 沪深300/中证500 等主要指数成分至少 100 只；默认阈值放宽到 50 覆盖小指数
MIN_ROWS = 50


def _split_con_code(con_code: str) -> tuple[str, str]:
    """600519.SH → ('600519', 'SH')。无后缀返回空 exchange。"""
    if "." in con_code:
        code, _, exchange = con_code.partition(".")
        return code, exchange
    return con_code, ""


def _format_month(yyyymm: str) -> str:
    """202607 → 2026-07。"""
    return f"{yyyymm[:4]}-{yyyymm[4:6]}"


def extract(index_code: str, month: str) -> list[dict]:
    """month 格式 YYYYMM。tushare index_weight 接受 start_date/end_date 范围。"""
    start = f"{month}01"
    # 月末简化为 28 号（tushare 会返回该区间内的数据）
    end = f"{month}28"
    return mcp_client.call(
        SOURCE_MCP,
        "index_weight",
        {"index_code": index_code, "start_date": start, "end_date": end},
    )


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
                source=SOURCE_MCP,
                source_tool="index_weight",
                fetched_at=fetched_at,
                params_hash=p_hash,
                etl_run_id=etl_run_id,
            ),
        })
    return result


def check_quality(rows: list[dict]):
    return run_checks(
        DOMAIN,
        rows,
        "",
        [min_row_count(MIN_ROWS), no_null_in(["code", "index_code"])],
    )


def run(index_code: str = "000300.SH", month: str = "", ods_root=None) -> dict:
    """month 格式 YYYYMM，默认上月。"""
    if not month:
        today = datetime.now(timezone.utc)
        # 上月 = 这个月 1 号 - 1 天
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        month = last_of_last_month.strftime("%Y%m")

    raw = extract(index_code, month)
    if not raw or (len(raw) == 1 and "error" in raw[0]):
        return {
            "status": "extract_failed",
            "domain": DOMAIN,
            "month": month,
            "error": raw[0].get("error") if raw else "empty",
        }
    clean = transform(raw, _format_month(month))
    report = check_quality(clean)
    if report.has_blocking():
        return {
            "status": "quality_failed",
            "domain": DOMAIN,
            "month": month,
            "issues": report.to_list(),
        }
    load_result = write_parquet(
        domain=DOMAIN,
        partition_col=PARTITION_COL,
        partition_val=_format_month(month),
        rows=clean,
        mode="overwrite",
        ods_root=ods_root,
    )
    return {
        "status": "ok",
        "domain": DOMAIN,
        "month": month,
        "rows": len(clean),
        "load": load_result,
        "issues": report.to_list(),
    }


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
