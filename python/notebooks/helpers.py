"""Notebook helper functions for MCP data access."""

import json
import urllib.request
import urllib.error
from typing import Optional

INTERNAL_STORE_URL = "http://localhost:8002"


def get_internal_store_url() -> str:
    """Returns the internal-store MCP base URL."""
    return INTERNAL_STORE_URL


def query_mcp(tool_name: str, params: Optional[dict] = None) -> list[dict]:
    """Generic MCP tool call via HTTP POST to internal-store."""
    payload = json.dumps({"tool": tool_name, "arguments": params or {}}).encode("utf-8")

    req = urllib.request.Request(
        f"{INTERNAL_STORE_URL}/mcp", data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot connect to internal-store at {INTERNAL_STORE_URL}: {e}") from e
    except Exception as e:
        raise ConnectionError(f"MCP call failed: {e}") from e


def get_experiments(limit: int = 100):
    """Fetch experiments from internal-store."""
    import pandas as pd

    result = query_mcp("list_experiments", {"limit": limit})
    if not result:
        return pd.DataFrame()
    rows = []
    for row in result:
        r = dict(row)
        for field in ["strategy", "params", "result"]:
            if field in r and isinstance(r[field], str):
                try:
                    r[field] = json.loads(r[field])
                except Exception:
                    pass
        rows.append(r)
    return pd.DataFrame(rows)


def get_best_strategies(top_k: int = 10):
    """Fetch top strategies by final_nav."""
    import pandas as pd

    result = query_mcp("get_best_strategies", {"top_k": top_k})
    if not result:
        return pd.DataFrame()
    rows = []
    for row in result:
        r = dict(row)
        if "strategy" in r and isinstance(r["strategy"], str):
            try:
                r["strategy"] = json.loads(r["strategy"])
            except Exception:
                pass
        rows.append(r)
    return pd.DataFrame(rows)


def get_backtest_results(limit: int = 20):
    """Fetch backtest results."""
    import pandas as pd

    result = query_mcp("list_backtest_results", {"limit": limit})
    if not result:
        return pd.DataFrame()
    return pd.DataFrame(result)


def get_portfolio(name: str = "default") -> dict:
    """Fetch current portfolio state."""
    result = query_mcp("get_portfolio", {"name": name})
    if not result:
        return {}
    return result[0] if result else {}


def get_episode_summaries():
    """Fetch episode summaries."""
    import pandas as pd

    result = query_mcp("list_episode_summaries")
    if not result:
        return pd.DataFrame()
    return pd.DataFrame(result)
