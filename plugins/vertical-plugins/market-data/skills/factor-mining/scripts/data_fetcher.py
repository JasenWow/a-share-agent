"""Data fetcher: connects to qlib-server via MCP to fetch OHLCV data.

Provides async functions to:
- Fetch OHLCV data via MCP qlib_get_data tool
- Pivot records to (T, N) numpy arrays
- Compute forward returns
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
