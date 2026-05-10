"""
Internal Data Store MCP Server — Local data management
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8002
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
import pandas as pd

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "./data"))
DB_PATH = DATA_ROOT / "cache" / "meta.db"

mcp = FastMCP(
    name="internal-store",
    version="0.1.0",
    description="Local data store MCP Server — cache query, backtest management",
)


def _init_db():
    """Initialize SQLite database if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            source      TEXT NOT NULL,
            tool_name   TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            fetched_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            row_count   INTEGER DEFAULT 0,
            PRIMARY KEY (source, tool_name, params_hash)
        );
        CREATE TABLE IF NOT EXISTS backtest_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            start_date  TEXT NOT NULL,
            end_date    TEXT NOT NULL,
            sharpe      REAL,
            max_drawdown REAL,
            annual_return REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            holdings    TEXT NOT NULL,
            cash        REAL DEFAULT 0,
            updated_at  TEXT DEFAULT (datetime('now'))
        );
    """
    )
    conn.commit()
    conn.close()


_init_db()


@mcp.tool()
def query_cache(source: str, tool_name: str, params: dict = {}) -> list[dict]:
    """
    Query local cache data. Returns cached data if not expired, otherwise returns empty with status.

    Args:
        source:    Data source name ("akshare" or "tushare").
        tool_name: MCP tool name.
        params:    Parameters dict used in original query.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

        row = conn.execute(
            "SELECT * FROM cache_entries WHERE source=? AND tool_name=? AND params_hash=?",
            (source, tool_name, params_hash),
        ).fetchone()
        conn.close()

        if not row:
            return [{"status": "cache_miss", "message": "No cache entry found"}]

        if row["expires_at"] < datetime.now().isoformat():
            return [{"status": "cache_expired", "message": "Cache entry has expired"}]

        file_path = DATA_ROOT / row["file_path"]
        if file_path.exists():
            df = pd.read_parquet(str(file_path))
            return df.to_dict(orient="records")
        return [{"status": "file_missing", "message": "Cache file not found"}]
    except Exception as e:
        return [{"error": str(e), "tool": "query_cache"}]


@mcp.tool()
def list_backtest_results(limit: int = 20) -> list[dict]:
    """
    List all backtest results.

    Args:
        limit: Maximum number of results to return.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_backtest_results"}]


@mcp.tool()
def get_portfolio(name: str = "default") -> dict:
    """
    Get current portfolio state.

    Args:
        name: Portfolio name (default: "default").
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM portfolio_state WHERE name=? ORDER BY updated_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        conn.close()
        if not row:
            return {"status": "not_found", "holdings": [], "cash": 0}
        return {
            "name": row["name"],
            "holdings": json.loads(row["holdings"]),
            "cash": row["cash"],
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        return {"error": str(e), "tool": "get_portfolio"}


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
