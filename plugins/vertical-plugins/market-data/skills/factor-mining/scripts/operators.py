"""Qlib operator -> DEAP primitive mapping.

Dictionary-based registry mapping Qlib-style operators to numpy callables
suitable for use as DEAP primitives in genetic programming.
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Helper: safe division (avoids divide-by-zero)
# ---------------------------------------------------------------------------

def _safe_div(a, b):
    """Element-wise division with zero-division protection."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.where(np.abs(b) > 1e-12, a / b, 0.0)


# ---------------------------------------------------------------------------
# Time-series operators (arity 2-3)
# ---------------------------------------------------------------------------

def _ts_mean(arr, window):
    """Rolling mean of last *window* elements, returning scalar."""
    arr = np.asarray(arr, dtype=float)
    return float(np.mean(arr[-int(window):]))


def _ts_std(arr, window):
    arr = np.asarray(arr, dtype=float)
    return float(np.std(arr[-int(window):]))


def _ts_max(arr, window):
    arr = np.asarray(arr, dtype=float)
    return float(np.max(arr[-int(window):]))


def _ts_min(arr, window):
    arr = np.asarray(arr, dtype=float)
    return float(np.min(arr[-int(window):]))


def _ts_rank(arr, window):
    """Rank of last value within rolling window."""
    arr = np.asarray(arr, dtype=float)
    w = arr[-int(window):]
    return float(np.sum(w[-1] >= w)) / len(w)


def _ts_sum(arr, window):
    arr = np.asarray(arr, dtype=float)
    return float(np.sum(arr[-int(window):]))


def _ts_corr(arr_a, arr_b):
    """Correlation between two series."""
    a = np.asarray(arr_a, dtype=float).ravel()
    b = np.asarray(arr_b, dtype=float).ravel()
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n < 2 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _delta(arr, window):
    arr = np.asarray(arr, dtype=float)
    w = int(window)
    if len(arr) <= w:
        return 0.0
    return float(arr[-1] - arr[-w - 1])


def _pct_change(arr, window):
    arr = np.asarray(arr, dtype=float)
    w = int(window)
    if len(arr) <= w or abs(arr[-w - 1]) < 1e-12:
        return 0.0
    return float((arr[-1] - arr[-w - 1]) / abs(arr[-w - 1]))


# ---------------------------------------------------------------------------
# Cross-section operators (arity 1)
# ---------------------------------------------------------------------------

def _rank(arr):
    """Cross-sectional rank scaled to [0, 1]."""
    arr = np.asarray(arr, dtype=float)
    order = arr.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(arr) + 1, dtype=float)
    return ranks / len(arr)


def _zscore(arr):
    arr = np.asarray(arr, dtype=float)
    std = np.std(arr)
    if std < 1e-12:
        return np.zeros_like(arr)
    return (arr - np.mean(arr)) / std


def _demean(arr):
    arr = np.asarray(arr, dtype=float)
    return arr - np.mean(arr)


def _scale(arr):
    """Scale so that sum of absolute values equals 1."""
    arr = np.asarray(arr, dtype=float)
    denom = np.sum(np.abs(arr))
    if denom < 1e-12:
        return np.zeros_like(arr)
    return arr / denom


def _sign(arr):
    arr = np.asarray(arr, dtype=float)
    return np.sign(arr)


# ---------------------------------------------------------------------------
# Arithmetic operators (arity 1-2)
# ---------------------------------------------------------------------------

def _add(a, b):
    return float(a) + float(b)


def _sub(a, b):
    return float(a) - float(b)


def _mul(a, b):
    return float(a) * float(b)


def _div(a, b):
    b = float(b)
    return float(a) / b if abs(b) > 1e-12 else 0.0


def _abs_op(a):
    return float(np.abs(a))


def _log_op(a):
    a = float(a)
    return float(np.log(a)) if a > 1e-12 else -25.0


def _exp_op(a):
    return float(np.clip(np.exp(float(a)), -1e10, 1e10))


def _max_op(a, b):
    return float(max(a, b))


def _min_op(a, b):
    return float(min(a, b))


def _sqrt_op(a):
    a = float(a)
    return float(np.sqrt(a)) if a > 0 else 0.0


# ---------------------------------------------------------------------------
# Conditional operators (arity 3)
# ---------------------------------------------------------------------------

def _if_else(cond, a, b):
    return float(a) if float(cond) > 0 else float(b)


def _clamp(val, lo, hi):
    return float(np.clip(float(val), float(lo), float(hi)))


