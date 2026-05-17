import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from generate_hypothesis import (
    FACTOR_LIBRARY,
    UNIVERSE_OPTIONS,
    REBALANCE_OPTIONS,
    TOP_K_OPTIONS,
    STOP_LOSS_OPTIONS,
    MAX_POSITION_OPTIONS,
    generate_random_hypothesis,
    generate_exploitative_hypothesis,
)


class TestFactorLibrary:
    def test_factor_library_has_12_factors(self):
        assert len(FACTOR_LIBRARY) == 12

    def test_factor_names_are_valid(self):
        for f in FACTOR_LIBRARY:
            assert isinstance(f, str)
            assert len(f) > 0


class TestRandomHypothesis:
    def test_has_required_fields(self):
        h = generate_random_hypothesis(seed=42)
        for field in ["factors", "weights", "universe", "rebalance", "top_k", "stop_loss", "max_position"]:
            assert field in h, f"missing {field}"

    def test_weights_sum_to_one(self):
        h = generate_random_hypothesis(seed=42)
        total = sum(h["weights"].values())
        assert abs(total - 1.0) < 0.01, f"weights sum to {total}, not 1.0"

    def test_factor_count_1_to_4(self):
        h = generate_random_hypothesis(seed=42)
        assert 1 <= len(h["factors"]) <= 4

    def test_no_duplicate_factors(self):
        h = generate_random_hypothesis(seed=42)
        assert len(h["factors"]) == len(set(h["factors"]))

    def test_universe_valid(self):
        h = generate_random_hypothesis(seed=42)
        assert h["universe"] in UNIVERSE_OPTIONS

    def test_seed_reproducibility(self):
        h1 = generate_random_hypothesis(seed=42)
        h2 = generate_random_hypothesis(seed=42)
        assert h1 == h2

    def test_different_seeds_different_results(self):
        h1 = generate_random_hypothesis(seed=42)
        h2 = generate_random_hypothesis(seed=123)
        assert h1 != h2


class TestExploitativeHypothesis:
    def test_empty_history_returns_random(self):
        h = generate_exploitative_hypothesis([], seed=42)
        assert "factors" in h
        assert "weights" in h

    def test_perturbs_best_strategy(self):
        best = [{"strategy": {"factors": ["momentum_20d", "value_pe"], "weights": {"momentum_20d": 0.7, "value_pe": 0.3}}}]
        h = generate_exploitative_hypothesis(best, seed=42)
        assert h["factors"] == ["momentum_20d", "value_pe"]
        # weights should be perturbed (not exactly 0.7 and 0.3)
        assert h["weights"]["momentum_20d"] != 0.7 or h["weights"]["value_pe"] != 0.3

    def test_keeps_top_k_from_best(self):
        best = [{"strategy": {"factors": ["momentum_20d"], "weights": {"momentum_20d": 1.0}, "top_k": 50}}]
        h = generate_exploitative_hypothesis(best, seed=42)
        assert h.get("top_k", 50) == 50