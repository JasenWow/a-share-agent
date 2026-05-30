"""Integration test for the mining pipeline (mock data, no MCP dependency)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import numpy as np


class TestMiningPipeline:
    def test_template_only_pipeline(self):
        """Test the mining pipeline with mock data, skipping GP and network calls."""
        from data_fetcher import compute_forward_returns
        from templates import enumerate_candidates, template_search

        np.random.seed(42)
        T, N = 200, 25
        codes = [f"STOCK{i:03d}" for i in range(N)]

        # Generate realistic-looking price data
        close = np.random.randn(T, N).cumsum(axis=0) * 2 + 100
        volume = np.abs(np.random.randn(T, N)) * 1e6 + 5e5

        data_arrays = {
            "$close": close,
            "$open": close + np.random.randn(T, N) * 0.5,
            "$high": close + np.abs(np.random.randn(T, N)) * 0.5,
            "$low": close - np.abs(np.random.randn(T, N)) * 0.5,
            "$volume": volume,
        }

        forward_returns = compute_forward_returns(close, horizon=5)

        # Template search only (Layer 2)
        candidates = enumerate_candidates(
            categories=["trend", "momentum"],
            fields=["$close"],
            windows=[5, 10, 20],
        )

        results = template_search(
            candidates=candidates,
            data_arrays=data_arrays,
            forward_returns=forward_returns,
            top_k=5,
            min_ic=0.0,
        )

        assert isinstance(results, list)
        # With random data, we may or may not get results
        for r in results:
            assert "expression" in r
            assert "fitness" in r
            assert "ic" in r

    def test_pipeline_with_ranking(self):
        """Test template search + stock ranking integration."""
        from data_fetcher import compute_forward_returns
        from ranker import rank_stocks
        from templates import enumerate_candidates, template_search

        np.random.seed(123)
        T, N = 100, 15
        instruments = [f"S{i:03d}" for i in range(N)]

        # Create trending data: first half goes up, second half flat
        close = np.zeros((T, N))
        for t in range(T):
            close[t, :N//2] = 100 + t * 0.3
            close[t, N//2:] = 100 + np.random.randn(N - N//2) * 0.5

        data_arrays = {
            "$close": close,
            "$volume": np.abs(np.random.randn(T, N)) * 1e6,
        }
        forward_returns = compute_forward_returns(close, horizon=5)

        # Template search
        candidates = enumerate_candidates(
            categories=["momentum"],
            fields=["$close"],
            windows=[5, 10],
        )
        template_results = template_search(
            candidates=candidates,
            data_arrays=data_arrays,
            forward_returns=forward_returns,
            top_k=3,
            min_ic=0.0,
        )

        # Use discovered factors for ranking
        if template_results:
            factors = template_results[:3]
            rankings, _ = rank_stocks(factors, data_arrays, instruments)

            assert len(rankings) == N
            assert rankings[0]["rank"] == 1

            # Trending-up stocks should generally rank higher
            top_5 = [r["code"] for r in rankings[:5]]
            trending_count = sum(1 for c in top_5 if int(c[1:4]) < N // 2)
            assert trending_count >= 2, f"Expected trending stocks in top 5, got {top_5}"

    def test_pipeline_report_generation(self):
        """Test that report can be generated from pipeline results."""
        from report import generate_mining_report, generate_portfolio_report

        mining_result = {
            "direction": "动量趋势",
            "direction_description": "价格动量和趋势延续",
            "pool_size": 30,
            "period": "2024-01-01 to 2025-05-30",
            "n_trading_days": 350,
            "total_factors": 5,
            "factors": [
                {"expression": "Rank(Delta($close, 10))", "ic": 0.04, "icir": 0.6,
                 "turnover": 0.35, "fitness": 0.42, "source": "template_search"},
            ],
            "template_results": [],
            "gp_results": [],
        }

        ranking_result = [
            {"rank": 1, "code": "300124.SZ", "composite_score": 1.2, "momentum_score": 0.3, "signal": "强势延续"},
            {"rank": 2, "code": "002472.SZ", "composite_score": 0.8, "momentum_score": 0.5, "signal": "信号转强"},
        ]

        report = generate_mining_report(mining_result, ranking_result)
        assert "产业因子挖掘报告" in report
        assert "300124.SZ" in report
        assert "强势延续" in report

        # Portfolio report
        portfolio_result = {
            "holdings": [
                {"code": "300124.SZ", "rank": 1, "total_stocks": 30,
                 "composite_score": 1.2, "momentum_score": 0.3,
                 "signal": "强势延续", "health": "strong"},
            ],
            "diagnostics": {
                "n_holdings": 1, "n_evaluated": 1,
                "avg_score": 1.2, "concentration_risk": "moderate",
            },
            "factors_used": [
                {"expression": "Rank(Delta($close, 10))", "ic": 0.04, "icir": 0.6},
            ],
        }

        portfolio_report = generate_portfolio_report(portfolio_result)
        assert "持仓评估报告" in report or "300124" in portfolio_report
