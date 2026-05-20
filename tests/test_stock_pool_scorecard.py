"""Tests for stock-pool scorecard filter — data models and filter logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scorecard script directory to sys.path so we can import it
_SCRIPT_DIR = (
    Path(__file__).parent.parent
    / "plugins"
    / "vertical-plugins"
    / "equity-research"
    / "skills"
    / "stock-pool"
    / "scripts"
)
sys.path.insert(0, str(_SCRIPT_DIR))

from scorecard import filter_candidates, load_candidates  # noqa: E402

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "scorecard_candidates.json"


@pytest.fixture()
def candidates():
    """Load the standard test fixture."""
    return load_candidates(FIXTURE_PATH)


@pytest.fixture()
def default_result(candidates):
    """Run scorecard with default parameters on the standard fixture."""
    return filter_candidates(candidates)


# ---- Test 1 ----


def test_pure_play_passes_all_dimensions(default_result):
    """pure_play stock with good data passes all four dimensions."""
    passed = default_result["passed"]
    assert len(passed) >= 1
    stock = next(s for s in passed if s["code"] == "300124.SZ")
    sc = stock["scorecard"]
    assert sc["relevance"]["pass"] is True
    assert sc["liquidity"]["pass"] is True
    assert sc["fundamentals"]["pass"] is True
    assert sc["valuation"]["pass"] is True


# ---- Test 2 ----


def test_passed_stock_has_all_scorecard_dimensions(default_result):
    """Every passed stock has relevance/liquidity/fundamentals/valuation keys with pass and value."""
    for stock in default_result["passed"]:
        sc = stock["scorecard"]
        for dim in ("relevance", "liquidity", "fundamentals", "valuation"):
            assert dim in sc, f"Missing dimension: {dim}"
            assert "pass" in sc[dim], f"Missing 'pass' in {dim}"
            assert "value" in sc[dim], f"Missing 'value' in {dim}"


# ---- Test 3 ----


def test_st_stock_rejected(default_result):
    """ST stock goes to rejected list."""
    rejected_codes = [r["code"] for r in default_result["rejected"]]
    assert "688001.SZ" in rejected_codes


# ---- Test 4 ----


def test_concept_low_relevance_rejected(default_result):
    """Concept stock with revenue_share_pct < 20 is rejected for relevance."""
    rejected = next(r for r in default_result["rejected"] if r["code"] == "000001.SZ")
    assert "相关性" in rejected["reason"]


# ---- Test 5 ----


def test_rejected_has_reason(default_result):
    """Every rejected item has a non-empty reason string."""
    for r in default_result["rejected"]:
        assert "reason" in r
        assert isinstance(r["reason"], str)
        assert len(r["reason"]) > 0


# ---- Test 6 ----


def test_output_has_theme_and_date(default_result):
    """Output contains theme and pool_date fields."""
    assert "theme" in default_result
    assert default_result["theme"] == "机器人"
    assert "pool_date" in default_result
    assert len(default_result["pool_date"]) > 0


# ---- Test 7 ----


def test_passed_count(default_result):
    """Verify correct count of passed stocks — only 300124.SZ passes."""
    assert len(default_result["passed"]) == 1


# ---- Test 8 ----


def test_rejected_count(default_result):
    """Verify correct count of rejected stocks — 000001.SZ and 688001.SZ."""
    assert len(default_result["rejected"]) == 2


# ---- Test 9 ----


def test_custom_liquidity_threshold(candidates):
    """Very high liquidity threshold rejects all stocks."""
    result = filter_candidates(candidates, min_liquidity=1_000_000_000)
    assert len(result["passed"]) == 0
    assert len(result["rejected"]) == 3


# ---- Test 10 ----


def test_custom_pe_percentile_cap(candidates):
    """Very low PE percentile cap causes valuation failure for high-PE stocks."""
    result = filter_candidates(candidates, pe_percentile_cap=10)
    # 300124.SZ pe_percentile=62 > 10 → valuation fail
    # 000001.SZ pe_percentile=30 > 10 → valuation fail (also relevance fail)
    # 688001.SZ pe_percentile=98 > 10 → valuation fail (also ST)
    rejected_codes = [r["code"] for r in result["rejected"]]
    assert "300124.SZ" in rejected_codes
    assert "000001.SZ" in rejected_codes
    assert "688001.SZ" in rejected_codes
    assert len(result["passed"]) == 0
