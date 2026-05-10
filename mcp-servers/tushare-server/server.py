"""
Tushare MCP Server — A-share high-quality data connector
Run: TUSHARE_TOKEN=xxx uvicorn server:mcp_app --host 0.0.0.0 --port 8001
"""

import os

from mcp.server.fastmcp import FastMCP
import tushare as ts
import pandas as pd

TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
if not TUSHARE_TOKEN:
    raise ValueError("TUSHARE_TOKEN environment variable not set")

pro = ts.pro_api(TUSHARE_TOKEN)

mcp = FastMCP(
    name="tushare-a-share",
    version="0.1.0",
    description="A-share high-quality data MCP Server based on Tushare Pro",
)


def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    """Convert DataFrame to JSON-serializable dict list."""
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")


@mcp.tool()
def daily(
    ts_code: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 5000,
) -> list[dict]:
    """
    Get A-share daily OHLCV data.

    Args:
        ts_code:    Stock code with suffix "000001.SZ". Empty returns all market.
        start_date: Start date "YYYYMMDD".
        end_date:   End date "YYYYMMDD".
    """
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date, limit=limit)
        return df_to_json(df, max_rows=limit)
    except Exception as e:
        return [{"error": str(e), "tool": "daily", "ts_code": ts_code}]


@mcp.tool()
def income(
    ts_code: str,
    period: str = "",
    report_type: int = 1,
) -> list[dict]:
    """
    Get income statement data.

    Args:
        ts_code:      Stock code "000001.SZ".
        period:       Report period "20240331".
        report_type:  1=consolidated 2=single quarter.
    """
    try:
        df = pro.income(ts_code=ts_code, period=period, report_type=report_type)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "income", "ts_code": ts_code}]


@mcp.tool()
def balancesheet(ts_code: str, period: str = "") -> list[dict]:
    """
    Get balance sheet data.

    Args:
        ts_code: Stock code "000001.SZ".
        period:  Report period "20240331".
    """
    try:
        df = pro.balancesheet(ts_code=ts_code, period=period)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "balancesheet", "ts_code": ts_code}]


@mcp.tool()
def cashflow(ts_code: str, period: str = "") -> list[dict]:
    """
    Get cash flow statement data.

    Args:
        ts_code: Stock code "000001.SZ".
        period:  Report period "20240331".
    """
    try:
        df = pro.cashflow(ts_code=ts_code, period=period)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "cashflow", "ts_code": ts_code}]


@mcp.tool()
def fina_indicator(ts_code: str, period: str = "") -> list[dict]:
    """
    Get financial indicators (ROE, gross margin, net margin, etc.).

    Args:
        ts_code: Stock code "000001.SZ".
        period:  Report period "20240331".
    """
    try:
        df = pro.fina_indicator(ts_code=ts_code, period=period)
        return df_to_json(df, max_rows=2000)
    except Exception as e:
        return [{"error": str(e), "tool": "fina_indicator", "ts_code": ts_code}]


@mcp.tool()
def index_weight(
    index_code: str = "399300.SZ",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Get index constituent weights (point-in-time, avoiding look-ahead bias).

    Args:
        index_code: Index code "399300.SZ" (沪深300).
        start_date: Start date "YYYYMMDD".
        end_date:   End date "YYYYMMDD".
    """
    try:
        df = pro.index_weight(index_code=index_code, start_date=start_date, end_date=end_date)
        return df_to_json(df, max_rows=10000)
    except Exception as e:
        return [{"error": str(e), "tool": "index_weight", "index_code": index_code}]


@mcp.tool()
def concept_detail(id: str = "") -> list[dict]:
    """
    Get concept sector constituent stocks.

    Args:
        id: Concept code (empty returns all concept list).
    """
    try:
        df = pro.concept_detail(id=id)
        return df_to_json(df, max_rows=5000)
    except Exception as e:
        return [{"error": str(e), "tool": "concept_detail", "id": id}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8001)
