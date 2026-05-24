"""End-to-end validation: GP factor mining with real data via MCP.

Three-phase pipeline:
  Phase 1: Fetch OHLCV via MCP (qlib-server) → compute forward returns
  Phase 2: GP evolution with vectorized numpy evaluation (no MCP)
  Phase 3: Register top factors via MCP (internal-store)

Usage:
    # Prerequisites: qlib-server on :8003, internal-store on :8002
    # First time: set --init-data to download qlib CN data
    uv run python scripts/validate_factor_mining.py --init-data
    uv run python scripts/validate_factor_mining.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Add factor-mining scripts to path
_SCRIPT_DIR = Path(__file__).resolve().parent.parent / (
    "plugins/vertical-plugins/market-data/skills/factor-mining/scripts"
)
sys.path.insert(0, str(_SCRIPT_DIR))

from data_fetcher import compute_forward_returns, fetch_ohlcv, init_qlib_data, register_factor_via_mcp
from fitness import evaluate_expression
from gp_engine import run_evolution
from mine_factors import mine_factors


# Default config for minimal verification
DEFAULT_UNIVERSE = "csi300"
DEFAULT_START = "2018-01-01"
DEFAULT_END = "2021-06-01"
DEFAULT_OPS = ["Ts_Mean", "Delta", "Rank", "Add", "Sub", "Mul", "Div"]
DEFAULT_FIELDS = ["$close", "$volume"]
FWD_HORIZON = 5
ICIR_THRESHOLD = 0.05


async def run(init_data: bool = False):
    print("=" * 60)
    print("Factor Mining End-to-End Validation")
    print("=" * 60)

    # --- Phase 0: Initialize qlib data if needed ---
    if init_data:
        print("\n[Phase 0] Downloading qlib CN data via MCP...")
        t0 = time.time()
        result = await init_qlib_data()
        elapsed = time.time() - t0
        if isinstance(result, dict) and result.get("status") == "error":
            print(f"  ERROR: {result.get('message')}")
            return
        print(f"  Done in {elapsed:.1f}s — {result}")

    # --- Phase 1: Fetch data via MCP ---
    print(f"\n[Phase 1] Fetching {DEFAULT_UNIVERSE} {DEFAULT_START}~{DEFAULT_END} via MCP...")
    t0 = time.time()
    data_arrays, dates, instruments = await fetch_ohlcv(
        universe=DEFAULT_UNIVERSE,
        start_date=DEFAULT_START,
        end_date=DEFAULT_END,
        fields=DEFAULT_FIELDS,
    )
    elapsed = time.time() - t0

    T = len(dates)
    N = len(instruments)
    for field, arr in data_arrays.items():
        valid_pct = 100.0 * (~np.isnan(arr)).sum() / arr.size
        print(f"  {field}: shape={arr.shape}, valid={valid_pct:.1f}%")
    print(f"  Dates: {T}, Instruments: {N}, Fetched in {elapsed:.1f}s")

    # Compute forward returns
    close_arr = data_arrays.get("$close")
    if close_arr is None:
        print("  ERROR: $close not in fetched data")
        return
    forward_returns = compute_forward_returns(close_arr, horizon=FWD_HORIZON)
    fwd_valid = 100.0 * (~np.isnan(forward_returns)).sum() / forward_returns.size
    print(f"  Forward returns ({FWD_HORIZON}d): valid={fwd_valid:.1f}%")

    # --- Phase 2: GP Evolution ---
    print("\n[Phase 2] Running GP evolution...")
    mining_direction = {
        "hypothesis": "momentum and mean-reversion in CSI300",
        "operators": DEFAULT_OPS,
        "data_fields": DEFAULT_FIELDS,
        "universe": DEFAULT_UNIVERSE,
        "period": f"{DEFAULT_START}~{DEFAULT_END}",
    }

    t0 = time.time()
    candidates = mine_factors(
        mining_direction=mining_direction,
        mock_mode=False,
        generations=8,
        population_size=30,
        max_depth=3,
        top_k=5,
        seed=42,
        data_arrays=data_arrays,
        forward_returns_2d=forward_returns,
    )
    elapsed = time.time() - t0
    print(f"  Evolution completed in {elapsed:.1f}s")
    print(f"  Top {len(candidates)} candidates:")

    # Evaluate each candidate with full metrics
    for i, c in enumerate(candidates):
        expr = c["expression"]
        try:
            fitness, metrics = evaluate_expression(
                expr,
                data_arrays=data_arrays,
                forward_returns_2d=forward_returns,
            )
        except Exception:
            metrics = {"ic": 0, "icir": 0, "turnover": 0}
        print(f"  #{i+1}  {expr}")
        print(f"       fitness={c['fitness']:.4f}  IC={metrics.get('ic', 0):.4f}  "
              f"ICIR={metrics.get('icir', 0):.2f}  turnover={metrics.get('turnover', 0):.4f}")

    # --- Phase 3: Register top factors via MCP ---
    print("\n[Phase 3] Registering factors via MCP...")
    registered = 0
    for c in candidates:
        try:
            _, metrics = evaluate_expression(
                c["expression"],
                data_arrays=data_arrays,
                forward_returns_2d=forward_returns,
            )
        except Exception:
            continue

        icir = metrics.get("icir", 0)
        if abs(icir) < ICIR_THRESHOLD:
            continue

        params = c["register_params"]
        params["ic"] = metrics.get("ic", 0)
        params["icir"] = icir
        params["turnover"] = metrics.get("turnover", 0)
        params["operators"] = DEFAULT_OPS
        params["data_fields"] = DEFAULT_FIELDS

        try:
            result = await register_factor_via_mcp(params)
            registered += 1
            print(f"  Registered: {c['name']} (ICIR={icir:.2f})")
        except Exception as e:
            print(f"  Failed to register {c['name']}: {e}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"DONE: {len(candidates)} candidates evaluated, {registered} factors registered")
    print("=" * 60)


import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Factor mining end-to-end validation")
    parser.add_argument("--init-data", action="store_true", help="Download qlib CN data first")
    args = parser.parse_args()
    asyncio.run(run(init_data=args.init_data))


if __name__ == "__main__":
    main()
