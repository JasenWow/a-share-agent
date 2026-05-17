import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from evolution import (
    CORRECTION_COUNT_LIMIT,
    CORRECTIONS,
    DOOM_THRESHOLD,
    MAX_ITERATIONS,
    EvolutionState,
    generate_correction,
    should_continue,
)


class TestEvolutionState:
    def test_creation(self):
        state = EvolutionState(
            iteration=1,
            best_return=0.05,
            recent_failures=[],
            failure_signatures={},
        )
        assert state.iteration == 1
        assert state.best_return == 0.05


class TestShouldContinue:
    def test_target_reached(self):
        state = EvolutionState(
            iteration=10,
            best_return=0.15,
            recent_failures=[],
            failure_signatures={},
        )
        should, reason = should_continue(state, target_return=0.10)
        assert should is False
        assert reason == "target_reached"

    def test_max_iterations_reached(self):
        state = EvolutionState(
            iteration=50,
            best_return=0.05,
            recent_failures=[],
            failure_signatures={},
        )
        should, reason = should_continue(state, target_return=0.10)
        assert should is False
        assert reason == "max_iterations"

    def test_doom_loop_detected(self):
        state = EvolutionState(
            iteration=5,
            best_return=0.02,
            recent_failures=["fail1", "fail2"],
            failure_signatures={"momentum_concentration": DOOM_THRESHOLD},
        )
        should, reason = should_continue(state, target_return=0.10)
        assert should is False
        assert reason == "doom_loop"

    def test_correction_limit_reached(self):
        state = EvolutionState(
            iteration=5,
            best_return=0.02,
            recent_failures=[],
            failure_signatures={
                "momentum_concentration": 2,
                "low_sharpe": 2,
                "high_turnover": 1,
            },
        )
        total = sum(state.failure_signatures.values())
        assert total >= CORRECTION_COUNT_LIMIT
        should, reason = should_continue(state, target_return=0.10)
        assert should is False
        assert reason == "correction_limit"

    def test_continue_normal(self):
        state = EvolutionState(
            iteration=5,
            best_return=0.02,
            recent_failures=[],
            failure_signatures={"momentum_concentration": 1},
        )
        should, reason = should_continue(state, target_return=0.10)
        assert should is True
        assert reason is None


class TestGenerateCorrection:
    def test_momentum_concentration(self):
        result = generate_correction("momentum_concentration")
        assert result == CORRECTIONS["momentum_concentration"]

    def test_value_overfit(self):
        result = generate_correction("value_overfit")
        assert result == CORRECTIONS["value_overfit"]

    def test_low_sharpe(self):
        result = generate_correction("low_sharpe")
        assert result == CORRECTIONS["low_sharpe"]

    def test_high_turnover(self):
        result = generate_correction("high_turnover")
        assert result == CORRECTIONS["high_turnover"]

    def test_unknown_signature(self):
        result = generate_correction("unknown_signature")
        assert "review strategy parameters" in result


class TestConstants:
    def test_max_iterations(self):
        assert MAX_ITERATIONS == 50

    def test_doom_threshold(self):
        assert DOOM_THRESHOLD == 3

    def test_correction_count_limit(self):
        assert CORRECTION_COUNT_LIMIT == 5

    def test_corrections_has_all_keys(self):
        expected = {"momentum_concentration", "value_overfit", "low_sharpe", "high_turnover"}
        assert set(CORRECTIONS.keys()) == expected


class TestEnrichedEvolutionState:
    def test_optional_fields_default_none(self):
        state = EvolutionState(
            iteration=1,
            best_return=0.05,
            recent_failures=[],
            failure_signatures={},
        )
        assert state.market_regime is None
        assert state.market_breadth is None
        assert state.volatility_index is None
        assert state.cash_ratio is None
        assert state.position_count is None
        assert state.sector_concentration is None
        assert state.unrealized_pnl is None

    def test_optional_fields_set(self):
        state = EvolutionState(
            iteration=5,
            best_return=0.12,
            recent_failures=[],
            failure_signatures={},
            market_regime="bull",
            market_breadth=1.8,
            volatility_index=0.15,
            cash_ratio=0.3,
            position_count=15,
            sector_concentration=0.25,
            unrealized_pnl=50000.0,
        )
        assert state.market_regime == "bull"
        assert state.cash_ratio == 0.3
        assert state.position_count == 15

    def test_should_continue_works_with_enriched_state(self):
        state = EvolutionState(
            iteration=5,
            best_return=0.02,
            recent_failures=[],
            failure_signatures={},
            market_regime="bear",
            volatility_index=0.4,
        )
        should, reason = should_continue(state, target_return=0.10)
        assert should is True
        assert reason is None