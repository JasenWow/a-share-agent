# MCP Server Development

> How to build, test, and extend MCP servers in this project. Covers FastMCP patterns, tool definition, error handling, caching, and the process for adding new tools or servers.

## Framework

All MCP servers use **FastMCP** from the `mcp` Python package:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="server-name",
    version="0.1.0",
    description="What this server provides",
)
```

Each server exposes an ASGI app via `mcp.streamable_http_app()` and runs behind `uvicorn`.

## Tool Definition Pattern

Every data endpoint becomes a decorated function. Follow this template:

```python
@mcp.tool()
def tool_name(param1: str, param2: str = "default_value") -> list[dict]:
    """
    One-line description of what this tool returns.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to "default_value".
    """
    try:
        df = external_api_call(param1, param2)
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "tool_name", "params": {"param1": param1}}]
```

Key rules:

1. **One `@mcp.tool()` per external API function** — don't multiplex multiple APIs in one tool.
2. **Docstring is mandatory** — it becomes the tool description exposed to agents.
3. **Type hints on all parameters** — agents need to know parameter types.
4. **Default values for optional parameters** — agents should be able to call with minimal args.
5. **Return `list[dict]`** — use `df_to_json()` to convert DataFrames consistently.
6. **Never raise unhandled exceptions** — catch and return error dicts. An unhandled exception crashes the MCP protocol.

## DataFrame-to-JSON Helper

All servers share this helper pattern:

```python
import pandas as pd

def df_to_json(df: pd.DataFrame, max_rows: int = 5000) -> list[dict]:
    """Convert DataFrame to JSON-serializable dict list."""
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.fillna("NaN").to_dict(orient="records")
```

Rules:
- **`max_rows` is mandatory** — prevent memory issues with large result sets.
- **NaN → "NaN" string** — JSON has no NaN literal; use the string representation.
- **Empty DataFrame → empty list** — never return `None` from a tool.

## Server Directory Structure

```
mcp-servers/<name>/
├── server.py          # FastMCP tool definitions (required)
├── pyproject.toml     # Python dependencies (required)
├── test_server.py     # Co-located tests (required)
└── README.md          # Tool documentation (required)
```

### pyproject.toml Template

```toml
[project]
name = "<name>-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0",
    "pandas>=2.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    # + data source library (akshare, tushare, etc.)
]

[project.scripts]
<name>-mcp = "server:main"
```

### ASGI App Export

Every `server.py` must export `mcp_app` at module level:

```python
# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)
```

## Error Handling

```python
@mcp.tool()
def stock_zh_a_hist(symbol: str, ...) -> list[dict]:
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, ...)
        if df.empty:
            return [{"warning": f"No data returned for symbol={symbol}"}]
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "stock_zh_a_hist", "symbol": symbol}]
```

Principles:
1. **Never crash the server** — catch all exceptions per-tool.
2. **Return structured error dicts** — include tool name and params for debugging.
3. **Distinguish warnings from errors** — "no data" is a warning, not an error.
4. **Log to stderr** — use `logging` module for server-side diagnostics.

## Caching Strategy

| Data Type | TTL | Storage | Rationale |
|-----------|-----|---------|-----------|
| Real-time quotes | No cache | — | Must be fresh |
| Daily OHLCV | 1 day | Parquet (per stock) | Stale after market close |
| Financial statements | 90 days | Parquet | Quarterly updates |
| Index constituents | 30 days | Parquet | Semi-annual rebalancing |
| Northbound flow | 1 day | Parquet | Daily update |
| Backtest results | Permanent | Parquet + SQLite | Never expires |

Caching is handled by `mcp-servers/internal-store/` — other servers do not implement their own cache. The agent accesses cached data via the `query_cache` tool before making live API calls.

## Port Assignment

| Server | Port | Config |
|--------|------|--------|
| AKShare | 8000 | `.mcp.json` → `akshare.url` |
| Tushare | 8001 | `.mcp.json` → `tushare.url` |
| Internal Store | 8002 | `.mcp.json` → `internal-store.url` |

## Adding a New Tool to an Existing Server

1. **Define the tool function** in `mcp-servers/<name>/server.py` with `@mcp.tool()` decorator.
2. **Add type hints and docstring** — agents rely on these for discovery.
3. **Handle errors** — wrap in try/except, return error dict on failure.
4. **Update `test_server.py`** — add at least a happy-path test and one error test.
5. **Update `README.md`** — add the tool to the documentation table.
6. **Verify**: restart the server, call the tool via curl or Claude Code, check response shape.

```bash
# Verify new tool is registered
curl http://localhost:8000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Adding a New MCP Server

1. **Create directory**: `mcp-servers/<name>/`
2. **Create `server.py`**: FastMCP setup + tool definitions + ASGI export.
3. **Create `pyproject.toml`**: list dependencies.
4. **Create `test_server.py`**: at least one test per tool.
5. **Create `README.md`**: tool documentation table.
6. **Register in `.mcp.json`**: add entry to `mcpServers` with type `http` and URL.
7. **Register in vertical plugin `.mcp.json`**: if agents need the new server.
8. **Assign a port**: use the next available port (8003, 8004, ...).
9. **Update `scripts/check.py`**: add the new server to the required servers list.
10. **Verify**: `python scripts/check.py` + server starts + tool responds.

## Authentication

- **Tushare**: Token-based. Pass via environment variable `TUSHARE_TOKEN`. Read in `server.py` with `os.environ.get("TUSHARE_TOKEN", "")`. Raise `ValueError` at import time if missing.
- **AKShare**: No authentication required.
- **Internal Store**: No authentication (localhost only).
- **Never hardcode tokens** in source code or config files committed to git.
