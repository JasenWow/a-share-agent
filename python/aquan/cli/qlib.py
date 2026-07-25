"""``aquan qlib`` — Qlib quant engine subcommand.

Wraps the 5 qlib-server MCP tools: initialize the data provider, fetch
raw feature data, evaluate a factor expression, list available
operators, and read a stock universe.
"""

from __future__ import annotations

import argparse
from typing import Any

from aquan.cli._format import format_output
from aquan.cli._mcp_proxy import CliMcpError, mcp_call

SOURCE = "qlib"


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "qlib",
        help="Qlib quant engine: data / eval / operators / universe.",
        description="Qlib-engine actions against the qlib MCP server.",
    )
    p.add_argument("action", choices=["init", "data", "eval", "operators", "universe"])
    p.add_argument("--source", default=None, help="Qlib data source id (init). Default 'qlib_cn_data'.")
    p.add_argument("--instruments", default=None, help="Instrument set (data/eval). 'all' or a universe name.")
    p.add_argument("--fields", default=None, help="Comma-separated feature fields (data), e.g. '$close,$volume'.")
    p.add_argument("--expression", default=None, help="Factor expression to evaluate (eval).")
    p.add_argument("--start", default=None, help="Start date YYYYMMDD.")
    p.add_argument("--end", default=None, help="End date YYYYMMDD.")
    p.add_argument("--name", default=None, help="Universe name (universe). Default 'csi300'.")
    p.add_argument("--limit", type=int, default=None, help="Max rows in table output (default 20).")
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of a table.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    action = args.action
    tool: str
    params: dict[str, Any] = {}

    if action == "init":
        tool = "qlib_init_data"
        if args.source is not None:
            params["source"] = args.source
    elif action == "data":
        tool = "qlib_get_data"
        if args.instruments is not None:
            params["instruments"] = args.instruments
        if args.fields is not None:
            params["fields"] = [s.strip() for s in args.fields.split(",") if s.strip()]
        if args.start is not None:
            params["start_date"] = args.start
        if args.end is not None:
            params["end_date"] = args.end
    elif action == "eval":
        tool = "qlib_eval_expression"
        if not args.expression:
            print("error: eval requires --expression", flush=True)
            return 2
        params["expression"] = args.expression
        if args.instruments is not None:
            params["instruments"] = args.instruments
        if args.start is not None:
            params["start_date"] = args.start
        if args.end is not None:
            params["end_date"] = args.end
    elif action == "operators":
        tool = "qlib_list_operators"
    elif action == "universe":
        tool = "qlib_get_universe"
        if args.name is not None:
            params["name"] = args.name
    else:
        print(f"Unknown action '{action}'", flush=True)
        return 2

    try:
        result = mcp_call(SOURCE, tool, params)
    except CliMcpError as e:
        print(f"error: {e}", flush=True)
        return 1

    print(format_output(result, json_out=args.json, limit=args.limit or 20), flush=True)
    return 0
