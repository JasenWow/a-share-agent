"""ETL 报告子命令：缺数据 / 任务历史。

Usage:
  uv run python -m etl.report --missing-dates --domain equity_daily --last 30d
  uv run python -m etl.report --jobs --status failed --last 7d
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import duckdb

from etl.config import META_DB_PATH, ODS_ROOT


def _parse_last(s: str) -> datetime:
    """'30d' / '7d' → datetime（当前时间减 N 天）。"""
    if not s.endswith("d"):
        raise ValueError(f"--last expects format like '30d', got: {s}")
    days = int(s[:-1])
    return datetime.now(timezone.utc) - timedelta(days=days)


def missing_dates(domain: str, last: str) -> None:
    """报告某 domain 在最近 N 天缺失的交易日。"""
    since = _parse_last(last)
    parquet_glob = str(ODS_ROOT / f"{domain}/dt=*/part-*.parquet")

    conn = duckdb.connect(str(META_DB_PATH))
    try:
        # 已有分区
        try:
            rows = conn.execute(
                f"""SELECT DISTINCT dt FROM read_parquet(
                        '{parquet_glob}', hive_partitioning=true
                    ) ORDER BY dt"""
            ).fetchall()
            have = {r[0] for r in rows}
        except Exception:
            have = set()

        # 期望交易日（用 exchange_calendars）
        try:
            import exchange_calendars as xcals

            sess = xcals.get_calendar("XSHG")
            sessions = sess.sessions_in_range(
                since.strftime("%Y-%m-%d"),
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
            expected = {s.strftime("%Y-%m-%d") for s in sessions}
        except ImportError:
            expected = set()

        missing = sorted(expected - have)
        print(f"Missing dates for {domain} (last {last}): {len(missing)}")
        for d in missing:
            print(f"  - {d}")
        if missing:
            start = missing[0].replace("-", "")
            end = missing[-1].replace("-", "")
            print(f"\nBackfill: uv run python -m etl.runner {domain} --start {start} --end {end}")
    finally:
        conn.close()


def jobs_report(status: str | None, last: str) -> None:
    """报告队列任务历史。"""
    since = _parse_last(last)
    conn = duckdb.connect(str(META_DB_PATH))
    try:
        if status:
            rows = conn.execute(
                """SELECT id, domain, status, attempts, error,
                          created_at, finished_at
                   FROM etl_jobs
                   WHERE status = ? AND created_at >= ?
                   ORDER BY created_at DESC LIMIT 100""",
                [status, since.isoformat()],
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, domain, status, attempts, error,
                          created_at, finished_at
                   FROM etl_jobs
                   WHERE created_at >= ?
                   ORDER BY created_at DESC LIMIT 100""",
                [since.isoformat()],
            ).fetchall()

        print(f"Jobs (status={status or 'all'}, last {last}): {len(rows)}")
        for r in rows:
            err = f" | {r[4][:80]}" if r[4] else ""
            print(f"  [{r[2]:9}] {r[1]:20} attempts={r[3]} created={r[5][:19]}{err}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL report")
    parser.add_argument("--missing-dates", action="store_true")
    parser.add_argument("--quality-trend", action="store_true", help="(not yet implemented; needs quality_log table)")
    parser.add_argument("--jobs", action="store_true")
    parser.add_argument("--domain", default="equity_daily")
    parser.add_argument(
        "--status",
        default=None,
        choices=["pending", "running", "completed", "failed"],
    )
    parser.add_argument("--last", default="30d", help="time window, e.g. 30d / 7d")
    args = parser.parse_args()

    if args.missing_dates:
        missing_dates(args.domain, args.last)
    elif args.jobs:
        jobs_report(args.status, args.last)
    elif args.quality_trend:
        print("TODO: quality-trend needs quality_log table (not in this plan)")
        return 1
    else:
        parser.error("must specify --missing-dates / --jobs / --quality-trend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
