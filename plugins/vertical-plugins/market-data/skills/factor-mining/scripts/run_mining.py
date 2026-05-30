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
    test_ratio: float = 0.3,
    top_n: int = 5,
    rebalance_days: int = 5,
    commission: float = 0.003,
) -> dict[str, Any]:
    """Run the full factor mining pipeline on a stock pool.

    Includes train/test split, OOS validation, and backtest.

    Args:
        codes: Stock codes for the pool.
        direction: Preset direction name (key in DIRECTIONS).
        start_date: Historical data start date.
        end_date: Historical data end date. Defaults to today.
        top_k_templates: Number of top template candidates to keep.
        test_ratio: Fraction of data reserved for out-of-sample testing.
        top_n: Number of top-ranked stocks to hold in backtest.
        rebalance_days: Rebalance frequency in trading days.
        commission: Single-side commission rate.

    Returns:
        Dict with pipeline results including factors, validation, and backtest.
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

    # Get close prices
    close_key = "$close" if "$close" in data_arrays else "close"
    if close_key not in data_arrays:
        raise ValueError("Close price data not available")

    # --- Train/Test Split ---
    T_total = len(dates)
    split_idx = int(T_total * (1 - test_ratio))
    print(f"[Pipeline]   Train: {dates[0]} ~ {dates[split_idx-1]} ({split_idx} days)")
    print(f"[Pipeline]   Test:  {dates[split_idx]} ~ {dates[-1]} ({T_total - split_idx} days)")

    # Split data arrays
    train_arrays = {k: v[:split_idx] for k, v in data_arrays.items()}
    test_arrays = {k: v[split_idx:] for k, v in data_arrays.items()}

    # Forward returns for train
    forward_returns = compute_forward_returns(train_arrays[close_key], horizon=forward_horizon)
    print(f"[Pipeline]   Forward returns horizon: {forward_horizon} days")

    # Step 2: Template search (train set only)
    print("[Pipeline] Step 2: Template search (train set)...")
    candidates = enumerate_candidates(
        templates=TEMPLATES,
        fields=fields,
        windows=windows,
        categories=categories,
    )
    print(f"[Pipeline]   Enumerated {len(candidates)} candidates")

    template_results = template_search(
        candidates=candidates,
        data_arrays=train_arrays,
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

    # --- OOS Validation (test set) ---
    print(f"[Pipeline] Step 4: OOS validation ({len(unique_factors)} candidates)...")
    test_fwd = compute_forward_returns(test_arrays[close_key], horizon=forward_horizon)

    validated_factors = []
    for f in unique_factors:
        try:
            from fitness import evaluate_expression
            _, test_metrics = evaluate_expression(
                f["expression"],
                data_arrays=test_arrays,
                forward_returns_2d=test_fwd,
            )
            train_ic = f.get("ic", 0.0)
            test_ic = test_metrics.get("ic", 0.0)
            # Keep if test IC has same sign as train IC
            if train_ic != 0 and np.sign(test_ic) == np.sign(train_ic):
                f["test_ic"] = test_ic
                f["test_icir"] = test_metrics.get("icir", 0.0)
                f["test_t_stat"] = test_metrics.get("t_stat", 0.0)
                f["train_ic"] = train_ic
                f["train_icir"] = f.get("icir", 0.0)
                f["train_t_stat"] = f.get("t_stat", 0.0)
                validated_factors.append(f)
        except Exception:
            continue

    print(f"[Pipeline]   {len(validated_factors)}/{len(unique_factors)} factors survived OOS validation")

    # Sort by fitness
    validated_factors.sort(key=lambda x: x["fitness"], reverse=True)

    # --- Step 5: Backtest ---
    print(f"[Pipeline] Step 5: Backtest (top-{top_n}, rebalance={rebalance_days}d, commission={commission*100:.1f}%)...")
    from backtest import BacktestConfig, run_backtest as run_bt
    bt_config = BacktestConfig(
        top_n=top_n,
        rebalance_days=rebalance_days,
        commission=commission,
    )
    bt_result = run_bt(
        factors=validated_factors[:top_k_templates],
        data_arrays=data_arrays,
        instruments=instruments,
        config=bt_config,
        test_start_idx=split_idx,
    )
    print(f"[Pipeline]   Backtest: ann_return={bt_result.metrics['annualized_return']*100:+.1f}% "
          f"sharpe={bt_result.metrics['sharpe_ratio']:.2f} "
          f"max_dd={bt_result.metrics['max_drawdown']*100:.1f}%")

    print(f"[Pipeline] Done: {len(validated_factors)} validated factors")

    return {
        "direction": direction,
        "direction_description": dir_config["description"],
        "pool_size": len(codes),
        "period": f"{start_date} to {end_date}",
        "n_trading_days": len(dates),
        "train_period": f"{dates[0]} ~ {dates[split_idx-1]}",
        "test_period": f"{dates[split_idx]} ~ {dates[-1]}",
        "split_idx": split_idx,
        "total_factors_mined": len(unique_factors),
        "factors": validated_factors,
        "backtest": {
            "metrics": bt_result.metrics,
            "n_trades": len(bt_result.trades),
            "equity_curve": bt_result.equity_curve,
            "benchmark_curve": bt_result.benchmark_curve,
            "rebalance_dates": bt_result.rebalance_dates,
        },
        "template_results": [
            {k: v for k, v in r.items() if k in ("expression", "ic", "icir", "turnover", "fitness", "category")}
            for r in template_results
        ],
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Factor mining pipeline for industry stock pools")
    
    # Stock pool source: either explicit codes or concept name
    pool_group = parser.add_mutually_exclusive_group(required=True)
    pool_group.add_argument("--codes", nargs="+", help="Explicit stock codes (e.g. 300124 002747)")
    pool_group.add_argument("--concept", help="Concept board name (e.g. 机器人, 人工智能)")
    
    parser.add_argument("--direction", default="综合探索", choices=list(DIRECTIONS.keys()),
                        help="Mining direction preset")
    parser.add_argument("--start-date", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--top-k", type=int, default=10, help="Top K factors to return")
    parser.add_argument("--gp-generations", type=int, default=15, help="GP generations")
    parser.add_argument("--skip-gp", action="store_true", help="Skip GP refinement")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--test-ratio", type=float, default=0.3, help="Test set ratio (default 0.3)")
    parser.add_argument("--top-n", type=int, default=5, help="Backtest top-N holdings")
    parser.add_argument("--rebalance", type=int, default=5, help="Rebalance frequency (days)")
    parser.add_argument("--commission", type=float, default=0.003, help="Commission rate")
    args = parser.parse_args()

    # Resolve stock pool
    codes = args.codes
    if args.concept:
        import sys
        server_dir = Path(__file__).resolve().parents[6] / "mcp-servers" / "akshare-server"
        sys.path.insert(0, str(server_dir))
        from server import stock_board_concept_cons as _concept
        result = _concept(symbol=args.concept)
        codes = [d["代码"] for d in result if "error" not in d]
        if not codes:
            print(f"ERROR: No stocks found for concept '{args.concept}'")
            sys.exit(1)
        print(f"[CLI] Concept '{args.concept}': {len(codes)} stocks")

    result = run_mining_pipeline(
        codes=codes,
        direction=args.direction,
        start_date=args.start_date,
        end_date=args.end_date,
        top_k_templates=args.top_k,
        skip_gp=args.skip_gp,
        seed=args.seed,
        test_ratio=args.test_ratio,
        top_n=args.top_n,
        rebalance_days=args.rebalance,
        commission=args.commission,
    )

    # Print summary
    print(f"\n{'='*60}")
    print(f"Factor Mining Report: {result['direction']}")
    print(f"Pool: {result['pool_size']} stocks | Period: {result['period']}")
    print(f"Train: {result.get('train_period', '?')} | Test: {result.get('test_period', '?')}")
    print(f"{'='*60}")
    for i, f in enumerate(result["factors"][:10]):
        train_ic = f.get('train_ic', f.get('ic', 0))
        test_ic = f.get('test_ic', 0)
        sig = '✅' if f.get('is_significant', False) else '  '
        print(f"  {i+1}. {sig} train_IC={train_ic:.4f} test_IC={test_ic:.4f}  [{f.get('source', '?')}]")
        print(f"     {f['expression']}")

    # Backtest summary
    bt = result.get("backtest", {})
    if bt and bt.get("metrics"):
        m = bt["metrics"]
        print(f"\n{'='*60}")
        print(f"Backtest (top-{args.top_n}, rebalance={args.rebalance}d)")
        print(f"{'='*60}")
        print(f"  Annualized Return: {m['annualized_return']*100:+.1f}%")
        print(f"  Sharpe Ratio:      {m['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:      {m['max_drawdown']*100:.1f}%")
        print(f"  Win Rate:          {m['win_rate']*100:.1f}%")
        print(f"  Excess Return:     {m['excess_return']*100:+.1f}%")
        print(f"  Information Ratio: {m['information_ratio']:.2f}")
        print(f"  Trades:            {bt['n_trades']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fp:
            json.dump(result, fp, ensure_ascii=False, indent=2, default=_json_default)
        print(f"\nResults saved to {args.output}")


def _json_default(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return str(obj)


if __name__ == "__main__":
    main()
