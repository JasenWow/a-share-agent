"""Factor library client: hashing, naming, and registration helpers.

Provides utilities for managing discovered factor expressions:
- Deterministic hashing for deduplication
- Human-readable name generation
- Registration parameter construction (for MCP calls)
"""

from __future__ import annotations

import hashlib
import re


def expression_hash(expression: str) -> str:
    """Compute a deterministic SHA-256 based hash for a factor expression.

    Args:
        expression: Qlib-style factor expression string.

    Returns:
        First 16 hex characters of the SHA-256 digest.
    """
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()[:16]


def name_from_expression(expression: str) -> str:
    """Generate a human-readable name from an expression.

    Extracts the first 3 operator names found in the expression and
    joins them with underscores, lowercased.

    Args:
        expression: Qlib-style factor expression string.

    Returns:
        Lowercase name like "rank_ts_mean_ts_std".
    """
    # Match operator names: word chars before '('
    operators = re.findall(r"([A-Za-z_]\w*)\s*\(", expression)
    # Filter out data fields (starting with $) and common non-operators
    operators = [op for op in operators if not op.startswith("$")]
    # Take first 3 and join
    parts = operators[:3] if operators else ["unknown"]
    return "_".join(p.lower() for p in parts)


def build_register_params(
    expression: str,
    fitness: float,
    metrics: dict,
    mining_direction: dict | None = None,
) -> dict:
    """Build parameter dict for MCP register_factor call.

    Args:
        expression: Factor expression string.
        fitness: Composite fitness score.
        metrics: Detailed metrics from fitness evaluation.
        mining_direction: Original mining direction for traceability.

    Returns:
        Dict suitable for passing to register_factor MCP tool.
    """
    return {
        "expression": expression,
        "name": name_from_expression(expression),
        "hash": expression_hash(expression),
        "fitness": fitness,
        "ic": metrics.get("ic", 0.0),
        "icir": metrics.get("icir", 0.0),
        "turnover": metrics.get("turnover", 0.0),
        "universe": mining_direction.get("universe", "") if mining_direction else "",
        "period": mining_direction.get("period", "") if mining_direction else "",
        "hypothesis": mining_direction.get("hypothesis", "") if mining_direction else "",
    }
