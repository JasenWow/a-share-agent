"""数据质量检查框架。

每张 ODS 表在 ETL 内联跑一组 CheckFunc。
CheckFunc 返回 CheckResult（含 blocking 标志）。
QualityReport 汇总所有结果，has_blocking() 用于决定是否阻断写入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CheckResult:
    passed: bool
    blocking: bool
    message: str
    check: str  # 检查名


# CheckFunc 签名：(rows, date) -> CheckResult
CheckFunc = Callable[[list[dict], str], CheckResult]


@dataclass
class QualityReport:
    issues: list[dict] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        if not result.passed:
            self.issues.append(
                {
                    "check": result.check,
                    "passed": result.passed,
                    "blocking": result.blocking,
                    "message": result.message,
                }
            )

    def has_blocking(self) -> bool:
        return any(i["blocking"] for i in self.issues)

    def to_list(self) -> list[dict]:
        return list(self.issues)


def run_checks(
    domain: str,
    rows: list[dict],
    date: str,
    checks: list[CheckFunc],
) -> QualityReport:
    """跑所有检查，返回 QualityReport。"""
    report = QualityReport()
    for check in checks:
        result = check(rows, date)
        report.add(result)
    return report


# --------------------------------------------------------------------------
# 内置 check 工厂函数
# --------------------------------------------------------------------------


def min_row_count(threshold: int) -> CheckFunc:
    """行数 ≥ threshold，否则 blocking。"""

    def _check(rows: list[dict], date: str) -> CheckResult:
        n = len(rows)
        if n >= threshold:
            return CheckResult(True, False, f"rows={n} >= {threshold}", "min_row_count")
        return CheckResult(False, True, f"rows={n} < {threshold}", "min_row_count")

    return _check


def no_null_in(fields: list[str]) -> CheckFunc:
    """指定字段不允许 null，否则 blocking。"""

    def _check(rows: list[dict], date: str) -> CheckResult:
        for f in fields:
            nulls = sum(1 for r in rows if r.get(f) is None)
            if nulls > 0:
                return CheckResult(
                    False,
                    True,
                    f"field '{f}' has {nulls} nulls",
                    "no_null_in",
                )
        return CheckResult(True, False, "no nulls in required fields", "no_null_in")

    return _check


def date_is(expected: str, field: str) -> CheckFunc:
    """指定字段值全部等于 expected，否则 blocking。"""

    def _check(rows: list[dict], date: str) -> CheckResult:
        bad = [r for r in rows if str(r.get(field, "")) != expected]
        if bad:
            return CheckResult(
                False,
                True,
                f"{len(bad)} rows have {field} != {expected}",
                "date_is",
            )
        return CheckResult(True, False, f"all rows {field}={expected}", "date_is")

    return _check
