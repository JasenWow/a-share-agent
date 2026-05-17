import json
import pytest
import sqlite3
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
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            strategy TEXT NOT NULL,
            params TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            state TEXT NOT NULL,
            strategy TEXT NOT NULL,
            reward TEXT NOT NULL,
            next_state TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS episode_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            final_nav REAL NOT NULL,
            sharpe REAL NOT NULL,
            max_drawdown REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
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


class TestRecordExperiment:
    def test_record_experiment_basic(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment

            strategy = {"type": "momentum", "period": 20}
            params = {"lookback": 60, "rebalance": "monthly"}
            result_data = {"final_nav": 1.15, "sharpe": 1.8, "max_drawdown": 0.12}
            rows = record_experiment("test_exp", strategy, params, result_data)
            assert len(rows) == 1
            assert rows[0]["name"] == "test_exp"
            assert rows[0]["strategy"] == json.dumps(strategy)

    def test_list_experiments(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, list_experiments

            strategy = {"type": "mean_reversion"}
            params = {"window": 30}
            result_data = {"final_nav": 1.05}
            record_experiment("exp1", strategy, params, result_data)
            record_experiment("exp2", strategy, params, result_data)
            rows = list_experiments()
            assert len(rows) == 2


class TestGetBestStrategies:
    def test_get_best_strategies(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, get_best_strategies

            strategy = {"type": "momentum"}
            params = {"period": 20}
            record_experiment("exp1", strategy, params, {"final_nav": 1.1, "sharpe": 1.0, "max_drawdown": 0.1})
            record_experiment("exp2", strategy, params, {"final_nav": 1.3, "sharpe": 2.0, "max_drawdown": 0.05})
            record_experiment("exp3", strategy, params, {"final_nav": 1.2, "sharpe": 1.5, "max_drawdown": 0.08})
            best = get_best_strategies(top_k=2)
            assert len(best) == 2
            assert best[0]["final_nav"] == 1.3
            assert best[1]["final_nav"] == 1.2


class TestRecordTransition:
    def test_record_transition_basic(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_transition

            state = {"position": 0.5, "cash": 50000}
            strategy = {"action": "buy", "volume": 100}
            reward = {"pnl": 1000}
            next_state = {"position": 0.6, "cash": 49000}
            rows = record_transition(1, state, strategy, reward, next_state)
            assert len(rows) == 1
            assert rows[0]["experiment_id"] == 1
            assert rows[0]["state"] == json.dumps(state)


class TestRecordEpisodeSummary:
    def test_record_episode_summary_basic(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_episode_summary

            rows = record_episode_summary(
                period="2024Q1",
                initial_capital=1000000,
                final_nav=1150000,
                sharpe=1.8,
                max_drawdown=0.12,
            )
            assert len(rows) == 1
            assert rows[0]["period"] == "2024Q1"
            assert rows[0]["final_nav"] == 1150000

    def test_list_episode_summaries(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_episode_summary, list_episode_summaries

            record_episode_summary("2024Q1", 1000000, 1100000, 1.5, 0.1)
            record_episode_summary("2024Q2", 1100000, 1150000, 1.8, 0.12)
            rows = list_episode_summaries()
            assert len(rows) == 2


class TestNoTemplateArtifacts:
    def test_no_list_cache_function_exists(self):
        """Verify no broken list_cache function exists in the server module."""
        import server
        # The server module should not have any reference to ak.new_function or df_to_json in list_cache
        import inspect
        source = inspect.getsource(server)
        assert "def list_cache" not in source, "list_cache function should be removed"
