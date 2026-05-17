"""Tests for factor fitness function."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import numpy as np


class TestFitness:
    def test_compute_ic_perfect_predictor(self):
        from fitness import compute_rank_ic

        factor = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        assert compute_rank_ic(factor, returns) > 0.9

    def test_compute_ic_random(self):
        from fitness import compute_rank_ic

        np.random.seed(42)
        factor = np.random.randn(100)
        returns = np.random.randn(100)
        assert abs(compute_rank_ic(factor, returns)) < 0.3

    def test_compute_ic_series(self):
        from fitness import compute_ic_series

        factor_values = np.array(
            [[1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 3.0, 2.0, 1.0], [1.0, 3.0, 2.0, 5.0, 4.0]]
        )
        forward_returns = np.array(
            [[0.01, 0.02, 0.03, 0.04, 0.05], [0.05, 0.04, 0.03, 0.02, 0.01], [0.01, 0.03, 0.02, 0.05, 0.04]]
        )
        ic_series = compute_ic_series(factor_values, forward_returns)
        assert len(ic_series) == 3
        assert all(-1 <= ic <= 1 for ic in ic_series)

    def test_fitness_score(self):
        from fitness import compute_fitness

        score = compute_fitness(ic_series=np.array([0.05, 0.04, 0.06, 0.03, 0.05]), turnover=0.3)
        expected_icir = np.mean([0.05, 0.04, 0.06, 0.03, 0.05]) / np.std([0.05, 0.04, 0.06, 0.03, 0.05])
        expected_ic = np.mean([0.05, 0.04, 0.06, 0.03, 0.05])
        expected = 0.6 * expected_icir + 0.2 * expected_ic - 0.2 * 0.3
        assert abs(score - expected) < 1e-6

    def test_fitness_handles_nan(self):
        from fitness import compute_fitness

        result = compute_fitness(ic_series=np.array([0.05, float("nan"), 0.04]), turnover=0.3)
        assert not np.isnan(result)

    def test_evaluate_expression_mock(self):
        from fitness import evaluate_expression

        np.random.seed(42)
        score, metrics = evaluate_expression(
            expression="Rank($close / $open)",
            instruments="csi300",
            start_date="2024-01-01",
            end_date="2024-12-31",
            _mock_factor_values=np.random.randn(100),
            _mock_forward_returns=np.random.randn(100),
        )
        assert "ic" in metrics
        assert "icir" in metrics
