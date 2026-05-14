"""
AKShare MCP Server — A-share data connector
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8000
"""

from mcp.server.fastmcp import FastMCP
import akshare as ak
import pandas as pd
import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
import json
from datetime import datetime, timedelta

mcp = FastMCP(
    name="akshare-a-share",
    instructions="A-share data MCP Server based on AKShare. Version 0.1.0",
)


def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    """Convert DataFrame to JSON-serializable dict list, truncating oversized results."""
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")


def _code_to_tencent_prefix(code: str) -> str:
    """Map 6-digit stock code to Tencent market prefix."""
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith("6"):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


def _tencent_spot(codes: list[str]) -> list[dict]:
    """
    Fetch A-share realtime quotes from Tencent API as fallback when Eastmoney fails.
    codes: list of 6-digit stock codes (e.g., ["000001", "600519"]).
    """
    tencent_codes = [f"{_code_to_tencent_prefix(c)}{c}" for c in codes]
    url = f"https://qt.gtimg.cn/q={','.join(tencent_codes)}"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"Tencent spot API request failed: {e}", "tool": "stock_zh_a_spot"}]

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

        code = parts[2]
        try:
            latest = float(parts[3]) if parts[3] else "NaN"
            prev_close = float(parts[4]) if parts[4] else "NaN"
            open_price = float(parts[5]) if parts[5] else "NaN"
            high = float(parts[33]) if parts[33] else "NaN"
            low = float(parts[34]) if parts[34] else "NaN"
            change_pct = float(parts[32]) if parts[32] else "NaN"
            change_amt = float(parts[31]) if parts[31] else "NaN"
            volume = float(parts[6]) if parts[6] else "NaN"  # 手
            amount = float(parts[37]) if parts[37] else "NaN"  # 万
            turnover = float(parts[38]) if parts[38] else "NaN"
            pe = float(parts[39]) if parts[39] else "NaN"
            amplitude = round((high - low) / prev_close * 100, 2) if isinstance(prev_close, float) and prev_close > 0 else "NaN"
        except (ValueError, TypeError):
            continue

        results.append({
            "代码": code,
            "名称": parts[1],
            "最新价": latest,
            "涨跌幅": change_pct,
            "涨跌额": change_amt,
            "今开": open_price,
            "昨收": prev_close,
            "最高": high,
            "最低": low,
            "成交量": volume,
            "成交额": amount,
            "振幅": amplitude,
            "换手率": turnover,
            "市盈率": pe,
        })

    return results


def _tencent_fallback(symbol: str, start_date: str, end_date: str, limit: int = 320) -> list[dict]:
    """
    Fetch A-share OHLCV from Tencent API as fallback when Eastmoney fails.
    symbol: 6-digit stock code, possibly with .SZ/.SH suffix (e.g., "001309.SZ")
    start_date: "YYYYMMDD"
    end_date: "YYYYMMDD"
    limit: number of days to fetch (default 320)
    """
    # Strip .SZ or .SH suffix if present
    clean_symbol = symbol.replace(".SZ", "").replace(".SH", "")

    if clean_symbol.startswith(("0", "3")):
        market = "sz"
    elif clean_symbol.startswith("6"):
        market = "sh"
    else:
        return [{"error": f"Unsupported symbol prefix for Tencent API: {clean_symbol}"}]

    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={market}{clean_symbol},day,,,{limit},qfq"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"Tencent API request failed: {e}"}]

    text = resp.text
    if text.startswith("kline_dayqfq="):
        text = text[len("kline_dayqfq="):]
    else:
        return [{"error": "Unexpected Tencent response format"}]

    try:
        data = json.loads(text)
    except Exception as e:
        return [{"error": f"Failed to parse Tencent JSON: {e}"}]

    key = f"{market}{clean_symbol}"
    if key not in data.get("data", {}):
        return [{"error": f"Key '{key}' not found in Tencent response"}]

    qfqday = data["data"][key].get("qfqday", [])
    if not qfqday:
        return []

    # qfqday is a list of [date, open, close, high, low, volume]
    results = []
    for row in qfqday:
        if len(row) < 6:
            continue
        date_str = row[0]
        # Filter by date range
        date_cmp = date_str.replace("-", "")
        if start_date and date_cmp < start_date:
            continue
        if end_date and date_cmp > end_date:
            continue

        # Convert volume from shares to 万股 (ten thousand shares)
        try:
            volume_shares = float(row[5])
            volume_wan = volume_shares / 10000.0
        except (ValueError, TypeError):
            volume_wan = "NaN"

        results.append({
            "日期": date_str,
            "股票代码": clean_symbol,
            "开盘": float(row[1]) if row[1] not in ("None", None) else "NaN",
            "收盘": float(row[2]) if row[2] not in ("None", None) else "NaN",
            "最高": float(row[3]) if row[3] not in ("None", None) else "NaN",
            "最低": float(row[4]) if row[4] not in ("None", None) else "NaN",
            "成交量": volume_wan,
            "成交额": "NaN",
            "振幅": "NaN",
            "涨跌幅": "NaN",
            "涨跌额": "NaN",
            "换手率": "NaN",
        })

    return results


