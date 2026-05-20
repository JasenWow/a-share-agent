"""Stock-pool scorecard filter — pure data transformation, no I/O.

Reads candidate JSON, applies relevance / liquidity / fundamentals / valuation
filters, and outputs pass/reject results.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_yuan(amount: float) -> str:
    """Format an amount in yuan to a human-readable string (e.g. '1.2亿', '3200万')."""
    if amount >= 100_000_000:
        return f"{amount / 100_000_000:.1f}亿"
    if amount >= 10_000:
        return f"{amount / 10_000:.0f}万"
    return f"{amount:.0f}"


# ---------------------------------------------------------------------------
# Core filter logic
# ---------------------------------------------------------------------------


def _evaluate_stock(
    stock: dict[str, Any],
    min_liquidity: float,
    pe_percentile_cap: int,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Evaluate a single candidate against the four scorecard dimensions.

    Returns (scorecard_dict, failure_reasons).
    """
    reasons: list[str] = []

    # --- Relevance ---
    revenue_share = stock.get("revenue_share_pct", 0)
    stock_type = stock.get("type", "concept")
    relevance_pass = stock_type == "pure_play" or revenue_share >= 20
    relevance_value = f"{revenue_share}%"
    if not relevance_pass:
        reasons.append(f"相关性不足：收入占比 {revenue_share}%（需 >= 20% 或 pure_play）")

    # --- Liquidity ---
    avg_turnover = stock.get("avg_turnover_20d", 0)
    liquidity_pass = avg_turnover >= min_liquidity
    liquidity_value = _format_yuan(avg_turnover)
    if not liquidity_pass:
        reasons.append(f"流动性不足：日均 {liquidity_value}")

    # --- Fundamentals ---
    is_st = stock.get("is_st", False)
    fundamentals_pass = not is_st
    fundamentals_value = "ST" if is_st else "正常"
    if not fundamentals_pass:
        reasons.append("基本面：ST 股票")

    # --- Valuation ---
    pe_ttm = stock.get("pe_ttm")
    if pe_ttm is None:
        valuation_pass = True
        valuation_value = "PE无数据(跳过)"
    else:
        pe_pct = stock.get("pe_percentile", 0)
        valuation_pass = pe_pct <= pe_percentile_cap
        valuation_value = f"PE {pe_ttm}x (分位 {pe_pct}%)"
        if not valuation_pass:
            reasons.append(f"估值过高：PE {pe_ttm}x (分位 {pe_pct}%，上限 {pe_percentile_cap}%)")

    scorecard = {
        "relevance": {"value": relevance_value, "pass": relevance_pass},
        "liquidity": {"value": liquidity_value, "pass": liquidity_pass},
        "fundamentals": {"value": fundamentals_value, "pass": fundamentals_pass},
        "valuation": {"value": valuation_value, "pass": valuation_pass},
    }

    return scorecard, reasons


def filter_candidates(
    data: dict[str, Any],
    min_liquidity: float = 50_000_000,
    pe_percentile_cap: int = 95,
) -> dict[str, Any]:
    """Apply scorecard filter to all candidates.

    Args:
        data: Parsed JSON with "theme" and "candidates" keys.
        min_liquidity: Minimum 20-day average turnover in yuan (default 50M).
        pe_percentile_cap: Maximum PE percentile rank (default 95).

    Returns:
        Dict with theme, pool_date, passed, and rejected lists.
    """
    theme = data.get("theme", "")
    candidates = data.get("candidates", [])

    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for stock in candidates:
        scorecard, reasons = _evaluate_stock(stock, min_liquidity, pe_percentile_cap)

        if reasons:
            rejected.append(
                {
                    "code": stock["code"],
                    "name": stock["name"],
                    "reason": "；".join(reasons),
                }
            )
        else:
            passed.append(
                {
                    "code": stock["code"],
                    "name": stock["name"],
                    "type": stock["type"],
                    "scorecard": scorecard,
                }
            )

    return {
        "theme": theme,
        "pool_date": date.today().isoformat(),
        "passed": passed,
        "rejected": rejected,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_candidates(path: Path) -> dict[str, Any]:
    """Load candidate JSON from disk."""
    with open(path) as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for scorecard filter."""
    parser = argparse.ArgumentParser(description="Stock-pool scorecard filter")
    parser.add_argument("--input", required=True, type=Path, help="Path to candidate JSON file")
    parser.add_argument("--output", required=True, type=Path, help="Path to write scorecard results")
    parser.add_argument("--min-liquidity", type=float, default=50_000_000, help="Min 20d avg turnover (yuan)")
    parser.add_argument("--pe-percentile-cap", type=int, default=95, help="Max PE percentile rank")
    args = parser.parse_args(argv)

    data = load_candidates(args.input)
    result = filter_candidates(data, min_liquidity=args.min_liquidity, pe_percentile_cap=args.pe_percentile_cap)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
