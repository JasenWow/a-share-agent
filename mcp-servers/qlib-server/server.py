"""
Qlib MCP Server — Data engine for factor expression evaluation.
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8003
"""

import os
import subprocess
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "./data"))
QLIB_DATA_DIR = DATA_ROOT / "qlib"

mcp = FastMCP(
    name="qlib-server",
    instructions="Qlib data engine MCP Server — factor expression evaluation, operator catalog. Version 0.1.0",
)

_QLIB_INITIALIZED = False


def _ensure_qlib_init():
    """Initialize Qlib with the configured data directory."""
    global _QLIB_INITIALIZED
    if _QLIB_INITIALIZED:
        return
    import qlib

    if not QLIB_DATA_DIR.exists():
        raise FileNotFoundError(f"Qlib data not found at {QLIB_DATA_DIR}. Run qlib_init_data first.")
    qlib.init(provider_uri=str(QLIB_DATA_DIR), region="cn")
    _QLIB_INITIALIZED = True


def _df_to_records(df: pd.DataFrame, max_rows: int = 10000) -> list[dict]:
    """Convert DataFrame to JSON-serializable record list, truncating oversized results."""
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.reset_index().fillna("NaN").to_dict(orient="records")


# ---------------------------------------------------------------------------
# Tool 1: qlib_init_data
# ---------------------------------------------------------------------------


