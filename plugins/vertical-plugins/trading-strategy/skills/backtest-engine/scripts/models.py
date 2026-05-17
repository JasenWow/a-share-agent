"""Data classes for the backtest engine — no I/O, no DB."""

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
    name: str = ""

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
    cost_basis: float = 0.0
    entry_date: str = ""
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
        self.shares = max(0, self.shares - shares)
        self.sellable_shares = max(0, self.sellable_shares - shares)

    def mark_sellable(self) -> None:
        self.sellable_shares = self.shares


@dataclass
class Signal:
    """A trading signal."""

    signal_date: str
    stock_code: str
    direction: str
    target_weight: float = 0.0
    target_shares: int = 0


@dataclass
class TradeRecord:
    """An executed trade."""

    trade_date: str
    stock_code: str
    direction: str
    shares: int
    price: float
    amount: float
    commission: float = 0.0
    stamp_duty: float = 0.0
    slippage_cost: float = 0.0
    total_cost: float = 0.0
    realized_pnl: float = 0.0
    signal_date: str = ""


@dataclass
class SessionConfig:
    """Backtest session configuration."""

    session_id: str
    name: str = ""
    strategy: str = ""
    initial_capital: float = 1000000.0
    start_date: str = ""
    end_date: str = ""
    universe: list[str] = field(default_factory=list)
    benchmark: str = "sh000300"
    commission_rate: float = 0.00025
    stamp_duty_rate: float = 0.0005
    slippage_rate: float = 0.0005
    exclude_st: bool = True


@dataclass
class Portfolio:
    """Portfolio state during backtest."""

    cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def total_value(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    def get_position(self, stock_code: str) -> Position | None:
        return self.positions.get(stock_code)


@dataclass
class DayResult:
    """Output of processing a single trading day."""

    trade_date: str
    nav: float
    cash: float
    positions_value: float
    daily_return: float
    benchmark_return: float
    excess_return: float
    benchmark_value: float
    benchmark_close: float
    trades: list[TradeRecord] = field(default_factory=list)
    position_snapshots: list[dict] = field(default_factory=list)
