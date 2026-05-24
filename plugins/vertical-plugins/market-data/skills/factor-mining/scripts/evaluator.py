"""Vectorized expression evaluator for GP-generated factor expressions.

Evaluates Qlib-style expression strings against pre-fetched (T, N) numpy arrays
using vectorized numpy/pandas operations. No MCP roundtrips during evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Safe division helper
# ---------------------------------------------------------------------------

def _safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.where(np.abs(b) > 1e-12, a / b, 0.0)


# ---------------------------------------------------------------------------
# Vectorized time-series operators (rolling along axis 0 = time)
# ---------------------------------------------------------------------------

def _vec_ts_mean(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return pd.Series(arr).rolling(window, min_periods=1).mean().values
    return pd.DataFrame(arr).rolling(window, min_periods=1).mean().values


def _vec_ts_std(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return pd.Series(arr).rolling(window, min_periods=1).std().values
    return pd.DataFrame(arr).rolling(window, min_periods=1).std().values


def _vec_ts_max(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return pd.Series(arr).rolling(window, min_periods=1).max().values
    return pd.DataFrame(arr).rolling(window, min_periods=1).max().values


def _vec_ts_min(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return pd.Series(arr).rolling(window, min_periods=1).min().values
    return pd.DataFrame(arr).rolling(window, min_periods=1).min().values


def _vec_ts_sum(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return pd.Series(arr).rolling(window, min_periods=1).sum().values
    return pd.DataFrame(arr).rolling(window, min_periods=1).sum().values


def _vec_ts_rank(arr, window):
    window = max(int(window), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).rank(pct=True).values
    result = np.full_like(arr, np.nan)
    df = pd.DataFrame(arr)
    for col in df.columns:
        result[:, col] = df[col].rolling(window, min_periods=1).rank(pct=True).values
    return result


def _vec_delta(arr, period):
    period = max(int(period), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        result = np.full_like(arr, np.nan)
        result[period:] = arr[period:] - arr[:-period]
        return result
    result = np.full_like(arr, np.nan)
    result[period:] = arr[period:] - arr[:-period]
    return result


def _vec_pct_change(arr, period):
    period = max(int(period), 1)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        s = pd.Series(arr)
        return s.pct_change(periods=period).values
    df = pd.DataFrame(arr)
    return df.pct_change(periods=period).values


# ---------------------------------------------------------------------------
# Vectorized cross-section operators (operate along axis 1 = stocks per row)
# ---------------------------------------------------------------------------

def _vec_rank(arr):
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return _rank_1d(arr)
    return np.apply_along_axis(_rank_1d, 1, arr)


def _rank_1d(arr):
    mask = ~np.isnan(arr)
    result = np.full_like(arr, np.nan, dtype=float)
    if mask.sum() < 2:
        return result
    valid = arr[mask]
    order = valid.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(order) + 1, dtype=float)
    result[mask] = ranks / len(order)
    return result


def _vec_zscore(arr):
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        std = np.nanstd(arr)
        if std < 1e-12:
            return np.zeros_like(arr)
        return (arr - np.nanmean(arr)) / std
    means = np.nanmean(arr, axis=1, keepdims=True)
    stds = np.nanstd(arr, axis=1, keepdims=True)
    stds = np.where(stds < 1e-12, 1.0, stds)
    return (arr - means) / stds


def _vec_demean(arr):
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        return arr - np.nanmean(arr)
    return arr - np.nanmean(arr, axis=1, keepdims=True)


def _vec_scale(arr):
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 1:
        denom = np.nansum(np.abs(arr))
        if denom < 1e-12:
            return np.zeros_like(arr)
        return arr / denom
    denoms = np.nansum(np.abs(arr), axis=1, keepdims=True)
    denoms = np.where(denoms < 1e-12, 1.0, denoms)
    return arr / denoms


def _vec_sign(arr):
    return np.sign(np.asarray(arr, dtype=float))


# ---------------------------------------------------------------------------
# Vectorized arithmetic operators
# ---------------------------------------------------------------------------

def _vec_add(a, b):
    return np.asarray(a, dtype=float) + np.asarray(b, dtype=float)


def _vec_sub(a, b):
    return np.asarray(a, dtype=float) - np.asarray(b, dtype=float)


def _vec_mul(a, b):
    return np.asarray(a, dtype=float) * np.asarray(b, dtype=float)


def _vec_div(a, b):
    return _safe_div(a, b)


def _vec_abs(a):
    return np.abs(np.asarray(a, dtype=float))


def _vec_log(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 1e-12, np.log(a), -25.0)


def _vec_exp(a):
    return np.clip(np.exp(np.asarray(a, dtype=float)), -1e10, 1e10)


def _vec_max(a, b):
    return np.maximum(np.asarray(a, dtype=float), np.asarray(b, dtype=float))


def _vec_min(a, b):
    return np.minimum(np.asarray(a, dtype=float), np.asarray(b, dtype=float))


def _vec_sqrt(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, np.sqrt(a), 0.0)


# ---------------------------------------------------------------------------
# Vectorized conditional operators
# ---------------------------------------------------------------------------

def _vec_if_else(cond, a, b):
    cond = np.asarray(cond, dtype=float)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.where(cond > 0, a, b)


def _vec_clamp(val, lo, hi):
    return np.clip(np.asarray(val, dtype=float), float(lo), float(hi))


# ---------------------------------------------------------------------------
# Operator namespace for eval()
# ---------------------------------------------------------------------------

_OPERATOR_NAMESPACE = {
    # Time-series
    "Ts_Mean": _vec_ts_mean,
    "Ts_Std": _vec_ts_std,
    "Ts_Max": _vec_ts_max,
    "Ts_Min": _vec_ts_min,
    "Ts_Rank": _vec_ts_rank,
    "Ts_Sum": _vec_ts_sum,
    "Delta": _vec_delta,
    "Pct_Change": _vec_pct_change,
    # Cross-section
    "Rank": _vec_rank,
    "ZScore": _vec_zscore,
    "Demean": _vec_demean,
    "Scale": _vec_scale,
    "Sign": _vec_sign,
    # Arithmetic
    "Add": _vec_add,
    "Sub": _vec_sub,
    "Mul": _vec_mul,
    "Div": _vec_div,
    "Abs": _vec_abs,
    "Log": _vec_log,
    "Exp": _vec_exp,
    "Max": _vec_max,
    "Min": _vec_min,
    "Sqrt": _vec_sqrt,
    # Conditional
    "If_Else": _vec_if_else,
    "Clamp": _vec_clamp,
}


def evaluate_expression_vec(
    expression: str,
    data_arrays: dict[str, np.ndarray],
) -> np.ndarray:
    """Evaluate a GP-generated expression against pre-fetched numpy data.

    Uses Python eval() with a restricted namespace containing vectorized
    operator functions and data arrays.

    Args:
        expression: GP expression string, e.g. "Ts_Mean($close, 5) / $close".
        data_arrays: Dict mapping field names to (T, N) arrays, e.g. {"$close": arr}.

    Returns:
        (T, N) numpy array of factor values.
    """
    # Build eval namespace: operators + data fields (strip $ for valid Python)
    namespace = dict(_OPERATOR_NAMESPACE)
    for field, arr in data_arrays.items():
        key = field.lstrip("$")
        namespace[key] = arr

    # Convert expression: $close → close
    eval_expr = expression.replace("$", "")

    try:
        result = eval(eval_expr, {"__builtins__": {}}, namespace)
        return np.asarray(result, dtype=float)
    except Exception:
        return np.full((1, 1), np.nan)
