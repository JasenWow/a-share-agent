"""
Tests for Prediction Store MCP Server.
"""

import tempfile
from pathlib import Path

import pytest

from server import (
    _validate_stock_code,  # noqa: F401
    _validate_date,  # noqa: F401
    manage_watchlist,
    store_prediction,
    get_predictions,
    record_actual,
    batch_record_actual,
    get_accuracy_report,
    get_error_analysis,
    get_next_trading_day,
)

DB_PATH = Path(tempfile.gettempdir()) / "test_predictions.db"


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Use a temp DB for each test."""
    import server

    monkeypatch.setattr(server, "DB_PATH", DB_PATH)
    server._init_db()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


class TestManageWatchlist:
    def test_add_stocks(self):
        result = manage_watchlist("add", ["000001", "600519"])
        assert len(result) == 2
        assert result[0]["status"] == "added"
        assert result[1]["status"] == "added"

    def test_list_stocks(self):
        manage_watchlist("add", ["000001", "600519"])
        result = manage_watchlist("list")
        assert len(result) == 2
        codes = {r["stock_code"] for r in result}
        assert codes == {"000001", "600519"}

    def test_remove_stocks(self):
        manage_watchlist("add", ["000001", "600519"])
        result = manage_watchlist("remove", ["000001"])
        assert result[0]["status"] == "removed"
        list_result = manage_watchlist("list")
        assert len(list_result) == 1

    def test_reject_exceeds_20(self):
        for i in range(20):
            code = f"{i:06d}"
            manage_watchlist("add", [code])
        result = manage_watchlist("add", ["999999"])
        assert "error" in result[0]
        assert "limit" in result[0]["error"].lower()

    def test_reject_invalid_code(self):
        result = manage_watchlist("add", ["12345"])
        assert "error" in result[0]
        assert "6 digits" in result[0]["error"]


class TestStorePrediction:
    def test_store_prediction(self):
        result = store_prediction("000001", "20260509", 1.5, 0.7, "{}")
        assert len(result) == 1
        assert result[0]["stock_code"] == "000001"
        assert result[0]["predicted_pct"] == 1.5
        assert result[0]["version"] == 1

    def test_upsert_version_increment(self):
        r1 = store_prediction("000001", "20260509", 1.5, 0.7)
        r2 = store_prediction("000001", "20260509", 2.0, 0.8)
        assert r2[0]["version"] > r1[0]["version"]

    def test_validation_invalid_stock_code(self):
        result = store_prediction("12345", "20260509", 1.5, 0.7)
        assert "error" in result[0]

    def test_validation_invalid_date(self):
        result = store_prediction("000001", "2026-05-09", 1.5, 0.7)
        assert "error" in result[0]

    def test_validation_pct_out_of_range(self):
        result = store_prediction("000001", "20260509", 35.0, 0.7)
        assert "error" in result[0]

    def test_validation_confidence_out_of_range(self):
        result = store_prediction("000001", "20260509", 1.5, 1.5)
        assert "error" in result[0]


class TestGetPredictions:
    def test_query_by_stock(self):
        store_prediction("000001", "20260509", 1.5, 0.7)
        store_prediction("600519", "20260509", 2.0, 0.8)
        result = get_predictions(stock_code="000001")
        assert len(result) == 1
        assert result[0]["stock_code"] == "000001"

    def test_query_by_date(self):
        store_prediction("000001", "20260510", 1.5, 0.7)
        result = get_predictions(signal_date="20260510")
        assert len(result) == 1

    def test_limit_enforcement(self):
        result = get_predictions(limit=5)
        assert isinstance(result, list)


class TestRecordActual:
    def test_record_actual(self):
        store_prediction("000001", "20260510", 1.0, 0.7)
        result = record_actual("000001", "20260510", 1.2)
        assert len(result) == 1
        assert result[0]["actual_pct"] == 1.2
        assert result[0]["error"] == 0.2

    def test_auto_error_compute(self):
        store_prediction("000001", "20260511", 2.0, 0.8)
        result = record_actual("000001", "20260511", 1.5)
        assert result[0]["error"] == -0.5

    def test_record_actual_not_found(self):
        result = record_actual("999999", "20260511", 1.0)
        assert "error" in result[0]


class TestBatchRecordActual:
    def test_batch_operations(self):
        store_prediction("000001", "20260512", 1.0, 0.7)
        store_prediction("600519", "20260512", 2.0, 0.8)
        actuals = [
            {"stock_code": "000001", "actual_pct": 1.2},
            {"stock_code": "600519", "actual_pct": 2.1},
        ]
        result = batch_record_actual("20260512", actuals)
        assert len(result) == 2


class TestGetAccuracyReport:
    def test_compute_metrics(self):
        store_prediction("000001", "20260513", 1.0, 0.7)
        record_actual("000001", "20260513", 1.2)
        result = get_accuracy_report(days=30)
        assert len(result) == 1
        assert "mae" in result[0]
        assert "hit_rate" in result[0]
        assert "bias" in result[0]

    def test_empty_report(self):
        result = get_accuracy_report(days=1)
        assert result[0]["total"] == 0


class TestGetErrorAnalysis:
    def test_error_pattern_analysis(self):
        store_prediction("000001", "20260514", 1.0, 0.7)
        record_actual("000001", "20260514", 1.2)
        result = get_error_analysis(days=30)
        assert len(result) == 1
        assert "by_stock" in result[0]
        assert "by_direction" in result[0]
        assert "by_magnitude" in result[0]


class TestGetNextTradingDay:
    def test_next_trading_day(self):
        result = get_next_trading_day("20260501")
        assert len(result) == 1
        assert "next_trading_day" in result[0]
        assert isinstance(result[0]["next_trading_day"], str)

    def test_next_trading_day_today(self):
        today = "20260511"
        result = get_next_trading_day(today)
        assert "next_trading_day" in result[0]

    def test_invalid_date(self):
        result = get_next_trading_day("invalid")
        assert "error" in result[0]


class TestValidationHelpers:
    def test_validate_stock_code_valid(self):
        assert _validate_stock_code("000001") is True
        assert _validate_stock_code("600519") is True

    def test_validate_stock_code_invalid(self):
        assert _validate_stock_code("12345") is False
        assert _validate_stock_code("1234567") is False
        assert _validate_stock_code("000001.SZ") is False

    def test_validate_date_valid(self):
        assert _validate_date("20260509") is True
        assert _validate_date("20240101") is True

    def test_validate_date_invalid(self):
        assert _validate_date("2026-05-09") is False
        assert _validate_date("2026051") is False
        assert _validate_date("invalid") is False