"""Tests for catalog CRUD."""

import duckdb
import pytest

from etl.catalog import register, get, list_all, init_catalog


@pytest.fixture()
def db(tmp_path):
    """临时 DuckDB + catalog 表。"""
    db_path = tmp_path / "meta.db"
    conn = duckdb.connect(str(db_path))
    init_catalog(conn)
    yield conn
    conn.close()


def _entry(**overrides):
    base = {
        "table_name": "ods_equity_daily",
        "domain": "equity_prices",
        "source_mcp": "tushare",
        "source_tool": "daily",
        "partition_col": "dt",
        "partition_grain": "daily",
        "schema_json": '{"code": "str"}',
        "description": "股票日线行情",
        "owner": "etl",
    }
    base.update(overrides)
    return base


def test_register_and_get(db):
    """注册后能查到。"""
    register(db, _entry())
    row = get(db, "ods_equity_daily")
    assert row["table_name"] == "ods_equity_daily"
    assert row["source_mcp"] == "tushare"


def test_register_is_upsert(db):
    """重名注册是更新不是报错。"""
    register(db, _entry(description="v1"))
    register(db, _entry(description="v2"))
    row = get(db, "ods_equity_daily")
    assert row["description"] == "v2"


def test_get_missing_returns_none(db):
    """查不到返回 None。"""
    assert get(db, "nonexistent") is None


def test_list_all(db):
    """list_all 返回所有注册项，按 table_name 排序。"""
    for name in ["t1", "t2", "t3"]:
        register(db, _entry(table_name=name, description=name))
    rows = list_all(db)
    assert len(rows) == 3
    names = [r["table_name"] for r in rows]
    assert names == ["t1", "t2", "t3"]


def test_init_catalog_is_idempotent(db):
    """重复 init 不报错。"""
    init_catalog(db)  # 第二次
    # 仍可正常注册
    register(db, _entry())
    assert get(db, "ods_equity_daily") is not None
