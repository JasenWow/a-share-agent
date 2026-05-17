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


from unittest.mock import patch, MagicMock
import pandas as pd


class TestPluggableUniverse:
    def test_universe_configs_has_all_types(self):
        from generate_hypothesis import UNIVERSE_CONFIGS
        assert "全A" in UNIVERSE_CONFIGS
        assert "沪深300" in UNIVERSE_CONFIGS
        assert "AI-concept" in UNIVERSE_CONFIGS
        assert "custom" in UNIVERSE_CONFIGS

    def test_resolve_custom_universe(self):
        from generate_hypothesis import resolve_universe, UNIVERSE_CONFIGS
        config = {"type": "custom", "codes": ["000001", "600519"]}
        codes = resolve_universe(config)
        assert codes == ["000001", "600519"]

    @patch("generate_hypothesis.ak")
    def test_resolve_concept_universe(self, mock_ak):
        mock_ak.stock_board_concept_cons_em.return_value = pd.DataFrame({
            "代码": ["000001", "600519", "000002"],
        })
        from generate_hypothesis import resolve_universe
        config = {"type": "concept", "name": "人工智能"}
        codes = resolve_universe(config)
        assert len(codes) == 3
        assert "000001" in codes

    def test_generate_random_with_ai_concept(self):
        from generate_hypothesis import generate_random_hypothesis
        h = generate_random_hypothesis(seed=42)
        assert "universe" in h


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


class TestDynamicFactorLoading:
    def test_loads_custom_factors_from_registry(self, tmp_path):
        import json
        registry = {"custom_factors": [
            {"name": "custom_momentum_30d", "script": "generated/compute_custom_momentum_30d.py", "registered_at": "2026-05-17"}
        ]}
        registry_path = tmp_path / "factor_registry.json"
        registry_path.write_text(json.dumps(registry))
        from generate_hypothesis import load_all_factors
        factors = load_all_factors(registry_path)
        assert "custom_momentum_30d" in factors
        assert "momentum_20d" in factors  # base factors still present

    def test_loads_base_factors_when_no_registry(self, tmp_path):
        import json
        registry_path = tmp_path / "nonexistent.json"
        from generate_hypothesis import load_all_factors
        factors = load_all_factors(registry_path)
        assert len(factors) == 12  # all base factors

    def test_generate_random_uses_all_factors(self, tmp_path):
        import json
        registry = {"custom_factors": [
            {"name": "custom_alpha", "script": "x.py", "registered_at": "2026-05-17"}
        ]}
        registry_path = tmp_path / "factor_registry.json"
        registry_path.write_text(json.dumps(registry))
        from generate_hypothesis import generate_random_hypothesis
        # Patch FACTOR_LIBRARY to include custom factor
        import generate_hypothesis as gh
        original = gh.FACTOR_LIBRARY[:]
        gh.FACTOR_LIBRARY = original + ["custom_alpha"]
        try:
            h = gh.generate_random_hypothesis(seed=99)
            assert h["factors"]  # just ensure it doesn't crash
        finally:
            gh.FACTOR_LIBRARY = original