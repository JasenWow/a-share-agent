"""Tests for index_constituents ETL domain."""
import json
from pathlib import Path
from unittest.mock import patch

from ods.index_constituents import (
    DOMAIN,
    PARTITION_COL,
    transform,
    run,
    _split_con_code,
    _format_month,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_index_weight.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_constants():
    assert DOMAIN == "index_constituents"
    assert PARTITION_COL == "dt"


def test_split_con_code():
    """600519.SH → ('600519', 'SH')。"""
    assert _split_con_code("600519.SH") == ("600519", "SH")
    assert _split_con_code("000001") == ("000001", "")


def test_format_month():
    """202607 → 2026-07。"""
    assert _format_month("202607") == "2026-07"


def test_transform_strips_con_code():
    """con_code 拆为 code + exchange；index_code 去后缀。"""
    raw = _load_fixture()
    clean = transform(raw, "2026-07")
    assert clean[0]["code"] == "600519"
    assert clean[0]["exchange"] == "SH"
    assert clean[0]["index_code"] == "000300"
    assert clean[0]["weight"] == 5.23


def test_transform_preserves_trade_date():
    """月度分区下 trade_date 保留原 YYYYMMDD。"""
    raw = _load_fixture()
    clean = transform(raw, "2026-07")
    assert clean[0]["trade_date"] == "20260717"


def test_transform_injects_meta():
    raw = _load_fixture()
    clean = transform(raw, "2026-07")
    for r in clean:
        assert r["__source"] == "tushare"
        assert r["__source_tool"] == "index_weight"


def test_run_ok_with_lowered_threshold(tmp_path):
    """端到端 mock + 降低 quality 阈值。"""
    raw = _load_fixture()
    with patch("ods.index_constituents.mcp_client.call", return_value=raw):
        with patch("ods.index_constituents.MIN_ROWS", 1):
            result = run("000300.SH", month="202607", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 3
    pq_file = tmp_path / "index_constituents" / "dt=2026-07" / "part-0.parquet"
    assert pq_file.exists()
