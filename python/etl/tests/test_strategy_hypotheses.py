"""Tests for strategy_hypotheses ETL domain (sub-project ❷)."""

import json
from pathlib import Path
from unittest.mock import patch

from etl.ods.strategy_hypotheses import (
    DOMAIN,
    PARTITION_COL,
    SOURCE_MCP,
    transform,
    run,
    _format_partition,
    CATALOG_ENTRY,
)

FIXTURE = Path(__file__).parent / "fixtures" / "internal_store_experiments.json"


def _load():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "strategy_hypotheses"
    assert PARTITION_COL == "dt"
    assert SOURCE_MCP == "internal-store"


def test_catalog_entry_shape():
    assert CATALOG_ENTRY["table_name"] == "ods_strategy_hypotheses"
    assert "schema_json" in CATALOG_ENTRY


def test_format_partition():
    assert _format_partition("20260718") == "2026-07-18"


def test_transform_preserves_json():
    """strategy/params/result 是 JSON 字符串，原样保留。"""
    raw = _load()
    clean = transform(raw, "20260718")
    assert len(clean) == 2
    first = clean[0]
    assert first["experiment_id"] == 1
    assert first["name"] == "exp_momentum_20d_v1"
    # JSON 字段原样保留（可被 json.loads 反序列化）
    parsed_strategy = json.loads(first["strategy_json"])
    assert "factors" in parsed_strategy
    parsed_result = json.loads(first["result_json"])
    assert "final_nav" in parsed_result


def test_transform_injects_meta():
    raw = _load()
    clean = transform(raw, "20260718")
    for r in clean:
        assert r["__source"] == "internal-store"
        assert r["__source_tool"] == "list_experiments"


def test_run_ok(tmp_path):
    raw = _load()
    with patch("etl.ods.strategy_hypotheses.mcp_client.call", return_value=raw):
        with patch("etl.ods.strategy_hypotheses.MIN_ROWS", 1):
            result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
    pq_file = tmp_path / "strategy_hypotheses" / "dt=2026-07-18" / "part-0.parquet"
    assert pq_file.exists()


def test_run_extract_failure(tmp_path):
    with patch(
        "etl.ods.strategy_hypotheses.mcp_client.call",
        return_value=[{"error": "down"}],
    ):
        result = run(date="20260718", ods_root=tmp_path)
    assert result["status"] == "extract_failed"
