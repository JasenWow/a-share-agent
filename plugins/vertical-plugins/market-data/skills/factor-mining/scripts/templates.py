"""Factor template definitions and enumeration search.

Defines factor templates across 6 categories (trend, momentum, volatility,
volume-price, mean-reversion, strength) and provides grid search over
template × field × window combinations.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from evaluator import evaluate_expression_vec
from fitness import compute_fitness, compute_ic_series, compute_turnover


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

# Each template is a format string with placeholders:
#   $X, $Y  → data fields (e.g., $close, $volume)
#   {W}     → window size (e.g., 5, 10, 20, 60)
#   {W1},{W2} → two independent window sizes

TEMPLATES: dict[str, list[str]] = {
    "trend": [
        "Rank($X / Ts_Mean($X, {W}))",                  # price relative to moving average
        "Rank(Delta($X, {W}) / Ts_Std($X, {W}))",      # normalized momentum
    ],
    "momentum": [
        "Rank(Delta($X, {W}))",                          # absolute momentum
        "Rank(Ts_Sum(Sign(Delta($X, 1)), {W}))",        # fraction of up days
    ],
    "volatility": [
        "Rank(-1 * Ts_Std($X, {W}))",                   # low volatility
        "Rank(Ts_Mean($X, {W1}) / Ts_Std($X, {W2}))",   # volatility-adjusted level
    ],
    "volume_price": [
        "Ts_Corr($X, $Y, {W})",                          # price-volume correlation
        "Rank($X / Ts_Sum($Y, {W}))",                    # price-to-volume ratio
    ],
    "mean_reversion": [
        "Rank(($X - Ts_Mean($X, {W})) / Ts_Std($X, {W}))",  # z-score reversion
        "Rank(-1 * Abs($X / Ts_Mean($X, {W}) - 1))",        # deviation reversal
    ],
    "strength": [
        "Rank(Ts_Max($X, {W}) / $X)",                   # distance from high (lower = stronger)
        "Rank($X / Ts_Min($X, {W}))",                   # distance from low (higher = stronger)
    ],
}

DEFAULT_FIELDS = ["$close", "$open", "$high", "$low", "$volume"]
DEFAULT_WINDOWS = [5, 10, 20, 60]


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def enumerate_candidates(
    templates: dict[str, list[str]] | None = None,
    fields: list[str] | None = None,
    windows: list[int] | None = None,
    categories: list[str] | None = None,
) -> list[dict[str, str]]:
    """Generate all candidate expressions from template × field × window grid.

    Args:
        templates: Template dict. Defaults to TEMPLATES.
        fields: Data field names like ["$close", "$volume"].
        windows: Window sizes like [5, 10, 20, 60].
        categories: Only enumerate these categories. None = all.

    Returns:
        List of dicts with keys "expression", "category", "template".
    """
    if templates is None:
        templates = TEMPLATES
    if fields is None:
        fields = DEFAULT_FIELDS
    if windows is None:
        windows = DEFAULT_WINDOWS

    candidates = []

    for cat, cat_templates in templates.items():
        if categories and cat not in categories:
            continue
        for tmpl in cat_templates:
            # Determine template type: single-field, dual-field, or dual-window
            has_dual_field = "$Y" in tmpl
            has_dual_window = "{W1}" in tmpl

            if has_dual_window and has_dual_field:
                # e.g. "Rank(Ts_Mean($X, {W1}) / Ts_Std($X, {W2}))"
                for x in fields:
                    expr_base = tmpl.replace("$X", x)
                    for w1 in windows:
                        for w2 in windows:
                            expr = expr_base.replace("{W1}", str(w1)).replace("{W2}", str(w2))
                            candidates.append({
                                "expression": expr,
                                "category": cat,
                                "template": tmpl,
                            })
            elif has_dual_window:
                for x in fields:
                    expr_base = tmpl.replace("$X", x)
                    for w1 in windows:
                        for w2 in windows:
                            expr = expr_base.replace("{W1}", str(w1)).replace("{W2}", str(w2))
                            candidates.append({
                                "expression": expr,
                                "category": cat,
                                "template": tmpl,
                            })
            elif has_dual_field:
                # e.g. "Ts_Corr($X, $Y, {W})"
                for x in fields:
                    for y in fields:
                        if x == y:
                            continue
                        expr_base = tmpl.replace("$X", x).replace("$Y", y)
                        for w in windows:
                            expr = expr_base.replace("{W}", str(w))
                            candidates.append({
                                "expression": expr,
                                "category": cat,
                                "template": tmpl,
                            })
            else:
                # Single field, single window
                for x in fields:
                    expr_base = tmpl.replace("$X", x)
                    for w in windows:
                        expr = expr_base.replace("{W}", str(w))
                        candidates.append({
                            "expression": expr,
                            "category": cat,
                            "template": tmpl,
                        })

    return candidates


# ---------------------------------------------------------------------------
# Template search evaluation
# ---------------------------------------------------------------------------

def evaluate_candidate(
    expression: str,
    data_arrays: dict[str, np.ndarray],
    forward_returns: np.ndarray,
    min_periods: int = 20,
) -> dict[str, Any]:
    """Evaluate a single candidate expression.

    Args:
        expression: Factor expression string.
        data_arrays: Dict mapping field names to (T, N) arrays.
        forward_returns: (T, N) forward returns array.
        min_periods: Minimum number of valid periods for IC calculation.

    Returns:
        Dict with expression, ic, icir, turnover, fitness, n_periods.
    """
    try:
        factor_values = evaluate_expression_vec(expression, data_arrays)
        if factor_values.ndim == 1:
            factor_values = factor_values.reshape(1, -1)
        forward_returns = np.asarray(forward_returns, dtype=float)
        if forward_returns.ndim == 1:
            forward_returns = forward_returns.reshape(1, -1)

        ic_series = compute_ic_series(factor_values, forward_returns)
        turnover = compute_turnover(np.argsort(np.argsort(factor_values), axis=1))
        fitness = compute_fitness(ic_series, turnover)

        ic_clean = ic_series[~np.isnan(ic_series)]
        mean_ic = float(np.mean(ic_clean)) if len(ic_clean) > 0 else 0.0
        std_ic = float(np.std(ic_clean)) if len(ic_clean) > 1 else 0.0
        icir = mean_ic / std_ic if std_ic > 1e-12 else 0.0

        return {
            "expression": expression,
            "ic": mean_ic,
            "icir": icir,
            "turnover": turnover,
            "fitness": fitness,
            "n_periods": len(ic_clean),
        }
    except Exception:
        return {
            "expression": expression,
            "ic": 0.0,
            "icir": 0.0,
            "turnover": 0.0,
            "fitness": -999.0,
            "n_periods": 0,
        }


def template_search(
    candidates: list[dict[str, str]],
    data_arrays: dict[str, np.ndarray],
    forward_returns: np.ndarray,
    top_k: int = 20,
    min_ic: float = 0.02,
    min_periods: int = 20,
) -> list[dict[str, Any]]:
    """Evaluate all candidates and return top-k sorted by fitness.

    Args:
        candidates: List of candidate dicts from enumerate_candidates().
        data_arrays: Dict mapping field names to (T, N) arrays.
        forward_returns: (T, N) forward returns array.
        top_k: Number of top candidates to return.
        min_ic: Minimum absolute IC to consider valid.
        min_periods: Minimum valid periods for IC calculation.

    Returns:
        List of evaluation result dicts sorted by fitness descending.
    """
    results = []
    for cand in candidates:
        result = evaluate_candidate(
            cand["expression"], data_arrays, forward_returns, min_periods
        )
        result["category"] = cand["category"]
        result["template"] = cand["template"]
        # Only keep results with meaningful IC
        if abs(result["ic"]) >= min_ic and result["n_periods"] >= min_periods:
            results.append(result)

    results.sort(key=lambda r: r["fitness"], reverse=True)
    return results[:top_k]
