"""Tests for factor library client and mining loop."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))



class TestFactorLibrary:
    def test_expression_hash_consistent(self):
        from factor_library import expression_hash

        assert expression_hash("Rank($close / $open)") == expression_hash("Rank($close / $open)")

    def test_expression_hash_different(self):
        from factor_library import expression_hash

        assert expression_hash("Rank($close)") != expression_hash("Rank($volume)")

    def test_name_from_expression(self):
        from factor_library import name_from_expression

        name = name_from_expression("Rank(Ts_Mean($close, 20) / Ts_Std($close, 60))")
        assert "rank" in name
        assert "ts_mean" in name


class TestMiningDirection:
    def test_valid_direction(self):
        from mine_factors import validate_mining_direction

        direction = {
            "hypothesis": "test",
            "operators": ["Rank", "Add"],
            "data_fields": ["$close"],
            "universe": "csi300",
            "period": "2020-01-01 to 2025-01-01",
        }
        is_valid, msg = validate_mining_direction(direction)
        assert is_valid

    def test_missing_operators(self):
        from mine_factors import validate_mining_direction

        direction = {
            "hypothesis": "test",
            "operators": [],
            "data_fields": ["$close"],
            "universe": "csi300",
            "period": "2020-01-01 to 2025-01-01",
        }
        is_valid, msg = validate_mining_direction(direction)
        assert not is_valid
