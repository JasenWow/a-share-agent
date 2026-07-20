"""aquan project configuration: paths and MCP endpoints.

Reads from environment with sensible defaults. This is the project-level
config — domain-specific derivations (e.g. ODS_ROOT for ETL) live in their
consuming packages and import from here.

Environment variables:
- DATA_ROOT          — data directory root (default: <repo>/data)
- AKSHARE_PORT       — akshare MCP server port (default: 8000)
- TUSHARE_PORT       — tushare MCP server port (default: 8001)
- INTERNAL_STORE_PORT— internal-store MCP server port (default: 8002)
- TUSHARE_TOKEN      — tushare API token (no default; required for tushare)
"""

from __future__ import annotations

import os
from pathlib import Path

# Project root: python/aquan/core/config.py -> up 4 levels = repo root.
# During migration (Phase 1-4) this python/ lives inside the repo at <repo>/python/,
# so parents[3] is the repo root. After Phase 4, this stays the same shape.
ROOT = Path(__file__).resolve().parents[3]

# Data root (shares DATA_ROOT env var with internal-store MCP server).
DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(ROOT / "data")))

# Warehouse root (DuckDB + Parquet).
WAREHOUSE_ROOT = DATA_ROOT / "warehouse"

# MCP server endpoints (ports overridable via env, matches .env.example).
AKSHARE_PORT = os.environ.get("AKSHARE_PORT", "8000")
TUSHARE_PORT = os.environ.get("TUSHARE_PORT", "8001")
INTERNAL_STORE_PORT = os.environ.get("INTERNAL_STORE_PORT", "8002")

MCP_AKSHARE_URL = f"http://localhost:{AKSHARE_PORT}/mcp"
MCP_TUSHARE_URL = f"http://localhost:{TUSHARE_PORT}/mcp"
MCP_INTERNAL_STORE_URL = f"http://localhost:{INTERNAL_STORE_PORT}/mcp"


def ensure_warehouse_dirs() -> None:
    """Create warehouse directory structure if missing."""
    WAREHOUSE_ROOT.mkdir(parents=True, exist_ok=True)
    (WAREHOUSE_ROOT / "ods").mkdir(parents=True, exist_ok=True)
    (WAREHOUSE_ROOT / "_logs").mkdir(parents=True, exist_ok=True)
