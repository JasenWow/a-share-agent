"""A-share transaction costs, board limits, and trading constraints — pure functions, no I/O."""

from __future__ import annotations

from models import BarData, SessionConfig


def calculate_buy_cost(
    amount: float,
    price: float,
    shares: int,
    commission_rate: float,
    slippage_rate: float,
) -> tuple[float, float, float, float]:
    """Calculate total cost for a buy order.

    Returns (commission, stamp_duty, slippage_cost, total_cost).
    """
    commission = max(amount * commission_rate, 5.0)
    stamp_duty = 0.0
    slippage_cost = amount * slippage_rate
    return commission, stamp_duty, slippage_cost, commission + slippage_cost


def calculate_sell_cost(
    amount: float,
    commission_rate: float,
    stamp_duty_rate: float,
    slippage_rate: float,
) -> tuple[float, float, float, float]:
    """Calculate total cost for a sell order.

    Returns (commission, stamp_duty, slippage_cost, total_cost).
    """
    commission = max(amount * commission_rate, 5.0)
    stamp_duty = amount * stamp_duty_rate
    slippage_cost = amount * slippage_rate
    return commission, stamp_duty, slippage_cost, commission + stamp_duty + slippage_cost


def round_lot_size(shares: int) -> int:
    """Round down to nearest 100 shares (A-share lot size)."""
    return (shares // 100) * 100


def get_board_limit(stock_code: str, bar: BarData | None = None) -> float:
    """Return the board-specific daily price limit percentage as a fraction."""
    if bar and bar.is_st:
        return 0.05
    if stock_code.startswith("300") or stock_code.startswith("688"):
        return 0.20
    if stock_code.startswith("8") or stock_code.startswith("4"):
        return 0.30
    return 0.10


def is_price_in_limit(exec_price: float, prev_close: float, limit_pct: float) -> bool:
    """Check if the execution price is within the board price limit."""
    if prev_close <= 0:
        return True
    return abs(exec_price / prev_close - 1) <= limit_pct * 1.01


def is_limit_up(open_price: float, prev_close: float, limit_pct: float) -> bool:
    """Check if the stock opened at limit-up."""
    if prev_close <= 0:
        return False
    return open_price >= prev_close * (1 + limit_pct) * 0.995


def is_limit_down(open_price: float, prev_close: float, limit_pct: float) -> bool:
    """Check if the stock opened at limit-down."""
    if prev_close <= 0:
        return False
    return open_price <= prev_close * (1 - limit_pct) * 1.005


def should_exclude(
    stock_code: str,
    bar: BarData,
    config: SessionConfig,
    prev_close: float = 0.0,
) -> tuple[bool, str]:
    """Check if a stock should be excluded from trading. Returns (excluded, reason)."""
    if bar.is_suspended:
        return True, "suspended"
    if config.exclude_st and bar.is_st:
        return True, "ST"
    limit_pct = get_board_limit(stock_code, bar)
    if prev_close > 0 and is_limit_up(bar.open, prev_close, limit_pct):
        return True, "limit_up"
    if prev_close > 0 and is_limit_down(bar.open, prev_close, limit_pct):
        return True, "limit_down"
    return False, ""


def apply_buy_slippage(price: float, slippage_rate: float) -> float:
    return price * (1 + slippage_rate)


def apply_sell_slippage(price: float, slippage_rate: float) -> float:
    return price * (1 - slippage_rate)


def calculate_max_buy_shares(
    cash: float,
    price: float,
    commission_rate: float,
    slippage_rate: float,
) -> int:
    """Calculate maximum affordable shares with lot-size rounding."""
    exec_price = apply_buy_slippage(price, slippage_rate)
    cost_per_share = exec_price * (1 + commission_rate)
    if cost_per_share <= 0:
        return 0
    return round_lot_size(int(cash / cost_per_share))
