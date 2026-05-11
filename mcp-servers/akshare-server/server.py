"""
AKShare MCP Server — A-share data connector
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8000
"""

from mcp.server.fastmcp import FastMCP
import akshare as ak
import pandas as pd
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
