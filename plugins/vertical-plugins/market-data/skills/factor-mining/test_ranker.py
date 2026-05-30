"""Tests for stock ranking and portfolio evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import numpy as np


class TestRankStocks:
    def test_rank_stocks_basic(self):
        from ranker import rank_stocks

        np.random.seed(42)
        T, N = 60, 10
        instruments = [f"STOCK{i:03d}" for i in range(N)]
        data_arrays = {
            "$close": np.random.randn(T, N).cumsum(axis=0) + 100,
        }
        forward_returns = np.random.randn(T, N) * 0.02

        factors = [
            {"expression": "Rank($close / Ts_Mean($close, 20))", "icir": 0.5, "ic": 0.03},
        ]

        results, details = rank_stocks(factors, data_arrays, instruments)

        assert len(results) == N
        assert results[0]["rank"] == 1
        assert results[0]["code"] is not None
        assert "composite_score" in results[0]
        assert "signal" in results[0]

    def test_rank_signals_classified(self):
        from ranker import rank_stocks

        np.random.seed(42)
        T, N = 60, 20
        instruments = [f"S{i:03d}" for i in range(N)]
        # Create data where first half trends up, second half trends down
        data = np.zeros((T, N))
        for t in range(T):
            data[t, :N//2] = 100 + t * 0.5  # uptrend
            data[t, N//2:] = 100 - t * 0.3  # downtrend
        data_arrays = {"$close": data}

        factors = [
            {"expression": "Rank(Delta($close, 5))", "icir": 1.0, "ic": 0.05},
        ]

        results, _ = rank_stocks(factors, data_arrays, instruments)

        # Should have classified signals
        signals = {r["signal"] for r in results}
        assert len(signals) > 0
        # Uptrend stocks should rank higher
        top_codes = [r["code"] for r in results[:5]]
        assert any(c.startswith("S00") for c in top_codes)  # uptrend group


class TestPortfolioEvaluation:
    def test_evaluate_portfolio(self):
        from ranker import evaluate_portfolio

        np.random.seed(42)
        T, N = 60, 10
        instruments = [f"STOCK{i:03d}" for i in range(N)]
        data_arrays = {
            "$close": np.random.randn(T, N).cumsum(axis=0) + 100,
        }

        factors = [
            {"expression": "Rank($close / Ts_Mean($close, 20))", "icir": 0.5, "ic": 0.03},
        ]

        holdings = [
            {"code": "STOCK000"},
            {"code": "STOCK005"},
            {"code": "STOCK009"},
        ]

        result = evaluate_portfolio(holdings, factors, data_arrays, instruments)

        assert "holdings" in result
        assert "diagnostics" in result
        assert len(result["holdings"]) == 3
        assert result["diagnostics"]["n_holdings"] == 3

    def test_evaluate_portfolio_missing_stock(self):
        from ranker import evaluate_portfolio

        np.random.seed(42)
        T, N = 60, 5
        instruments = [f"S{i:03d}" for i in range(N)]
        data_arrays = {"$close": np.random.randn(T, N).cumsum(axis=0) + 100}

        factors = [
            {"expression": "Rank($close)", "icir": 0.5, "ic": 0.03},
        ]

        holdings = [
            {"code": "S000"},  # exists
            {"code": "MISSING"},  # does not exist
        ]

        result = evaluate_portfolio(holdings, factors, data_arrays, instruments)

        assert len(result["holdings"]) == 2
        # Missing stock should have None scores
        missing = next(h for h in result["holdings"] if h["code"] == "MISSING")
        assert missing["composite_score"] is None
        assert missing["signal"] == "无数据"
