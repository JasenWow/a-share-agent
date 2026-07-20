"""ETL metadata field injection: stamp ODS records with provenance.

Five metadata fields (prefix __ to avoid colliding with business fields):
- __source:        data source (tushare / akshare)
- __source_tool:   MCP tool name (daily / stock_zh_a_hist / direct_sdk)
- __fetched_at:    fetch time, ISO8601 with timezone
- __params_hash:   sha256 of MCP call params (computed via aquan.utils.hashing)
- __etl_run_id:    ETL run instance id
"""

from __future__ import annotations


def inject(
    source: str,
    source_tool: str,
    fetched_at: str,
    params_hash: str,
    etl_run_id: str,
) -> dict[str, str]:
    """Return the five metadata fields as a dict, to merge into business records."""
    return {
        "__source": source,
        "__source_tool": source_tool,
        "__fetched_at": fetched_at,
        "__params_hash": params_hash,
        "__etl_run_id": etl_run_id,
    }
