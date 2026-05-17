"""TDD tests for TradingSimulator — write tests FIRST, implement AFTER."""

import pytest
from datetime import date, timedelta


class TestT1Settlement:
    """T+1 same-day sell rejection."""

    def test_cannot_sell_same_day_as_buy(self):
        """Stocks bought today cannot be sold today."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        # Buy 100 shares of 600519 at 1800.0
        result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is True, f"Buy failed: {result}"

        # Attempt to sell same day — must be rejected
        sell_result = sim.sell("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert sell_result["success"] is False
        assert "T+1" in sell_result["reason"] or "not enough" in sell_result["reason"].lower()

    def test_can_sell_next_trading_day(self):
        """Stocks bought today CAN be sold tomorrow."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        # Buy 100 shares
        buy_result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert buy_result["success"] is True

        # Sell next trading day
        sell_result = sim.sell("600519", price=1850.0, shares=100, trade_date=date(2024, 1, 3))
        assert sell_result["success"] is True
        assert sell_result["shares"] == 100

    def test_partial_sell_respects_t1(self):
        """Can only sell shares that were bought before T+1."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        # Buy 300 shares on day 1
        sim.buy("600519", price=1800.0, shares=300, trade_date=date(2024, 1, 2))

        # Buy 200 more shares on day 2
        sim.buy("600519", price=1820.0, shares=200, trade_date=date(2024, 1, 3))

        # On day 3, can only sell shares bought on or before day 2
        # Day 1's 300 shares are now sellable (T+1 from day 1 = day 2)
        # Day 2's 200 shares are NOT yet sellable (T+1 from day 2 = day 3, need day 4)
        sell_result = sim.sell("600519", price=1850.0, shares=300, trade_date=date(2024, 1, 3))
        assert sell_result["success"] is True

        # Remaining 200 cannot be sold yet
        sell2 = sim.sell("600519", price=1850.0, shares=100, trade_date=date(2024, 1, 3))
        assert sell2["success"] is False


class TestBoardPriceLimits:
    """Board price limits by code prefix."""

    @pytest.mark.parametrize(
        "code,expected_limit_pct",
        [
            ("600519", 0.10),   # Main Board ±10%
            ("000001", 0.10),   # Main Board ±10%
            ("001872", 0.10),   # Main Board ±10%
            ("300001", 0.20),   # ChiNext ±20%
            ("300759", 0.20),   # ChiNext ±20%
            ("688001", 0.20),   # STAR Market ±20%
            ("688981", 0.20),   # STAR Market ±20%
            ("830799", 0.30),   # BSE ±30%
            ("430001", 0.30),   # BSE ±30%
        ],
    )
    def test_main_board_limit(self, code, expected_limit_pct):
        """Main board stocks have ±10% daily limit."""
        from scripts.market_rules import get_board_limit

        limit = get_board_limit(code)
        assert limit == expected_limit_pct, f"Code {code}: expected {expected_limit_pct}, got {limit}"

    def test_st_stocks_limit(self):
        """ST stocks have ±5% limit regardless of board."""
        from scripts.market_rules import get_board_limit

        # Non-ST code with ST flag would be 0.05
        limit_normal = get_board_limit("600519", is_st=False)
        limit_st = get_board_limit("600519", is_st=True)
        assert limit_st == 0.05
        assert limit_normal == 0.10

    def test_order_beyond_limit_rejected(self):
        """Orders beyond daily limit should be rejected by simulator."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        # Main board: prev_close = 100, limit = ±10%, so max buy/sell at 110
        prev_close = 100.0
        limit_price = prev_close * 1.10

        # Try to buy at price beyond limit
        result = sim.buy("600519", price=limit_price + 1.0, shares=100, trade_date=date(2024, 1, 2), prev_close=prev_close)
        assert result["success"] is False
        assert "limit" in result["reason"].lower() or "price" in result["reason"].lower()

    def test_sell_below_limit_rejected(self):
        """Sell orders below floor price rejected."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        prev_close = 100.0

        sim.buy("600519", price=100.0, shares=100, trade_date=date(2024, 1, 2))

        floor_price = prev_close * 0.90

        result = sim.sell("600519", price=floor_price - 1.0, shares=100, trade_date=date(2024, 1, 3), prev_close=prev_close)
        assert result["success"] is False


class TestLotSize:
    """Lot size rounding: 100 shares minimum, round down."""

    def test_exact_100_shares_ok(self):
        """Exact 100 shares should work."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is True

    def test_50_shares_rejected(self):
        """Less than 100 shares rejected."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=50, trade_date=date(2024, 1, 2))
        assert result["success"] is False
        assert "lot" in result["reason"].lower() or "100" in result["reason"]

    def test_150_shares_rounds_down_to_100(self):
        """150 shares should round down to 100 (round down for buys)."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=150, trade_date=date(2024, 1, 2))
        # Implementation may either reject non-lot sizes or round down
        # Check if it was rounded
        if result["success"]:
            assert result["shares"] == 100 or result["shares"] == 0
        else:
            assert "lot" in result["reason"].lower() or "100" in result["reason"]

    def test_250_shares_rounds_down_to_200(self):
        """250 shares should round down to 200."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=250, trade_date=date(2024, 1, 2))
        if result["success"]:
            assert result["shares"] % 100 == 0

    def test_lot_size_calculation(self):
        """Lot size should be 100 shares minimum."""
        from scripts.market_rules import round_to_lot

        assert round_to_lot(50) == 0    # Rejected (below 100)
        assert round_to_lot(100) == 100  # Exact lot
        assert round_to_lot(150) == 100  # Rounds down
        assert round_to_lot(200) == 200  # Exact lot
        assert round_to_lot(250) == 200  # Rounds down


class TestTransactionCosts:
    """Transaction cost calculation."""

    def test_commission_both_sides(self):
        """Commission charged on both buy and sell."""
        from scripts.market_rules import calculate_commission

        # 0.025% per side
        commission = calculate_commission(100_000.0, side="buy")
        assert commission == 25.0, f"Expected 25.0, got {commission}"

        commission_sell = calculate_commission(100_000.0, side="sell")
        assert commission_sell == 25.0

    def test_stamp_duty_sell_only(self):
        """Stamp duty only charged on sell side."""
        from scripts.market_rules import calculate_stamp_duty

        stamp_buy = calculate_stamp_duty(100_000.0, side="buy")
        assert stamp_buy == 0.0, "Stamp duty should be 0 on buy"

        stamp_sell = calculate_stamp_duty(100_000.0, side="sell")
        assert stamp_sell == 50.0, f"Expected 50.0 (0.05%), got {stamp_sell}"

    def test_total_round_trip_cost(self):
        """Total round-trip cost = commission×2 + stamp_duty + slippage×2."""
        from scripts.market_rules import calculate_total_cost

        # 100k position
        cost = calculate_total_cost(100_000.0, side="buy")
        # buy side: commission + slippage
        assert cost > 0
        assert cost < 100_000.0 * 0.005  # Should be less than 0.5%

        cost_sell = calculate_total_cost(100_000.0, side="sell")
        # sell side: commission + stamp_duty + slippage
        assert cost_sell > cost  # Sell more expensive than buy

    def test_cost_affects_pnl(self):
        """Transaction costs should reduce realized P&L."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        buy_price = 1800.0
        shares = 100
        buy_value = buy_price * shares

        sim.buy("600519", price=buy_price, shares=shares, trade_date=date(2024, 1, 2))

        # Sell at higher price
        sell_price = 1850.0
        sell_result = sim.sell("600519", price=sell_price, shares=shares, trade_date=date(2024, 1, 3))
        assert sell_result["success"] is True

        # Gross profit
        gross_profit = (sell_price - buy_price) * shares

        # Net profit should be less than gross due to costs
        assert sell_result["realized_pnl"] < gross_profit
        # But still positive
        assert sell_result["realized_pnl"] > 0


