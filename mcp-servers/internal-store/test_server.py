import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "cache" / "meta.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            source TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            PRIMARY KEY (source, tool_name, params_hash)
        );
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            strategy TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            sharpe REAL,
            max_drawdown REAL,
            annual_return REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            holdings TEXT NOT NULL,
            cash REAL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """
    )
    conn.commit()
    conn.close()
    return db_path


class TestQueryCache:
    def test_cache_miss(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import query_cache

            result = query_cache(source="akshare", tool_name="test_tool")
            assert result[0]["status"] == "cache_miss"


class TestListBacktestResults:
    def test_empty_results(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import list_backtest_results

            result = list_backtest_results()
            assert result == []
