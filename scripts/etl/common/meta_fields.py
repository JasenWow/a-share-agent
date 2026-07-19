"""元数据字段注入：给 ODS 记录加追溯信息。

5 个字段（前缀 __ 避免与业务字段冲突）：
- __source:        数据源（tushare / akshare）
- __source_tool:   MCP 工具名（daily / stock_zh_a_hist / direct_sdk）
- __fetched_at:    拉取时间 ISO8601 带时区
- __params_hash:   MCP 调用参数的 sha256
- __etl_run_id:    ETL 运行实例 ID
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def params_hash(params: dict[str, Any]) -> str:
    """计算参数 dict 的稳定 sha256（key 排序，不依赖顺序）。

    用 default=str 兜底处理非 JSON 原生类型（datetime/Path 等）。
    """
    canonical = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def inject(
    source: str,
    source_tool: str,
    fetched_at: str,
    params_hash: str,
    etl_run_id: str,
) -> dict[str, str]:
    """返回 5 个元数据字段的 dict，供 merge 到业务记录中。"""
    return {
        "__source": source,
        "__source_tool": source_tool,
        "__fetched_at": fetched_at,
        "__params_hash": params_hash,
        "__etl_run_id": etl_run_id,
    }
