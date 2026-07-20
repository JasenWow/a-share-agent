"""Tests for ETL config module.

After Phase 3 restructure:
- Project-level config (ROOT, DATA_ROOT, WAREHOUSE_ROOT, MCP URLs) lives
  in aquan.core.config and has its own smoke tests.
- ETL-specific config (ODS_ROOT, META_DB_PATH, LOGS_DIR) lives here in
  etl.config, derived from aquan.core.config.WAREHOUSE_ROOT.

These tests cover the ETL derivations and the ensure_dirs delegation.
"""

from pathlib import Path

from etl.config import (
    LOGS_DIR,
    META_DB_PATH,
    ODS_ROOT,
    ensure_dirs,
)


def test_etl_paths_derived_from_warehouse_root():
    """ODS_ROOT / META_DB_PATH / LOGS_DIR sit under WAREHOUSE_ROOT."""
    from aquan.core.config import WAREHOUSE_ROOT

    assert ODS_ROOT == WAREHOUSE_ROOT / "ods"
    assert META_DB_PATH == WAREHOUSE_ROOT / "meta.db"
    assert LOGS_DIR == WAREHOUSE_ROOT / "_logs"


def test_warehouse_root_under_data():
    """WAREHOUSE_ROOT 默认指向 <repo>/data/warehouse。"""
    from aquan.core.config import WAREHOUSE_ROOT

    assert isinstance(WAREHOUSE_ROOT, Path)
    assert WAREHOUSE_ROOT.name == "warehouse"
    assert WAREHOUSE_ROOT.parent.name == "data"


def test_mcp_urls_defaults():
    """MCP URL 默认值正确（与 .env.example 端口一致）。"""
    from aquan.core.config import (
        MCP_AKSHARE_URL,
        MCP_INTERNAL_STORE_URL,
        MCP_TUSHARE_URL,
    )

    assert MCP_AKSHARE_URL == "http://localhost:8000/mcp"
    assert MCP_TUSHARE_URL == "http://localhost:8001/mcp"
    assert MCP_INTERNAL_STORE_URL == "http://localhost:8002/mcp"


def test_mcp_urls_respect_env(monkeypatch):
    """MCP 端口可通过环境变量覆盖。"""
    import importlib

    monkeypatch.setenv("AKSHARE_PORT", "9000")
    monkeypatch.setenv("TUSHARE_PORT", "9001")
    monkeypatch.setenv("INTERNAL_STORE_PORT", "9002")

    import aquan.core.config as cfg

    importlib.reload(cfg)
    assert cfg.MCP_AKSHARE_URL == "http://localhost:9000/mcp"
    assert cfg.MCP_TUSHARE_URL == "http://localhost:9001/mcp"
    assert cfg.MCP_INTERNAL_STORE_URL == "http://localhost:9002/mcp"


def test_ensure_dirs_creates_structure(tmp_path, monkeypatch):
    """ensure_dirs 建出 warehouse/ods/_logs 三级目录。"""
    monkeypatch.setattr("aquan.core.config.WAREHOUSE_ROOT", tmp_path / "warehouse")
    ensure_dirs()
    assert (tmp_path / "warehouse").is_dir()
    assert (tmp_path / "warehouse" / "ods").is_dir()
    assert (tmp_path / "warehouse" / "_logs").is_dir()
