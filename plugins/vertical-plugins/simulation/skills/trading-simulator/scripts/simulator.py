"""TradingSimulator for A-share market with T+1 settlement."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .market_rules import (
    calculate_total_cost,
    get_price_limit,
    round_to_lot,
    MIN_LOT_SIZE,
)


@dataclass
class Position:
    shares: int = 0
    avg_price: float = 0.0
    buy_dates: dict[int, tuple[date, float]] = field(default_factory=dict)


@dataclass
class TradeRecord:
    action: str
    code: str
    price: float
    shares: int
    trade_date: date
    trade_value: float
    cost: float
    realized_pnl: float = 0.0


class TradingSimulator:
    """A-share trading simulator with T+1 settlement enforcement."""

    def __init__(self, initial_capital: float = 1_000_000.0) -> None:
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.trade_history: list[TradeRecord] = []
        self.current_date: Optional[date] = None

    def buy(
        self, code: str, price: float, shares: int, trade_date: date, prev_close: Optional[float] = None
    ) -> dict:
        """Execute a buy order.

        Args:
            code: 6-digit stock code
            price: execution price
            shares: number of shares to buy
            trade_date: date of the trade
            prev_close: previous close price for limit checking (optional)

        Returns:
            dict with keys: success (bool), reason (str), shares (int), cost (float)
        """
        self.current_date = trade_date

        lot_shares = round_to_lot(shares)
        if lot_shares == 0:
            return {
                "success": False,
                "reason": f"Lot size must be at least {MIN_LOT_SIZE} shares",
                "shares": 0,
                "cost": 0.0,
            }

        if lot_shares != shares:
            return {
                "success": False,
                "reason": f"Shares must be multiple of {MIN_LOT_SIZE}",
                "shares": 0,
                "cost": 0.0,
            }

        trade_value = price * lot_shares
        cost = calculate_total_cost(trade_value, side="buy")
        total_cost = trade_value + cost

        if self.cash < total_cost:
            return {
                "success": False,
                "reason": "Insufficient cash",
                "shares": 0,
                "cost": 0.0,
            }

        if prev_close is not None:
            floor_price, ceiling_price = get_price_limit(code, prev_close)
            if price > ceiling_price or price < floor_price:
                return {
                    "success": False,
                    "reason": f"Price {price} beyond daily limit [{floor_price}, {ceiling_price}]",
                    "shares": 0,
                    "cost": 0.0,
                }

        self.cash -= total_cost

        if code not in self.positions:
            self.positions[code] = Position()

        pos = self.positions[code]
        total_cost_basis = pos.shares * pos.avg_price + lot_shares * price
        pos.shares += lot_shares
        pos.avg_price = total_cost_basis / pos.shares

        lot_idx = lot_shares
        while lot_idx in pos.buy_dates:
            lot_idx += 1
        pos.buy_dates[lot_idx] = (trade_date, price)

        record = TradeRecord(
            action="buy",
            code=code,
            price=price,
            shares=lot_shares,
            trade_date=trade_date,
            trade_value=trade_value,
            cost=cost,
        )
        self.trade_history.append(record)

        return {
            "success": True,
            "reason": "",
            "shares": lot_shares,
            "cost": cost,
        }

    def sell(
        self, code: str, price: float, shares: int, trade_date: date, prev_close: Optional[float] = None
    ) -> dict:
        """Execute a sell order with T+1 settlement enforcement.

        Args:
            code: 6-digit stock code
            price: execution price
            shares: number of shares to sell
            trade_date: date of the trade
            prev_close: previous close price for limit checking (optional)

        Returns:
            dict with keys: success (bool), reason (str), shares (int), realized_pnl (float)
        """
        self.current_date = trade_date

        if code not in self.positions:
            return {
                "success": False,
                "reason": "No position in this stock",
                "shares": 0,
                "realized_pnl": 0.0,
            }

        pos = self.positions[code]

        sellable_shares = self._get_sellable_shares(code, trade_date)
        if sellable_shares <= 0:
            return {
                "success": False,
                "reason": "T+1: no shares available to sell",
                "shares": 0,
                "realized_pnl": 0.0,
            }

        if shares > sellable_shares:
            return {
                "success": False,
                "reason": f"T+1: only {sellable_shares} shares available to sell (bought {pos.shares} total)",
                "shares": 0,
                "realized_pnl": 0.0,
            }

        if shares % MIN_LOT_SIZE != 0:
            return {
                "success": False,
                "reason": f"Shares must be multiple of {MIN_LOT_SIZE}",
                "shares": 0,
                "realized_pnl": 0.0,
            }

        if prev_close is not None:
            floor_price, ceiling_price = get_price_limit(code, prev_close)
            if price < floor_price:
                return {
                    "success": False,
                    "reason": f"Price {price} below floor {floor_price}",
                    "shares": 0,
                    "realized_pnl": 0.0,
                }

        trade_value = price * shares
        cost = calculate_total_cost(trade_value, side="sell")
        net_proceeds = trade_value - cost

        realized_pnl = 0.0
        avg_cost = self._get_avg_cost_for_sell(code, shares)
        realized_pnl = net_proceeds - (avg_cost * shares)

        self.cash += net_proceeds

        shares_to_remove = shares
        sorted_lots = sorted(pos.buy_dates.keys())
        for lot_key in sorted_lots:
            if shares_to_remove <= 0:
                break
            lot_date, lot_price = pos.buy_dates[lot_key]
            if lot_date <= trade_date:
                lot_shares = min(lot_key if lot_key <= shares_to_remove else shares_to_remove, lot_key)
                shares_to_remove -= lot_shares
                del pos.buy_dates[lot_key]

        if shares_to_remove > 0:
            remaining = shares_to_remove
            for lot_key in sorted(pos.buy_dates.keys(), reverse=True):
                lot_shares = min(remaining, lot_key)
                if lot_date <= trade_date:
                    del pos.buy_dates[lot_key]
                    remaining -= lot_shares
                if remaining <= 0:
                    break

        pos.shares -= shares
        if pos.shares == 0:
            del self.positions[code]

        record = TradeRecord(
            action="sell",
            code=code,
            price=price,
            shares=shares,
            trade_date=trade_date,
            trade_value=trade_value,
            cost=cost,
            realized_pnl=realized_pnl,
        )
        self.trade_history.append(record)

        return {
            "success": True,
            "reason": "",
            "shares": shares,
            "realized_pnl": realized_pnl,
        }

    def _get_sellable_shares(self, code: str, trade_date: date) -> int:
        """Return number of shares that can be sold on a given date (T+1 enforcement)."""
        if code not in self.positions:
            return 0

        pos = self.positions[code]
        sellable = 0

        for lot_shares, (buy_date, _) in pos.buy_dates.items():
            if buy_date < trade_date:
                sellable += lot_shares

        return sellable

    def _get_avg_cost_for_sell(self, code: str, shares: int) -> float:
        """Calculate average cost basis for shares being sold using FIFO."""
        pos = self.positions[code]

        shares_to_consider = shares
        total_cost = 0.0

        for lot_shares, (buy_date, lot_price) in pos.buy_dates.items():
            if shares_to_consider <= 0:
                break
            sell_from_lot = min(lot_shares, shares_to_consider)
            total_cost += sell_from_lot * lot_price
            shares_to_consider -= sell_from_lot

        if shares_to_consider > 0:
            return pos.avg_price

        return total_cost / shares if shares > 0 else 0.0

    def get_portfolio_value(self, current_prices: Optional[dict[str, float]] = None) -> float:
        """Calculate total portfolio value.

        Args:
            current_prices: dict mapping code to current price (optional)

        Returns:
            Total portfolio value (cash + positions)
        """
        positions_value = 0.0
        for code, pos in self.positions.items():
            if current_prices and code in current_prices:
                positions_value += pos.shares * current_prices[code]
            else:
                positions_value += pos.shares * pos.avg_price

        return self.cash + positions_value

    def get_position_summary(self) -> dict:
        """Return summary of all positions."""
        return {
            code: {"shares": pos.shares, "avg_price": pos.avg_price}
            for code, pos in self.positions.items()
        }