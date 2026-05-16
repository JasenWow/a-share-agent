"""Tests for the paper-trader backtest engine."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch DB_PATH before importing modules that use it
_tmpdir = tempfile.mkdtemp()
_tmp_db = Path(_tmpdir) / "backtest.db"

import engine as engine_mod  # noqa: E402
import cost_model  # noqa: E402
from engine import BacktestEngine  # noqa: E402
from models import BarData, Position, Portfolio, SessionConfig, Signal  # noqa: E402
from performance import compute_performance  # noqa: E402

# Patch DB paths
engine_mod.DB_PATH = _tmp_db
engine_mod.PREDICTION_DB_PATH = _tmp_db.parent / "nonexistent_predictions.db"

import server as server_mod  # noqa: E402
from server import _init_db  # noqa: E402

server_mod.DB_PATH = _tmp_db


@pytest.fixture(autouse=True)
def init_test_db():
    """Initialize a fresh test database for each test."""
    # Ensure module-level DB paths point to our temp DB (may have been overwritten by other test files)
    engine_mod.DB_PATH = _tmp_db
    engine_mod.PREDICTION_DB_PATH = _tmp_db.parent / "nonexistent_predictions.db"
    server_mod.DB_PATH = _tmp_db

    _tmp_db.parent.mkdir(parents=True, exist_ok=True)
    if _tmp_db.exists():
        _tmp_db.unlink()
    conn = sqlite3.connect(str(_tmp_db))
    conn.executescript(Path(__file__).parent.joinpath("schema.sql").read_text())
    conn.commit()
    conn.close()
    yield
    if _tmp_db.exists():
        _tmp_db.unlink()


def _insert_session(session_id="test001", **kwargs):
    """Helper to insert a session into the test DB."""
    defaults = {
        "name": "test",
        "strategy": "test_strategy",
        "initial_capital": 1000000.0,
        "start_date": "20250102",
        "end_date": "20250110",
        "universe": json.dumps(["000001", "600519"]),
        "benchmark": "sh000300",
        "cost_commission": 0.00025,
        "cost_stamp_duty": 0.0005,
        "cost_slippage": 0.0005,
        "exclude_st": 1,
    }
    defaults.update(kwargs)
    conn = sqlite3.connect(str(_tmp_db))
    conn.execute(
        "INSERT INTO sessions (session_id, name, strategy, initial_capital, start_date, end_date, "
        "universe, benchmark, cost_commission, cost_stamp_duty, cost_slippage, exclude_st) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            defaults["name"],
            defaults["strategy"],
            defaults["initial_capital"],
            defaults["start_date"],
            defaults["end_date"],
            defaults["universe"],
            defaults["benchmark"],
            defaults["cost_commission"],
            defaults["cost_stamp_duty"],
            defaults["cost_slippage"],
            defaults["exclude_st"],
        ),
    )
    conn.commit()
    conn.close()


def _insert_trading_calendar():
    """Insert trading calendar entries for testing."""
    conn = sqlite3.connect(str(_tmp_db))
    for d in ["20250102", "20250103", "20250106", "20250107", "20250108", "20250109", "20250110"]:
        conn.execute(
            "INSERT OR REPLACE INTO trading_calendar (trade_date, is_trading_day) VALUES (?, 1)", (d,)
        )
    conn.commit()
    conn.close()


def _make_bar(date: str, open_: float, close: float, volume: float = 1e8, name: str = "测试") -> dict:
    return {
        "日期": date,
        "开盘": open_,
        "收盘": close,
        "最高": close * 1.01,
        "最低": open_ * 0.99,
        "成交量": volume,
        "名称": name,
    }


# === Cost Model Tests ===


class TestCostModel:
    def test_buy_cost(self):
        comm, stamp, slip, total = cost_model.calculate_buy_cost(100000, 10.0, 10000, 0.00025, 0.0005)
        assert comm == 25.0
        assert stamp == 0.0
        assert slip == 50.0
        assert total == 75.0

    def test_buy_cost_minimum_commission(self):
        comm, _, _, _ = cost_model.calculate_buy_cost(1000, 10.0, 100, 0.00025, 0.0005)
        assert comm == 5.0  # Minimum commission

    def test_sell_cost(self):
        comm, stamp, slip, total = cost_model.calculate_sell_cost(100000, 0.00025, 0.0005, 0.0005)
        assert comm == 25.0
        assert stamp == 50.0
        assert slip == 50.0
        assert total == 125.0

    def test_round_lot_size(self):
        assert cost_model.round_lot_size(150) == 100
        assert cost_model.round_lot_size(100) == 100
        assert cost_model.round_lot_size(99) == 0
        assert cost_model.round_lot_size(250) == 200

    def test_board_limit_main(self):
        assert cost_model.get_board_limit("000001") == 0.10
        assert cost_model.get_board_limit("600519") == 0.10

    def test_board_limit_chinext(self):
        assert cost_model.get_board_limit("300750") == 0.20

    def test_board_limit_star(self):
        assert cost_model.get_board_limit("688981") == 0.20

    def test_board_limit_bse(self):
        assert cost_model.get_board_limit("830799") == 0.30
        assert cost_model.get_board_limit("430047") == 0.30

    def test_board_limit_st(self):
        bar = BarData(date="20250102", open=5.0, close=5.0, high=5.0, low=5.0, volume=1e8, name="*ST测试")
        assert cost_model.get_board_limit("000001", bar) == 0.05

    def test_limit_up_detection(self):
        assert cost_model.is_limit_up(11.0, 10.0, 0.10) is True
        assert cost_model.is_limit_up(10.5, 10.0, 0.10) is False

    def test_limit_down_detection(self):
        assert cost_model.is_limit_down(9.0, 10.0, 0.10) is True
        assert cost_model.is_limit_down(9.5, 10.0, 0.10) is False

    def test_should_exclude_suspended(self):
        bar = BarData(date="20250102", open=10.0, close=10.0, high=10.0, low=10.0, volume=0, name="测试")
        config = SessionConfig(session_id="t", exclude_st=True)
        excluded, reason = cost_model.should_exclude("000001", bar, config)
        assert excluded is True
        assert reason == "suspended"

    def test_should_exclude_st(self):
        bar = BarData(date="20250102", open=5.0, close=5.0, high=5.0, low=5.0, volume=1e8, name="*ST测试")
        config = SessionConfig(session_id="t", exclude_st=True)
        excluded, reason = cost_model.should_exclude("000001", bar, config)
        assert excluded is True
        assert reason == "ST"

    def test_should_not_exclude_normal(self):
        bar = BarData(date="20250102", open=10.0, close=10.0, high=10.0, low=10.0, volume=1e8, name="平安银行")
        config = SessionConfig(session_id="t", exclude_st=True)
        excluded, reason = cost_model.should_exclude("000001", bar, config, prev_close=10.0)
        assert excluded is False

    def test_slippage(self):
        assert cost_model.apply_buy_slippage(10.0, 0.0005) == 10.0 * 1.0005
        assert cost_model.apply_sell_slippage(10.0, 0.0005) == 10.0 * 0.9995

    def test_max_buy_shares(self):
        shares = cost_model.calculate_max_buy_shares(100000, 10.0, 0.00025, 0.0005)
        assert shares > 0
        assert shares % 100 == 0


# === Models Tests ===


class TestPosition:
    def test_add_shares_new(self):
        pos = Position(stock_code="000001")
        pos.add_shares(1000, 10.0, "20250102")
        assert pos.shares == 1000
        assert pos.cost_basis == 10.0
        assert pos.entry_date == "20250102"

    def test_add_shares_average_cost(self):
        pos = Position(stock_code="000001")
        pos.add_shares(1000, 10.0, "20250102")
        pos.add_shares(1000, 12.0, "20250103")
        assert pos.shares == 2000
        assert pos.cost_basis == 11.0

    def test_remove_shares(self):
        pos = Position(stock_code="000001", shares=1000, sellable_shares=1000, cost_basis=10.0)
        pos.remove_shares(300)
        assert pos.shares == 700
        assert pos.sellable_shares == 700

    def test_unrealized_pnl(self):
        pos = Position(stock_code="000001", shares=1000, cost_basis=10.0, market_value=12000)
        assert pos.unrealized_pnl == 2000.0
        assert abs(pos.unrealized_pnl_pct - 0.2) < 1e-6

    def test_mark_sellable(self):
        pos = Position(stock_code="000001", shares=1000, sellable_shares=0)
        pos.mark_sellable()
        assert pos.sellable_shares == 1000


class TestPortfolio:
    def test_total_value(self):
        pos = Position(stock_code="000001", shares=1000, cost_basis=10.0, market_value=11000)
        p = Portfolio(cash=500000, positions={"000001": pos})
        assert p.total_value == 511000.0


# === Engine Tests ===


class TestBacktestEngine:
    def setup_method(self):
        _insert_session("test001")
        _insert_trading_calendar()

    def test_load_bar_data(self):
        engine = BacktestEngine("test001")
        data = {
            "000001": [_make_bar("20250102", 10.0, 10.5), _make_bar("20250103", 10.5, 11.0)],
            "600519": [_make_bar("20250102", 1500.0, 1520.0)],
        }
        result = engine.load_bar_data(["000001", "600519"], data)
        assert result["loaded"] == 2
        assert "000001" in engine.bar_data
        assert "20250102" in engine.bar_data["000001"]

    def test_load_bar_data_missing_stock(self):
        engine = BacktestEngine("test001")
        data = {"000001": [_make_bar("20250102", 10.0, 10.5)]}
        result = engine.load_bar_data(["000001", "999999"], data)
        assert result["loaded"] == 1
        assert "999999" in result["failed"]

    def test_register_signals(self):
        engine = BacktestEngine("test001")
        signals = [Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.5)]
        count = engine.register_signals(signals)
        assert count == 1
        assert "20250102" in engine.signals

    @patch("engine.get_trading_days")
    def test_run_simple_buy_hold(self, mock_trading_days):
        """Test a simple buy-and-hold strategy over 3 days."""
        mock_trading_days.return_value = ["20250102", "20250103", "20250106"]

        engine = BacktestEngine("test001")
        # Load bar data
        engine.load_bar_data(
            ["000001"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.5),
                    _make_bar("20250103", 10.5, 11.0),
                    _make_bar("20250106", 11.0, 11.5),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3850.0},
            ],
        )
        # Signal: buy 000001 at end of day 1, execute at day 2 open
        engine.register_signals([Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.5)])

        result = engine.run()
        assert result["status"] == "completed"
        assert result["total_trades"] == 1  # One buy trade

        # Check that position was created
        conn = sqlite3.connect(str(_tmp_db))
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades WHERE session_id = 'test001'").fetchall()
        assert len(trades) == 1
        assert trades[0]["direction"] == "buy"
        assert trades[0]["stock_code"] == "000001"

        # Check NAV records
        nav = conn.execute("SELECT * FROM daily_nav WHERE session_id = 'test001' ORDER BY trade_date").fetchall()
        assert len(nav) == 3
        conn.close()

    @patch("engine.get_trading_days")
    def test_run_t_plus_1_enforcement(self, mock_trading_days):
        """Test that T+1 rule is enforced: cannot sell on the same day as buy."""
        mock_trading_days.return_value = ["20250102", "20250103", "20250106"]

        engine = BacktestEngine("test001")
        engine.load_bar_data(
            ["000001"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.5),
                    _make_bar("20250103", 10.5, 11.0),
                    _make_bar("20250106", 11.0, 11.5),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3850.0},
            ],
        )
        # Buy signal on day 1, sell signal also on day 1
        # Buy executes on day 2 open, sell signal on day 1 should execute on day 2 open too
        # But the buy just happened so shares aren't sellable yet
        engine.register_signals(
            [
                Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.5),
                Signal(signal_date="20250102", stock_code="000001", direction="sell"),
            ]
        )

        engine.run()
        # The sell should not execute because shares aren't sellable on day 2
        conn = sqlite3.connect(str(_tmp_db))
        conn.row_factory = sqlite3.Row
        sells = conn.execute("SELECT * FROM trades WHERE session_id = 'test001' AND direction = 'sell'").fetchall()
        assert len(sells) == 0  # No sell executed
        buys = conn.execute("SELECT * FROM trades WHERE session_id = 'test001' AND direction = 'buy'").fetchall()
        assert len(buys) == 1  # But buy did execute
        conn.close()

    @patch("engine.get_trading_days")
    def test_run_buy_and_sell_next_day(self, mock_trading_days):
        """Test buy on day 1, sell on day 3 (T+1 satisfied)."""
        mock_trading_days.return_value = ["20250102", "20250103", "20250106", "20250107"]

        engine = BacktestEngine("test001")
        engine.load_bar_data(
            ["000001"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.5),
                    _make_bar("20250103", 10.5, 11.0),
                    _make_bar("20250106", 11.0, 10.0),
                    _make_bar("20250107", 10.0, 10.5),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3850.0},
                {"日期": "20250107", "收盘": 3830.0},
            ],
        )
        engine.register_signals(
            [
                Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.5),
                Signal(signal_date="20250103", stock_code="000001", direction="sell"),
            ]
        )

        result = engine.run()
        assert result["status"] == "completed"

        conn = sqlite3.connect(str(_tmp_db))
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades WHERE session_id = 'test001' ORDER BY id").fetchall()
        assert len(trades) == 2
        assert trades[0]["direction"] == "buy"
        assert trades[1]["direction"] == "sell"
        conn.close()


# === Performance Tests ===


class TestPerformance:
    def setup_method(self):
        _insert_session("perf_test", start_date="20250102", end_date="20250110", initial_capital=1000000.0)
        _insert_trading_calendar()

    @patch("engine.get_trading_days")
    def test_compute_performance(self, mock_trading_days):
        mock_trading_days.return_value = ["20250102", "20250103", "20250106", "20250107", "20250108"]

        engine = BacktestEngine("perf_test")
        engine.load_bar_data(
            ["000001"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.2),
                    _make_bar("20250103", 10.2, 10.5),
                    _make_bar("20250106", 10.5, 10.3),
                    _make_bar("20250107", 10.3, 10.8),
                    _make_bar("20250108", 10.8, 11.0),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3810.0},
                {"日期": "20250107", "收盘": 3840.0},
                {"日期": "20250108", "收盘": 3830.0},
            ],
        )
        engine.register_signals(
            [Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.3)]
        )
        engine.run()

        perf = compute_performance("perf_test")
        assert len(perf) == 1
        metrics = perf[0]
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "annual_return" in metrics
        assert "win_rate" in metrics
        assert metrics["trading_days"] == 5
        assert metrics["total_trades"] == 1

    def test_compute_performance_no_data(self):
        perf = compute_performance("nonexistent")
        assert len(perf) == 1
        assert "error" in perf[0]


# === Server Tool Tests ===


class TestServerTools:
    def setup_method(self):
        _init_db()

    def test_create_session(self):
        result = server_mod.create_session(start_date="20250102", end_date="20250110", name="test_session")
        assert len(result) == 1
        assert "session_id" in result[0]
        assert result[0]["status"] == "created"

    def test_list_sessions(self):
        server_mod.create_session(start_date="20250102", end_date="20250110")
        result = server_mod.list_sessions()
        assert len(result) >= 1

    def test_list_sessions_filter_status(self):
        server_mod.create_session(start_date="20250102", end_date="20250110")
        result = server_mod.list_sessions(status="created")
        assert all(r["status"] == "created" for r in result)

    def test_get_session_status_not_found(self):
        result = server_mod.get_session_status("nonexistent")
        assert len(result) == 1
        assert "error" in result[0]


# === Step-by-Step Mode Tests ===


class TestStepMode:
    def setup_method(self):
        _insert_session("step_test", start_date="20250102", end_date="20250110", universe=json.dumps(["000001", "600519"]))
        _insert_trading_calendar()

    @patch("engine.get_trading_days")
    def test_step_single_day(self, mock_trading_days):
        """Test stepping through one day at a time."""
        mock_trading_days.return_value = ["20250102", "20250103", "20250106"]

        engine = BacktestEngine("step_test")
        engine.load_bar_data(
            ["000001", "600519"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.5),
                    _make_bar("20250103", 10.5, 11.0),
                    _make_bar("20250106", 11.0, 11.5),
                ],
                "600519": [
                    _make_bar("20250102", 1500.0, 1520.0),
                    _make_bar("20250103", 1520.0, 1510.0),
                    _make_bar("20250106", 1510.0, 1530.0),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3850.0},
            ],
        )

        # Step 1: First day
        result = engine.step()
        assert result["status"] == "running"
        assert result["trade_date"] == "20250102"
        assert result["day_index"] == 1
        assert result["remaining_days"] == 2
        assert "000001" in result["market_data"]
        assert result["nav"] == 1000000.0  # No positions yet

        # Submit buy signal for today (executes tomorrow at open)
        engine.register_signals([Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.5)])

        # Step 2: Second day - buy executes at today's open
        result = engine.step()
        assert result["status"] == "running"
        assert result["trade_date"] == "20250103"
        assert len(result["positions"]) == 1
        assert result["positions"][0]["stock_code"] == "000001"

        # Check trade was recorded
        conn = sqlite3.connect(str(_tmp_db))
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades WHERE session_id = 'step_test'").fetchall()
        assert len(trades) == 1
        assert trades[0]["direction"] == "buy"
        conn.close()

        # Step 3: Third day
        result = engine.step()
        assert result["status"] == "running"
        assert result["trade_date"] == "20250106"
        assert result["remaining_days"] == 0

    @patch("engine.get_trading_days")
    def test_step_completed(self, mock_trading_days):
        """Test that stepping past the end marks session completed."""
        mock_trading_days.return_value = ["20250102"]

        engine = BacktestEngine("step_test")
        engine.load_bar_data(
            ["000001"],
            {"000001": [_make_bar("20250102", 10.0, 10.5)]},
        )
        engine.load_benchmark([{"日期": "20250102", "收盘": 3800.0}])

        # Step through the only day
        engine.step()

        # Step again - should be completed
        result = engine.step()
        assert result["status"] == "completed"

    @patch("engine.get_trading_days")
    def test_step_with_daily_decisions(self, mock_trading_days):
        """Test the full agent workflow: step -> observe -> decide -> step."""
        mock_trading_days.return_value = ["20250102", "20250103", "20250106", "20250107"]

        engine = BacktestEngine("step_test")
        engine.load_bar_data(
            ["000001", "600519"],
            {
                "000001": [
                    _make_bar("20250102", 10.0, 10.5),
                    _make_bar("20250103", 10.5, 11.0),
                    _make_bar("20250106", 11.0, 10.0),
                    _make_bar("20250107", 10.0, 10.5),
                ],
                "600519": [
                    _make_bar("20250102", 1500.0, 1520.0),
                    _make_bar("20250103", 1520.0, 1530.0),
                    _make_bar("20250106", 1530.0, 1510.0),
                    _make_bar("20250107", 1510.0, 1520.0),
                ],
            },
        )
        engine.load_benchmark(
            [
                {"日期": "20250102", "收盘": 3800.0},
                {"日期": "20250103", "收盘": 3820.0},
                {"日期": "20250106", "收盘": 3810.0},
                {"日期": "20250107", "收盘": 3840.0},
            ],
        )

        # Day 1: observe market, decide to buy 000001
        r1 = engine.step()
        assert r1["trade_date"] == "20250102"
        assert "000001" in r1["market_data"]
        engine.register_signals([Signal(signal_date="20250102", stock_code="000001", direction="buy", target_weight=0.4)])

        # Day 2: 000001 bought at open, now decide to buy 600519 too
        r2 = engine.step()
        assert r2["trade_date"] == "20250103"
        assert len(r2["positions"]) == 1
        engine.register_signals([Signal(signal_date="20250103", stock_code="600519", direction="buy", target_weight=0.3)])

        # Day 3: 600519 bought, 000001 still held (not sellable on day 2, now sellable on day 3)
        r3 = engine.step()
        assert r3["trade_date"] == "20250106"
        assert len(r3["positions"]) == 2  # Both held

        # Agent decides to sell 000001 (now sellable)
        engine.register_signals([Signal(signal_date="20250106", stock_code="000001", direction="sell")])

        # Day 4: 000001 sold at open
        r4 = engine.step()
        assert r4["trade_date"] == "20250107"
        assert len(r4["positions"]) == 1
        assert r4["positions"][0]["stock_code"] == "600519"

        # Verify total trades
        conn = sqlite3.connect(str(_tmp_db))
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades WHERE session_id = 'step_test' ORDER BY id").fetchall()
        assert len(trades) == 3  # buy 000001, buy 600519, sell 000001
        assert trades[0]["direction"] == "buy"
        assert trades[0]["stock_code"] == "000001"
        assert trades[1]["direction"] == "buy"
        assert trades[1]["stock_code"] == "600519"
        assert trades[2]["direction"] == "sell"
        assert trades[2]["stock_code"] == "000001"
        conn.close()
