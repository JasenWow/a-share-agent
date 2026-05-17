"""DEAP Genetic Programming engine for factor expression evolution.

Builds a typed primitive set from selected operators, evolves expression trees,
and returns candidate factor expressions ranked by fitness.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
from deap import algorithms, base, creator, gp, tools

from fitness import evaluate_expression
from operators import get_operator


# ---------------------------------------------------------------------------
# Ensure DEAP creator classes are created only once
# ---------------------------------------------------------------------------

_creator_initialized = False


def _ensure_creator():
    """Idempotently register DEAP creator classes."""
    global _creator_initialized
    if _creator_initialized:
        return

    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)
    _creator_initialized = True


# ---------------------------------------------------------------------------
# Primitive set construction
# ---------------------------------------------------------------------------

def create_pset(
    operator_names: list[str],
    data_fields: list[str],
) -> gp.PrimitiveSet:
    """Build a DEAP PrimitiveSet from named operators and data fields.

    Args:
        operator_names: List of operator names to include (must exist in registry).
        data_fields: List of data field names like "$close", "$volume".

    Returns:
        Configured PrimitiveSet with primitives and terminals.
    """
    pset = gp.PrimitiveSet("MAIN", arity=0)

    for name in operator_names:
        op = get_operator(name)
        if op is None:
            raise ValueError(f"Unknown operator: {name}")
        pset.addPrimitive(op["deap_func"], arity=op["arity"], name=name)

    # Add ephemeral constants (random floats)
    pset.addEphemeralConstant("rand_const", lambda: round(random.uniform(1, 60), 1))

    # Add data field terminals (keep original name for mapping lookup)
    for field in data_fields:
        pset.addTerminal(field, name=field)

    return pset


# ---------------------------------------------------------------------------
# Expression conversion
# ---------------------------------------------------------------------------

def individual_to_expression(individual: gp.PrimitiveTree) -> str:
    """Convert a DEAP individual tree to a Qlib expression string.

    Args:
        individual: DEAP PrimitiveTree individual.

    Returns:
        Qlib-style expression string.
    """
    # Use DEAP's string representation and clean it up
    expr_str = str(individual)
    # DEAP renders calls like "Rank($close)" directly
    return expr_str


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------

def _mock_evaluate(individual, pset):
    """Mock evaluation for testing: returns a random fitness."""
    return (random.uniform(-1.0, 1.0),)


def run_evolution(
    operator_names: list[str],
    data_fields: list[str],
    generations: int = 10,
    population_size: int = 100,
    max_depth: int = 4,
    top_k: int = 10,
    mock_mode: bool = False,
    seed: int | None = None,
    **kwargs: Any,
) -> list[dict]:
    """Run a full GP evolution loop and return top-k candidates.

    Args:
        operator_names: Operators to include in the primitive set.
        data_fields: Data field terminals.
        generations: Number of generations to evolve.
        population_size: Number of individuals per generation.
        max_depth: Maximum tree depth (bloat control).
        top_k: Number of top candidates to return.
        mock_mode: If True, use random fitness for testing.
        seed: Random seed for reproducibility.
        **kwargs: Additional arguments passed to fitness evaluation.

    Returns:
        List of dicts with keys "expression" and "fitness", sorted by fitness desc.
    """
    _ensure_creator()

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    pset = create_pset(operator_names, data_fields)

    toolbox = base.Toolbox()
    toolbox.register("expr", gp.genHalfAndHalf, pset=pset, min_=1, max_=max_depth)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.expr)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # Evaluation function
    if mock_mode:
        toolbox.register("evaluate", _mock_evaluate, pset=pset)
    else:
        def _evaluate(ind):
            expr_str = individual_to_expression(ind)
            try:
                fitness, _ = evaluate_expression(expr_str, **kwargs)
            except Exception:
                fitness = -999.0
            return (fitness,)

        toolbox.register("evaluate", _evaluate)

    # Selection, crossover, mutation with bloat control
    toolbox.register("select", tools.selDoubleTournament, fitness_size=3, parsimony_size=1.4, fitness_first=True)
    toolbox.register("mate", gp.cxOnePoint)
    toolbox.register("expr_mut", gp.genFull, min_=0, max_=max_depth)
    toolbox.register("mutate", gp.mutUniform, expr=toolbox.expr_mut, pset=pset)

    # Bloat control via static limit
    max_tree_len = 2 ** (max_depth + 1)
    toolbox.decorate("mate", gp.staticLimit(key=len, max_value=max_tree_len))
    toolbox.decorate("mutate", gp.staticLimit(key=len, max_value=max_tree_len))

    # Run evolution
    pop = toolbox.population(n=population_size)
    algorithms.eaSimple(
        pop,
        toolbox,
        cxpb=0.5,
        mutpb=0.2,
        ngen=generations,
        verbose=False,
    )

    # Extract top-k
    top = tools.selBest(pop, k=min(top_k, len(pop)))
    candidates = []
    for ind in top:
        candidates.append({
            "expression": individual_to_expression(ind),
            "fitness": float(ind.fitness.values[0]),
        })

    return candidates
