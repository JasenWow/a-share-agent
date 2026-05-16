"""Data classes for the paper-trader backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BarData:
    """Single-day OHLCV record for a stock."""

    date: str  # YYYYMMDD
    open: float
    close: float
    high: float
    low: float
    volume: float
    name: str = ""  # Stock name (for ST detection)

    @property
    def is_suspended(self) -> bool:
        return self.volume == 0

    @property
    def is_st(self) -> bool:
        return "ST" in self.name.upper()


@dataclass
class Position:
    """A single stock position."""

    stock_code: str
    shares: int = 0
    sellable_shares: int = 0
    cost_basis: float = 0.0  # Average cost per share (including slippage)
    entry_date: str = ""  # First buy date (YYYYMMDD)
    market_value: float = 0.0
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.shares * self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        cost = self.shares * self.cost_basis
        return (self.market_value - cost) / cost if cost > 0 else 0.0

    def add_shares(self, shares: int, price: float, date: str) -> None:
        """Add shares (buy). Updates cost basis as weighted average."""
        if self.shares == 0:
            self.cost_basis = price
            self.entry_date = date
        else:
            total_cost = self.cost_basis * self.shares + price * shares
            self.shares += shares
            self.cost_basis = total_cost / self.shares if self.shares > 0 else 0.0
            return
        self.shares = shares

    def remove_shares(self, shares: int) -> None:
        """Remove shares (sell). Does not change cost basis."""
        self.shares = max(0, self.shares - shares)
        self.sellable_shares = max(0, self.sellable_shares - shares)

    def mark_sellable(self) -> None:
        """Mark all shares as sellable (T+1 unlock)."""
        self.sellable_shares = self.shares


@dataclass
class Signal:
    """A trading signal."""

    signal_date: str  # YYYYMMDD - when signal is generated
    stock_code: str  # 6-digit
    direction: str  # "buy" or "sell"
    target_weight: float = 0.0  # Target portfolio weight (for buy, takes precedence)
    target_shares: int = 0  # Target shares (for buy when weight=0)


@dataclass
class TradeRecord:
    """An executed trade."""

    trade_date: str  # YYYYMMDD - execution date
    stock_code: str
    direction: str  # "buy" or "sell"
    shares: int
    price: float  # Execution price (after slippage)
    amount: float  # price * shares
    commission: float = 0.0
    stamp_duty: float = 0.0
    slippage_cost: float = 0.0
    total_cost: float = 0.0  # commission + stamp_duty + slippage_cost
    realized_pnl: float = 0.0  # For sell trades
    signal_date: str = ""  # When the signal was generated


@dataclass
class SessionConfig:
    """Backtest session configuration."""

    session_id: str
    name: str = ""
    strategy: str = ""
    status: str = "created"  # created | loading | ready | running | completed | failed
    initial_capital: float = 1000000.0
    start_date: str = ""
    end_date: str = ""
    universe: list[str] = field(default_factory=list)
    benchmark: str = "sh000300"
    commission_rate: float = 0.00025  # 0.025% per side
    stamp_duty_rate: float = 0.0005  # 0.05% sell only
    slippage_rate: float = 0.0005  # 0.05% one-way
    exclude_st: bool = True
    current_date: str = ""
    final_nav: float = 0.0
    total_trades: int = 0
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        import json

        return {
            "session_id": self.session_id,
            "name": self.name,
            "strategy": self.strategy,
            "status": self.status,
            "initial_capital": self.initial_capital,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "universe": json.dumps(self.universe),
            "benchmark": self.benchmark,
            "commission_rate": self.commission_rate,
            "stamp_duty_rate": self.stamp_duty_rate,
            "slippage_rate": self.slippage_rate,
            "exclude_st": int(self.exclude_st),
            "current_date": self.current_date,
            "final_nav": self.final_nav,
            "total_trades": self.total_trades,
            "error_message": self.error_message,
        }


@dataclass
class Portfolio:
    """Portfolio state during backtest."""

    cash: float
    positions: dict[str, Position] = field(default_factory=dict)  # stock_code -> Position

    @property
    def total_value(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    def get_position(self, stock_code: str) -> Position | None:
        return self.positions.get(stock_code)
