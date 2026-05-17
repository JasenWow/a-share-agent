"""Factor mining loop orchestrator.

Validates mining directions and orchestrates GP evolution to discover
candidate factor expressions.
"""

from __future__ import annotations

from typing import Any

from factor_library import build_register_params
from gp_engine import run_evolution


# Required fields in a mining direction dict
_REQUIRED_FIELDS = {"hypothesis", "operators", "data_fields", "universe", "period"}


def validate_mining_direction(direction: dict[str, Any]) -> tuple[bool, str]:
    """Validate that a mining direction dict has all required fields.

    Args:
        direction: Mining direction configuration dict.

    Returns:
        Tuple of (is_valid, message).
    """
    missing = _REQUIRED_FIELDS - set(direction.keys())
    if missing:
        return False, f"Missing required fields: {', '.join(sorted(missing))}"

    if not direction["operators"]:
        return False, "operators list must not be empty"

    if not direction["data_fields"]:
        return False, "data_fields list must not be empty"

    return True, "OK"


def mine_factors(
    mining_direction: dict[str, Any],
    mock_mode: bool = False,
    generations: int = 10,
    population_size: int = 100,
    max_depth: int = 4,
    top_k: int = 10,
    seed: int | None = None,
) -> list[dict]:
    """Run the factor mining loop.

    Validates the mining direction, runs GP evolution, and enriches
    candidates with metadata for registration.

    Args:
        mining_direction: Dict with keys: hypothesis, operators, data_fields,
                          universe, period.
        mock_mode: If True, use random fitness for testing.
        generations: Number of GP generations.
        population_size: Population size for GP.
        max_depth: Maximum expression tree depth.
        top_k: Number of top candidates to return.
        seed: Random seed for reproducibility.

    Returns:
        List of candidate dicts with expression, fitness, name, hash, and
        registration parameters.
    """
    is_valid, msg = validate_mining_direction(mining_direction)
    if not is_valid:
        raise ValueError(f"Invalid mining direction: {msg}")

    candidates = run_evolution(
        operator_names=mining_direction["operators"],
        data_fields=mining_direction["data_fields"],
        generations=generations,
        population_size=population_size,
        max_depth=max_depth,
        top_k=top_k,
        mock_mode=mock_mode,
        seed=seed,
    )

    # Enrich with metadata
    enriched = []
    for candidate in candidates:
        expr = candidate["expression"]
        fitness = candidate["fitness"]

        params = build_register_params(
            expression=expr,
            fitness=fitness,
            metrics={"ic": 0.0, "icir": 0.0, "turnover": 0.0},
            mining_direction=mining_direction,
        )

        enriched.append({
            "expression": expr,
            "fitness": fitness,
            "name": params["name"],
            "hash": params["hash"],
            "register_params": params,
        })

    return enriched