@mcp.tool()
def qlib_init_data(source: str = "qlib_cn_data") -> dict:
    """
    Download and initialize Qlib CN stock data.

    Args:
        source: Data source identifier. Only "qlib_cn_data" is supported.
    """
    try:
        QLIB_DATA_DIR.mkdir(parents=True, exist_ok=True)

        if source == "qlib_cn_data":
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "qlib.run.get_data",
                    "--qlib-dir",
                    str(QLIB_DATA_DIR),
                    "--region",
                    "cn",
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"Data download failed: {result.stderr[:500]}"}
        else:
            return {"status": "error", "message": f"Unsupported source: {source}. Use 'qlib_cn_data'."}

        return {"status": "ok", "data_dir": str(QLIB_DATA_DIR)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Tool 2: qlib_get_data
# ---------------------------------------------------------------------------


@mcp.tool()
def qlib_get_data(
    instruments: str = "all",
    fields: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Get feature data from Qlib for specified instruments and fields.

    Args:
        instruments: Instrument pool name (e.g., "all", "csi300", "csi500").
        fields:      Feature fields to fetch. Defaults to OHLCV + amount.
        start_date:  Start date "YYYY-MM-DD".
        end_date:    End date "YYYY-MM-DD".
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        if fields is None:
            fields = ["$close", "$open", "$high", "$low", "$volume", "$amount"]

        df = D.features(instruments, fields, start_time=start_date or None, end_time=end_date or None)
        return _df_to_records(df)
    except Exception as e:
        return [{"error": str(e), "tool": "qlib_get_data"}]


# ---------------------------------------------------------------------------
# Tool 3: qlib_eval_expression
# ---------------------------------------------------------------------------


@mcp.tool()
def qlib_eval_expression(
    expression: str,
    instruments: str = "csi300",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Evaluate a Qlib factor expression over a universe of stocks.

    Args:
        expression: Qlib expression string (e.g., "Ts_Mean($close, 5) / $close").
        instruments: Instrument pool name (e.g., "csi300", "csi500", "all").
        start_date:  Start date "YYYY-MM-DD".
        end_date:    End date "YYYY-MM-DD".
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        df = D.features(instruments, [expression], start_time=start_date or None, end_time=end_date or None)
        return _df_to_records(df)
    except Exception as e:
        return [{"error": str(e), "tool": "qlib_eval_expression"}]


# ---------------------------------------------------------------------------
# Tool 4: qlib_list_operators
# ---------------------------------------------------------------------------

_OPERATORS = [
    # Time-series operators
    {"name": "Ts_Mean", "signature": "Ts_Mean(x, d)", "category": "time-series", "description": "Rolling mean over past d periods."},
    {"name": "Ts_Std", "signature": "Ts_Std(x, d)", "category": "time-series", "description": "Rolling standard deviation over past d periods."},
    {"name": "Ts_Max", "signature": "Ts_Max(x, d)", "category": "time-series", "description": "Rolling maximum over past d periods."},
    {"name": "Ts_Min", "signature": "Ts_Min(x, d)", "category": "time-series", "description": "Rolling minimum over past d periods."},
    {"name": "Ts_Rank", "signature": "Ts_Rank(x, d)", "category": "time-series", "description": "Percentile rank of current value in past d periods."},
    {"name": "Ts_Sum", "signature": "Ts_Sum(x, d)", "category": "time-series", "description": "Rolling sum over past d periods."},
    {"name": "Ts_Prod", "signature": "Ts_Prod(x, d)", "category": "time-series", "description": "Rolling product over past d periods."},
    {"name": "Ts_Corr", "signature": "Ts_Corr(x, y, d)", "category": "time-series", "description": "Rolling Pearson correlation between x and y over past d periods."},
    {"name": "Ts_Covariance", "signature": "Ts_Covariance(x, y, d)", "category": "time-series", "description": "Rolling covariance between x and y over past d periods."},
    {"name": "Delta", "signature": "Delta(x, d)", "category": "time-series", "description": "x - Ref(x, d). Difference from d periods ago."},
    {"name": "Pct_Change", "signature": "Pct_Change(x, d)", "category": "time-series", "description": "Percentage change: (x - Ref(x, d)) / Ref(x, d)."},
    # Cross-section operators
    {"name": "Rank", "signature": "Rank(x)", "category": "cross-section", "description": "Cross-sectional rank (percentile) of x across all instruments."},
    {"name": "ZScore", "signature": "ZScore(x)", "category": "cross-section", "description": "Cross-sectional z-score: (x - mean) / std across instruments."},
    {"name": "Demean", "signature": "Demean(x)", "category": "cross-section", "description": "Cross-sectional de-mean: x - mean(x) across instruments."},
    {"name": "Scale", "signature": "Scale(x)", "category": "cross-section", "description": "Scale x so that sum of absolute values equals 1."},
    {"name": "Sign", "signature": "Sign(x)", "category": "cross-section", "description": "Sign of x: 1 if positive, -1 if negative, 0 otherwise."},
    # Arithmetic operators
    {"name": "Add", "signature": "Add(x, y)", "category": "arithmetic", "description": "Element-wise addition: x + y."},
    {"name": "Sub", "signature": "Sub(x, y)", "category": "arithmetic", "description": "Element-wise subtraction: x - y."},
    {"name": "Mul", "signature": "Mul(x, y)", "category": "arithmetic", "description": "Element-wise multiplication: x * y."},
    {"name": "Div", "signature": "Div(x, y)", "category": "arithmetic", "description": "Element-wise division: x / y."},
    {"name": "Abs", "signature": "Abs(x)", "category": "arithmetic", "description": "Absolute value of x."},
    {"name": "Log", "signature": "Log(x)", "category": "arithmetic", "description": "Natural logarithm of x."},
    {"name": "Exp", "signature": "Exp(x)", "category": "arithmetic", "description": "Exponential of x: e^x."},
    {"name": "Max", "signature": "Max(x, y)", "category": "arithmetic", "description": "Element-wise maximum of x and y."},
    {"name": "Min", "signature": "Min(x, y)", "category": "arithmetic", "description": "Element-wise minimum of x and y."},
    {"name": "Sqrt", "signature": "Sqrt(x)", "category": "arithmetic", "description": "Square root of x."},
    # Conditional operators
    {"name": "If_Else", "signature": "If(cond, x, y)", "category": "conditional", "description": "Return x if cond is true, otherwise y."},
    {"name": "Clamp", "signature": "Clamp(x, lower, upper)", "category": "conditional", "description": "Clip x to [lower, upper] range."},
]


@mcp.tool()
def qlib_list_operators() -> list[dict]:
    """List all available Qlib operators with name, signature, category, and description."""
    return _OPERATORS


# ---------------------------------------------------------------------------
# Tool 5: qlib_get_universe
# ---------------------------------------------------------------------------


@mcp.tool()
def qlib_get_universe(name: str = "csi300") -> list[dict]:
    """
    Get instrument list for a given universe.

    Args:
        name: Universe name (e.g., "csi300", "csi500", "all").
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        instruments = D.instruments(name)
        stock_list = D.list_instruments(instruments=instruments, start_time=None, end_time=None)
        return [{"instrument": s} for s in stock_list]
    except Exception as e:
        return [{"error": str(e), "tool": "qlib_get_universe"}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8003)
