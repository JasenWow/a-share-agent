"""ODS 数据字典（catalog）CRUD。

catalog 表存 DuckDB，记录每个 ODS 表的元信息（数据源、分区、schema、所有者）。
"""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_catalog(conn: duckdb.DuckDBPyConnection) -> None:
    """建 catalog 表（幂等）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ods_catalog (
            table_name      TEXT PRIMARY KEY,
            domain          TEXT NOT NULL,
            source_mcp      TEXT NOT NULL,
            source_tool     TEXT NOT NULL,
            partition_col   TEXT NOT NULL,
            partition_grain TEXT NOT NULL,
            schema_json     TEXT NOT NULL,
            description     TEXT,
            owner           TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )


def register(conn: duckdb.DuckDBPyConnection, entry: dict) -> None:
    """注册或更新一个 ODS 表（upsert）。"""
    now = _now()
    conn.execute(
        """
        INSERT INTO ods_catalog (
            table_name, domain, source_mcp, source_tool,
            partition_col, partition_grain, schema_json,
            description, owner, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (table_name) DO UPDATE SET
            domain = EXCLUDED.domain,
            source_mcp = EXCLUDED.source_mcp,
            source_tool = EXCLUDED.source_tool,
            partition_col = EXCLUDED.partition_col,
            partition_grain = EXCLUDED.partition_grain,
            schema_json = EXCLUDED.schema_json,
            description = EXCLUDED.description,
            owner = EXCLUDED.owner,
            updated_at = EXCLUDED.updated_at
        """,
        [
            entry["table_name"],
            entry["domain"],
            entry["source_mcp"],
            entry["source_tool"],
            entry["partition_col"],
            entry["partition_grain"],
            entry["schema_json"],
            entry.get("description", ""),
            entry.get("owner", "etl"),
            now,
            now,
        ],
    )


def get(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict | None:
    """查单个表，无则 None。"""
    row = conn.execute("SELECT * FROM ods_catalog WHERE table_name = ?", [table_name]).fetchone()
    if not row:
        return None
    cols = [d[0] for d in conn.description]
    return dict(zip(cols, row))


def list_all(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """列出所有 catalog 记录，按 table_name 排序。"""
    rows = conn.execute("SELECT * FROM ods_catalog ORDER BY table_name").fetchall()
    cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]
