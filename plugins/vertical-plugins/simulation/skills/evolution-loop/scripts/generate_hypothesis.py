"""Hypothesis generation for Meta-Agent strategy exploration."""

import akshare as ak
import random
from typing import Literal

# Factor library (12 factors)
FACTOR_LIBRARY = [
    "momentum_20d", "momentum_60d", "momentum_120d",
    "value_pe", "value_pb", "value_pc",
    "quality_roe", "quality_debt", "quality_growth",
    "low_vol_20d", "low_vol_60d",
    "size_log_mcap",
]

# Strategy parameters
UNIVERSE_CONFIGS = {
    "全A":      {"type": "index", "name": "全A"},
    "沪深300":  {"type": "index", "name": "000300"},
    "中证500":  {"type": "index", "name": "000905"},
    "中证1000": {"type": "index", "name": "000852"},
    "AI-concept": {"type": "concept", "name": "人工智能"},
    "custom":   {"type": "custom", "codes": []},
}

UNIVERSE_OPTIONS = list(UNIVERSE_CONFIGS.keys())

REBALANCE_OPTIONS = ["daily", "weekly", "monthly"]
TOP_K_OPTIONS = [20, 30, 50, 100]
STOP_LOSS_OPTIONS = [0.05, 0.10, 0.15]
MAX_POSITION_OPTIONS = [0.05, 0.10, 0.15]


def resolve_universe(config: dict) -> list[str]:
    """Resolve a universe config to a list of stock codes.

    Args:
        config: Dict with keys "type" and optionally "name" or "codes".

    Returns:
        List of stock code strings.
    """
    universe_type = config.get("type", "index")

    if universe_type == "custom":
        return config.get("codes", [])

    if universe_type == "concept":
        concept_name = config.get("name", "人工智能")
        df = ak.stock_board_concept_cons_em(symbol=concept_name)
        return df["代码"].tolist()

    # index type
    index_name = config.get("name", "000300")
    if index_name == "全A":
        df = ak.stock_zh_a_spot_em()
        return df["代码"].tolist()
    df = ak.index_stock_cons_csindex(symbol=index_name)
    return df["代码"].tolist()


def generate_random_hypothesis(seed=None) -> dict:
    """Generate a random strategy hypothesis."""
    rng = random.Random(seed)

    # Sample 1-4 factors
    n_factors = rng.randint(1, 4)
    factors = rng.sample(FACTOR_LIBRARY, n_factors)

    # Generate random weights summing to 1.0
    raw_weights = [rng.random() for _ in factors]
    total = sum(raw_weights)
    weights = {f: round(w / total, 2) for f, w in zip(factors, raw_weights)}

    return {
        "factors": factors,
        "weights": weights,
        "universe": rng.choice(UNIVERSE_OPTIONS),
        "rebalance": rng.choice(REBALANCE_OPTIONS),
        "top_k": rng.choice(TOP_K_OPTIONS),
        "stop_loss": rng.choice(STOP_LOSS_OPTIONS),
        "max_position": rng.choice(MAX_POSITION_OPTIONS),
    }


def generate_exploitative_hypothesis(best_strategies: list[dict], seed=None) -> dict:
    """Generate hypothesis by perturbing best historical strategy."""
    if not best_strategies:
        return generate_random_hypothesis(seed=seed)

    rng = random.Random(seed)
    best = best_strategies[0]
    strategy = best.get("strategy", {})

    factors = strategy.get("factors", FACTOR_LIBRARY[:1])
    weights = strategy.get("weights", {}).copy()

    # Perturb weights: add ±0.1 noise, clamp to [0.01, 1.0], renormalize
    new_weights = {}
    for f in factors:
        w = weights.get(f, 1.0 / len(factors))
        noise = rng.uniform(-0.1, 0.1)
        w = max(0.01, min(1.0, w + noise))
        new_weights[f] = round(w, 4)

    # Renormalize to sum to 1.0
    total = sum(new_weights.values())
    new_weights = {f: round(w / total, 4) for f, w in new_weights.items()}

    return {
        "factors": factors,
        "weights": new_weights,
        "universe": strategy.get("universe", rng.choice(UNIVERSE_OPTIONS)),
        "rebalance": strategy.get("rebalance", rng.choice(REBALANCE_OPTIONS)),
        "top_k": strategy.get("top_k", rng.choice(TOP_K_OPTIONS)),
        "stop_loss": rng.choice(STOP_LOSS_OPTIONS),
        "max_position": rng.choice(MAX_POSITION_OPTIONS),
    }


import json
from pathlib import Path

def load_all_factors(registry_path: Path | None = None) -> list[str]:
    """Load base factors + any registered custom factors."""
    factors = FACTOR_LIBRARY[:]
    if registry_path and registry_path.exists():
        data = json.loads(registry_path.read_text())
        for entry in data.get("custom_factors", []):
            if entry["name"] not in factors:
                factors.append(entry["name"])
    return factors