@mcp.tool()
def stock_zh_a_spot(symbol: str | None = None) -> list[dict]:
    """
    Get A-share realtime quote snapshot.
    Optionally filter by stock code. Returns all A-shares with latest price, change %, volume, etc.

    Args:
        symbol: Optional 6-digit stock code to filter (e.g., "000001").
    """
    try:
        df = ak.stock_zh_a_spot_em()
        if symbol:
            df = df[df["代码"] == symbol]
        return df_to_json(df, max_rows=10000)
    except Exception as e:
        if isinstance(e, (RequestsConnectionError, requests.exceptions.ProxyError)):
            if symbol:
                return _tencent_spot([symbol])
            return [{"error": "Eastmoney unavailable and no symbol specified. Tencent fallback requires a specific stock code.", "tool": "stock_zh_a_spot", "hint": "Call again with symbol parameter, e.g. stock_zh_a_spot(symbol='000001')"}]
        return [{"error": str(e), "tool": "stock_zh_a_spot", "symbol": symbol}]


@mcp.tool()
def stock_zh_a_hist(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> list[dict]:
    """
    Get historical OHLCV data for a single A-share stock.

    Args:
        symbol:     6-digit stock code (e.g., "000001").
        period:     "daily" / "weekly" / "monthly".
        start_date: Start date "YYYYMMDD", defaults to 1 year ago.
        end_date:   End date "YYYYMMDD", defaults to today.
        adjust:     "qfq" (forward-adjusted) / "hfq" (backward) / "" (none).
    """
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        return df_to_json(df)
    except Exception as e:
        if isinstance(e, (RequestsConnectionError, requests.exceptions.ProxyError)):
            return _tencent_fallback(symbol=symbol, start_date=start_date, end_date=end_date)
        return [{"error": str(e), "tool": "stock_zh_a_hist", "symbol": symbol}]


@mcp.tool()
def stock_financial_abstract(symbol: str, indicator: str = "按年度") -> list[dict]:
    """
    Get financial abstract (THS source) for a stock.

    Args:
        symbol:    6-digit stock code (e.g., "000001").
        indicator: "按年度" / "按单季度".
    """
    try:
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator=indicator)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_financial_abstract", "symbol": symbol}]


@mcp.tool()
def stock_financial_report_sina(
    stock: str,
    symbol: str = "利润表",
    type: str = "年报",
) -> list[dict]:
    """
    Get detailed financial statements from Sina Finance.

    Args:
        stock:  Stock code with prefix "sh600000" or "sz000001".
        symbol: Statement type "利润表" / "资产负债表" / "现金流量表".
        type:   Report type "年报" / "中报" / "一季报" / "三季报".
    """
    try:
        df = ak.stock_financial_report_sina(stock=stock, symbol=symbol)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_financial_report_sina", "stock": stock}]


@mcp.tool()
def stock_rank_cxg_thsh(indicator: str = "成分股") -> list[dict]:
    """
    Get Shenwan industry classification constituent stocks.
    """
    try:
        df = ak.stock_rank_cxg_thsh(indicator=indicator)
        return df_to_json(df, max_rows=5000)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_rank_cxg_thsh"}]


@mcp.tool()
def stock_hsgt_north_net_flow_in_em() -> list[dict]:
    """
    Get northbound capital (沪港通/深港通) net flow history.
    Returns date, net buy amount, cumulative net buy, etc.
    """
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(indicator="北上")
        return df_to_json(df, max_rows=10000)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_hsgt_north_net_flow_in_em"}]


@mcp.tool()
def stock_lhb_detail_em(
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Get dragon-tiger list (龙虎榜) detail data from East Money.

    Args:
        start_date: Start date "YYYYMMDD".
        end_date:   End date "YYYYMMDD".
    """
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_lhb_detail_em", "start_date": start_date}]


@mcp.tool()
def index_stock_cons(symbol: str = "000300") -> list[dict]:
    """
    Get index constituent stock list.

    Args:
        symbol: Index code (e.g., "000300" for 沪深300, "000905" for 中证500).
    """
    try:
        df = ak.index_stock_cons_csindex(symbol=symbol)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "index_stock_cons", "symbol": symbol}]


@mcp.tool()
def stock_zh_index_daily(
    symbol: str = "sh000300",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Get index daily OHLCV data.

    Args:
        symbol:     Index code with prefix "sh"/"sz" (e.g., "sh000300").
        start_date: Start date "YYYYMMDD".
        end_date:   End date "YYYYMMDD".
    """
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
        return [{"error": str(e), "tool": "stock_zh_index_daily", "symbol": symbol}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)
