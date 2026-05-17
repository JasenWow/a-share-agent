import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pytest

from scripts.simulator import TradingSimulator


class TestMultiDayTrading:
    def test_buy_day1_sell_day2_allowed(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        day1 = date(2024, 1, 2)
        day2 = date(2024, 1, 3)

        buy_result = sim.buy("600519", price=1800.0, shares=100, trade_date=day1)
        assert buy_result["success"] is True, f"Buy day1 failed: {buy_result}"
        assert sim.positions["600519"].shares == 100

        sell_day2 = sim.sell("600519", price=1820.0, shares=100, trade_date=day2)
        assert sell_day2["success"] is True, "Next-day sell should be allowed"
        assert sell_day2["shares"] == 100
        assert sell_day2["realized_pnl"] > 0

        assert "600519" not in sim.positions

    def test_buy_day1_sell_same_day_rejected(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        day1 = date(2024, 1, 2)

        buy_result = sim.buy("600519", price=1800.0, shares=100, trade_date=day1)
        assert buy_result["success"] is True

        sell_same_day = sim.sell("600519", price=1800.0, shares=100, trade_date=day1)
        assert sell_same_day["success"] is False, "Same-day sell should be rejected"
        assert "T+1" in sell_same_day["reason"] or "not" in sell_same_day["reason"].lower()


class TestPortfolioStateTracking:
    def test_nav_calculation(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))

        nav = sim.get_portfolio_value(current_prices={"600519": 1850.0})
        assert nav > 0
        assert "600519" in sim.positions

    def test_position_tracking_multiple_stocks(self):
        sim = TradingSimulator(initial_capital=2_000_000.0)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        sim.buy("000001", price=12.0, shares=1000, trade_date=date(2024, 1, 2))

        positions = sim.get_position_summary()
        assert "600519" in positions
        assert "000001" in positions
        assert positions["600519"]["shares"] == 100
        assert positions["000001"]["shares"] == 1000

    def test_cash_tracking(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)

        initial_cash = sim.cash
        buy_result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert buy_result["success"] is True

        assert sim.cash < initial_cash

        sim.sell("600519", price=1850.0, shares=100, trade_date=date(2024, 1, 3))
        assert sim.cash > initial_cash - (1800.0 * 100)


class TestT1EdgeCases:
    def test_same_day_sell_rejected(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        day1 = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=day1)

        sell_same_day = sim.sell("600519", price=1820.0, shares=100, trade_date=day1)
        assert sell_same_day["success"] is False

    def test_partial_t1_release(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        sim.buy("600519", price=1820.0, shares=100, trade_date=date(2024, 1, 3))

        sell_result = sim.sell("600519", price=1850.0, shares=100, trade_date=date(2024, 1, 4))
        assert sell_result["success"] is True

        sell2 = sim.sell("600519", price=1860.0, shares=100, trade_date=date(2024, 1, 5))
        assert sell2["success"] is True


class TestInsufficientCash:
    def test_buy_with_insufficient_cash(self):
        sim = TradingSimulator(initial_capital=10_000.0)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is False
        assert "cash" in result["reason"].lower() or "insufficient" in result["reason"].lower()

    def test_buy_exhausts_cash_then_more_fails(self):
        sim = TradingSimulator(initial_capital=200_000.0)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))

        result = sim.buy("000001", price=50.0, shares=1000, trade_date=date(2024, 1, 2))
        assert result["success"] is False


class TestLotSizeEdgeCases:
    def test_buy_below_100_shares_rejected(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=50, trade_date=date(2024, 1, 2))
        assert result["success"] is False
        assert "lot" in result["reason"].lower() or "100" in result["reason"]

    def test_buy_150_shares_rejected(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=150, trade_date=date(2024, 1, 2))
        assert result["success"] is False

    def test_sell_below_100_shares_rejected(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))

        result = sim.sell("600519", price=1850.0, shares=50, trade_date=date(2024, 1, 3))
        assert result["success"] is False


