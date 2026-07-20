"""Idempotent Parquet writer: atomic per-partition overwrite.

Partition path: {ods_root}/{domain}/{partition_col}={partition_val}/part-0.parquet
Atomicity: write to .tmp, verify, then os.replace to target.
"""

from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from aquan.core.config import WAREHOUSE_ROOT


def write(
    domain: str,
    partition_col: str,
    partition_val: str,
    rows: list[dict],
    mode: str = "overwrite",
    ods_root: Path | None = None,
) -> dict:
    """Write a Parquet partition.

    Args:
        domain:         data domain (e.g. equity_daily)
        partition_col:  partition column name (e.g. dt / period)
        partition_val:  partition value (e.g. 2026-07-17 / 2026-07 / 2024Q4)
        rows:           data rows (list[dict])
        mode:           overwrite (only mode supported in this phase)
        ods_root:       ODS root directory (default: derived from WAREHOUSE_ROOT)

    Returns:
        {"status": "ok", "rows": N, "path": "warehouse/ods/..."}

    Raises:
        ValueError: rows is empty (would create an invalid parquet file)
        RuntimeError: post-write read-back verification failed
    """
    if not rows:
        raise ValueError("Cannot write empty rows (would create invalid parquet)")

    if ods_root is None:
        ods_root = WAREHOUSE_ROOT / "ods"

    partition_dir = ods_root / domain / f"{partition_col}={partition_val}"
    partition_dir.mkdir(parents=True, exist_ok=True)

    target = partition_dir / "part-0.parquet"
    tmp = partition_dir / "part-0.parquet.tmp"

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, tmp, compression="snappy")

    # Read back via ParquetFile.read() to avoid dataset API cross-file type merging
    # (from_pylist infers low-cardinality columns as dictionary; write/read consistency holds).
    verify = pq.ParquetFile(tmp).read()
    if verify.num_rows != len(rows):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Parquet verify failed: wrote {len(rows)} rows but read back {verify.num_rows}")

    os.replace(tmp, target)

    return {
        "status": "ok",
        "rows": len(rows),
        "path": str(target.relative_to(ods_root.parent)),
    }
