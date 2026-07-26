#!/usr/bin/env python3
"""Dummy subprocess runner for testing SubprocessRunner boundaries.

Usage:
  echo '{"dataset": "equity_daily", "session_date": "2026-08-04"}' | python dummy_subprocess.py etl
  python dummy_subprocess.py dbt
"""

import json
import sys

def etl_ok():
    print(json.dumps({"status": "ok", "dataset": "equity_daily", "date": "2026-08-04", "rows": 4231}))

def etl_failed():
    print(json.dumps({"status": "extract_failed", "error_code": "401", "error_message": "token invalid"}))

def etl_quality_failed():
    print(json.dumps({"status": "quality_failed", "dataset": "equity_daily", "date": "2026-08-04", "issues": [{"check": "min_row_count", "passed": False}]}))

def dbt_ok():
    print(json.dumps({"status": "success"}))

def dbt_failed():
    print(json.dumps({"status": "error", "error_code": "check_failed", "error_message": "OHLC invariant violated"}))

def main():
    if len(sys.argv) < 2:
        print('{"status": "error", "error_code": "usage", "error_message": "missing stage argument"}')
        sys.exit(1)

    stage = sys.argv[1]

    if stage == "etl-ok":
        etl_ok()
    elif stage == "etl-failed":
        etl_failed()
    elif stage == "etl-quality-failed":
        etl_quality_failed()
    elif stage == "dbt-ok":
        dbt_ok()
    elif stage == "dbt-failed":
        dbt_failed()
    else:
        print('{"status": "error", "error_code": "invalid_stage", "error_message": f"unknown stage: {stage}"}')
        sys.exit(1)

if __name__ == "__main__":
    main()