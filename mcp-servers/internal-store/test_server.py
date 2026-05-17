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
            assert rows[0]["state"] == json.dumps(state, sort_keys=True)


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


class TestGetSimilarStates:
    def test_finds_matching_states(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, get_similar_states

            record_experiment("exp1", {"type": "momentum"}, {"market_regime": "bull", "volatility": 0.2}, {"final_nav": 1.1})
            record_experiment("exp2", {"type": "value"}, {"market_regime": "bull", "volatility": 0.25}, {"final_nav": 1.05})
            record_experiment("exp3", {"type": "momentum"}, {"market_regime": "bear", "volatility": 0.4}, {"final_nav": 0.9})
            results = get_similar_states({"market_regime": "bull", "volatility": 0.2}, top_k=5)
            # Both exp1 and exp2 share market_regime=bull; exp1 also shares volatility
            assert len(results) >= 2
            assert results[0]["name"] == "exp1"

    def test_returns_empty_when_no_match(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import get_similar_states

            results = get_similar_states({"market_regime": "range"}, top_k=5)
            assert results == []

    def test_respects_top_k(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, get_similar_states

            for i in range(10):
                record_experiment(f"exp_{i}", {"type": "a"}, {"market_regime": "bull"}, {"final_nav": 1.0 + i * 0.01})
            results = get_similar_states({"market_regime": "bull"}, top_k=3)
            assert len(results) == 3


class TestGetFailures:
    def test_get_failures_returns_negative_returns(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, get_failures

            record_experiment("good_exp", {"type": "a"}, {}, {"final_nav": 1.3})
            record_experiment("bad_exp", {"type": "b"}, {}, {"final_nav": 0.85})
            record_experiment("ok_exp", {"type": "c"}, {}, {"final_nav": 1.0})
            failures = get_failures()
            assert len(failures) == 1
            assert failures[0]["name"] == "bad_exp"

    def test_get_failures_with_limit(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, get_failures

            for i in range(5):
                record_experiment(f"bad_{i}", {"type": "b"}, {}, {"final_nav": 0.8})
            failures = get_failures(limit=3)
            assert len(failures) == 3

    def test_get_failures_empty(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import get_failures

            failures = get_failures()
            assert failures == []


class TestNoTemplateArtifacts:
    def test_no_list_cache_function_exists(self):
        """Verify no broken list_cache function exists in the server module."""
        import server
        # The server module should not have any reference to ak.new_function or df_to_json in list_cache
        import inspect
        source = inspect.getsource(server)
        assert "def list_cache" not in source, "list_cache function should be removed"


class TestGetTransitionMatrix:
    def test_aggregates_transitions_by_strategy(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import record_experiment, record_transition, get_transition_matrix
            import json as json_mod

            record_experiment("exp1", {"type": "momentum"}, {"market_regime": "bull"}, {"final_nav": 1.1})
            state = {"market_regime": "bull"}
            strategy_a = {"factors": ["momentum_20d"], "action": "buy"}
            strategy_b = {"factors": ["value_pe"], "action": "sell"}
            record_transition(1, state, strategy_a, {"pnl": 100}, {"market_regime": "bull"})
            record_transition(1, state, strategy_a, {"pnl": 200}, {"market_regime": "bull"})
            record_transition(1, state, strategy_b, {"pnl": -50}, {"market_regime": "bull"})
            matrix = get_transition_matrix(state)
            a_key = json_mod.dumps(strategy_a, sort_keys=True)
            assert a_key in matrix
            assert matrix[a_key]["count"] == 2
            assert matrix[a_key]["avg_reward"] == 150.0

    def test_empty_when_no_transitions(self, temp_db):
        with patch("server.DB_PATH", temp_db):
            from server import get_transition_matrix

            matrix = get_transition_matrix({"market_regime": "bear"})
            assert matrix == {}
