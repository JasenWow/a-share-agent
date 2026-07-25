"""``aquan stock`` — A-share market data subcommand.

Aggregates 17 MCP tools across the akshare and tushare servers under a
single CLI surface. Each ``action`` maps to exactly one MCP tool, with
CLI arg names translated to the tool's parameter names.

Coverage:
  akshare (10): data_source_health, stock_zh_a_spot, stock_zh_a_hist,
                stock_board_concept_cons, index_stock_cons,
                stock_financial_abstract, stock_financial_report_sina,
                stock_hsgt_north_net_flow_in_em, stock_lhb_detail_em,
                stock_zh_index_daily
  tushare  (7): daily, income, balancesheet, cashflow, fina_indicator,
                index_weight, concept_detail

Actions are grouped: quotes (spot/hist/daily), fundamentals (financial/
income/balancesheet/cashflow/fina_indicator), boards (concept/concept_detail/
index_cons/index_weight/index_daily), flow (northbound/lhb), meta (health).
"""

from __future__ import annotations

import argparse
from typing import Any

from aquan.cli._format import format_output
from aquan.cli._mcp_proxy import CliMcpError, mcp_call

# action → (mcp_source, mcp_tool, {cli_arg: mcp_param})
# cli_arg names are the --foo flags; mcp_param is the tool's kwarg name.
ACTION_MAP: dict[str, tuple[str, str, dict[str, str]]] = {
    # --- quotes ---
    "spot": ("akshare", "stock_zh_a_spot", {"code": "symbol"}),
    "hist": (
        "akshare",
        "stock_zh_a_hist",
        {
            "code": "symbol",
            "period": "period",
            "start": "start_date",
            "end": "end_date",
            "adjust": "adjust",
        },
    ),
    "daily": (
        "tushare",
        "daily",
        {"code": "ts_code", "start": "start_date", "end": "end_date"},
    ),
    # --- fundamentals ---
    "financial": (
        "akshare",
        "stock_financial_abstract",
        {"code": "symbol", "indicator": "indicator"},
    ),
    "financial_report": (
        "akshare",
        "stock_financial_report_sina",
        {"code": "stock", "report": "symbol"},
    ),
    "income": ("tushare", "income", {"code": "ts_code", "period": "period"}),
    "balancesheet": ("tushare", "balancesheet", {"code": "ts_code", "period": "period"}),
    "cashflow": ("tushare", "cashflow", {"code": "ts_code", "period": "period"}),
    "fina_indicator": ("tushare", "fina_indicator", {"code": "ts_code", "period": "period"}),
    # --- boards / indices ---
    "concept": ("akshare", "stock_board_concept_cons", {"code": "symbol"}),
    "concept_detail": ("tushare", "concept_detail", {"code": "id"}),
    "index_cons": ("akshare", "index_stock_cons", {"code": "symbol"}),
    "index_weight": (
        "tushare",
        "index_weight",
        {"code": "index_code", "start": "start_date", "end": "end_date"},
    ),
    "index_daily": (
        "akshare",
        "stock_zh_index_daily",
        {"code": "symbol", "start": "start_date", "end": "end_date"},
    ),
    # --- flow / dragon-tiger ---
    "northbound": ("akshare", "stock_hsgt_north_net_flow_in_em", {}),
    "lhb": ("akshare", "stock_lhb_detail_em", {"start": "start_date", "end": "end_date"}),
    # --- meta ---
    "health": ("akshare", "data_source_health", {}),
}

ACTIONS_BY_GROUP: dict[str, list[str]] = {
    "quotes": ["spot", "hist", "daily"],
    "fundamentals": ["financial", "financial_report", "income", "balancesheet", "cashflow", "fina_indicator"],
    "boards": ["concept", "concept_detail", "index_cons", "index_weight", "index_daily"],
    "flow": ["northbound", "lhb"],
    "meta": ["health"],
}


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "stock",
        help="A-share market data (quotes, fundamentals, concepts, indices, flow).",
        description=_format_action_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("action", choices=list(ACTION_MAP.keys()), help="See command help for the full action list.")
    p.add_argument("--code", help="6-digit stock code or index code (e.g. 600519, 000300, sh000300).")
    p.add_argument("--symbol", dest="code", help="Alias for --code.")
    p.add_argument("--start", help="Start date YYYYMMDD.")
    p.add_argument("--end", help="End date YYYYMMDD.")
    p.add_argument("--period", help="Period (daily/weekly/monthly) or report period (YYYYMMQQ).")
    p.add_argument("--adjust", default=None, help="Adjust type for hist: qfq/hfq/'' (default qfq).")
    p.add_argument("--indicator", help="Financial abstract indicator (default 按年度).")
    p.add_argument("--report", help="Financial report type (利润表/资产负债表/现金流量表).")
    p.add_argument("--limit", type=int, default=None, help="Max rows in table output (default 20).")
    p.add_argument("--mcp-limit", type=int, default=None, help="Override the MCP tool's own row limit.")
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of a table.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    if args.action not in ACTION_MAP:
        print(f"Unknown action '{args.action}'. Available: {', '.join(ACTION_MAP.keys())}", flush=True)
        return 2

    source, tool, param_map = ACTION_MAP[args.action]
    params: dict[str, Any] = {}
    for cli_key, mcp_key in param_map.items():
        value = getattr(args, cli_key, None)
        if value is not None:
            params[mcp_key] = value
    if args.mcp_limit is not None:
        params["limit"] = args.mcp_limit

    try:
        result = mcp_call(source, tool, params)
    except CliMcpError as e:
        print(f"error: {e}", flush=True)
        return 1

    print(format_output(result, json_out=args.json, limit=args.limit or 20), flush=True)
    return 0


def _format_action_help() -> str:
    """Render the action catalog grouped by category for --help."""
    lines = ["A-share market data actions:", ""]
    for group, actions in ACTIONS_BY_GROUP.items():
        lines.append(f"  {group}:")
        for action in actions:
            source, tool, _ = ACTION_MAP[action]
            lines.append(f"    {action:<18} → {source}.{tool}")
        lines.append("")
    lines.append("Common args: --code --start --end --period --limit --json")
    return "\n".join(lines)
