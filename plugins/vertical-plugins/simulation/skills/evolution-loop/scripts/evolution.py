"""
Evolution loop control for strategy optimization.

Provides state management, doom loop detection, and corrective action generation.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvolutionState:
    """Tracks the current state of the evolution loop."""

    iteration: int
    best_return: float
    recent_failures: list[str] = field(default_factory=list)
    failure_signatures: dict[str, int] = field(default_factory=dict)
    market_regime: Optional[str] = None
    market_breadth: Optional[float] = None
    volatility_index: Optional[float] = None
    cash_ratio: Optional[float] = None
    position_count: Optional[int] = None
    sector_concentration: Optional[float] = None
    unrealized_pnl: Optional[float] = None


# Constants
MAX_ITERATIONS = 50
DOOM_THRESHOLD = 3
CORRECTION_COUNT_LIMIT = 5


# Correction mappings
CORRECTIONS: dict[str, str] = {
    "momentum_concentration": "reduce momentum weight, diversify factors",
    "value_overfit": "increase lookback period, reduce rebalancing frequency",
    "low_sharpe": "add defensive factors (low_vol, quality), reduce position count",
    "high_turnover": "extend holding period, use score threshold for rebalancing",
}


def should_continue(state: EvolutionState, target_return: float) -> tuple[bool, str | None]:
    """
    Determine whether evolution should continue.

    Returns:
        tuple[bool, str|None]: (should_continue, reason)
            - (False, "target_reached") if best_return >= target_return
            - (False, "max_iterations") if iteration >= MAX_ITERATIONS
            - (False, "doom_loop") if any signature >= DOOM_THRESHOLD
            - (False, "correction_limit") if total corrections >= CORRECTION_COUNT_LIMIT
            - (True, None) to continue
    """
    # Check if target has been reached
    if state.best_return >= target_return:
        return (False, "target_reached")

    # Check if max iterations reached
    if state.iteration >= MAX_ITERATIONS:
        return (False, "max_iterations")

    # Check for doom loop (repeated failures)
    for signature, count in state.failure_signatures.items():
        if count >= DOOM_THRESHOLD:
            return (False, "doom_loop")

    # Check correction count limit
    total_corrections = sum(state.failure_signatures.values())
    if total_corrections >= CORRECTION_COUNT_LIMIT:
        return (False, "correction_limit")

    return (True, None)


def generate_correction(failure_signature: str) -> str:
    """
    Generate a corrective action based on failure pattern.

    Args:
        failure_signature: The type of failure detected.

    Returns:
        str: Corrective action to take.
    """
    return CORRECTIONS.get(
        failure_signature,
        "review strategy parameters, consider regime change",
    )