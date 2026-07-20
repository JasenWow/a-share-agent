"""Tests for equity_daily ETL domain."""

import json
from pathlib import Path
from unittest.mock import patch

from etl.ods.equity_daily import (
    DOMAIN,
    PARTITION_COL,
    SOURCE_MCP,
    transform,
    run,
    CATALOG_ENTRY,
    _split_ts_code,
    _format_partition,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tushare_daily_20260717.json"


def _load_fixture():
    return json.loads(FIXTURE.read_text())


def test_constants():
    """domain 常量符合 spec。"""
    assert DOMAIN == "equity_daily"
    assert PARTITION_COL == "dt"
    assert SOURCE_MCP == "tushare"


def test_catalog_entry_shape():
    """CATALOG_ENTRY 含必需字段，供 init.py 注册。"""
    assert CATALOG_ENTRY["table_name"] == "ods_equity_daily"
    for f in ["domain", "source_mcp", "source_tool", "partition_col", "partition_grain", "schema_json", "description"]:
        assert f in CATALOG_ENTRY


def test_split_ts_code_with_suffix():
    """600519.SH → ('600519', 'SH')。"""
    assert _split_ts_code("600519.SH") == ("600519", "SH")
    assert _split_ts_code("000001.SZ") == ("000001", "SZ")


def test_split_ts_code_bare_code():
    """裸码从代码派生 exchange。"""
    assert _split_ts_code("600519") == ("600519", "SH")
    assert _split_ts_code("000001") == ("000001", "SZ")
    assert _split_ts_code("300001") == ("300001", "SZ")
    assert _split_ts_code("830001") == ("830001", "BJ")


def test_format_partition():
    """YYYYMMDD → YYYY-MM-DD（hive 分区格式）。"""
    assert _format_partition("20260717") == "2026-07-17"


def test_transform_strips_ts_code_suffix():
    """transform 把 600519.SH 拆成 code=600519 + exchange=SH。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    assert len(clean) == 3
    first = clean[0]
    assert first["code"] == "600519"
    assert first["exchange"] == "SH"
    assert first["close"] == 1692.0


def test_transform_casts_types():
    """transform 把字符串/混合类型标准化。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    for r in clean:
        assert isinstance(r["open"], float)
        assert isinstance(r["close"], float)
        assert isinstance(r["code"], str)


def test_transform_injects_meta_fields():
    """transform 注入 5 个元数据字段。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    for r in clean:
        for f in ["__source", "__source_tool", "__fetched_at", "__params_hash", "__etl_run_id"]:
            assert f in r
        assert r["__source"] == "tushare"
        assert r["__source_tool"] == "daily"


def test_transform_volume_renamed_from_vol():
    """tushare 的 vol 字段重命名为 volume。"""
    raw = _load_fixture()
    clean = transform(raw, "20260717")
    assert "vol" not in clean[0]
    assert "volume" in clean[0]
    assert clean[0]["volume"] == 1234567.0


def test_transform_skips_error_rows():
    """工具返回的 error 行不应进 ODS。"""
    raw = [{"error": "rate limited"}]
    clean = transform(raw, "20260717")
    assert clean == []


def test_run_quality_failed_when_too_few_rows(tmp_path):
    """行数 <4000（生产阈值）时阻断，不写文件。"""
    raw = _load_fixture()  # 只 3 行
    with patch("etl.ods.equity_daily.mcp_client.call", return_value=raw):
        result = run("20260717", ods_root=tmp_path)
    assert result["status"] == "quality_failed"
    pq_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    assert not pq_file.exists()


def test_run_ok_with_lowered_threshold(tmp_path):
    """端到端：mock MCP + 降低 quality 阈值验证落地。"""
    raw = _load_fixture()
    with patch("etl.ods.equity_daily.mcp_client.call", return_value=raw):
        with patch("etl.ods.equity_daily.MIN_DAILY_ROWS", 1):
            result = run("20260717", ods_root=tmp_path)
    assert result["status"] == "ok"
    assert result["rows"] == 3
    pq_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    assert pq_file.exists()


def test_run_extract_failed_returns_error(tmp_path):
    """MCP 返回 error 时 status=extract_failed。"""
    with patch("etl.ods.equity_daily.mcp_client.call", return_value=[{"error": "rate limited"}]):
        result = run("20260717", ods_root=tmp_path)
    assert result["status"] == "extract_failed"
