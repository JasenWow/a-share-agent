"""Tests for financial_income ETL domain."""

import json
from pathlib import Path
from unittest.mock import patch

from etl.ods.financial_income import (
    DOMAIN,
    PARTITION_COL,
    transform,
    run,
    _end_date_to_period,
    _split_ts_code,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_income.json"


def _load():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "financial_income"
    assert PARTITION_COL == "period"


def test_end_date_to_period():
    """财报期末日 → 季度标签。"""
    assert _end_date_to_period("20251231") == "2025Q4"
    assert _end_date_to_period("20250930") == "2025Q3"
    assert _end_date_to_period("20250630") == "2025Q2"
    assert _end_date_to_period("20250331") == "2025Q1"


def test_split_ts_code():
    assert _split_ts_code("600519.SH") == ("600519", "SH")
    assert _split_ts_code("000001") == ("000001", "")


def test_transform_partition_period():
    """period 分区字段写入正确；end_date 保留原值。"""
    raw = _load()
    clean = transform(raw, "2025Q4")
    assert clean[0]["period"] == "2025Q4"
    assert clean[0]["end_date"] == "20251231"


def test_transform_strips_ts_code():
    raw = _load()
    clean = transform(raw, "2025Q4")
    assert clean[0]["code"] == "600519"
    assert clean[0]["exchange"] == "SH"


def test_transform_injects_meta():
    raw = _load()
    clean = transform(raw, "2025Q4")
    for r in clean:
        assert r["__source"] == "tushare"
        assert r["__source_tool"] == "income"


def test_run_ok_with_lowered_threshold(tmp_path):
    """端到端：mock MCP + 降低 quality 阈值验证落地。"""
    raw = _load()
    with patch("etl.ods.financial_income.mcp_client.call", return_value=raw):
        with patch("etl.ods.financial_income.MIN_ROWS", 1):
            result = run(period="20251231", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 2
    pq_file = tmp_path / "financial_income" / "period=2025Q4" / "part-0.parquet"
    assert pq_file.exists()
