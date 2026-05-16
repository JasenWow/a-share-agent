"""Performance metrics calculation for backtest results."""

from __future__ import annotations

import math

from engine import _get_conn

RISK_FREE_RATE = 0.02  # 2% annual
TRADING_DAYS_PER_YEAR = 252


def compute_performance(session_id: str) -> list[dict]:
    """Compute full performance metrics from daily_nav and trades tables.

    Returns single-element list with metrics dict.
    """
    conn = _get_conn()
    try:
        nav_rows = conn.execute(
            "SELECT * FROM daily_nav WHERE session_id = ? ORDER BY trade_date",
            (session_id,),
        ).fetchall()
        trade_rows = conn.execute(
            "SELECT * FROM trades WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        session = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()

    if not nav_rows:
        return [{"error": "No NAV data found", "session_id": session_id}]

    daily_returns = [r["daily_return"] for r in nav_rows]
    benchmark_returns = [r["benchmark_return"] for r in nav_rows]
    nav_series = [r["nav"] for r in nav_rows]
    excess_returns = [r["excess_return"] for r in nav_rows]
    n = len(nav_rows)

    initial_capital = session["initial_capital"] if session else nav_series[0]

    # Total return
    total_return = nav_series[-1] / initial_capital - 1

    # Annualized return (geometric)
    years = n / TRADING_DAYS_PER_YEAR
    if years > 0 and total_return > -1:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = total_return

    # Annualized volatility
    mean_dr = sum(daily_returns) / n if n > 0 else 0.0
    daily_vol = math.sqrt(sum((r - mean_dr) ** 2 for r in daily_returns) / max(n - 1, 1))
    annual_vol = daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)

    # Sharpe ratio
    rf_daily = (1 + RISK_FREE_RATE) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_rf = [r - rf_daily for r in daily_returns]
    mean_excess_rf = sum(excess_rf) / n if n > 0 else 0.0
    sharpe = (math.sqrt(TRADING_DAYS_PER_YEAR) * mean_excess_rf / daily_vol) if daily_vol > 0 else 0.0

    # Sortino ratio
    downside = [r - rf_daily for r in daily_returns if r < rf_daily]
    downside_vol = math.sqrt(sum(d ** 2 for d in downside) / n) * math.sqrt(TRADING_DAYS_PER_YEAR) if n > 0 else 0.0
    sortino = (annual_return - RISK_FREE_RATE) / downside_vol if downside_vol > 0 else 0.0

    # Maximum drawdown
    peak = nav_series[0]
    max_dd = 0.0
    max_dd_start = nav_rows[0]["trade_date"]
    max_dd_end = nav_rows[0]["trade_date"]
    peak_idx = 0
    for i, nav in enumerate(nav_series):
        if nav > peak:
            peak = nav
            peak_idx = i
        dd = (peak - nav) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_start = nav_rows[peak_idx]["trade_date"]
            max_dd_end = nav_rows[i]["trade_date"]

    # Calmar ratio
    calmar = annual_return / max_dd if max_dd > 0 else float("inf")

    # Win rate
    win_days = sum(1 for r in daily_returns if r > 0)
    win_rate = win_days / n if n > 0 else 0.0

    # Profit factor
    gross_profit = sum(r for r in daily_returns if r > 0)
    gross_loss = abs(sum(r for r in daily_returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Annual turnover
    trades = [dict(r) for r in trade_rows]
    total_buy_amount = sum(t["amount"] for t in trades if t["direction"] == "buy")
    avg_nav = sum(nav_series) / n if n > 0 else initial_capital
    annual_turnover = (total_buy_amount / avg_nav) * (TRADING_DAYS_PER_YEAR / n) if avg_nav > 0 and n > 0 else 0.0

    # Cost breakdown
    total_commission = sum(t["commission"] for t in trades)
    total_stamp_duty = sum(t["stamp_duty"] for t in trades)
    total_slippage = sum(t["slippage_cost"] for t in trades)

    # Benchmark comparison
    bm_total_return = (1 + benchmark_returns[0])
    for r in benchmark_returns[1:]:
        bm_total_return *= (1 + r)
    bm_total_return -= 1
    bm_annual_return = (1 + bm_total_return) ** (1 / years) - 1 if years > 0 and bm_total_return > -1 else bm_total_return

    excess_annual = annual_return - bm_annual_return

    # Tracking error
    mean_excess = sum(excess_returns) / n if n > 0 else 0.0
    tracking_error = math.sqrt(sum((e - mean_excess) ** 2 for e in excess_returns) / max(n - 1, 1)) * math.sqrt(TRADING_DAYS_PER_YEAR)

    # Information ratio
    information_ratio = excess_annual / tracking_error if tracking_error > 0 else 0.0

    return [
        {
            "session_id": session_id,
            "total_return": round(total_return, 6),
            "annual_return": round(annual_return, 6),
            "annual_volatility": round(annual_vol, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 6),
            "max_drawdown_start": max_dd_start,
            "max_drawdown_end": max_dd_end,
            "calmar_ratio": round(calmar, 4) if calmar != float("inf") else "inf",
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else "inf",
            "annual_turnover": round(annual_turnover, 4),
            "total_trades": len(trades),
            "buy_trades": sum(1 for t in trades if t["direction"] == "buy"),
            "sell_trades": sum(1 for t in trades if t["direction"] == "sell"),
            "total_commission": round(total_commission, 2),
            "total_stamp_duty": round(total_stamp_duty, 2),
            "total_slippage": round(total_slippage, 2),
            "total_cost": round(total_commission + total_stamp_duty + total_slippage, 2),
            "benchmark_total_return": round(bm_total_return, 6),
            "benchmark_annual_return": round(bm_annual_return, 6),
            "excess_annual_return": round(excess_annual, 6),
            "tracking_error": round(tracking_error, 6),
            "information_ratio": round(information_ratio, 4),
            "trading_days": n,
        }
    ]
