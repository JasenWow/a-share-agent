"""Backtest metrics computation.

Provides two sets of metrics:
1. Portfolio-level: annualized return, Sharpe, drawdown, win rate, IR
2. Factor-level: IC, ICIR, t-stat, significance test
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats


# ---------------------------------------------------------------------------
# Portfolio-level metrics
# ---------------------------------------------------------------------------

def compute_backtest_metrics(
    equity: np.ndarray,
    benchmark: np.ndarray | None = None,
    trading_days_per_year: int = 244,
) -> dict:
    """Compute full backtest performance metrics.

    Args:
        equity: (T,) equity curve starting at 1.0.
        benchmark: (T,) benchmark equity curve starting at 1.0, or None.
        trading_days_per_year: trading days per year (default 244 for A-share).

    Returns:
        Dict of performance metrics.
    """
    equity = np.asarray(equity, dtype=float)
    if len(equity) < 2:
        return _empty_metrics()

    # Daily returns
    daily_ret = np.diff(equity) / equity[:-1]
    n_days = len(daily_ret)
    years = n_days / trading_days_per_year

    # Total return
    total_return = float(equity[-1] / equity[0] - 1)

    # Annualized return
    annualized_return = float((equity[-1] / equity[0]) ** (1.0 / years) - 1) if years > 0 else 0.0

    # Annualized volatility
    annualized_vol = float(np.std(daily_ret) * np.sqrt(trading_days_per_year))

    # Sharpe ratio (rf=0)
    sharpe = float(np.mean(daily_ret) / np.std(daily_ret) * np.sqrt(trading_days_per_year)) if np.std(daily_ret) > 0 else 0.0

    # Max drawdown
    cummax = np.maximum.accumulate(equity)
    drawdown = (equity - cummax) / cummax
    max_drawdown = float(np.min(drawdown))

    # Max drawdown duration
    in_drawdown = drawdown < 0
    dd_duration = 0
    max_dd_duration = 0
    for dd in in_drawdown:
        if dd:
            dd_duration += 1
            max_dd_duration = max(max_dd_duration, dd_duration)
        else:
            dd_duration = 0

    # Calmar ratio
    calmar = float(annualized_return / abs(max_drawdown)) if abs(max_drawdown) > 1e-6 else 0.0

    # Win rate
    win_rate = float(np.mean(daily_ret > 0))

    # Benchmark comparison
    excess_return = 0.0
    information_ratio = 0.0
    if benchmark is not None:
        benchmark = np.asarray(benchmark, dtype=float)
        if len(benchmark) == len(equity):
            bm_ret = np.diff(benchmark) / benchmark[:-1]
            active_ret = daily_ret - bm_ret
            excess_return = float(np.mean(active_ret) * trading_days_per_year)
            tracking_error = float(np.std(active_ret) * np.sqrt(trading_days_per_year))
            information_ratio = float(excess_return / tracking_error) if tracking_error > 0 else 0.0

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "max_drawdown_duration": max_dd_duration,
        "calmar_ratio": calmar,
        "win_rate": win_rate,
        "n_days": n_days,
        "years": years,
        "excess_return": excess_return,
        "information_ratio": information_ratio,
    }


def _empty_metrics() -> dict:
    return {
        "total_return": 0.0, "annualized_return": 0.0,
        "annualized_volatility": 0.0, "sharpe_ratio": 0.0,
        "max_drawdown": 0.0, "max_drawdown_duration": 0,
        "calmar_ratio": 0.0, "win_rate": 0.0,
        "n_days": 0, "years": 0.0,
        "excess_return": 0.0, "information_ratio": 0.0,
    }


# ---------------------------------------------------------------------------
# Factor-level metrics
# ---------------------------------------------------------------------------

def compute_factor_metrics(
    ic_series: np.ndarray,
    n_stocks: int = 0,
) -> dict:
    """Compute statistical metrics for a factor's IC series.

    Args:
        ic_series: Per-period IC values (may contain NaN).
        n_stocks: Number of stocks in cross-section (for display).

    Returns:
        Dict with IC statistics and significance test.
    """
    ic_series = np.asarray(ic_series, dtype=float)
    clean = ic_series[~np.isnan(ic_series)]

    if len(clean) < 2:
        return _empty_factor_metrics(n_stocks)

    mean_ic = float(np.mean(clean))
    std_ic = float(np.std(clean))
    icir = mean_ic / std_ic if std_ic > 1e-12 else 0.0

    # t-statistic: t = mean / (std / sqrt(n))
    t_stat = float(mean_ic / (std_ic / np.sqrt(len(clean)))) if std_ic > 1e-12 else 0.0

    # Significance: |t| > 2 (approx 5% level)
    is_significant = abs(t_stat) > 2.0

    # IC positive percentage
    ic_positive_pct = float(np.mean(clean > 0) * 100)

    return {
        "mean_ic": mean_ic,
        "ic_std": std_ic,
        "icir": icir,
        "t_stat": t_stat,
        "is_significant": is_significant,
        "ic_positive_pct": ic_positive_pct,
        "n_periods": len(clean),
        "n_stocks": n_stocks,
    }


def _empty_factor_metrics(n_stocks: int = 0) -> dict:
    return {
        "mean_ic": 0.0, "ic_std": 0.0, "icir": 0.0,
        "t_stat": 0.0, "is_significant": False,
        "ic_positive_pct": 0.0, "n_periods": 0, "n_stocks": n_stocks,
    }
