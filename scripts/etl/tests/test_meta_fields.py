"""Tests for meta_fields injection."""
from common.meta_fields import inject, params_hash


def test_params_hash_stable():
    """相同参数（任意顺序）产生相同 hash。"""
    h1 = params_hash({"code": "600519", "date": "20260717"})
    h2 = params_hash({"date": "20260717", "code": "600519"})
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_params_hash_different():
    """不同参数产生不同 hash。"""
    h1 = params_hash({"code": "600519"})
    h2 = params_hash({"code": "000001"})
    assert h1 != h2


def test_params_hash_handles_nested_and_nonstr():
    """嵌套结构和非字符串值不报错。"""
    h = params_hash({"a": [1, 2, 3], "b": {"c": 1.5}, "d": None})
    assert len(h) == 64


def test_inject_returns_5_fields():
    """inject 返回 5 个元数据字段。"""
    result = inject(
        source="tushare",
        source_tool="daily",
        fetched_at="2026-07-17T17:00:00+08:00",
        params_hash="abc123",
        etl_run_id="20260717_170000_equity_daily",
    )
    assert set(result.keys()) == {
        "__source",
        "__source_tool",
        "__fetched_at",
        "__params_hash",
        "__etl_run_id",
    }
    assert result["__source"] == "tushare"
    assert result["__source_tool"] == "daily"
    assert result["__params_hash"] == "abc123"
    assert result["__etl_run_id"] == "20260717_170000_equity_daily"


def test_inject_field_names_dunder_prefixed():
    """所有元数据字段以 __ 前缀开头（避免与业务字段冲突）。"""
    result = inject("s", "t", "now", "h", "r")
    for key in result:
        assert key.startswith("__")
