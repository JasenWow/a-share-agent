#!/usr/bin/env python3
"""Full simulation runner for A-share trading strategies."""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from simulator import TradingSimulator
from market_rules import (
    calculate_total_cost,
    get_price_limit,
    round_to_lot,
    MIN_LOT_SIZE,
)


def next_trading_day(d: date) -> date:
    """Return next trading day (skip weekends)."""
    next_day = d + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day


def run_simulation(
    initial_capital: float,
    start_date: date,
    end_date: date,
    signals: list[dict],
    verbose: bool = True,
) -> dict:
    """Run a backtest simulation with given signals.

    Args:
        initial_capital: starting capital
        start_date: simulation start
        end_date: simulation end
        signals: list of signal dicts with keys: date, code, action (buy/sell), price, shares
        verbose: print progress

    Returns:
        dict with keys: final_capital, total_return, trade_count, trades, portfolio_history
    """
    sim = TradingSimulator(initial_capital=initial_capital)
    portfolio_history = []
    current_date = start_date

    signals_by_date = {}
    for sig in signals:
        sig_date = sig["date"]
        if sig_date not in signals_by_date:
            signals_by_date[sig_date] = []
        signals_by_date[sig_date].append(sig)

    while current_date <= end_date:
        if current_date.weekday() >= 5:
            current_date = next_trading_day(current_date)
            if current_date > end_date:
                break

        if current_date in signals_by_date:
            for sig in signals_by_date[current_date]:
                code = sig["code"]
                action = sig["action"]
                price = sig["price"]
                shares = sig["shares"]
                prev_close = sig.get("prev_close")

                if action.lower() == "buy":
                    result = sim.buy(code, price, shares, current_date, prev_close)
                    if verbose:
                        status = "OK" if result["success"] else f"FAIL({result['reason']})"
                        print(f"  BUY  {code} {shares}@{price} {status}")
                else:
                    result = sim.sell(code, price, shares, current_date, prev_close)
                    if verbose:
                        status = "OK" if result["success"] else f"FAIL({result['reason']})"
                        print(
                            f"  SELL {code} {shares}@{price} {status} "
                            f"pnl={result.get('realized_pnl', 0):.2f}"
                        )

        pv = sim.get_portfolio_value()
        portfolio_history.append({"date": current_date, "value": pv})

        if verbose:
            print(f"[{current_date}] Portfolio: {pv:,.2f} | Cash: {sim.cash:,.2f}")

        current_date = next_trading_day(current_date)

    final_value = sim.get_portfolio_value()
    total_return = (final_value - initial_capital) / initial_capital * 100

    return {
        "final_capital": final_value,
        "total_return_pct": total_return,
        "trade_count": len(sim.trade_history),
        "trades": [
            {
                "action": t.action,
                "code": t.code,
                "price": t.price,
                "shares": t.shares,
                "date": t.trade_date.isoformat(),
                "value": t.trade_value,
                "cost": t.cost,
                "pnl": t.realized_pnl,
            }
            for t in sim.trade_history
        ],
        "portfolio_history": portfolio_history,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A-share trading simulation")
    parser.add_argument("--capital", type=float, default=1_000_000, help="Initial capital")
    parser.add_argument(
        "--start", type=str, required=True, help="Start date YYYYMMDD"
    )
    parser.add_argument("--end", type=str, required=True, help="End date YYYYMMDD")
    parser.add_argument("--config", type=str, help="JSON config file with signals")
    parser.add_argument("--output", type=str, help="Output JSON file for results")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    start_date = date(
        int(args.start[:4]), int(args.start[4:6]), int(args.start[6:8])
    )
    end_date = date(int(args.end[:4]), int(args.end[4:6]), int(args.end[6:8]))

    signals = []
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                signals = data.get("signals", [])

            signals = [
                {
                    **sig,
                    "date": (
                        date(
                            int(sig["date"][:4]),
                            int(sig["date"][4:6]),
                            int(sig["date"][6:8]),
                        )
                        if isinstance(sig["date"], str)
                        else sig["date"]
                    ),
                }
                for sig in signals
            ]

    print("=== A-Share Trading Simulation ===")
    print(f"Capital: {args.capital:,.2f}")
    print(f"Period:  {start_date} → {end_date}")
    print(f"Signals: {len(signals)}")
    print()

    results = run_simulation(
        initial_capital=args.capital,
        start_date=start_date,
        end_date=end_date,
        signals=signals,
        verbose=not args.quiet,
    )

    print()
    print("=== Results ===")
    print(f"Final Capital:   {results['final_capital']:,.2f}")
    print(f"Total Return:   {results['total_return_pct']:.2f}%")
    print(f"Total Trades:   {results['trade_count']}")

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()