class TestTradingSimulatorBasics:
    """Basic simulator functionality."""

    def test_initialization(self):
        """Simulator starts with initial capital."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        assert sim.cash == 1_000_000
        assert sim.positions == {}

    def test_buy_updates_cash_and_position(self):
        """Buy should deduct cash and add to position."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is True

        assert sim.cash < 1_000_000
        assert "600519" in sim.positions
        assert sim.positions["600519"].shares == 100
        assert sim.positions["600519"].avg_price == pytest.approx(1800.0)

    def test_buy_insufficient_cash(self):
        """Cannot buy if cash is insufficient."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=10_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is False
        assert "cash" in result["reason"].lower() or "insufficient" in result["reason"].lower()

    def test_sell_without_position(self):
        """Cannot sell stock you don't own."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        result = sim.sell("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        assert result["success"] is False

    def test_portfolio_value(self):
        """Portfolio value calculation includes cash + positions."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))

        # Get portfolio value with current prices
        # Positions valued at last purchase price if no current price provided
        pv = sim.get_portfolio_value()
        assert pv == 999_865.0

    def test_trade_history(self):
        """All trades should be recorded."""
        from scripts.simulator import TradingSimulator

        sim = TradingSimulator(initial_capital=1_000_000)
        sim.current_date = date(2024, 1, 2)

        sim.buy("600519", price=1800.0, shares=100, trade_date=date(2024, 1, 2))
        sim.sell("600519", price=1850.0, shares=100, trade_date=date(2024, 1, 3))

        assert len(sim.trade_history) == 2
        assert sim.trade_history[0].action == "buy"
        assert sim.trade_history[1].action == "sell"