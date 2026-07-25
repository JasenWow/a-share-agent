"""``aquan factor`` — factor lifecycle subcommand.

Aggregates 5 MCP tools on the internal-store server that cover the
factor lifecycle: discover (list), record new (register / candidates),
and transition state (promote / deprecate). reject_factor is folded
into the same shape as deprecate.
"""

from __future__ import annotations

import argparse
import json as _json
from typing import Any

from aquan.cli._format import format_output
from aquan.cli._mcp_proxy import CliMcpError, mcp_call

SOURCE = "internal-store"

ACTION_MAP: dict[str, tuple[str, dict[str, str]]] = {
    # read-only
    "list": ("list_factors", {"status": "status", "universe": "universe"}),
    "candidates": ("list_candidates", {"limit": "limit"}),
    # write — register a new candidate
    "register": (
        "register_factor_candidate",
        {
            "name": "name",
            "expression": "expression",
            "operators": "operators",
            "fields": "data_fields",
            "hypothesis": "hypothesis",
            "ic": "ic",
            "icir": "icir",
            "turnover": "turnover",
        },
    ),
    # state transitions
    "promote": ("promote_factor", {"id": "factor_id", "reviewer": "reviewer", "notes": "notes"}),
    "deprecate": ("deprecate_factor", {"id": "factor_id", "reason": "reason"}),
    "reject": ("reject_factor", {"id": "factor_id", "reason": "reason", "reviewer": "reviewer"}),
}


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "factor",
        help="Factor lifecycle: list / register / promote / deprecate.",
        description="Factor lifecycle actions against the internal-store MCP.",
    )
    p.add_argument("action", choices=list(ACTION_MAP.keys()))
    # read
    p.add_argument("--status", default=None, help="Filter by status (active/deprecated/all). Default 'active'.")
    p.add_argument("--universe", default=None, help="Filter by universe (e.g. csi300).")
    p.add_argument("--limit", type=int, default=None, help="Max rows (default 50 for candidates, 20 otherwise).")
    # register
    p.add_argument("--name", help="Factor name (register).")
    p.add_argument("--expression", help="Factor expression string (register).")
    p.add_argument("--operators", help="Comma-separated operator list (register), e.g. 'mean,stddev'.")
    p.add_argument("--fields", help="Comma-separated data fields (register), e.g. 'close,volume'.")
    p.add_argument("--hypothesis", default="", help="Hypothesis text (register).")
    p.add_argument("--ic", type=float, default=None, help="Information coefficient (register).")
    p.add_argument("--icir", type=float, default=None, help="ICIR (register).")
    p.add_argument("--turnover", type=float, default=None, help="Turnover (register).")
    # transitions
    p.add_argument("--id", type=int, default=None, help="Factor id (promote/deprecate/reject).")
    p.add_argument("--reason", default=None, help="Reason text (deprecate/reject).")
    p.add_argument("--reviewer", default=None, help="Reviewer name (promote/reject).")
    p.add_argument("--notes", default=None, help="Notes (promote).")
    # output
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of a table.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    if args.action not in ACTION_MAP:
        print(f"Unknown action '{args.action}'. Available: {', '.join(ACTION_MAP.keys())}", flush=True)
        return 2

    tool, param_map = ACTION_MAP[args.action]
    params: dict[str, Any] = {}
    for cli_key, mcp_key in param_map.items():
        value = getattr(args, cli_key, None)
        if value is None:
            continue
        # operators / fields arrive as comma-separated strings; the MCP tool wants a list.
        if cli_key in ("operators", "fields") and isinstance(value, str):
            params[mcp_key] = [s.strip() for s in value.split(",") if s.strip()]
        else:
            params[mcp_key] = value

    # required-arg sanity for the write actions
    if args.action == "register":
        missing = [k for k in ("name", "expression", "operators", "fields") if not getattr(args, k)]
        if missing:
            print(f"error: register requires --{', --'.join(missing)}", flush=True)
            return 2
    if args.action in ("promote", "deprecate", "reject") and args.id is None:
        print(f"error: {args.action} requires --id", flush=True)
        return 2

    try:
        result = mcp_call(SOURCE, tool, params)
    except CliMcpError as e:
        print(f"error: {e}", flush=True)
        return 1

    default_limit = 50 if args.action == "candidates" else 20
    print(format_output(result, json_out=args.json, limit=args.limit or default_limit), flush=True)
    return 0


# silence unused import lint for json (kept for future structured output extension)
_ = _json
