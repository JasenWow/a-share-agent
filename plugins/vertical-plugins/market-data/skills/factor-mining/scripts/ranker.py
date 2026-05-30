"""Stock ranking and portfolio evaluation using discovered factors.

Two modes:
1. rank_stocks — rank a stock pool using active factors
2. evaluate_portfolio — diagnose a user's holdings
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from evaluator import evaluate_expression_vec


# ---------------------------------------------------------------------------
# Stock ranking
# ---------------------------------------------------------------------------

def rank_stocks(
    factors: list[dict[str, Any]],
    data_arrays: dict[str, np.ndarray],
    instruments: list[str],
    lookback: int = 5,
) -> list[dict[str, Any]]:
    """Rank stocks in a pool using discovered factors.

    For each factor:
    1. Evaluate factor expression → (T, N) values
    2. Take latest values as current score
    3. Take change over lookback days as momentum signal

    Composite score = weighted sum (weight = factor ICIR).

    Args:
        factors: List of factor dicts with "expression", "icir" keys.
        data_arrays: Dict mapping field names to (T, N) arrays.
        instruments: List of stock codes (aligned with axis 1 of data_arrays).
        lookback: Number of days to look back for momentum signal.

    Returns:
        List of dicts sorted by composite score descending.
    """
    N = len(instruments)
    composite = np.zeros(N)
    momentum = np.zeros(N)
    total_weight = 0.0
    factor_details = []

    total_non_vol_weight = 0.0
    factor_meta = []  # (expr, weight, is_vol_only)

    # First pass: compute raw weights and identify volume factors
    for factor in factors:
        expr = factor["expression"]
        raw_weight = abs(factor.get("icir", 0.0))
        if raw_weight < 1e-6:
            continue
        is_vol_only = "$volume" in expr and "$close" not in expr
        if not is_vol_only:
            total_non_vol_weight += raw_weight
        factor_meta.append((expr, raw_weight, is_vol_only))

    # Cap volume factor weights at 30% of non-volume weight
    max_vol_weight = 0.3 * total_non_vol_weight if total_non_vol_weight > 0 else 0.0

    for factor in factors:
        expr = factor["expression"]
        ic = factor.get("ic", 0.0)
        weight = abs(factor.get("icir", 0.0))
        if weight < 1e-6:
            continue

        # Direction: flip for negative-IC factors
        sign = 1.0 if ic >= 0 else -1.0

        # Volume factor weight cap
        is_vol_only = "$volume" in expr and "$close" not in expr
        if is_vol_only and max_vol_weight > 0:
            weight = min(weight, max_vol_weight)

        try:
            values = evaluate_expression_vec(expr, data_arrays)
            if values.ndim == 1:
                values = values.reshape(1, -1)

            T = values.shape[0]
            if T < 2:
                continue

            # Current score: zscore of latest row
            latest = values[-1].astype(float)
            mask = ~np.isnan(latest)
            if mask.sum() < 2:
                continue

            mean_val = np.nanmean(latest)
            std_val = np.nanstd(latest)
            if std_val < 1e-12:
                continue
            zscore = np.where(mask, (latest - mean_val) / std_val, 0.0)

            # Momentum signal: change in zscore over lookback
            if T > lookback:
                prev = values[-(lookback + 1)].astype(float)
                prev_mask = ~np.isnan(prev)
                prev_mean = np.nanmean(prev)
                prev_std = np.nanstd(prev)
                if prev_std > 1e-12:
                    prev_zscore = np.where(prev_mask, (prev - prev_mean) / prev_std, 0.0)
                    delta = zscore - prev_zscore
                else:
                    delta = np.zeros(N)
            else:
                delta = np.zeros(N)

            composite += weight * sign * zscore
            momentum += weight * delta
            total_weight += weight

            factor_details.append({
                "expression": expr,
                "icir": factor.get("icir", 0.0),
                "ic": factor.get("ic", 0.0),
            })

        except Exception:
            continue

    if total_weight > 1e-6:
        composite /= total_weight
        momentum /= total_weight

    # Build results
    results = []
    for i, code in enumerate(instruments):
        results.append({
            "code": code,
            "composite_score": float(composite[i]),
            "momentum_score": float(momentum[i]),
        })

    # Sort by composite score
    results.sort(key=lambda x: x["composite_score"], reverse=True)

    # Add rank
    for rank, r in enumerate(results, 1):
        r["rank"] = rank

    # Classify signals using percentile-based thresholds
    all_scores = [r["composite_score"] for r in results]
    all_momentum = [r["momentum_score"] for r in results]
    score_p75 = np.percentile(all_scores, 75) if len(all_scores) >= 4 else np.mean(all_scores)
    mom_median = np.median(all_momentum) if len(all_momentum) >= 2 else 0.0

    for r in results:
        if r["composite_score"] > score_p75 and r["momentum_score"] > mom_median:
            r["signal"] = "强势延续"  # Strong and getting stronger
        elif r["composite_score"] > score_p75 and r["momentum_score"] <= mom_median:
            r["signal"] = "强势但转弱"  # Strong but fading
        elif r["composite_score"] <= score_p75 and r["momentum_score"] > mom_median + 0.2:
            r["signal"] = "信号转强"  # Not strong yet but accelerating
        else:
            r["signal"] = "弱势"

    return results, factor_details


# ---------------------------------------------------------------------------
# Portfolio evaluation
# ---------------------------------------------------------------------------

def evaluate_portfolio(
    holdings: list[dict[str, Any]],
    factors: list[dict[str, Any]],
    data_arrays: dict[str, np.ndarray],
    instruments: list[str],
) -> dict[str, Any]:
    """Evaluate a user's portfolio using discovered factors.

    Args:
        holdings: List of dicts with "code" and optional "shares"/"weight".
        factors: List of factor dicts.
        data_arrays: Dict mapping field names to (T, N) arrays.
        instruments: List of stock codes aligned with data_arrays.

    Returns:
        Portfolio evaluation report.
    """
    # Rank all instruments first
    rankings, factor_details = rank_stocks(factors, data_arrays, instruments)

    # Build lookup
    rank_map = {r["code"]: r for r in rankings}

    # Evaluate each holding
    holding_results = []
    for h in holdings:
        code = h["code"]
        if code in rank_map:
            r = rank_map[code]
            holding_results.append({
                "code": code,
                "rank": r["rank"],
                "total_stocks": len(instruments),
                "composite_score": r["composite_score"],
                "momentum_score": r["momentum_score"],
                "signal": r["signal"],
                "health": _assess_health(r),
            })
        else:
            holding_results.append({
                "code": code,
                "rank": None,
                "total_stocks": len(instruments),
                "composite_score": None,
                "momentum_score": None,
                "signal": "无数据",
                "health": "unknown",
            })

    # Portfolio-level diagnostics
    valid_scores = [r["composite_score"] for r in holding_results if r["composite_score"] is not None]

    diagnostics = {
        "n_holdings": len(holdings),
        "n_evaluated": len(valid_scores),
        "avg_score": float(np.mean(valid_scores)) if valid_scores else 0.0,
        "concentration_risk": _assess_concentration(holding_results, len(instruments)),
    }

    return {
        "holdings": holding_results,
        "diagnostics": diagnostics,
        "factors_used": factor_details,
    }


def _assess_health(rank_result: dict) -> str:
    """Assess the health of a single holding based on ranking."""
    score = rank_result.get("composite_score", 0)
    momentum = rank_result.get("momentum_score", 0)

    if score > 1.0 and momentum > 0:
        return "strong"
    elif score > 0 and momentum > 0:
        return "healthy"
    elif score > 0 and momentum <= 0:
        return "weakening"
    elif score <= 0 and momentum > 0.2:
        return "recovering"
    else:
        return "weak"


def _assess_concentration(holding_results: list[dict], total_stocks: int) -> str:
    """Assess if holdings are too concentrated in top ranks."""
    ranks = [r["rank"] for r in holding_results if r.get("rank") is not None]
    if not ranks:
        return "unknown"

    # Check if most holdings are in top 20%
    top_threshold = total_stocks * 0.2
    in_top = sum(1 for r in ranks if r <= top_threshold)
    ratio = in_top / len(ranks)

    if ratio > 0.8:
        return "high_concentration"  # Most holdings in top ranks
    elif ratio > 0.5:
        return "moderate"
    else:
        return "diversified"
