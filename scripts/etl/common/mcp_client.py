"""MCP HTTP 客户端：封装 JSON-RPC tools/call 调用，带重试。

协议参考：plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts/track_experiment.py
端点：{MCP_URL}/mcp，POST JSON-RPC 2.0。
返回 result.content[0].text 是 JSON 字符串，解析后是 list[dict]。
"""
from __future__ import annotations

import json
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


def get_last_params_hash() -> str:
    """返回最近一次 call() 的 params_hash。"""
    return _last_params_hash


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
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool, "arguments": params},
    }

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                raise McpError(f"MCP error from {source}.{tool}: {data['error']}")

            if "result" not in data:
                raise McpError(
                    f"MCP malformed response from {source}.{tool}: no result"
                )

            content = data["result"].get("content", [])
            if not content:
                return []

            text = content[0].get("text", "[]")
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                parsed = [parsed]
            return parsed

        except (requests.RequestException, ConnectionError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避：1s, 2s, 4s
                continue
            break

    raise McpError(
        f"MCP call {source}.{tool} failed after {max_retries} retries: {last_exc}"
    )


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
