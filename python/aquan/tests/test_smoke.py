"""Smoke tests for the aquan public layer (Phase 1).

These verify the package skeleton imports cleanly and key invariants hold.
They do NOT exercise network or filesystem operations — those belong with
the consuming code (etl tests, mcp-server tests).
"""

from __future__ import annotations

import pytest


def test_version_exposed():
    from aquan import __version__

    assert isinstance(__version__, str) and __version__


def test_core_config_paths_resolve_to_repo():
    from aquan.core.config import DATA_ROOT, ROOT, WAREHOUSE_ROOT

    # ROOT must be the repo root (contains python/ and RESTRUCTURE-PLAN.md).
    assert (ROOT / "python").is_dir()
    assert (ROOT / "RESTRUCTURE-PLAN.md").is_file()
    # WAREHOUSE_ROOT is under DATA_ROOT.
    assert WAREHOUSE_ROOT == DATA_ROOT / "warehouse"


def test_core_config_mcp_urls_have_default_ports():
    from aquan.core.config import MCP_AKSHARE_URL, MCP_INTERNAL_STORE_URL, MCP_TUSHARE_URL

    assert ":8000/mcp" in MCP_AKSHARE_URL
    assert ":8001/mcp" in MCP_TUSHARE_URL
    assert ":8002/mcp" in MCP_INTERNAL_STORE_URL


def test_errors_mcperror_is_aquanerror():
    from aquan.core.errors import AquanError
    from aquan.utils.http import McpError

    assert issubclass(McpError, AquanError)


def test_hashing_is_order_independent():
    from aquan.utils.hashing import params_hash

    assert params_hash({"a": 1, "b": 2}) == params_hash({"b": 2, "a": 1})
    assert params_hash({"a": 1}) != params_hash({"a": 2})


def test_io_write_rejects_empty_rows():
    from aquan.utils.io import write

    with pytest.raises(ValueError, match="empty"):
        write("equity_daily", "dt", "2026-01-01", [])


def test_metrics_compile_query_smoke():
    from aquan.metrics import compile_query, list_metrics

    # Sanity: catalog is populated.
    assert len(list_metrics()) >= 10

    # Compile a known query shape (no DB execution, just string).
    sql = compile_query(metric="icir", dimensions=["universe"], filters={"universe": "csi300"})
    assert "SELECT" in sql.upper()
    assert "FROM" in sql.upper()
    assert "csi300" in sql


def test_cli_main_returns_zero_for_version_like_invocation():
    from aquan.cli import main

    # No args -> argparse requires a subcommand and exits non-zero via SystemExit.
    # We confirm main() surfaces this rather than silently returning 0.
    with pytest.raises(SystemExit):
        main([])


def test_cli_main_health_action_runs():
    """Calling a real subcommand should reach the dispatch layer (argparse
    parses successfully). We don't exercise MCP here — `health` is the
    cheapest action and we accept a non-zero exit if the MCP server is down.
    """
    from aquan.cli import main

    # main() returns the subprocess exit code; we only assert it doesn't crash
    # at the argparse/dispatch layer (it'll be 0 or 1 depending on MCP availability).
    rc = main(["stock", "health"])
    assert rc in (0, 1)