# ---------------------------------------------------------------------------
# Operator registry
# ---------------------------------------------------------------------------

OPERATOR_REGISTRY: dict[str, list[dict]] = {
    "time-series": [
        {"name": "Ts_Mean", "arity": 2, "qlib_expr": "Ts_Mean({0}, {1})", "deap_func": _ts_mean},
        {"name": "Ts_Std", "arity": 2, "qlib_expr": "Ts_Std({0}, {1})", "deap_func": _ts_std},
        {"name": "Ts_Max", "arity": 2, "qlib_expr": "Ts_Max({0}, {1})", "deap_func": _ts_max},
        {"name": "Ts_Min", "arity": 2, "qlib_expr": "Ts_Min({0}, {1})", "deap_func": _ts_min},
        {"name": "Ts_Rank", "arity": 2, "qlib_expr": "Ts_Rank({0}, {1})", "deap_func": _ts_rank},
        {"name": "Ts_Sum", "arity": 2, "qlib_expr": "Ts_Sum({0}, {1})", "deap_func": _ts_sum},
        {"name": "Ts_Corr", "arity": 2, "qlib_expr": "Ts_Corr({0}, {1})", "deap_func": _ts_corr},
        {"name": "Delta", "arity": 2, "qlib_expr": "Delta({0}, {1})", "deap_func": _delta},
        {"name": "Pct_Change", "arity": 2, "qlib_expr": "Pct_Change({0}, {1})", "deap_func": _pct_change},
    ],
    "cross-section": [
        {"name": "Rank", "arity": 1, "qlib_expr": "Rank({0})", "deap_func": _rank},
        {"name": "ZScore", "arity": 1, "qlib_expr": "ZScore({0})", "deap_func": _zscore},
        {"name": "Demean", "arity": 1, "qlib_expr": "Demean({0})", "deap_func": _demean},
        {"name": "Scale", "arity": 1, "qlib_expr": "Scale({0})", "deap_func": _scale},
        {"name": "Sign", "arity": 1, "qlib_expr": "Sign({0})", "deap_func": _sign},
    ],
    "arithmetic": [
        {"name": "Add", "arity": 2, "qlib_expr": "({0} + {1})", "deap_func": _add},
        {"name": "Sub", "arity": 2, "qlib_expr": "({0} - {1})", "deap_func": _sub},
        {"name": "Mul", "arity": 2, "qlib_expr": "({0} * {1})", "deap_func": _mul},
        {"name": "Div", "arity": 2, "qlib_expr": "({0} / {1})", "deap_func": _div},
        {"name": "Abs", "arity": 1, "qlib_expr": "Abs({0})", "deap_func": _abs_op},
        {"name": "Log", "arity": 1, "qlib_expr": "Log({0})", "deap_func": _log_op},
        {"name": "Exp", "arity": 1, "qlib_expr": "Exp({0})", "deap_func": _exp_op},
        {"name": "Max", "arity": 2, "qlib_expr": "Max({0}, {1})", "deap_func": _max_op},
        {"name": "Min", "arity": 2, "qlib_expr": "Min({0}, {1})", "deap_func": _min_op},
        {"name": "Sqrt", "arity": 1, "qlib_expr": "Sqrt({0})", "deap_func": _sqrt_op},
    ],
    "conditional": [
        {"name": "If_Else", "arity": 3, "qlib_expr": "If({0}, {1}, {2})", "deap_func": _if_else},
        {"name": "Clamp", "arity": 3, "qlib_expr": "Clamp({0}, {1}, {2})", "deap_func": _clamp},
    ],
}


# Build name -> operator lookup for fast access
_OPERATOR_BY_NAME: dict[str, dict] = {}
for _cat, _ops in OPERATOR_REGISTRY.items():
    for _op in _ops:
        _OPERATOR_BY_NAME[_op["name"]] = _op


def get_operator(name: str) -> dict | None:
    """Look up an operator by name."""
    return _OPERATOR_BY_NAME.get(name)


def expression_to_qlib_string(op_name: str, args: list[str]) -> str:
    """Format an operator with its arguments as a Qlib expression string.

    Args:
        op_name: Operator name, e.g. "Rank", "Ts_Mean".
        args: List of argument string representations.

    Returns:
        Formatted Qlib expression string.
    """
    op = _OPERATOR_BY_NAME.get(op_name)
    if op is None:
        return f"{op_name}({', '.join(args)})"
    return op["qlib_expr"].format(*args)
