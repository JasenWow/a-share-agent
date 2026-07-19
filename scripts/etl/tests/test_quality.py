"""Tests for data quality checks."""

from common.quality import (
    run_checks,
    QualityReport,
    min_row_count,
    no_null_in,
    date_is,
)


def test_min_row_count_pass():
    """行数达标通过。"""
    check = min_row_count(100)
    result = check([{"a": 1}] * 150, "20260717")
    assert result.passed is True


def test_min_row_count_fail_blocking():
    """行数不足阻断。"""
    check = min_row_count(100)
    result = check([{"a": 1}] * 50, "20260717")
    assert result.passed is False
    assert result.blocking is True
    assert "100" in result.message


def test_no_null_in_pass():
    """关键字段无 null 通过。"""
    check = no_null_in(["code", "close"])
    rows = [{"code": "600519", "close": 1692.0}, {"code": "000001", "close": 12.5}]
    assert check(rows, "20260717").passed is True


def test_no_null_in_fail():
    """关键字段有 null 阻断。"""
    check = no_null_in(["code", "close"])
    rows = [{"code": "600519", "close": None}]
    result = check(rows, "20260717")
    assert result.passed is False
    assert result.blocking is True


def test_date_is_pass():
    """日期字段与预期一致通过。"""
    check = date_is("20260717", "trade_date")
    rows = [{"trade_date": "20260717"}, {"trade_date": "20260717"}]
    assert check(rows, "20260717").passed is True


def test_date_is_fail():
    """日期字段不一致阻断。"""
    check = date_is("20260717", "trade_date")
    rows = [{"trade_date": "20260716"}]
    assert check(rows, "20260717").passed is False


def test_run_checks_collects_all():
    """run_checks 跑所有检查并汇总。"""
    checks = [min_row_count(2), no_null_in(["code"])]
    rows = [{"code": "600519"}, {"code": "000001"}]
    report = run_checks("equity_daily", rows, "20260717", checks)
    assert report.has_blocking() is False
    assert len(report.issues) == 0


def test_run_checks_blocking_detected():
    """有 blocking issue 时 has_blocking 返回 True。"""
    checks = [min_row_count(100)]
    rows = [{"code": "600519"}]
    report = run_checks("equity_daily", rows, "20260717", checks)
    assert report.has_blocking() is True
    assert len(report.issues) == 1


def test_quality_report_to_list():
    """to_list 用于序列化到日志。"""
    report = QualityReport()
    report.issues.append(
        {
            "check": "min_row_count",
            "passed": False,
            "blocking": True,
            "message": "x",
        }
    )
    lst = report.to_list()
    assert len(lst) == 1
    assert lst[0]["check"] == "min_row_count"
