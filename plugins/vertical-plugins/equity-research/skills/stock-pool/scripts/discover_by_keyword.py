"""Discover stocks by querying Tushare concept_detail by concept ID.

Usage:
    # First, find concept IDs for a theme (may hit rate limit - wait 60s between calls)
    uv run python scripts/discover_concept_stocks.py --theme PCB --action list_concepts

    # Then query stocks for known concept IDs
    uv run python scripts/discover_concept_stocks.py --theme PCB --concept-ids TS2 TS5 TS9 --output out/PCB_concepts.json
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

TUSHARE_URL = "http://localhost:8001/mcp"


class MCPSession:
    def __init__(self, url: str, *, timeout: float = 15.0):
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

    async def _post(self, payload: dict) -> httpx.Response:
        assert self._client
        h = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        r = await self._client.post(self.url, json=payload, headers=h)
        if "mcp-session-id" in r.headers:
            self.session_id = r.headers["mcp-session-id"]
        return r

    async def initialize(self) -> dict:
        r = await self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "discover", "version": "1.0"}},
        })
        text = (await r.aread()).decode()
        for line in text.split("\n"):
            if line.startswith("data:"):
                return json.loads(line[5:]).get("result", {})
        return {}

    async def call_tool(self, tool_name: str, arguments: dict) -> list[dict]:
        r = await self._post({
            "jsonrpc": "2.0", "id": 99, "method": "tools/call",
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
        content = data.get("result", {}).get("content", [])
        rows = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                try:
                    rows.append(json.loads(item["text"]))
                except Exception:
                    pass
        return rows


async def list_all_concepts(session: MCPSession) -> list[dict]:
    """List all Tushare concept entries. Rate limit: 1 req/min."""
    return await session.call_tool("concept_detail", {})


async def search_concepts_by_keyword(
    session: MCPSession,
    keywords: list[str],
    cooldown: float = 70.0,
) -> dict[str, list[dict]]:
    """Search concepts by keyword, return {concept_name: [concept_rows]}.

    Since concept_detail with no args returns ALL concepts (~3000),
    we do ONE call and filter locally.
    """
    all_concepts = await session.call_tool("concept_detail", {})
    if not all_concepts or isinstance(all_concepts, dict):
        return {}

    matched: dict[str, list[dict]] = {}
    for row in all_concepts:
        cn = row.get("concept_name", "")
        if cn:
            for kw in keywords:
                if kw.lower() in cn.lower():
                    matched[cn] = row
                    break
    return matched


async def get_concept_stocks(session: MCPSession, concept_id: str) -> list[dict]:
    """Get stocks in a concept by ID."""
    return await session.call_tool("concept_detail", {"id": concept_id})


async def discover_by_keyword(
    theme: str,
    keywords: list[str],
    *,
    cooldown: float = 70.0,
) -> list[dict[str, Any]]:
    """Discover stocks for a theme via Tushare concept keyword search.

    Does ONE call to concept_detail (listing all concepts), filters by keywords,
    then for each matching concept queries its members.

    Rate limit: ~1 req/min for concept_detail calls.
    A theme with 3 keywords × 1 match × 1 req = ~1 req.
    """
    results: dict[str, dict[str, Any]] = {}

    async with MCPSession(TUSHARE_URL) as session:
        await session.initialize()

        # Step 1: search all concepts for keyword matches
        matched = await search_concepts_by_keyword(session, keywords, cooldown=cooldown)
        print(f"  Found {len(matched)} matching concepts: {list(matched.keys())[:10]}")

        # Step 2: for each matched concept, get its stock members
        for concept_name, concept_row in matched.items():
            concept_id = concept_row.get("id", "")
            if not concept_id:
                continue

            await asyncio.sleep(cooldown)
            try:
                stocks = await get_concept_stocks(session, concept_id)
                for row in stocks:
                    code = row.get("ts_code", "") or row.get("code", "")
                    name = row.get("name", "")
                    if code and len(code) == 10 and name:
                        key = code
                        if key not in results:
                            results[key] = {
                                "code": code,
                                "name": name,
                                "source": "tushare",
                                "concept": concept_name,
                                "theme": theme,
                            }
            except Exception as e:
                print(f"  [WARN] concept {concept_name} ({concept_id}) failed: {e}")

    return list(results.values())[:200]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover concept stocks via Tushare")
    parser.add_argument("--theme", required=True, help="Theme name")
    parser.add_argument("--keywords", nargs="+", required=True, help="Keyword to search in concept names")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--cooldown", type=float, default=70.0, help="Seconds between Tushare calls (default 70)")
    args = parser.parse_args()

    print(f"\nDiscovering '{args.theme}' stocks (keywords: {args.keywords})")
    print(f"NOTE: Tushare concept_detail rate limit is 1 req/min. Using cooldown={args.cooldown}s")
    print(f"      This will take ~{args.cooldown}s if keywords match.\n")

    result = asyncio.run(discover_by_keyword(
        args.theme,
        args.keywords,
        cooldown=args.cooldown,
    ))

    output = {"theme": args.theme, "stocks": result, "count": len(result)}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResult: {len(result)} stocks -> {args.output}")
    for s in result[:10]:
        print(f"  {s['code']} {s['name']} ({s.get('concept','')})")