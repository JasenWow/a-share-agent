"""ODS ETL: 股票日线行情。

数据源：tushare daily（主）/ akshare stock_zh_a_hist（备）
分区：dt=YYYY-MM-DD（日频）

五段式契约：extract → transform → check_quality → load → run
所有 ODS domain 都照此模式。
"""
from __future__ import annotations

from datetime import datetime, timezone

from common import mcp_client
from common.meta_fields import inject
from common.meta_fields import params_hash as compute_hash
from common.parquet_writer import write as write_parquet
from common.quality import (
    run_checks,
    min_row_count,
    no_null_in,
    date_is,
)

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
    # 本期暂不实现 akshare 全市场批量，留待后续增量
    raise NotImplementedError(f"akshare fallback not implemented for {DOMAIN}")


def _split_ts_code(ts_code: str) -> tuple[str, str]:
    """600519.SH → ('600519', 'SH')。裸码从代码派生。"""
    if "." in ts_code:
        code, _, exchange = ts_code.partition(".")
        return code, exchange
    code = ts_code
    if code.startswith("6"):
        return code, "SH"
    if code.startswith(("0", "3")):
        return code, "SZ"
    if code.startswith("8"):
        return code, "BJ"
    return code, "SZ"


def transform(rows: list[dict], date: str) -> list[dict]:
    """最小标准化：列名 snake_case + 类型 + 裸码化 + 元数据注入。"""
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
                source=SOURCE_MCP,
                source_tool="daily",
                fetched_at=fetched_at,
                params_hash=p_hash,
                etl_run_id=etl_run_id,
            ),
        })
    return result


def check_quality(rows: list[dict], date: str):
    """数据质量检查。"""
    return run_checks(
        DOMAIN,
        rows,
        date,
        [
            min_row_count(MIN_DAILY_ROWS),
            no_null_in(["code", "close"]),
            date_is(date, "trade_date"),
        ],
    )


def _format_partition(date: str) -> str:
    """YYYYMMDD → YYYY-MM-DD（hive 分区格式）。"""
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}"


def load(rows: list[dict], date: str, ods_root=None) -> dict:
    """幂等写入。"""
    return write_parquet(
        domain=DOMAIN,
        partition_col=PARTITION_COL,
        partition_val=_format_partition(date),
        rows=rows,
        mode="overwrite",
        ods_root=ods_root,
    )


def run(date: str, source: str = SOURCE_MCP, ods_root=None) -> dict:
    """端到端：extract → transform → check → load。"""
    raw = extract(date, source)
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


# 元数据（供 catalog 注册用，init.py 引用）
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
