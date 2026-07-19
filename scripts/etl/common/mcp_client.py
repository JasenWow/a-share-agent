"""MCP HTTP 客户端：封装 JSON-RPC streamable-http 协议，带重试。

协议：MCP Streamable HTTP（FastMCP 默认）。
端点：{MCP_URL}/mcp，POST JSON-RPC 2.0 over HTTP，响应为 SSE 流。

完整握手：
  1. POST initialize -> 拿 mcp-session-id 响应头
  2. POST notifications/initialized（带 session-id）
  3. POST tools/call（带 session-id）-> SSE 响应里取 data 行解析 JSON

session 按数据源缓存复用（首次调用时握手，后续直接用）。
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import requests

from common.config import (
    MCP_AKSHARE_URL,
    MCP_TUSHARE_URL,
    MCP_INTERNAL_STORE_URL,
)


class McpError(Exception):
    """MCP 调用异常（协议错误 / 重试耗尽）。"""


# 源名 → URL 映射
_SOURCE_URLS = {
    "akshare": MCP_AKSHARE_URL,
    "tushare": MCP_TUSHARE_URL,
    "internal-store": MCP_INTERNAL_STORE_URL,
}

# 记录最近一次调用的 params_hash（供 meta_fields 用）
_last_params_hash: str = ""

# 每个数据源的 session-id 缓存（握手后复用）
_sessions: dict[str, str] = {}


def get_last_params_hash() -> str:
    """返回最近一次 call() 的 params_hash。"""
    return _last_params_hash


def _ensure_session(source: str, url: str, timeout: int = 10) -> str:
    """对给定数据源做 MCP initialize 握手，返回并缓存 session-id。

    已握过手的数据源直接返回缓存的 session。
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
            "clientInfo": {"name": "etl-client", "version": "0.1.0"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    resp = requests.post(url, json=init_payload, headers=headers, timeout=timeout)
    resp.raise_for_status()

    # session-id 在响应头里
    session_id = resp.headers.get("mcp-session-id")
    if not session_id:
        raise McpError(f"MCP initialize for {source} returned no mcp-session-id header")

    # 发 notifications/initialized（协议要求）
    notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    requests.post(
        url,
        json=notif,
        headers={**headers, "mcp-session-id": session_id},
        timeout=timeout,
    )

    _sessions[source] = session_id
    return session_id


def _parse_sse_json(raw_text: str) -> dict:
    """从 SSE 流文本里提取第一行 data: 的 JSON 内容。

    SSE 格式：
        event: message
        data: {"jsonrpc":"2.0",...}

    若不是 SSE（纯 JSON），直接 json.loads。
    """
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            return json.loads(payload)
    # 不是 SSE 格式，尝试直接解析
    return json.loads(raw_text)


def call(
    source: str,
    tool: str,
    params: dict[str, Any],
    timeout: int = 30,
    max_retries: int = 3,
) -> list[dict]:
    """调用 MCP 工具，返回 list[dict]。

    Args:
        source:     数据源名（akshare / tushare / internal-store）
        tool:       MCP 工具名（如 daily / stock_zh_a_hist）
        params:     工具参数
        timeout:    单次请求超时秒
        max_retries: 网络错误重试次数

    Returns:
        工具返回的 list[dict]。如果是工具内部错误，原样返回 [{"error": ...}]。

    Raises:
        McpError: MCP 协议错误或网络重试耗尽。
    """
    global _last_params_hash
    from common.meta_fields import params_hash

    _last_params_hash = params_hash(params)

    if source not in _SOURCE_URLS:
        raise McpError(f"Unknown MCP source: {source}")

    url = _SOURCE_URLS[source]

    # 握手（带重试：session 过期时清缓存重试一次）
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
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()

            data = _parse_sse_json(resp.text)

            # session 过期/无效：清缓存重试
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

            # content 可能多段（如 internal-store 每行一个 JSON text）
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
                time.sleep(2**attempt)  # 指数退避：1s, 2s, 4s
                continue
            break

    raise McpError(f"MCP call {source}.{tool} failed after {max_retries} retries: {last_exc}")


def health_check(source: str, max_retries: int = 1) -> bool:
    """ping 数据源的健康检查工具。True = 健康。

    不同 server 用不同的"轻量"调用来探活：
    - akshare: data_source_health 工具
    - tushare: daily 工具 + limit=1（tushare 没有专门的 health 工具）
    - internal-store: list_experiments 工具
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
    """清除某数据源的 session 缓存（供测试或 session 失效场景）。"""
    _sessions.pop(source, None)