class TestInternalStoreRecording:
    @pytest.fixture
    def mock_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_meta.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    strategy    TEXT NOT NULL,
                    params      TEXT NOT NULL,
                    result      TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now'))
                );
                """
            )
            conn.commit()
            conn.close()
            yield str(db_path)

    def test_record_experiment_directly(self, mock_db):
        conn = sqlite3.connect(mock_db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO experiments (name, strategy, params, result) VALUES (?, ?, ?, ?)",
            (
                "ma_cross_v1",
                json.dumps({"ma_short": 5, "ma_long": 20}),
                json.dumps({"capital": 1_000_000}),
                json.dumps({"final_nav": 1.15, "sharpe": 1.2}),
            ),
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(mock_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM experiments WHERE name=?", ("ma_cross_v1",)).fetchone()
        conn.close()
        assert row is not None
        assert json.loads(row["strategy"]) == {"ma_short": 5, "ma_long": 20}

    def test_record_experiment_via_mcp_mock(self, mock_db):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        sim.current_date = date(2024, 1, 2)
        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))

        conn = sqlite3.connect(mock_db)
        conn.row_factory = sqlite3.Row
        experiment_name = "integration_test_run"
        strategy_config = {"stocks": ["600519"], "entry_price": 1800.0}
        simulation_result = {
            "initial_capital": 1_000_000.0,
            "final_nav": sim.get_portfolio_value(),
            "positions": sim.get_position_summary(),
            "trade_count": len(sim.trade_history),
        }

        conn.execute(
            "INSERT INTO experiments (name, strategy, params, result) VALUES (?, ?, ?, ?)",
            (
                experiment_name,
                json.dumps(strategy_config),
                json.dumps({}),
                json.dumps(simulation_result),
            ),
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(mock_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM experiments WHERE name=?", (experiment_name,)).fetchone()
        conn.close()
        assert row is not None
        result = json.loads(row["result"])
        assert result["trade_count"] == 1
        assert "final_nav" in result


class TestFullSimulationCycle:
    @pytest.mark.integration
    def test_complete_trading_cycle(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        day1 = date(2024, 1, 2)
        day2 = date(2024, 1, 3)
        day3 = date(2024, 1, 4)

        buy1 = sim.buy("600519", price=1800.0, shares=100, trade_date=day1)
        assert buy1["success"] is True

        buy2 = sim.buy("000001", price=12.0, shares=1000, trade_date=day2)
        assert buy2["success"] is True

        sell_day2 = sim.sell("600519", price=1820.0, shares=100, trade_date=day2)
        assert sell_day2["success"] is True

        sell_day3 = sim.sell("000001", price=13.0, shares=1000, trade_date=day3)
        assert sell_day3["success"] is True
        assert sell_day3["realized_pnl"] > 0

        nav = sim.get_portfolio_value()
        assert nav > 0

        positions = sim.get_position_summary()
        assert "600519" not in positions
        assert "000001" not in positions

        cash = sim.cash
        assert cash > 0

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, strategy TEXT NOT NULL,
                params TEXT NOT NULL, result TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            "INSERT INTO experiments (name, strategy, params, result) VALUES (?, ?, ?, ?)",
            (
                "full_cycle_test",
                json.dumps({"stocks": ["600519", "000001"]}),
                json.dumps({"initial_capital": 1_000_000.0}),
                json.dumps({
                    "final_nav": nav,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "positions": positions,
                    "cash": cash,
                    "trade_history_count": len(sim.trade_history),
                }),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM experiments WHERE name=?", ("full_cycle_test",)).fetchone()
        conn.close()
        assert row is not None

    @pytest.mark.integration
    def test_multi_day_trade_history_integrity(self):
        sim = TradingSimulator(initial_capital=1_000_000.0)
        day1 = date(2024, 1, 2)
        day2 = date(2024, 1, 3)
        day3 = date(2024, 1, 4)

        sim.buy("600519", price=1800.0, shares=100, trade_date=day1)
        sim.buy("600519", price=1820.0, shares=100, trade_date=day2)
        sim.sell("600519", price=1850.0, shares=100, trade_date=day3)
        sim.sell("600519", price=1860.0, shares=100, trade_date=date(2024, 1, 5))

        assert len(sim.trade_history) == 4
        assert sim.trade_history[0].action == "buy"
        assert sim.trade_history[0].trade_date == day1
        assert sim.trade_history[1].action == "buy"
        assert sim.trade_history[1].trade_date == day2
        assert sim.trade_history[2].action == "sell"
        assert sim.trade_history[2].trade_date == day3
        assert sim.trade_history[3].action == "sell"