"""MCP HTTP client: JSON-RPC streamable-http protocol with retry.

Protocol: MCP Streamable HTTP (FastMCP default).
Endpoint: {MCP_URL}/mcp, POST JSON-RPC 2.0 over HTTP, response is SSE stream.

Full handshake:
  1. POST initialize -> get mcp-session-id response header
  2. POST notifications/initialized (with session-id)
  3. POST tools/call (with session-id) -> parse JSON from SSE data: lines

Session is cached per source (handshake once, reuse afterwards).

This is the aquan-canonical version. The original copy at
scripts/etl/common/mcp_client.py remains in place during migration and will
be removed in Phase 3 once ETL switches its imports.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import requests

from aquan.core.config import (
    MCP_AKSHARE_URL,
    MCP_INTERNAL_STORE_URL,
    MCP_TUSHARE_URL,
)
from aquan.core.errors import AquanError


class McpError(AquanError):
    """MCP invocation error (protocol error / retries exhausted)."""


# Source name -> URL mapping.
_SOURCE_URLS = {
    "akshare": MCP_AKSHARE_URL,
    "tushare": MCP_TUSHARE_URL,
    "internal-store": MCP_INTERNAL_STORE_URL,
}

# Most recent call's params_hash (read by callers like meta_fields).
_last_params_hash: str = ""

# Per-source session-id cache (populated after handshake, reused).
_sessions: dict[str, str] = {}


def get_last_params_hash() -> str:
    """Return params_hash from the most recent call()."""
    return _last_params_hash


def _is_loopback_url(url: str) -> bool:
    """True if url points at localhost or 127.0.0.1 (should bypass any proxy)."""
    lowered = url.lower()
    return "://localhost" in lowered or "://127.0.0.1" in lowered or "://[::1]" in lowered


def _bypass_proxy_if_loopback(url: str) -> dict[str, str | None] | None:
    """For loopback targets, return an explicit empty proxy map so requests
    ignores system/HTTP_PROXY settings that would otherwise route the call
    through a VPN/forwarder (which returns 503 for localhost services).

    Returns None for non-loopback URLs so the default proxy resolution applies.
    """
    if _is_loopback_url(url):
        return {"http": None, "https": None}
    return None


def _ensure_session(source: str, url: str, timeout: int = 10) -> str:
    """Handshake with the MCP source, return and cache the session-id.

    Subsequent calls for the same source reuse the cached session.
    """
    if source in _sessions:
        return _sessions[source]

    init_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aquan-client", "version": "0.1.0"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    proxies = _bypass_proxy_if_loopback(url)
    resp = requests.post(url, json=init_payload, headers=headers, timeout=timeout, proxies=proxies)
    resp.raise_for_status()

    session_id = resp.headers.get("mcp-session-id")
    if not session_id:
        raise McpError(f"MCP initialize for {source} returned no mcp-session-id header")

    # Send notifications/initialized (protocol requirement).
    notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    requests.post(
        url,
        json=notif,
        headers={**headers, "mcp-session-id": session_id},
        timeout=timeout,
        proxies=proxies,
    )

    _sessions[source] = session_id
    return session_id


def _parse_sse_json(raw_text: str) -> dict:
    """Extract the first `data:` line's JSON payload from an SSE stream.

    SSE format:
        event: message
        data: {"jsonrpc":"2.0",...}

    Falls back to direct json.loads if the response is plain JSON (not SSE).
    """
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:") :].strip()
            return json.loads(payload)
    return json.loads(raw_text)


def call(
    source: str,
    tool: str,
    params: dict[str, Any],
    timeout: int = 30,
    max_retries: int = 3,
) -> list[dict]:
    """Invoke an MCP tool, return list[dict].

    Args:
        source:      MCP source name (akshare / tushare / internal-store)
        tool:        MCP tool name (e.g. daily / stock_zh_a_hist)
        params:      tool arguments
        timeout:     per-request timeout in seconds
        max_retries: network-error retry attempts

    Returns:
        The tool's return value as list[dict]. Tool-internal errors come
        back as [{"error": ...}].

    Raises:
        McpError: MCP protocol error or network retries exhausted.
    """
    global _last_params_hash

    # Compute params_hash lazily; meta_fields import is local to avoid cycle.
    from aquan.utils.hashing import params_hash

    _last_params_hash = params_hash(params)

    if source not in _SOURCE_URLS:
        raise McpError(f"Unknown MCP source: {source}")

    url = _SOURCE_URLS[source]

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            session_id = _ensure_session(source, url, timeout=timeout)

            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": tool, "arguments": params},
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id,
            }
            resp = requests.post(
                url, json=payload, headers=headers, timeout=timeout, proxies=_bypass_proxy_if_loopback(url)
            )
            resp.raise_for_status()

            data = _parse_sse_json(resp.text)

            # Session expired/invalid: clear cache and retry once.
            if "error" in data:
                err_msg = str(data["error"])
                if "session" in err_msg.lower() or "unauthorized" in err_msg.lower():
                    _sessions.pop(source, None)
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)
                        continue
                raise McpError(f"MCP error from {source}.{tool}: {data['error']}")

            if "result" not in data:
                raise McpError(f"MCP malformed response from {source}.{tool}: no result")

            content = data["result"].get("content", [])
            if not content:
                return []

            # content may be multi-segment (e.g. internal-store emits one JSON text per row).
            results: list[dict] = []
            for chunk in content:
                if chunk.get("type") != "text":
                    continue
                text = chunk.get("text", "")
                if not text:
                    continue
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, list):
                    results.extend(parsed)
                elif isinstance(parsed, dict):
                    results.append(parsed)
            return results

        except (requests.RequestException, ConnectionError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2**attempt)  # exponential backoff: 1s, 2s, 4s
                continue
            break

    raise McpError(f"MCP call {source}.{tool} failed after {max_retries} retries: {last_exc}")


def health_check(source: str, max_retries: int = 1) -> bool:
    """Ping a source's lightweight probe tool. True = healthy.

    Each server has a different "lightweight" call:
    - akshare:        data_source_health tool
    - tushare:        daily tool with limit=1 (no dedicated health tool)
    - internal-store: list_experiments tool
    """
    try:
        if source == "tushare":
            call(source, "daily", {"limit": 1}, max_retries=max_retries, timeout=10)
        elif source == "akshare":
            call(source, "data_source_health", {}, max_retries=max_retries, timeout=10)
        elif source == "internal-store":
            call(source, "list_experiments", {}, max_retries=max_retries, timeout=10)
        else:
            return False
        return True
    except McpError:
        return False
    except Exception:
        return False


def reset_session(source: str) -> None:
    """Clear a source's cached session (for tests or session invalidation)."""
    _sessions.pop(source, None)
