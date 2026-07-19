"""A-Share 量化指标语义层。

把 (metric_name, dimensions, filters) 编译成 DuckDB SQL，避免各处"同名异义"。

Usage:
    from metrics import compile_query, list_metrics, describe_metric

    # 列出所有可用指标
    metrics_list = list_metrics()

    # 查询"动量因子的 ICIR 在 csi300 的值"
    sql = compile_query(
        metric="icir",
        dimensions=["universe", "factor_name"],
        filters={"universe": "csi300", "factor_name": "momentum_20d"},
    )
    # → SELECT universe, factor_name, avg(ic)/stddev(ic) AS icir
    #   FROM ods_factor_experiments
    #   WHERE universe = 'csi300' AND name = 'momentum_20d'
    #   GROUP BY universe, factor_name

设计原则：
- 编译器只生成 SQL 字符串，不执行（执行由 chat-database adapter / DuckDB CLI 负责）
- 公式以 metric.formula 为权威，dimensions 是 GROUP BY 字段
- 不做 SQL 注入防护：调用方（agent / 内部工具）可信；外部输入需在上游 sanitization
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_METRICS_YML = Path(__file__).resolve().parent / "metrics.yml"


def _load_catalog() -> dict[str, Any]:
    """加载 metrics.yml（每次调用重读，开发期便利；生产可加缓存）。"""
    with open(_METRICS_YML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_metrics(category: str | None = None) -> list[dict[str, Any]]:
    """列出所有指标（可选按 category 过滤）。"""
    catalog = _load_catalog()
    metrics = catalog.get("metrics", [])
    if category:
        return [m for m in metrics if m.get("category") == category]
    return metrics


def describe_metric(name: str) -> dict[str, Any]:
    """返回单个指标的完整定义。KeyError 若不存在。"""
    for m in list_metrics():
        if m["name"] == name:
            return m
    raise KeyError(f"Unknown metric: {name}. Available: {[m['name'] for m in list_metrics()]}")


def list_dimensions() -> list[dict[str, Any]]:
    """返回维度词典。"""
    return _load_catalog().get("dimensions", [])


def compile_query(
    metric: str,
    dimensions: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> str:
    """把 (metric, dimensions, filters) 编译成 DuckDB SQL 字符串。

    Args:
        metric:     指标名（必须在 metrics.yml 中）
        dimensions: GROUP BY 字段（如 ["universe", "factor_name"]）。None=不分组，返回标量
        filters:    WHERE 等值过滤（如 {"universe": "csi300"}）
        limit:      返回行数上限

    Returns:
        DuckDB 可执行的 SQL 字符串（不执行）

    Raises:
        KeyError: metric 不存在；dimension/filter 字段不在该指标声明的 dimensions 内
    """
    spec = describe_metric(metric)
    formula = spec["formula"]
    table = spec["source_table"]
    allowed_dims = set(spec.get("dimensions", []))

    dimensions = dimensions or []
    filters = filters or {}

    # 校验 dimensions/filters 在该指标的 allowed_dims 内
    for d in dimensions:
        if d not in allowed_dims:
            raise KeyError(
                f"Dimension '{d}' not allowed for metric '{metric}'. Allowed: {sorted(allowed_dims)}"
            )
    for k in filters:
        if k not in allowed_dims:
            raise KeyError(
                f"Filter '{k}' not allowed for metric '{metric}'. Allowed: {sorted(allowed_dims)}"
            )

    # 维度名 → 实际列名（特殊映射：factor_name 在 ods_factor_experiments 是 name）
    def _col(dim: str) -> str:
        mapping = {"factor_name": "name", "strategy_name": "name"}
        return mapping.get(dim, dim)

    # SELECT 子句
    if dimensions:
        dim_cols = ", ".join(_col(d) for d in dimensions)
        select_clause = f"{dim_cols}, {formula} AS {metric}"
        group_clause = f"GROUP BY {dim_cols}"
    else:
        select_clause = f"{formula} AS {metric}"
        group_clause = ""

    # WHERE 子句
    where_parts: list[str] = []
    for k, v in filters.items():
        col = _col(k)
        if isinstance(v, str):
            where_parts.append(f"{col} = '{v}'")
        elif isinstance(v, (int, float)):
            where_parts.append(f"{col} = {v}")
        elif isinstance(v, list):
            vals = ", ".join(f"'{x}'" if isinstance(x, str) else str(x) for x in v)
            where_parts.append(f"{col} IN ({vals})")
        else:
            where_parts.append(f"{col} = '{v}'")
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    sql = f"SELECT {select_clause} FROM {table}"
    if where_clause:
        sql += f" {where_clause}"
    if group_clause:
        sql += f" {group_clause}"
    if limit:
        sql += f" LIMIT {limit}"

    return sql
