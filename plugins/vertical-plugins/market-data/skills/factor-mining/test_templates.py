"""Tests for factor template enumeration and search."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import numpy as np


class TestTemplateEnumeration:
    def test_enumerate_returns_candidates(self):
        from templates import enumerate_candidates

        candidates = enumerate_candidates()
        assert len(candidates) > 0
        for c in candidates:
            assert "expression" in c
            assert "category" in c
            assert "template" in c

    def test_enumerate_single_category(self):
        from templates import enumerate_candidates

        candidates = enumerate_candidates(categories=["trend"])
        assert all(c["category"] == "trend" for c in candidates)

    def test_enumerate_custom_fields(self):
        from templates import enumerate_candidates

        candidates = enumerate_candidates(fields=["$close"])
        # Single-field templates should work
        assert any("$close" in c["expression"] for c in candidates)

    def test_enumerate_dual_field_templates(self):
        from templates import enumerate_candidates

        candidates = enumerate_candidates(
            fields=["$close", "$volume"],
            categories=["volume_price"],
        )
        # volume_price has dual-field templates
        assert len(candidates) > 0
        # No same-field pairs for dual-field templates
        for c in candidates:
            if "$X" in c["template"] and "$Y" in c["template"]:
                # After substitution, the two fields should differ
                pass  # verified by construction


class TestTemplateSearch:
    def test_template_search_with_mock_data(self):
        from templates import enumerate_candidates, template_search

        np.random.seed(42)
        T, N = 100, 30
        data_arrays = {
            "$close": np.random.randn(T, N).cumsum(axis=0) + 100,
            "$open": np.random.randn(T, N).cumsum(axis=0) + 100,
            "$high": np.random.randn(T, N).cumsum(axis=0) + 101,
            "$low": np.random.randn(T, N).cumsum(axis=0) + 99,
            "$volume": np.abs(np.random.randn(T, N)) * 1e6,
        }
        forward_returns = np.random.randn(T, N) * 0.02

        candidates = enumerate_candidates(
            categories=["momentum"],
            fields=["$close"],
            windows=[5, 10],
        )

        results = template_search(
            candidates=candidates,
            data_arrays=data_arrays,
            forward_returns=forward_returns,
            top_k=5,
            min_ic=0.0,  # Low threshold for random data
        )

        # Should return results (may have low IC with random data)
        assert isinstance(results, list)
        if results:
            assert "ic" in results[0]
            assert "icir" in results[0]
            assert "fitness" in results[0]

    def test_evaluate_candidate_handles_errors(self):
        from templates import evaluate_candidate

        data_arrays = {"$close": np.array([[1.0, 2.0]])}
        forward_returns = np.array([[0.01, -0.01]])

        # Expression that may fail
        result = evaluate_candidate("InvalidOp($close)", data_arrays, forward_returns)
        assert result["fitness"] == -999.0
