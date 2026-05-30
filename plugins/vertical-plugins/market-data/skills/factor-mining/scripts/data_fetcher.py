"""Data fetcher: fetch OHLCV data for stock pools.

Two data paths:
1. Qlib universe (e.g., csi300) via qlib-server MCP
2. Custom stock list (e.g., industry pool from stock-pool skill) via AKShare MCP

Both output aligned (T, N) numpy arrays for factor evaluation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

QLIB_SERVER_URL = "http://localhost:8003/mcp"
STORE_SERVER_URL = "http://localhost:8002/mcp"

DEFAULT_FIELDS = ["$close", "$open", "$high", "$low", "$volume", "$amount"]
POOL_FIELDS = ["$close", "$open", "$high", "$low", "$volume"]  # fields for pool-based fetching


def _records_to_arrays(
    records: list[dict],
    fields: list[str],
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    """Pivot flat records from qlib_get_data to (T, N) arrays per field.

    Args:
        records: List of dicts with keys: datetime, instrument, + field columns.
        fields: Field names to extract.

    Returns:
        (data_arrays, dates, instruments) where data_arrays maps field→ndarray(T,N).
    """
    if not records:
        raise ValueError("No data records returned from qlib-server")

    df = pd.DataFrame(records)
    # Identify index columns (qlib_get_data returns via _df_to_records which resets index)
    date_col = "datetime" if "datetime" in df.columns else "date"
    inst_col = "instrument" if "instrument" in df.columns else "instrument"

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values([date_col, inst_col])

    dates = sorted(df[date_col].unique())
    instruments = sorted(df[inst_col].unique())

    data_arrays = {}
    for field in fields:
        if field not in df.columns:
            continue
        pivot = df.pivot(index=date_col, columns=inst_col, values=field)
        pivot = pivot.reindex(index=dates, columns=instruments)
        # Convert string "NaN" back to actual NaN
        pivot = pivot.replace("NaN", np.nan).astype(float)
        data_arrays[field] = pivot.values

    return data_arrays, [str(d.date()) for d in pd.to_datetime(dates)], instruments


async def fetch_ohlcv(
    universe: str = "csi300",
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31",
    fields: list[str] | None = None,
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    """Fetch OHLCV data from qlib-server via MCP.

    Args:
        universe: Instrument pool name (e.g., "csi300", "csi500").
        start_date: Start date "YYYY-MM-DD".
        end_date: End date "YYYY-MM-DD".
        fields: Data fields to fetch.

    Returns:
        (data_arrays, dates, instruments).
    """
    if fields is None:
        fields = DEFAULT_FIELDS

    async with streamablehttp_client(QLIB_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "qlib_get_data",
                {
                    "instruments": universe,
                    "fields": fields,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

    # Extract records from MCP result
    records = _extract_records(result)
    return _records_to_arrays(records, fields)


async def init_qlib_data() -> dict:
    """Trigger qlib data download via MCP (one-time setup)."""
    async with streamablehttp_client(QLIB_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("qlib_init_data", {"source": "qlib_cn_data"})
    return _extract_records(result)


def compute_forward_returns(
    close_2d: np.ndarray,
    horizon: int = 5,
) -> np.ndarray:
    """Compute forward returns: close[t+h] / close[t] - 1.

    Args:
        close_2d: (T, N) close price array.
        horizon: Forward return horizon in periods.

    Returns:
        (T, N) forward returns array. Last `horizon` rows are NaN.
    """
    T, N = close_2d.shape
    fwd = np.full((T, N), np.nan, dtype=float)
    if T <= horizon:
        return fwd
    fwd[:T - horizon] = close_2d[horizon:] / close_2d[:T - horizon] - 1.0
    return fwd


async def fetch_pool_data(
    codes: list[str],
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    fields: list[str] | None = None,
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    """Fetch OHLCV data for a custom list of stock codes via AKShare MCP.

    Used by factor-mining when the target is a specific industry pool
    (e.g., stocks from stock-pool skill) rather than a Qlib universe.

    Args:
        codes: Stock codes like ["300124.SZ", "002472.SZ"].
        start_date: Start date "YYYY-MM-DD".
        end_date: End date "YYYY-MM-DD".
        fields: Data fields to fetch (without $ prefix internally).

    Returns:
        (data_arrays, dates, instruments) where data_arrays maps field→ndarray(T,N).
    """
    if fields is None:
        fields = POOL_FIELDS

    import asyncio
    import json

    AKSHARE_SERVER_URL = "http://localhost:8000/mcp"

    # Strip $ prefix for field names used in pivot columns
    field_names = [f.lstrip("$") for f in fields]

    all_records = []
    async with streamablehttp_client(AKSHARE_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for code in codes:
                try:
                    result = await session.call_tool(
                        "stock_zh_a_hist",
                        {
                            "symbol": code,
                            "period": "daily",
                            "start_date": start_date.replace("-", ""),
                            "end_date": end_date.replace("-", ""),
                            "adjust": "qfq",
                        },
                    )
                    records = _extract_records(result)
                    for rec in records:
                        rec["instrument"] = code
                    all_records.extend(records)
                except Exception:
                    continue

    if not all_records:
        raise ValueError(f"No data records returned for {len(codes)} stocks")

    df = pd.DataFrame(all_records)
    date_col = "日期" if "日期" in df.columns else "datetime"
    if date_col == "日期":
        df = df.rename(columns={"日期": "datetime"})
        date_col = "datetime"

    # Map AKShare column names to standard field names
    col_map = {"开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"}
    df = df.rename(columns=col_map)

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values([date_col, "instrument"])

    dates = sorted(df[date_col].unique())
    instruments = sorted(df["instrument"].unique())

    data_arrays = {}
    for fname in field_names:
        if fname not in df.columns:
            continue
        pivot = df.pivot(index=date_col, columns="instrument", values=fname)
        pivot = pivot.reindex(index=dates, columns=instruments)
        pivot = pivot.replace("NaN", np.nan)
        pivot = pd.to_numeric(pivot, errors="coerce")
        # Store with $ prefix to match template field names
        data_arrays[f"${fname}"] = pivot.values

    return data_arrays, [str(d.date()) for d in pd.to_datetime(dates)], instruments


def fetch_pool_data_sync(
    codes: list[str],
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    fields: list[str] | None = None,
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    """Synchronous wrapper for fetch_pool_data."""
    import asyncio

    return asyncio.run(fetch_pool_data(codes, start_date, end_date, fields))


def fetch_ohlcv_sync(
    universe: str = "csi300",
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31",
    fields: list[str] | None = None,
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    """Synchronous wrapper for fetch_ohlcv."""
    import asyncio

    return asyncio.run(fetch_ohlcv(universe, start_date, end_date, fields))


async def register_factor_via_mcp(params: dict) -> dict:
    """Register a factor to internal-store via MCP."""
    async with streamablehttp_client(STORE_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("register_factor", params)
    records = _extract_records(result)
    return records[0] if records else {}


def _extract_records(result: Any) -> list[dict]:
    """Extract record dicts from MCP CallToolResult."""
    import json

    records = []
    for content in result.content:
        if hasattr(content, "text"):
            data = json.loads(content.text)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
    return records
