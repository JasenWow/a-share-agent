"""Thin proxy from the aquan CLI to the running MCP servers.

Reuses ``aquan.utils.http.call`` (the canonical MCP-over-HTTP client
already used by the ETL pipeline). The CLI never speaks MCP directly —
it always goes through this helper so error handling is uniform:

- MCP server unreachable → friendly stderr message, exit non-zero
- MCP returns an error document → surface it as a clear failure
- success → return the tool's list[dict] / dict

Why not call the server.py functions directly (in-process):
  The CLI is invoked as a subprocess by pi-runtime. Spinning up the
  MCP HTTP path keeps a single access route for every consumer
  (dashboard, ETL, CLI) and lets the CLI be a pure data-shaping layer.
"""

from __future__ import annotations

from typing import Any

from aquan.utils.http import McpError, call as _mcp_call


class CliMcpError(Exception):
    """Raised when an MCP call fails in a way the CLI should surface."""


def mcp_call(source: str, tool: str, params: dict[str, Any] | None = None) -> list[dict] | dict:
    """Call an MCP tool and return its result.

    Args:
        source:  MCP source name (akshare / tushare / internal-store / qlib).
        tool:    MCP tool name (e.g. "stock_zh_a_hist").
        params:  tool arguments (None → empty dict).

    Returns:
        The tool's result (list[dict] or dict).

    Raises:
        CliMcpError: server unreachable, protocol error, or tool error.
    """
    try:
        result = _mcp_call(source, tool, params or {})
    except McpError as e:
        raise CliMcpError(f"MCP {source}.{tool} failed: {e}") from e
    except Exception as e:  # noqa: BLE001 — we want to wrap any unexpected error
        # Connection refused, timeout, etc. Surface a friendly message rather
        # than letting the traceback bleed into the agent's view.
        msg = str(e).lower()
        if "connection" in msg or "refused" in msg or "timeout" in msg:
            raise CliMcpError(f"MCP server '{source}' is unreachable. Is it running on the expected port? ({e})") from e
        raise CliMcpError(f"MCP {source}.{tool} raised: {e}") from e

    # MCP tools return their result as a list[dict]; some surface tool-level
    # errors as [{"error": "..."}] instead of raising. Detect and wrap.
    if isinstance(result, list) and result and isinstance(result[0], dict) and "error" in result[0]:
        raise CliMcpError(f"MCP {source}.{tool} returned error: {result[0]['error']}")
    if isinstance(result, dict) and "error" in result:
        raise CliMcpError(f"MCP {source}.{tool} returned error: {result['error']}")

    return result
