"""ETL 统一调度入口。

Usage:
  uv run python -m etl.runner equity_daily --date 20260717
  uv run python -m etl.runner equity_daily --start 2024-01-01 --end 2024-12-31
  uv run python -m etl.runner --priority P0 --date 20260717
  uv run python -m etl.runner --all --date 20260717
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from etl.config import LOGS_DIR, ensure_dirs
from aquan.utils import http as mcp_client

# domain 名 → (module_path, priority) 映射
_DOMAIN_REGISTRY = {
    "equity_daily": ("etl.ods.equity_daily", "P0"),
    "index_constituents": ("etl.ods.index_constituents", "P0"),
    "financial_income": ("etl.ods.financial_income", "P1"),
    # 实验数据入仓（子项目 ❷）：internal-store 快照，P2
    "factor_experiments": ("etl.ods.factor_experiments", "P2"),
    "backtest_runs": ("etl.ods.backtest_runs", "P2"),
    "strategy_hypotheses": ("etl.ods.strategy_hypotheses", "P2"),
}


def _import_domain(name: str):
    """动态 import domain 模块的 run 函数。"""
    module_name = _DOMAIN_REGISTRY[name][0]
    return __import__(module_name, fromlist=["run"])


def _run_single(domain: str, date: str) -> dict:
    """跑单个 domain 单日。返回运行报告。"""
    mod = _import_domain(domain)
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = mod.run(date)
        result["started_at"] = started
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception as e:
        return {
            "status": "error",
            "domain": domain,
            "date": date,
            "error": f"{type(e).__name__}: {e}",
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }


def _run_range(domain: str, start: str, end: str) -> list[dict]:
    """跑日期范围，逐日执行。start/end 格式 YYYYMMDD。

    用 exchange_calendars 过滤交易日；库不可用时退化为逐日（domain 会返回空数据）。
    """
    try:
        import exchange_calendars as xcals

        sess = xcals.get_calendar("XSHG")  # 上交所
        sessions = sess.sessions_in_range(start, end)
        dates = [s.strftime("%Y%m%d") for s in sessions]
    except ImportError:
        from datetime import datetime as dt, timedelta

        dates = []
        cur = dt.strptime(start, "%Y%m%d")
        end_dt = dt.strptime(end, "%Y%m%d")
        while cur <= end_dt:
            dates.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)

    return [_run_single(domain, d) for d in dates]


def _write_log(reports: list[dict]) -> str:
    """写运行日志 JSON 到 _logs/。返回路径。"""
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"etl_{ts}.json"
    log_path.write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))
    return str(log_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL runner")
    parser.add_argument(
        "domain",
        nargs="?",
        default=None,
        help="single domain (e.g., equity_daily)",
    )
    parser.add_argument("--date", default=None, help="YYYYMMDD")
    parser.add_argument("--start", default=None, help="YYYYMMDD (range start)")
    parser.add_argument("--end", default=None, help="YYYYMMDD (range end)")
    parser.add_argument(
        "--priority",
        default=None,
        choices=["P0", "P1", "P2"],
        help="run all domains of given priority",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="run all registered domains",
    )
    parser.add_argument(
        "--direct-sdk",
        action="store_true",
        help="(reserved) bypass MCP HTTP, call SDK directly. Currently no-op; all domains go through MCP HTTP.",
    )
    args = parser.parse_args()

    # 确定要跑的 domain 列表
    if args.domain:
        if args.domain not in _DOMAIN_REGISTRY:
            parser.error(f"unknown domain '{args.domain}'. Available: {', '.join(_DOMAIN_REGISTRY)}")
        domains = [args.domain]
    elif args.priority:
        domains = [n for n, (_, p) in _DOMAIN_REGISTRY.items() if p == args.priority]
    elif args.all:
        domains = list(_DOMAIN_REGISTRY.keys())
    else:
        parser.error("must specify domain, --priority, or --all")

    # 健康检查（任一不通只告警不退出）
    print("Health check:")
    for src in ["akshare", "tushare"]:
        ok = mcp_client.health_check(src)
        icon = "✓" if ok else "⚠️ "
        print(f"  {icon} MCP {src}: {'reachable' if ok else 'unreachable'}")

    reports = []
    for domain in domains:
        if args.start and args.end:
            print(f"\n→ {domain}: range {args.start} ~ {args.end}")
            reports.extend(_run_range(domain, args.start, args.end))
        else:
            date = args.date or datetime.now().strftime("%Y%m%d")
            print(f"\n→ {domain}: {date}")
            reports.append(_run_single(domain, date))

    # 汇总打印
    print("\n" + "=" * 60)
    for r in reports:
        status_icon = "✓" if r["status"] == "ok" else "✗"
        label = r.get("date") or r.get("period") or r.get("month", "")
        extra = f" ({r.get('rows')} rows)" if r.get("rows") else ""
        if r["status"] != "ok" and r.get("error"):
            extra += f" | {r['error']}"
        print(f"  {status_icon} {r.get('domain', '?'):20} {label} → {r['status']}{extra}")

    log_path = _write_log(reports)
    print(f"\nLog: {log_path}")

    # 任一失败返回非零
    return 0 if all(r["status"] == "ok" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
