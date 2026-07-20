"""ETL-specific path configuration.

Derives ETL paths (ODS root, meta.db, logs) from the project-level config
in aquan.core.config. Kept as a thin ETL-local module so ETL code says
`from etl.config import ODS_ROOT` rather than recomputing the path inline.

Historical note: the pre-restructure common/config.py mixed project-level
config (ROOT, DATA_ROOT, MCP URLs) with ETL-specific derivations. The
project-level pieces moved to aquan.core.config in Phase 1; only the
ETL derivations live here now.
"""

from __future__ import annotations

from aquan.core.config import WAREHOUSE_ROOT

# DuckDB metadata database (catalog, jobs, quality state).
META_DB_PATH = WAREHOUSE_ROOT / "meta.db"

# ODS Parquet root.
ODS_ROOT = WAREHOUSE_ROOT / "ods"

# ETL run logs.
LOGS_DIR = WAREHOUSE_ROOT / "_logs"


def ensure_dirs() -> None:
    """Create the warehouse directory structure if missing."""
    from aquan.core.config import ensure_warehouse_dirs

    ensure_warehouse_dirs()
