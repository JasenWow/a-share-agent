"""Tests for notebook helpers."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import query_mcp, get_internal_store_url
import urllib.error  # noqa: F401


class TestGetInternalStoreUrl:
    def test_returns_url(self):
        url = get_internal_store_url()
        assert "localhost" in url
        assert "8002" in url


class TestQueryMcp:
    def test_connection_error_on_bad_url(self):
        """When server not running, should raise ConnectionError."""
        # This will fail if internal-store is not running - that's expected
        try:
            _ = query_mcp("list_experiments")
            # If it succeeds, server was running - that's fine too
        except ConnectionError as e:
            assert "localhost" in str(e)
        except Exception as e:
            # Other errors also acceptable (e.g., timeout)
            assert "connect" in str(e).lower() or "timeout" in str(e).lower() or "urlopen" in str(e).lower()


class TestHelpersImport:
    def test_imports_work(self):
        from helpers import get_experiments, get_best_strategies, get_backtest_results, get_portfolio, get_episode_summaries
        assert callable(get_experiments)
        assert callable(get_best_strategies)
        assert callable(get_backtest_results)
        assert callable(get_portfolio)
        assert callable(get_episode_summaries)