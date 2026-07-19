"""Tests for factor_experiments ETL domain (sub-project ❷)."""

import json
from pathlib import Path
from unittest.mock import patch

from ods.factor_experiments import (
    DOMAIN,
    PARTITION_COL,
    SOURCE_MCP,
    transform,
    run,
    _format_partition,
    CATALOG_ENTRY,
)

FIXTURE = Path(__file__).parent / "fixtures" / "internal_store_factors.json"


def _load():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "factor_experiments"
    assert PARTITION_COL == "dt"
    assert SOURCE_MCP == "internal-store"


def test_catalog_entry_shape():
    assert CATALOG_ENTRY["table_name"] == "ods_factor_experiments"
    for f in [
        "domain",
        "source_mcp",
        "source_tool",
        "partition_col",
        "partition_grain",
        "schema_json",
        "description",
    ]:
        assert f in CATALOG_ENTRY


def test_format_partition():
    assert _format_partition("20260718") == "2026-07-18"


def test_transform_strips_error_rows():
    """fixture 里第 3 行是 {'error': ...}，应被过滤掉。"""
    raw = _load()
    clean = transform(raw, "20260718")
    assert len(clean) == 2  # 2 个有效因子 + 1 个 error row = 过滤后 2 行
    assert all("__source" in r for r in clean)


def test_transform_injects_meta():
    raw = _load()
    clean = transform(raw, "20260718")
    for r in clean:
        assert r["__source"] == "internal-store"
        assert r["__source_tool"] == "list_factors"
        assert r["snapshot_date"] == "20260718"


def test_transform_numeric_fields():
    raw = _load()
    clean = transform(raw, "20260718")
    first = clean[0]
    assert first["factor_id"] == 1
    assert first["name"] == "momentum_20d"
    assert isinstance(first["ic"], float)
    assert isinstance(first["sharpe"], float)


def test_run_ok(tmp_path):
    raw = _load()
    with patch("ods.factor_experiments.mcp_client.call", return_value=raw):
        with patch("ods.factor_experiments.MIN_ROWS", 1):
            result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
    pq_file = tmp_path / "factor_experiments" / "dt=2026-07-18" / "part-0.parquet"
    assert pq_file.exists()


def test_run_extract_failure_returns_status(tmp_path):
    """MCP 返回 error 时，status=extract_failed。"""
    with patch(
        "ods.factor_experiments.mcp_client.call",
        return_value=[{"error": "internal-store down"}],
    ):
        result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "extract_failed"
    assert result["domain"] == DOMAIN
