"""MCP HTTP Session utility — wraps raw httpx with JSON-RPC 2.0 over SSE."""

from __future__ import annotations

import json
from typing import Any

import httpx


class MCPSession:
    """Manages a raw httpx MCP session with proper session-id handling.

    Handles the StreamableHTTP transport with SSE event parsing.
    Each call_tool invocation reuses the same session-id across requests.
    """

    def __init__(self, url: str, *, timeout: float = 20.0):
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MCPSession":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        return h

    async def _post(self, payload: dict) -> httpx.Response:
        assert self._client
        r = await self._client.post(self.url, json=payload, headers=self._headers())
        if "mcp-session-id" in r.headers:
            self.session_id = r.headers["mcp-session-id"]
        return r

    async def initialize(self) -> dict:
        """Send MCP initialize request, capture session-id."""
        r = await self._post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-session", "version": "1.0"},
            },
        })
        text = (await r.aread()).decode()
        for line in text.split("\n"):
            if line.startswith("data:"):
                return json.loads(line[5:]).get("result", {})
        return {}

    async def list_tools(self) -> list[dict]:
        """Call tools/list, return tool list."""
        r = await self._post({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        text = (await r.aread()).decode()
        if text.startswith("{"):
            data = json.loads(text)
        else:
            for line in text.split("\n"):
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    break
            else:
                return []
        return data.get("result", {}).get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict) -> list[dict]:
        """Call an MCP tool, return parsed JSON rows.

        Parses both single-line JSON and SSE multi-line response formats.
        AKShare historical data returns one JSON row per line in content[].
        """
        r = await self._post({
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        text = (await r.aread()).decode()

        if text.startswith("{"):
            data = json.loads(text)
        else:
            for line in text.split("\n"):
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    break
            else:
                return []

        if "error" in data:
            return []

        result_data = data.get("result", {})
        content = result_data.get("content", [])

        # AKShare: content is list of per-row JSON strings
        if isinstance(content, list):
            rows = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    try:
                        rows.append(json.loads(item["text"]))
                    except Exception:
                        pass
            return rows

        return []

    async def call_tool_raw(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool, return full structured content (for single-result calls)."""
        r = await self._post({
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })
        text = (await r.aread()).decode()

        if text.startswith("{"):
            data = json.loads(text)
        else:
            for line in text.split("\n"):
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    break
            else:
                return {}

        if "error" in data:
            return {}

        result_data = data.get("result", {})
        content = result_data.get("content", [])

        if isinstance(content, list) and content:
            raw = content[0].get("text", "")
            try:
                return json.loads(raw)
            except Exception:
                return {"raw": raw}

        return {}

    def is_error(self, data: list[dict] | dict) -> bool:
        """Check if response contains an error."""
        if isinstance(data, list):
            return any("error" in str(d) for d in data)
        return "error" in data