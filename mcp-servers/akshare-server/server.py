"""
AKShare MCP Server — A-share data connector
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8000

Data source status (2026-05-30):
  ✅ Tencent API   — primary: realtime spot + daily OHLCV (qfq)
  ❌ East Money     — unreachable from current network (all push2 subdomains)
  ⚠️ CSIndex       — index constituent lists (may be slow)
  ❌ THS            — concept constituent lists blocked (401); name list too slow (39 pages)
"""

from mcp.server.fastmcp import FastMCP
import akshare as ak
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

mcp = FastMCP(
    name="akshare-a-share",
    instructions="A-share data MCP Server. v0.3.0. Primary: Tencent API. East Money degraded.",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")


def _market_prefix(code: str) -> str:
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith("6"):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


def _clean_symbol(symbol: str) -> str:
    return symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")


# ---------------------------------------------------------------------------
# Tencent API — primary data source
# ---------------------------------------------------------------------------


def _tencent_spot(codes: list[str]) -> list[dict]:
    """Batch realtime quotes from Tencent."""
    tc = [f"{_market_prefix(c)}{c}" for c in codes]
    url = f"https://qt.gtimg.cn/q={','.join(tc)}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"Tencent spot failed: {e}"}]

    results = []
    for line in resp.text.strip().split(";"):
        line = line.strip()
        if not line or '="' not in line:
            continue
        val = line.split('="')[1].rstrip('"')
        if not val:
            continue
        parts = val.split("~")
        if len(parts) < 48:
            continue
        try:
            latest = float(parts[3]) if parts[3] else "NaN"
            prev_close = float(parts[4]) if parts[4] else "NaN"
            open_ = float(parts[5]) if parts[5] else "NaN"
            high = float(parts[33]) if parts[33] else "NaN"
            low = float(parts[34]) if parts[34] else "NaN"
            change_pct = float(parts[32]) if parts[32] else "NaN"
            change_amt = float(parts[31]) if parts[31] else "NaN"
            volume = float(parts[6]) if parts[6] else "NaN"
            amount = float(parts[37]) if parts[37] else "NaN"
            turnover = float(parts[38]) if parts[38] else "NaN"
            pe = float(parts[39]) if parts[39] else "NaN"
            amplitude = (
                round((high - low) / prev_close * 100, 2)
                if isinstance(prev_close, float) and prev_close > 0
                else "NaN"
            )
        except (ValueError, TypeError):
            continue
        results.append({
            "代码": parts[2], "名称": parts[1],
            "最新价": latest, "涨跌幅": change_pct, "涨跌额": change_amt,
            "今开": open_, "昨收": prev_close, "最高": high, "最低": low,
            "成交量": volume, "成交额": amount,
            "振幅": amplitude, "换手率": turnover, "市盈率": pe,
        })
    return results


def _tencent_hist(symbol: str, start_date: str = "", end_date: str = "", limit: int = 800) -> list[dict]:
    """Daily OHLCV (前复权) from Tencent."""
    clean = _clean_symbol(symbol)
    market = _market_prefix(clean)
    if market == "bj" and clean.startswith("8"):
        # Tencent uses sse prefix for BJ stocks sometimes; try both
        pass

    url = (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?_var=kline_dayqfq&param={market}{clean},day,,,{limit},qfq"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"Tencent hist failed: {e}"}]

    text = resp.text
    prefix = "kline_dayqfq="
    if text.startswith(prefix):
        text = text[len(prefix):]
    else:
        return [{"error": "Unexpected Tencent response format"}]

    try:
        data = json.loads(text)
    except Exception as e:
        return [{"error": f"Parse Tencent JSON failed: {e}"}]

    key = f"{market}{clean}"
    stock_data = data.get("data", {}).get(key, {})
    day_key = "qfqday" if "qfqday" in stock_data else "day"
    rows = stock_data.get(day_key, [])
    if not rows:
        return []

    results = []
    for row in rows:
        if len(row) < 6:
            continue
        date_str = row[0]
        date_cmp = date_str.replace("-", "")
        if start_date and date_cmp < start_date:
            continue
        if end_date and date_cmp > end_date:
            continue
        try:
            vol = float(row[5]) / 10000.0
        except (ValueError, TypeError):
            vol = "NaN"
        results.append({
            "日期": date_str,
            "股票代码": clean,
            "开盘": float(row[1]) if row[1] not in ("None", None) else "NaN",
            "收盘": float(row[2]) if row[2] not in ("None", None) else "NaN",
            "最高": float(row[3]) if row[3] not in ("None", None) else "NaN",
            "最低": float(row[4]) if row[4] not in ("None", None) else "NaN",
            "成交量": vol,
            "成交额": "NaN",
            "振幅": "NaN",
            "涨跌幅": "NaN",
            "涨跌额": "NaN",
            "换手率": "NaN",
        })
    return results


# ---------------------------------------------------------------------------
# Concept pools — curated fallback (THS/East Money concept APIs unreliable)
# ---------------------------------------------------------------------------

_CONCEPT_POOL: dict[str, list[tuple[str, str]]] = {
    "机器人": [
        ("300024", "机器人"),   ("300124", "汇川技术"), ("002747", "埃斯顿"),
        ("300503", "昊志机电"), ("002527", "新时达"),   ("300709", "精研科技"),
        ("603728", "鸣志电器"), ("603901", "永创智能"), ("002008", "大族激光"),
        ("300316", "晶盛机电"), ("688169", "石头科技"), ("300457", "赢合科技"),
        ("002611", "东方精工"), ("300496", "中科创达"), ("300602", "飞荣达"),
        ("300699", "光威复材"), ("002049", "紫光国微"), ("300223", "北京君正"),
        ("300073", "当升科技"), ("300308", "中际旭创"), ("300782", "卓胜微"),
        ("688015", "交控科技"), ("002371", "北方华创"), ("300155", "安居宝"),
        ("300370", "安控科技"), ("300502", "新易盛"),   ("300476", "胜宏科技"),
        ("300413", "芒果超媒"),
    ],
}


# ---------------------------------------------------------------------------
# MCP Tools — primary
# ---------------------------------------------------------------------------


@mcp.tool()
def data_source_health() -> list[dict]:
    """Check which data sources are currently reachable."""
    import concurrent.futures

    def _check(name: str, url: str) -> dict:
        try:
            r = requests.get(url, timeout=3)
            return {"source": name, "status": "✅ online" if r.status_code == 200 else f"⚠️ HTTP {r.status_code}"}
        except Exception:
            return {"source": name, "status": "❌ unreachable"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(_check, "Tencent API", "https://qt.gtimg.cn/q=sh600519"),
            pool.submit(_check, "East Money API", "http://push2his.eastmoney.com/"),
        ]
        return [f.result() for f in futs]


@mcp.tool()
def stock_zh_a_spot(symbol: str | None = None) -> list[dict]:
    """
    Get A-share realtime quote snapshot (Tencent API).
    Args:
        symbol: 6-digit stock code (e.g., "000001"). If omitted, returns error (full scan unavailable).
    """
    if symbol:
        return _tencent_spot([symbol])
    try:
        df = ak.stock_zh_a_spot_em()
        return df_to_json(df, max_rows=10000)
    except Exception:
        return [{"error": "Full spot list unavailable. Provide symbol= for Tencent fallback."}]


@mcp.tool()
def stock_zh_a_hist(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> list[dict]:
    """
    Get historical OHLCV for a single A-share stock. Primary: Tencent; fallback: East Money.
    Args:
        symbol:     6-digit stock code (e.g., "000001").
        start_date: "YYYYMMDD", defaults to ~1 year ago.
        end_date:   "YYYYMMDD", defaults to today.
    """
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    # Tencent primary
    result = _tencent_hist(symbol, start_date, end_date)
    if result and not (len(result) == 1 and "error" in result[0]):
        return result

    # East Money fallback (threaded to avoid blocking)
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            df = ex.submit(
                ak.stock_zh_a_hist,
                symbol=symbol, period=period,
                start_date=start_date, end_date=end_date, adjust=adjust,
            ).result(timeout=10)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_zh_a_hist", "symbol": symbol}]


@mcp.tool()
def stock_board_concept_cons(symbol: str = "人工智能") -> list[dict]:
    """
    Get concept board constituent stock list. Tries: 1) curated pool 2) East Money.
    Args:
        symbol: Concept name (e.g., "机器人", "人工智能", "新能源", "芯片").
    """
    # Curated fallback first (instant, reliable)
    pool = _CONCEPT_POOL.get(symbol, [])
    if pool:
        return [{"代码": code, "名称": name} for code, name in pool]

    # East Money (may be down or slow, use thread timeout)
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            df = ex.submit(ak.stock_board_concept_cons_em, symbol=symbol).result(timeout=8)
        if df is not None and not df.empty:
            return df_to_json(df, max_rows=2000)
    except Exception:
        pass

    return [{"error": f"Concept '{symbol}' not available. Available: {list(_CONCEPT_POOL.keys())}",
             "tool": "stock_board_concept_cons"}]


@mcp.tool()
def index_stock_cons(symbol: str = "000300") -> list[dict]:
    """
    Get index constituent stock list (CSIndex).
    Args:
        symbol: "000300" (沪深300), "000905" (中证500), etc.
    """
    try:
        df = ak.index_stock_cons_csindex(symbol=symbol)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "index_stock_cons", "symbol": symbol}]


# ---------------------------------------------------------------------------
# Degraded tools (East Money / THS dependent — may return errors)
# ---------------------------------------------------------------------------


@mcp.tool()
def stock_financial_abstract(symbol: str, indicator: str = "按年度") -> list[dict]:
    """[DEGRADED] Financial abstract from THS."""
    try:
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator=indicator)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_financial_abstract"}]


@mcp.tool()
def stock_financial_report_sina(stock: str, symbol: str = "利润表") -> list[dict]:
    """[DEGRADED] Financial statements from Sina."""
    try:
        df = ak.stock_financial_report_sina(stock=stock, symbol=symbol)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_financial_report_sina"}]


@mcp.tool()
def stock_hsgt_north_net_flow_in_em() -> list[dict]:
    """[DEGRADED — East Money] Northbound capital net flow."""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(indicator="北上")
        return df_to_json(df, max_rows=10000)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_hsgt_north_net_flow_in_em"}]


@mcp.tool()
def stock_lhb_detail_em(start_date: str = "", end_date: str = "") -> list[dict]:
    """[DEGRADED — East Money] Dragon-tiger list."""
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_lhb_detail_em"}]


@mcp.tool()
def stock_zh_index_daily(symbol: str = "sh000300", start_date: str = "", end_date: str = "") -> list[dict]:
    """[DEGRADED] Index daily OHLCV."""
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zh_index_daily(symbol=symbol)
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_zh_index_daily"}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)
