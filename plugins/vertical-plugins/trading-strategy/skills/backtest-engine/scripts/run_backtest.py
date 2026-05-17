"""CLI entry point for running backtests standalone.

Usage:
    uv run python plugins/vertical-plugins/trading-strategy/skills/backtest-engine/scripts/run_backtest.py \
        --config config.json \
        --output results.json

Input JSON (config.json):
    {
      "session_id": "test",
      "initial_capital": 1000000,
      "start_date": "20240101",
      "end_date": "20241231",
      "universe": ["000001", "600036"],
      "benchmark": "sh000300",
      "commission_rate": 0.00025,
      "stamp_duty_rate": 0.0005,
      "slippage_rate": 0.0005,
      "exclude_st": true,
      "bar_data": {"000001": [{...}], "600036": [{...}]},
      "benchmark_data": [{...}],
      "signals": [{"signal_date": "20240102", "stock_code": "000001", "direction": "buy", "target_weight": 0.5}],
      "trading_days": ["20240102", "20240103", ...]
    }

Output JSON (results.json):
    {
      "status": "completed",
      "final_nav": ...,
      "total_return": ...,
      "performance": {...},
      "daily_nav": [...],
      "trades": [...],
      "positions": [...]
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow imports from this directory
sys.path.insert(0, str(Path(__file__).parent))

from engine import BacktestSimulator
from models import SessionConfig
from performance import compute_performance


def run(config: dict) -> dict:
    """Run backtest from config dict, return results dict."""
    session_config = SessionConfig(
        session_id=config.get("session_id", "cli"),
        initial_capital=config.get("initial_capital", 1000000.0),
        start_date=config.get("start_date", ""),
        end_date=config.get("end_date", ""),
        universe=config.get("universe", []),
        benchmark=config.get("benchmark", "sh000300"),
        commission_rate=config.get("commission_rate", 0.00025),
        stamp_duty_rate=config.get("stamp_duty_rate", 0.0005),
        slippage_rate=config.get("slippage_rate", 0.0005),
        exclude_st=config.get("exclude_st", True),
    )

    sim = BacktestSimulator(session_config)

    # Load bar data
    bar_data = config.get("bar_data", {})
    if bar_data:
        load_result = sim.load_bar_data(bar_data)
        print(f"Loaded {load_result['loaded']} stocks, {load_result['failed']} failed", file=sys.stderr)

    # Load benchmark
    benchmark_data = config.get("benchmark_data", [])
    if benchmark_data:
        sim.load_benchmark(benchmark_data)

    # Add signals
    signals = config.get("signals", [])
    if signals:
        sim.add_signals(signals)
        print(f"Added {len(signals)} signals", file=sys.stderr)

    # Get trading days
    trading_days = config.get("trading_days", [])
    if not trading_days:
        # Derive from bar data dates
        all_dates: set[str] = set()
        for code_data in sim.bar_data.values():
            all_dates.update(code_data.keys())
        trading_days = sorted(all_dates)
        # Filter to date range
        if session_config.start_date:
            trading_days = [d for d in trading_days if d >= session_config.start_date]
        if session_config.end_date:
            trading_days = [d for d in trading_days if d <= session_config.end_date]

    print(f"Running backtest over {len(trading_days)} trading days...", file=sys.stderr)

    # Run simulation
    result = sim.run(trading_days)

    if "error" in result:
        return result

    # Compute performance metrics
    perf = compute_performance(
        nav_rows=result["daily_nav"],
        trade_rows=result["trades"],
        initial_capital=session_config.initial_capital,
    )
    result["performance"] = perf

    print(
        f"Done. NAV={result['final_nav']:.2f}, Return={result['total_return']:.4%}, "
        f"Trades={result['total_trades']}, Sharpe={perf.get('sharpe_ratio', 'N/A')}",
        file=sys.stderr,
    )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A-share backtest simulation")
    parser.add_argument("--config", required=True, help="Path to input config JSON")
    parser.add_argument("--output", default="", help="Path to output results JSON (default: stdout)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    result = run(config)

    output_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
