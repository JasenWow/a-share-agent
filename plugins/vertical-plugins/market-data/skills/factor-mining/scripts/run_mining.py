"""End-to-end factor mining pipeline for industry-driven stock pools.

Pipeline:
1. Receive stock pool + direction
2. Fetch OHLCV data for the pool
3. Template search (Layer 2) — enumerate and evaluate factor templates
4. GP refinement (Layer 3) — evolve around best templates
5. Register validated factors to factor library
6. Output mining results
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

# Ensure scripts directory is on path
sys.path.insert(0, str(Path(__file__).parent))

from data_fetcher import compute_forward_returns, fetch_pool_data_sync
from factor_library import build_register_params
from gp_engine import run_evolution
from templates import (
    DEFAULT_FIELDS,
    DEFAULT_WINDOWS,
    TEMPLATES,
    enumerate_candidates,
    template_search,
)


# ---------------------------------------------------------------------------
# Preset directions
# ---------------------------------------------------------------------------

DIRECTIONS: dict[str, dict[str, Any]] = {
    "低波动": {
        "categories": ["volatility", "mean_reversion"],
        "fields": ["$close", "$volume"],
        "windows": [5, 10, 20, 60],
        "description": "低波动率股票的超额收益",
    },
    "动量趋势": {
        "categories": ["trend", "momentum"],
        "fields": ["$close", "$volume"],
        "windows": [5, 10, 20, 60],
        "description": "价格动量和趋势延续",
    },
    "量价关系": {
        "categories": ["volume_price", "strength"],
        "fields": ["$close", "$volume", "$open"],
        "windows": [5, 10, 20, 60],
        "description": "成交量与价格的协同关系",
    },
    "均值回归": {
        "categories": ["mean_reversion", "volatility"],
        "fields": ["$close", "$volume"],
        "windows": [5, 10, 20, 60],
        "description": "价格偏离后的回归",
    },
    "综合探索": {
        "categories": None,  # all categories
        "fields": DEFAULT_FIELDS,
        "windows": DEFAULT_WINDOWS,
        "description": "全方向搜索（较慢）",
    },
}


def run_mining_pipeline(
    codes: list[str],
    direction: str = "综合探索",
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    top_k_templates: int = 20,
    top_k_gp: int = 10,
    gp_generations: int = 15,
    gp_population: int = 100,
    gp_max_depth: int = 4,
    forward_horizon: int = 5,
    min_ic: float = 0.02,
    seed: int | None = None,
    skip_gp: bool = False,
) -> dict[str, Any]:
    """Run the full factor mining pipeline on a stock pool.

    Args:
        codes: Stock codes for the pool (e.g., ["300124.SZ", "002472.SZ"]).
        direction: Preset direction name (key in DIRECTIONS).
        start_date: Historical data start date.
        end_date: Historical data end date. Defaults to today.
        top_k_templates: Number of top template candidates to keep.
        top_k_gp: Number of top GP candidates to return.
        gp_generations: Number of GP evolution generations.
        gp_population: GP population size.
        gp_max_depth: Max GP expression tree depth.
        forward_horizon: Forward return horizon in days.
        min_ic: Minimum absolute IC to consider valid.
        seed: Random seed for reproducibility.
        skip_gp: If True, skip Layer 3 GP refinement.

    Returns:
        Dict with pipeline results including factors and metadata.
    """
    if end_date is None:
        end_date = date.today().isoformat()

    # Resolve direction
    dir_config = DIRECTIONS.get(direction, DIRECTIONS["综合探索"])
    categories = dir_config["categories"]
    fields = dir_config["fields"]
    windows = dir_config["windows"]

    print(f"[Pipeline] Direction: {direction} ({dir_config['description']})")
    print(f"[Pipeline] Pool: {len(codes)} stocks")
    print(f"[Pipeline] Period: {start_date} to {end_date}")

    # Step 1: Fetch data
    print("[Pipeline] Step 1: Fetching OHLCV data...")
    data_arrays, dates, instruments = fetch_pool_data_sync(
        codes=codes,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
    )
    print(f"[Pipeline]   Got {len(dates)} trading days, {len(instruments)} instruments")

    # Get close prices for forward returns
    close_key = "$close"
    if close_key not in data_arrays:
        # Try without $ prefix
        close_key = "close"
    if close_key not in data_arrays:
        raise ValueError("Close price data not available in fetched data")

    forward_returns = compute_forward_returns(data_arrays[close_key], horizon=forward_horizon)
    print(f"[Pipeline]   Forward returns horizon: {forward_horizon} days")

    # Step 2: Template search (Layer 2)
    print("[Pipeline] Step 2: Template search...")
    candidates = enumerate_candidates(
        templates=TEMPLATES,
        fields=fields,
        windows=windows,
        categories=categories,
    )
    print(f"[Pipeline]   Enumerated {len(candidates)} candidates")

    template_results = template_search(
        candidates=candidates,
        data_arrays=data_arrays,
        forward_returns=forward_returns,
        top_k=top_k_templates,
        min_ic=min_ic,
    )
    print(f"[Pipeline]   {len(template_results)} candidates passed IC filter")

    if not template_results:
        print("[Pipeline] WARNING: No factors passed the template search filter.")
        return {
            "direction": direction,
            "pool_size": len(codes),
            "template_results": [],
            "gp_results": [],
            "total_factors": 0,
        }

    # Print top 5
    for i, r in enumerate(template_results[:5]):
        print(f"[Pipeline]   Top {i+1}: IC={r['ic']:.4f} ICIR={r['icir']:.4f} fitness={r['fitness']:.4f}")
        print(f"[Pipeline]           {r['expression']}")

    # Step 3: GP refinement (Layer 3)
    gp_results = []
    if not skip_gp:
        print("[Pipeline] Step 3: GP refinement...")
        seed_expressions = [r["expression"] for r in template_results[:10]]

        # Collect operator names from template results
        all_operator_names = [
            "Rank", "ZScore", "Sign", "Abs",
            "Ts_Mean", "Ts_Std", "Ts_Max", "Ts_Min", "Ts_Sum",
            "Delta", "Pct_Change",
            "Add", "Sub", "Mul", "Div",
        ]

        try:
            gp_candidates = run_evolution(
                operator_names=all_operator_names,
                data_fields=fields,
                generations=gp_generations,
                population_size=gp_population,
                max_depth=gp_max_depth,
                top_k=top_k_gp,
                mock_mode=False,
                seed=seed,
                data_arrays=data_arrays,
                forward_returns_2d=forward_returns,
                seed_individuals=seed_expressions,
            )

            for c in gp_candidates:
                # Re-evaluate for detailed metrics
                from fitness import evaluate_expression
                _, detail = evaluate_expression(
                    c["expression"],
                    data_arrays=data_arrays,
                    forward_returns_2d=forward_returns,
                )
                gp_results.append({
                    "expression": c["expression"],
                    "fitness": c["fitness"],
                    "ic": detail.get("ic", 0.0),
                    "icir": detail.get("icir", 0.0),
                    "turnover": detail.get("turnover", 0.0),
                    "source": "gp_refinement",
                })

            print(f"[Pipeline]   GP produced {len(gp_results)} refined factors")
            for i, r in enumerate(gp_results[:3]):
                print(f"[Pipeline]   GP Top {i+1}: IC={r['ic']:.4f} ICIR={r['icir']:.4f}")
                print(f"[Pipeline]           {r['expression']}")
        except Exception as e:
            print(f"[Pipeline]   GP refinement failed: {e}")
            print("[Pipeline]   Falling back to template-only results")
            gp_results = []

    # Combine results
    all_factors = []
    for r in template_results:
        all_factors.append({**r, "source": "template_search"})
    all_factors.extend(gp_results)

    # Deduplicate by expression
    seen = set()
    unique_factors = []
    for f in all_factors:
        if f["expression"] not in seen:
            seen.add(f["expression"])
            unique_factors.append(f)

    # Sort by fitness
    unique_factors.sort(key=lambda x: x["fitness"], reverse=True)

    print(f"[Pipeline] Done: {len(unique_factors)} unique factors discovered")

    return {
        "direction": direction,
        "direction_description": dir_config["description"],
        "pool_size": len(codes),
        "period": f"{start_date} to {end_date}",
        "n_trading_days": len(dates),
        "template_results": [
            {k: v for k, v in r.items() if k in ("expression", "ic", "icir", "turnover", "fitness", "category")}
            for r in template_results
        ],
        "gp_results": [
            {k: v for k, v in r.items() if k in ("expression", "ic", "icir", "turnover", "fitness")}
            for r in gp_results
        ],
        "total_factors": len(unique_factors),
        "factors": unique_factors,
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Factor mining pipeline for industry stock pools")
    parser.add_argument("--codes", required=True, nargs="+", help="Stock codes")
    parser.add_argument("--direction", default="综合探索", choices=list(DIRECTIONS.keys()),
                        help="Mining direction preset")
    parser.add_argument("--start-date", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--top-k", type=int, default=10, help="Top K factors to return")
    parser.add_argument("--gp-generations", type=int, default=15, help="GP generations")
    parser.add_argument("--skip-gp", action="store_true", help="Skip GP refinement")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    result = run_mining_pipeline(
        codes=args.codes,
        direction=args.direction,
        start_date=args.start_date,
        end_date=args.end_date,
        top_k_gp=args.top_k,
        gp_generations=args.gp_generations,
        seed=args.seed,
        skip_gp=args.skip_gp,
    )

    # Print summary
    print(f"\n{'='*60}")
    print(f"Factor Mining Report: {result['direction']}")
    print(f"Pool: {result['pool_size']} stocks | Period: {result['period']}")
    print(f"{'='*60}")
    for i, f in enumerate(result["factors"][:10]):
        print(f"  {i+1}. IC={f['ic']:.4f} ICIR={f['icir']:.4f} TO={f['turnover']:.2f}  [{f.get('source', '?')}]")
        print(f"     {f['expression']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fp:
            json.dump(result, fp, ensure_ascii=False, indent=2, default=str)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
