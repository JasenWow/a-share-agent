"""A-share market rules: board limits, transaction costs, lot size."""

# Commission rate per side (0.025% = 万2.5)
COMMISSION_RATE = 0.00025

# Stamp duty rate on sell side only (0.05% = 千0.5)
STAMP_DUTY_RATE = 0.0005

# Default slippage per side (0.05% one-way)
SLIPPAGE_RATE = 0.0005

# Minimum lot size (100 shares)
MIN_LOT_SIZE = 100

# Board price limit by code prefix
BOARD_LIMITS = {
    "main": 0.10,      # 600xxx, 000xxx, 001xxx → ±10%
    "chinext": 0.20,   # 300xxx → ±20%
    "star": 0.20,      # 688xxx → ±20%
    "bse": 0.30,       # 8xxxxx, 4xxxxx → ±30%
    "st": 0.05,        # ST stocks → ±5% regardless of board
}


def get_board_limit(code: str, is_st: bool = False) -> float:
    """Return daily price limit fraction for a stock code.

    Args:
        code: 6-digit stock code
        is_st: True if stock is currently ST/*ST

    Returns:
        Limit as fraction (e.g., 0.10 for ±10%)
    """
    if is_st:
        return BOARD_LIMITS["st"]

    prefix = code[:3]

    if prefix.startswith("688"):
        return BOARD_LIMITS["star"]
    if prefix.startswith("300"):
        return BOARD_LIMITS["chinext"]
    if prefix.startswith("8") or prefix.startswith("4"):
        return BOARD_LIMITS["bse"]
    if prefix.startswith("6") or prefix.startswith("0") or prefix.startswith("1"):
        return BOARD_LIMITS["main"]

    return BOARD_LIMITS["main"]


def get_price_limit(code: str, prev_close: float, is_st: bool = False) -> tuple[float, float]:
    """Return (lower_limit, upper_limit) prices for a stock.

    Args:
        code: 6-digit stock code
        prev_close: previous day's closing price
        is_st: True if stock is currently ST/*ST

    Returns:
        (floor_price, ceiling_price)
    """
    limit = get_board_limit(code, is_st)
    floor_price = round(prev_close * (1 - limit), 2)
    ceiling_price = round(prev_close * (1 + limit), 2)
    return floor_price, ceiling_price


def round_to_lot(shares: int) -> int:
    """Round share count to nearest lot (100 shares), round DOWN.

    Args:
        shares: desired number of shares

    Returns:
        Nearest lot size (0 if below minimum lot)
    """
    if shares < MIN_LOT_SIZE:
        return 0
    return (shares // MIN_LOT_SIZE) * MIN_LOT_SIZE


def calculate_commission(trade_value: float, side: str = "both") -> float:
    """Calculate commission for a trade.

    Args:
        trade_value: total value of the trade (price × shares)
        side: 'buy', 'sell', or 'both'

    Returns:
        Commission amount
    """
    if side == "buy":
        return trade_value * COMMISSION_RATE
    if side == "sell":
        return trade_value * COMMISSION_RATE
    return trade_value * COMMISSION_RATE * 2


def calculate_stamp_duty(trade_value: float, side: str = "sell") -> float:
    """Calculate stamp duty for a trade (sell side only).

    Args:
        trade_value: total value of the trade
        side: 'buy' or 'sell'

    Returns:
        Stamp duty amount (0 for buy side)
    """
    if side == "buy":
        return 0.0
    return trade_value * STAMP_DUTY_RATE


def calculate_slippage(trade_value: float, side: str = "both") -> float:
    """Calculate slippage cost for a trade.

    Args:
        trade_value: total value of the trade
        side: 'buy', 'sell', or 'both'

    Returns:
        Slippage amount
    """
    if side == "both":
        return trade_value * SLIPPAGE_RATE * 2
    return trade_value * SLIPPAGE_RATE


def calculate_total_cost(trade_value: float, side: str = "buy") -> float:
    """Calculate total transaction cost for a trade.

    Args:
        trade_value: total value of the trade (price × shares)
        side: 'buy' or 'sell'

    Returns:
        Total cost (commission + stamp_duty + slippage)
    """
    commission = calculate_commission(trade_value, side=side)
    stamp = calculate_stamp_duty(trade_value, side=side)
    slippage = calculate_slippage(trade_value, side=side)

    if side == "both":
        return commission + slippage

    return commission + stamp + slippage