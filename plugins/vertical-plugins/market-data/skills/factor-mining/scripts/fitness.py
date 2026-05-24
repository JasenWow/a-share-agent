"""Factor fitness evaluation using IC/ICIR with turnover penalty.

Core metrics:
- Rank IC (Spearman rank correlation between factor values and forward returns)
- ICIR (mean IC / std IC across time periods)
- Turnover penalty (portfolio rebalance cost proxy)
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def compute_rank_ic(factor_values: np.ndarray, forward_returns: np.ndarray) -> float:
    """Compute Spearman rank correlation (Rank IC) between factor and returns.

    Args:
        factor_values: 1-D array of factor values across stocks.
        forward_returns: 1-D array of forward returns for same stocks.

    Returns:
        Spearman rank correlation coefficient in [-1, 1].
    """
    factor_values = np.asarray(factor_values, dtype=float)
    forward_returns = np.asarray(forward_returns, dtype=float)

    # Remove NaN entries
    mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
    f, r = factor_values[mask], forward_returns[mask]
    if len(f) < 3:
        return 0.0

    corr, _ = stats.spearmanr(f, r)
    return float(corr) if not np.isnan(corr) else 0.0


def compute_ic_series(
    factor_values_2d: np.ndarray,
    forward_returns_2d: np.ndarray,
) -> np.ndarray:
    """Compute Rank IC for each time period (row).

    Args:
        factor_values_2d: (T, N) array — factor values per period.
        forward_returns_2d: (T, N) array — forward returns per period.

    Returns:
        1-D array of IC values with length T.
    """
    factor_values_2d = np.asarray(factor_values_2d, dtype=float)
    forward_returns_2d = np.asarray(forward_returns_2d, dtype=float)
    n_periods = factor_values_2d.shape[0]

    ic_vals = np.array(
        [compute_rank_ic(factor_values_2d[t], forward_returns_2d[t]) for t in range(n_periods)]
    )
    return ic_vals


def compute_turnover(factor_ranks_2d: np.ndarray) -> float:
    """Estimate turnover as 1 - average rank correlation between adjacent periods.

    Args:
        factor_ranks_2d: (T, N) array of factor ranks per period.

    Returns:
        Turnover value in [0, 2]. Lower means more stable.
    """
    factor_ranks_2d = np.asarray(factor_ranks_2d, dtype=float)
    n_periods = factor_ranks_2d.shape[0]
    if n_periods < 2:
        return 0.0

    corr_sum = 0.0
    count = 0
    for t in range(n_periods - 1):
        mask = ~(np.isnan(factor_ranks_2d[t]) | np.isnan(factor_ranks_2d[t + 1]))
        if mask.sum() < 3:
            continue
        corr, _ = stats.spearmanr(factor_ranks_2d[t][mask], factor_ranks_2d[t + 1][mask])
        if not np.isnan(corr):
            corr_sum += corr
            count += 1

    if count == 0:
        return 1.0
    return 1.0 - corr_sum / count


def compute_fitness(ic_series: np.ndarray, turnover: float = 0.0) -> float:
    """Compute composite fitness score.

    Formula: 0.6 * ICIR + 0.2 * mean_IC - 0.2 * turnover

    NaN values in ic_series are ignored.

    Args:
        ic_series: Array of IC values across time periods.
        turnover: Estimated turnover penalty.

    Returns:
        Composite fitness score.
    """
    ic_series = np.asarray(ic_series, dtype=float)
    # Filter NaN
    ic_clean = ic_series[~np.isnan(ic_series)]
    if len(ic_clean) < 2:
        return 0.0

    mean_ic = float(np.mean(ic_clean))
    std_ic = float(np.std(ic_clean))
    icir = mean_ic / std_ic if std_ic > 1e-12 else 0.0

    return 0.6 * icir + 0.2 * mean_ic - 0.2 * turnover


def evaluate_expression(
    expression: str,
    instruments: str = "csi300",
    start_date: str = "2020-01-01",
    end_date: str = "2025-01-01",
    *,
    _mock_factor_values: np.ndarray | None = None,
    _mock_forward_returns: np.ndarray | None = None,
    data_arrays: dict | None = None,
    forward_returns_2d: np.ndarray | None = None,
) -> tuple[float, dict]:
    """Evaluate a factor expression and return fitness + detailed metrics.

    Three modes:
    1. Mock: pass _mock_factor_values and _mock_forward_returns
    2. Production: pass data_arrays (field→ndarray) and forward_returns_2d
    3. Neither: raises NotImplementedError

    Args:
        expression: Qlib-style factor expression string.
        instruments: Universe identifier.
        start_date: Back-test start date.
        end_date: Back-test end date.
        _mock_factor_values: (T, N) mock factor values for testing.
        _mock_forward_returns: (T, N) mock forward returns for testing.
        data_arrays: Dict mapping field names to (T, N) arrays for real eval.
        forward_returns_2d: (T, N) forward returns for real eval.

    Returns:
        Tuple of (fitness_score, metrics_dict).
    """
    if _mock_factor_values is not None and _mock_forward_returns is not None:
        factor_values = np.asarray(_mock_factor_values, dtype=float)
        forward_returns = np.asarray(_mock_forward_returns, dtype=float)
        if factor_values.ndim == 1:
            factor_values = factor_values.reshape(1, -1)
        if forward_returns.ndim == 1:
            forward_returns = forward_returns.reshape(1, -1)
    elif data_arrays is not None and forward_returns_2d is not None:
        from evaluator import evaluate_expression_vec

        factor_values = evaluate_expression_vec(expression, data_arrays)
        forward_returns = np.asarray(forward_returns_2d, dtype=float)
        if factor_values.ndim == 1:
            factor_values = factor_values.reshape(1, -1)
    else:
        raise NotImplementedError("Pass mock data or (data_arrays + forward_returns_2d)")

    ic_series = compute_ic_series(factor_values, forward_returns)
    turnover = compute_turnover(np.argsort(np.argsort(factor_values), axis=1))
    fitness = compute_fitness(ic_series, turnover)

    ic_clean = ic_series[~np.isnan(ic_series)]
    mean_ic = float(np.mean(ic_clean)) if len(ic_clean) > 0 else 0.0
    std_ic = float(np.std(ic_clean)) if len(ic_clean) > 1 else 0.0
    icir = mean_ic / std_ic if std_ic > 1e-12 else 0.0

    metrics = {
        "ic": mean_ic,
        "ic_std": std_ic,
        "icir": icir,
        "turnover": turnover,
        "n_periods": factor_values.shape[0],
    }

    return fitness, metrics
