"""Portfolio backtest engine for factor-based strategies.

Simulates top-N long portfolio with periodic rebalancing,
computes equity curves for strategy and equal-weight benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from evaluator import evaluate_expression_vec
from metrics import compute_backtest_metrics


@dataclass
class BacktestConfig:
    """Backtest configuration."""

    top_n: int = 5             # Number of top-ranked stocks to hold long
    rebalance_days: int = 5    # Rebalance frequency (trading days)
    commission: float = 0.003  # Single-side commission rate
    slippage: float = 0.001    # Slippage per trade

    def __post_init__(self):
        assert self.top_n >= 1, "top_n must be >= 1"
        assert self.rebalance_days >= 1, "rebalance_days must be >= 1"
        assert self.commission >= 0, "commission must be >= 0"


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    equity_curve: np.ndarray       # (T,) strategy net asset value, starting at 1.0
    benchmark_curve: np.ndarray    # (T,) equal-weight benchmark NAV, starting at 1.0
    trades: list[dict]             # Trade log
    metrics: dict                  # Performance metrics (from metrics.py)
    config: BacktestConfig = field(default_factory=BacktestConfig)
    rebalance_dates: list[int] = field(default_factory=list)  # Indices where rebalance happened


def run_backtest(
    factors: list[dict[str, Any]],
    data_arrays: dict[str, np.ndarray],
    instruments: list[str],
    config: BacktestConfig | None = None,
    test_start_idx: int = 0,
) -> BacktestResult:
    """Run a backtest of a factor-based ranking strategy.

    Strategy:
    - At each rebalance date, rank all stocks by composite factor score
    - Hold top-N stocks with equal weight
    - Deduct commission on position changes

    Args:
        factors: List of factor dicts with "expression", "ic", "icir" keys.
        data_arrays: Dict mapping "$field" → (T, N) arrays.
        instruments: Stock codes aligned with axis-1 of data_arrays.
        config: BacktestConfig (uses defaults if None).
        test_start_idx: Index in time axis where test period begins.

    Returns:
        BacktestResult with equity curves and metrics.
    """
    if config is None:
        config = BacktestConfig()

    T, N = _get_shape(data_arrays)
    close_key = "$close" if "$close" in data_arrays else "close"
    close = data_arrays[close_key]  # (T, N)

    # Pre-compute factor values for all periods
    factor_signs = []
    factor_weights = []
    factor_values_list = []

    total_non_vol_weight = 0.0
    for f in factors:
        expr = f["expression"]
        ic = f.get("ic", 0.0)
        weight = abs(f.get("icir", 0.0))
        if weight < 1e-6:
            continue

        # Direction: flip for negative-IC factors
        sign = 1.0 if ic >= 0 else -1.0

        # Volume factor weight cap
        is_vol_only = "$volume" in expr and "$close" not in expr
        if is_vol_only:
            # Will cap after first pass
            pass
        else:
            total_non_vol_weight += weight

        try:
            vals = evaluate_expression_vec(expr, data_arrays)
            if vals.ndim == 1:
                vals = vals.reshape(1, -1)
            # Pad or trim to match T
            if vals.shape[0] < T:
                pad = np.full((T - vals.shape[0], N), np.nan)
                vals = np.vstack([pad, vals])
            elif vals.shape[0] > T:
                vals = vals[:T]
            factor_signs.append(sign)
            factor_weights.append(weight)
            factor_values_list.append(vals.astype(float))
        except Exception:
            continue

    if not factor_values_list:
        # No valid factors — return flat equity
        return _flat_result(T, test_start_idx, config)

    # Cap volume factor weights
    max_vol_weight = 0.3 * total_non_vol_weight if total_non_vol_weight > 0 else 0.0
    for i, f in enumerate(factors):
        expr = f["expression"]
        is_vol_only = "$volume" in expr and "$close" not in expr
        if is_vol_only and max_vol_weight > 0:
            factor_weights[i] = min(factor_weights[i], max_vol_weight)

    total_w = sum(factor_weights)
    if total_w < 1e-6:
        return _flat_result(T, test_start_idx, config)

    # Build composite score per period: (T, N)
    composite = np.zeros((T, N))
    for sign, w, vals in zip(factor_signs, factor_weights, factor_values_list):
        # Zscore row-by-row
        for t in range(T):
            row = vals[t]
            mask = ~np.isnan(row)
            if mask.sum() < 2:
                continue
            mean_v = np.nanmean(row)
            std_v = np.nanstd(row)
            if std_v < 1e-12:
                continue
            z = np.where(mask, (row - mean_v) / std_v, 0.0)
            composite[t] += sign * (w / total_w) * z

    # --- Backtest loop (test period only) ---
    equity = np.ones(T)
    benchmark = np.ones(T)
    trades = []
    rebalance_dates = []
    current_holdings = set()  # set of instrument indices

    for t in range(max(test_start_idx, 1), T):
        # Equal-weight benchmark return
        bm_ret = _equal_weight_return(close[t - 1], close[t])
        benchmark[t] = benchmark[t - 1] * (1 + bm_ret)

        # Check if rebalance date
        is_rebalance = (t == test_start_idx) or \
                       ((t - test_start_idx) % config.rebalance_days == 0)

        if is_rebalance:
            rebalance_dates.append(t)
            # Rank by composite score at t
            scores = composite[t]
            valid_mask = ~np.isnan(scores)
            if valid_mask.sum() < config.top_n:
                # Not enough valid scores — hold previous or skip
                strat_ret = _portfolio_return(close[t - 1], close[t], list(current_holdings), N)
                equity[t] = equity[t - 1] * (1 + strat_ret)
                continue

            # Select top-N
            ranked_indices = np.argsort(-scores)  # descending
            new_holdings = set()
            for idx in ranked_indices:
                if valid_mask[idx] and len(new_holdings) < config.top_n:
                    new_holdings.add(int(idx))

            # Compute turnover cost
            sell = current_holdings - new_holdings
            buy = new_holdings - current_holdings
            n_trades = len(sell) + len(buy)
            turnover_cost = n_trades * (config.commission + config.slippage) / (2 * config.top_n)

            if n_trades > 0:
                trades.append({
                    "day": t,
                    "buy": [instruments[i] for i in buy],
                    "sell": [instruments[i] for i in sell],
                    "cost_pct": turnover_cost * 100,
                })

            current_holdings = new_holdings

            # First period: no return yet, just deduct cost
            if t == test_start_idx:
                equity[t] = equity[t - 1] * (1 - turnover_cost)
                continue

            # Compute strategy return
            strat_ret = _portfolio_return(close[t - 1], close[t], list(current_holdings), N)
            equity[t] = equity[t - 1] * (1 + strat_ret - turnover_cost)
        else:
            # Hold current positions
            strat_ret = _portfolio_return(close[t - 1], close[t], list(current_holdings), N)
            equity[t] = equity[t - 1] * (1 + strat_ret)

    # Trim to test period for metrics
    test_equity = equity[test_start_idx:]
    test_benchmark = benchmark[test_start_idx:]

    metrics = compute_backtest_metrics(test_equity, test_benchmark)

    return BacktestResult(
        equity_curve=equity,
        benchmark_curve=benchmark,
        trades=trades,
        metrics=metrics,
        config=config,
        rebalance_dates=rebalance_dates,
    )


def _get_shape(data_arrays: dict[str, np.ndarray]) -> tuple[int, int]:
    """Get (T, N) shape from data_arrays."""
    for v in data_arrays.values():
        if isinstance(v, np.ndarray) and v.ndim == 2:
            return v.shape
    return 0, 0


def _equal_weight_return(prev_close: np.ndarray, curr_close: np.ndarray) -> float:
    """Equal-weight return across all stocks with valid data."""
    mask = (~np.isnan(prev_close)) & (~np.isnan(curr_close)) & (prev_close > 0)
    if mask.sum() == 0:
        return 0.0
    rets = curr_close[mask] / prev_close[mask] - 1
    return float(np.mean(rets))


def _portfolio_return(
    prev_close: np.ndarray,
    curr_close: np.ndarray,
    holdings: list[int],
    N: int,
) -> float:
    """Equal-weight return for a specific set of holdings."""
    if not holdings:
        return 0.0
    rets = []
    for idx in holdings:
        if idx < len(prev_close) and idx < len(curr_close):
            p, c = prev_close[idx], curr_close[idx]
            if not (np.isnan(p) or np.isnan(c)) and p > 0:
                rets.append(c / p - 1)
    return float(np.mean(rets)) if rets else 0.0


def _flat_result(T: int, test_start: int, config: BacktestConfig) -> BacktestResult:
    """Return flat equity curve (no valid factors)."""
    equity = np.ones(T)
    benchmark = np.ones(T)
    test_eq = equity[test_start:]
    return BacktestResult(
        equity_curve=equity,
        benchmark_curve=benchmark,
        trades=[],
        metrics=compute_backtest_metrics(test_eq, test_eq),
        config=config,
    )
