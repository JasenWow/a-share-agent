"""Tests for ETL config module."""

from pathlib import Path

from common.config import (
    WAREHOUSE_ROOT,
    MCP_AKSHARE_URL,
    MCP_TUSHARE_URL,
    MCP_INTERNAL_STORE_URL,
    ensure_dirs,
)


def test_warehouse_root_under_data():
    """WAREHOUSE_ROOT 默认指向 <repo>/data/warehouse。"""
    assert isinstance(WAREHOUSE_ROOT, Path)
    assert WAREHOUSE_ROOT.name == "warehouse"
    assert WAREHOUSE_ROOT.parent.name == "data"


def test_mcp_urls_defaults():
    """MCP URL 默认值正确（与 .env.example 端口一致）。"""
    assert MCP_AKSHARE_URL == "http://localhost:8000/mcp"
    assert MCP_TUSHARE_URL == "http://localhost:8001/mcp"
    assert MCP_INTERNAL_STORE_URL == "http://localhost:8002/mcp"


def test_mcp_urls_respect_env(monkeypatch):
    """MCP 端口可通过环境变量覆盖。"""
    monkeypatch.setenv("AKSHARE_PORT", "9000")
    monkeypatch.setenv("TUSHARE_PORT", "9001")
    monkeypatch.setenv("INTERNAL_STORE_PORT", "9002")
    # 重新 import 验证 env 生效
    import importlib
    import common.config

    importlib.reload(common.config)
    assert common.config.MCP_AKSHARE_URL == "http://localhost:9000/mcp"
    assert common.config.MCP_TUSHARE_URL == "http://localhost:9001/mcp"
    assert common.config.MCP_INTERNAL_STORE_URL == "http://localhost:9002/mcp"


def test_ensure_dirs_creates_structure(tmp_path, monkeypatch):
    """ensure_dirs 建出 warehouse/ods/_logs 三级目录。"""
    monkeypatch.setattr("common.config.WAREHOUSE_ROOT", tmp_path / "warehouse")
    monkeypatch.setattr("common.config.ODS_ROOT", tmp_path / "warehouse" / "ods")
    monkeypatch.setattr("common.config.LOGS_DIR", tmp_path / "warehouse" / "_logs")
    ensure_dirs()
    assert (tmp_path / "warehouse").is_dir()
    assert (tmp_path / "warehouse" / "ods").is_dir()
    assert (tmp_path / "warehouse" / "_logs").is_dir()
