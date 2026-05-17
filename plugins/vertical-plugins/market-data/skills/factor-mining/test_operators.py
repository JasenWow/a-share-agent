"""Tests for Qlib operator -> DEAP primitive mapping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import numpy as np


class TestOperatorRegistry:
    def test_all_categories_present(self):
        from operators import OPERATOR_REGISTRY

        assert "time-series" in OPERATOR_REGISTRY
        assert "cross-section" in OPERATOR_REGISTRY
        assert "arithmetic" in OPERATOR_REGISTRY
        assert "conditional" in OPERATOR_REGISTRY

    def test_operator_has_required_fields(self):
        from operators import OPERATOR_REGISTRY

        for category, ops in OPERATOR_REGISTRY.items():
            for op in ops:
                assert "name" in op, f"Missing name in {category}"
                assert "arity" in op, f"Missing arity for {op.get('name', '?')}"
                assert "qlib_expr" in op, f"Missing qlib_expr for {op.get('name', '?')}"
                assert "deap_func" in op, f"Missing deap_func for {op.get('name', '?')}"

    def test_ts_mean_output(self):
        from operators import OPERATOR_REGISTRY

        ts_mean = next(op for op in OPERATOR_REGISTRY["time-series"] if op["name"] == "Ts_Mean")
        result = ts_mean["deap_func"](np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
        assert np.isclose(result, 4.0)

    def test_rank_output(self):
        from operators import OPERATOR_REGISTRY

        rank_op = next(op for op in OPERATOR_REGISTRY["cross-section"] if op["name"] == "Rank")
        result = rank_op["deap_func"](np.array([3.0, 1.0, 2.0, 5.0, 4.0]))
        expected = np.array([0.6, 0.2, 0.4, 1.0, 0.8])
        np.testing.assert_array_almost_equal(result, expected)

    def test_add_output(self):
        from operators import OPERATOR_REGISTRY

        add_op = next(op for op in OPERATOR_REGISTRY["arithmetic"] if op["name"] == "Add")
        assert add_op["deap_func"](3.0, 4.0) == 7.0

    def test_expression_to_qlib_string(self):
        from operators import expression_to_qlib_string

        assert expression_to_qlib_string("Rank", ["$close"]) == "Rank($close)"
        assert expression_to_qlib_string("Ts_Mean", ["$close", "20"]) == "Ts_Mean($close, 20)"
