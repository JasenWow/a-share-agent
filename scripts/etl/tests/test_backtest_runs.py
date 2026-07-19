"""Tests for backtest_runs ETL domain (sub-project ❷)."""

import json
from pathlib import Path
from unittest.mock import patch

from ods.backtest_runs import (
    DOMAIN,
    PARTITION_COL,
    SOURCE_MCP,
    transform,
    run,
    _format_partition,
    CATALOG_ENTRY,
)

FIXTURE = Path(__file__).parent / "fixtures" / "internal_store_backtest.json"


def _load():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "backtest_runs"
    assert PARTITION_COL == "dt"
    assert SOURCE_MCP == "internal-store"


def test_catalog_entry_shape():
    assert CATALOG_ENTRY["table_name"] == "ods_backtest_runs"
    assert "schema_json" in CATALOG_ENTRY


def test_format_partition():
    assert _format_partition("20260718") == "2026-07-18"


def test_transform_basic():
    raw = _load()
    clean = transform(raw, "20260718")
    assert len(clean) == 2
    first = clean[0]
    assert first["run_id"] == 1
    assert first["name"] == "momentum_top2_csi300"
    assert first["snapshot_date"] == "20260718"
    assert isinstance(first["sharpe"], float)
    assert isinstance(first["max_drawdown"], float)


def test_transform_injects_meta():
    raw = _load()
    clean = transform(raw, "20260718")
    for r in clean:
        assert r["__source"] == "internal-store"
        assert r["__source_tool"] == "list_backtest_results"


def test_run_ok(tmp_path):
    raw = _load()
    with patch("ods.backtest_runs.mcp_client.call", return_value=raw):
        with patch("ods.backtest_runs.MIN_ROWS", 1):
            result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
    pq_file = tmp_path / "backtest_runs" / "dt=2026-07-18" / "part-0.parquet"
    assert pq_file.exists()


def test_run_extract_failure(tmp_path):
    with patch(
        "ods.backtest_runs.mcp_client.call",
        return_value=[{"error": "down"}],
    ):
        result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "extract_failed"
