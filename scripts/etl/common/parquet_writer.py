"""幂等 Parquet 写入：按分区原子覆盖。

分区路径：{ods_root}/{domain}/{partition_col}={partition_val}/part-0.parquet
原子性：先写 .tmp，校验后 os.replace 覆盖
"""
from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def write(
    domain: str,
    partition_col: str,
    partition_val: str,
    rows: list[dict],
    mode: str = "overwrite",
    ods_root: Path | None = None,
) -> dict:
    """写入 Parquet 分区。

    Args:
        domain:         数据域（如 equity_daily）
        partition_col:  分区列名（如 dt / period）
        partition_val:  分区值（如 2026-07-17 / 2026-07 / 2024Q4）
        rows:           数据行（list[dict]）
        mode:           overwrite（本期仅支持此模式）
        ods_root:       ODS 根目录（默认从 config 读）

    Returns:
        {"status": "ok", "rows": N, "path": "warehouse/ods/..."}

    Raises:
        ValueError: rows 为空（不写无效 parquet）
        RuntimeError: 写后读校验失败
    """
    if not rows:
        raise ValueError("Cannot write empty rows (would create invalid parquet)")

    if ods_root is None:
        from common.config import ODS_ROOT
        ods_root = ODS_ROOT

    partition_dir = ods_root / domain / f"{partition_col}={partition_val}"
    partition_dir.mkdir(parents=True, exist_ok=True)

    target = partition_dir / "part-0.parquet"
    tmp = partition_dir / "part-0.parquet.tmp"

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, tmp, compression="snappy")

    # 用 ParquetFile.read() 单文件读取，避免 dataset API 的跨文件类型合并
    # （from_pylist 对低基数列会推断为 dictionary，write/read 一致即可）
    verify = pq.ParquetFile(tmp).read()
    if verify.num_rows != len(rows):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Parquet verify failed: wrote {len(rows)} rows but read back {verify.num_rows}"
        )

    os.replace(tmp, target)

    return {
        "status": "ok",
        "rows": len(rows),
        "path": str(target.relative_to(ods_root.parent)),
    }
