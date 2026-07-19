"""Tests for parquet_writer."""
import pyarrow.parquet as pq
import pytest

from common.parquet_writer import write


def test_write_creates_parquet_file(tmp_path):
    """写入生成 parquet 文件，行数正确。"""
    rows = [
        {"code": "600519", "close": 1692.0, "__source": "tushare"},
        {"code": "000001", "close": 12.5, "__source": "tushare"},
    ]
    result = write(
        domain="equity_daily",
        partition_col="dt",
        partition_val="2026-07-17",
        rows=rows,
        mode="overwrite",
        ods_root=tmp_path,
    )
    assert result["status"] == "ok"
    assert result["rows"] == 2
    parquet_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    assert parquet_file.exists()
    table = pq.read_table(parquet_file)
    assert table.num_rows == 2


def test_write_overwrite_is_idempotent(tmp_path):
    """同分区重跑覆盖，不产生重复。"""
    rows1 = [{"code": "600519", "close": 1692.0}]
    rows2 = [{"code": "600519", "close": 1700.0}]

    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows1, mode="overwrite", ods_root=tmp_path)
    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows2, mode="overwrite", ods_root=tmp_path)

    parquet_file = tmp_path / "equity_daily" / "dt=2026-07-17" / "part-0.parquet"
    table = pq.read_table(parquet_file)
    assert table.num_rows == 1
    assert table.to_pylist()[0]["close"] == 1700.0


def test_write_empty_rows_raises(tmp_path):
    """空 rows 报错，不写文件。"""
    with pytest.raises(ValueError, match="empty"):
        write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
              rows=[], mode="overwrite", ods_root=tmp_path)


def test_write_atomic_no_tmp_left(tmp_path):
    """写入后无 .tmp 残留文件。"""
    rows = [{"code": "600519", "close": 1692.0}]
    write(domain="equity_daily", partition_col="dt", partition_val="2026-07-17",
          rows=rows, mode="overwrite", ods_root=tmp_path)
    tmps = list(tmp_path.rglob("*.tmp"))
    assert tmps == []


def test_write_monthly_partition(tmp_path):
    """月度分区路径格式正确。"""
    rows = [{"index_code": "000300", "code": "600519"}]
    write(domain="index_constituents", partition_col="dt", partition_val="2026-07",
          rows=rows, mode="overwrite", ods_root=tmp_path)
    parquet_file = tmp_path / "index_constituents" / "dt=2026-07" / "part-0.parquet"
    assert parquet_file.exists()


def test_write_partition_path_format(tmp_path):
    """分区路径是 hive 格式 {col}={val}。"""
    rows = [{"code": "600519"}]
    write(domain="equity_daily", partition_col="period", partition_val="2024Q4",
          rows=rows, mode="overwrite", ods_root=tmp_path)
    parquet_file = tmp_path / "equity_daily" / "period=2024Q4" / "part-0.parquet"
    assert parquet_file.exists()
