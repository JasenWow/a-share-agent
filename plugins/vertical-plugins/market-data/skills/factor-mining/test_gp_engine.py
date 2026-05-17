"""Tests for DEAP GP engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))


class TestGPEngine:
    def test_create_pset(self):
        from gp_engine import create_pset

        pset = create_pset(operator_names=["Ts_Mean", "Rank", "Add"], data_fields=["$close", "$volume"])
        assert "Ts_Mean" in pset.mapping
        assert "Rank" in pset.mapping

    def test_individual_to_expression(self):
        from gp_engine import create_pset, individual_to_expression
        from deap import gp

        pset = create_pset(operator_names=["Rank"], data_fields=["$close"])
        expr = [pset.mapping["Rank"], pset.mapping["$close"]]
        individual = gp.PrimitiveTree(expr)
        assert individual_to_expression(individual) == "Rank($close)"

    def test_run_evolution_returns_candidates(self):
        from gp_engine import run_evolution

        result = run_evolution(
            operator_names=["Rank", "Add"],
            data_fields=["$close", "$open"],
            generations=3,
            population_size=10,
            max_depth=3,
            mock_mode=True,
        )
        assert len(result) > 0
        assert "expression" in result[0]
        assert "fitness" in result[0]
