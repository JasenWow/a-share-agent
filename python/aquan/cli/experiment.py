"""``aquan experiment`` — experiments / backtests / strategies subcommand.

Aggregates 12 MCP tools on the internal-store server that cover the
experiment lifecycle: list, record, step through, find best strategies,
inspect transitions, and query failures + episode summaries.

Record actions (record / record_step / record_transition /
record_episode) accept JSON strings for the dict-typed MCP parameters
(they parse with json.loads). Read actions return tables by default.
"""

from __future__ import annotations

import argparse
import json as _json
from typing import Any

from aquan.cli._format import format_output
from aquan.cli._mcp_proxy import CliMcpError, mcp_call

SOURCE = "internal-store"


def _parse_json_arg(name: str, value: str | None) -> Any:
    """Parse a JSON-string CLI arg, with a friendly error for bad input."""
    if value is None:
        return None
    try:
        return _json.loads(value)
    except _json.JSONDecodeError as e:
        raise SystemExit(f"error: --{name} is not valid JSON: {e}") from e


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "experiment",
        help="Experiments, backtests, strategies, episodes.",
        description="Experiment-lifecycle actions against the internal-store MCP.",
    )
    p.add_argument(
        "action",
        choices=[
            "list",
            "record",
            "steps",
            "latest_step",
            "best",
            "failures",
            "transitions",
            "similar",
            "matrix",
            "episode_summaries",
            "backtests",
            "portfolio",
        ],
    )
    # identifiers
    p.add_argument("--id", type=int, default=None, help="Experiment id.")
    p.add_argument("--name", default=None, help="Experiment name (record).")
    p.add_argument("--portfolio", default=None, help="Portfolio name (portfolio).")
    # numeric knobs
    p.add_argument("--top", type=int, default=None, help="top_k (best / similar).")
    p.add_argument("--limit", type=int, default=None, help="Max rows (failures / lists).")
    # record_experiment
    p.add_argument("--strategy", default=None, help="Strategy JSON (record).")
    p.add_argument("--params", default=None, help="Params JSON (record).")
    p.add_argument("--result", default=None, help="Result JSON (record).")
    # record_experiment_step
    p.add_argument("--step-index", type=int, default=None, help="Step index (record_step).")
    p.add_argument("--step-type", default=None, help="Step type (record_step).")
    p.add_argument("--hypothesis", default=None, help="Hypothesis JSON (record_step).")
    p.add_argument("--signals", default=None, help="Signals summary JSON (record_step).")
    p.add_argument("--sim-result", default=None, help="Simulation result JSON (record_step).")
    p.add_argument("--state", default=None, help="State snapshot JSON (record_step / state_vector for similar/matrix).")
    # record_transition
    p.add_argument("--reward", default=None, help="Reward JSON (record_transition).")
    p.add_argument("--next-state", default=None, help="Next state JSON (record_transition).")
    # record_episode_summary
    p.add_argument("--period", default=None, help="Period label (record_episode).")
    p.add_argument("--initial-capital", type=float, default=None, help="(record_episode).")
    p.add_argument("--final-nav", type=float, default=None, help="(record_episode).")
    p.add_argument("--sharpe", type=float, default=None, help="(record_episode).")
    p.add_argument("--max-drawdown", type=float, default=None, help="(record_episode).")
    # output
    p.add_argument("--json", action="store_true", help="Emit raw JSON instead of a table.")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    action = args.action
    params: dict[str, Any] = {}
    tool: str

    if action == "list":
        tool = "list_experiments"
    elif action == "record":
        tool = "record_experiment"
        _require(action, args, ["name", "strategy", "params", "result"])
        params.update(
            name=args.name,
            strategy=_parse_json_arg("strategy", args.strategy),
            params=_parse_json_arg("params", args.params),
            result=_parse_json_arg("result", args.result),
        )
    elif action == "steps":
        tool = "list_experiment_steps"
        _require(action, args, ["id"])
        params["experiment_id"] = args.id
    elif action == "latest_step":
        tool = "get_latest_step"
        _require(action, args, ["id"])
        params["experiment_id"] = args.id
    elif action == "best":
        tool = "get_best_strategies"
        if args.top is not None:
            params["top_k"] = args.top
    elif action == "failures":
        tool = "get_failures"
        if args.id is not None:
            params["experiment_id"] = args.id
        if args.limit is not None:
            params["limit"] = args.limit
    elif action == "transitions":
        # alias of record_transition for clarity in CLI space
        tool = "record_transition"
        _require(action, args, ["id", "state", "strategy", "reward", "next_state"])
        params.update(
            experiment_id=args.id,
            state=_parse_json_arg("state", args.state),
            strategy=_parse_json_arg("strategy", args.strategy),
            reward=_parse_json_arg("reward", args.reward),
            next_state=_parse_json_arg("next-state", args.next_state),
        )
    elif action == "similar":
        tool = "get_similar_states"
        _require(action, args, ["state"])
        params.update(
            state_vector=_parse_json_arg("state", args.state),
            top_k=args.top if args.top is not None else 5,
        )
    elif action == "matrix":
        tool = "get_transition_matrix"
        _require(action, args, ["state"])
        params["state_vector"] = _parse_json_arg("state", args.state)
    elif action == "episode_summaries":
        tool = "list_episode_summaries"
    elif action == "backtests":
        tool = "list_backtest_results"
        if args.limit is not None:
            params["limit"] = args.limit
    elif action == "portfolio":
        tool = "get_portfolio"
        if args.portfolio is not None:
            params["name"] = args.portfolio
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


def _require(action: str, args: argparse.Namespace, keys: list[str]) -> None:
    missing = [k for k in keys if not getattr(args, k.replace("-", "_"))]
    if missing:
        raise SystemExit(f"error: {action} requires --{', --'.join(missing)}")
