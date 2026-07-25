"""``aquan`` command-line entry point.

Aggregates four domain subcommands over the running MCP servers:

  aquan stock <action>        quotes, fundamentals, concepts, indices, flow
  aquan factor <action>       factor lifecycle: list / register / promote / ...
  aquan experiment <action>   experiments / backtests / strategies / episodes
  aquan qlib <action>         Qlib quant engine: data / eval / operators / ...

Each subcommand is a thin shaping layer on top of the canonical MCP
HTTP layer (``aquan.utils.http.call``). MCP servers stay unchanged;
this CLI exists to give the LLM agent (via @aquan/pi-runtime's
cli-tools) a compact, token-efficient surface instead of 44 raw MCP
tool schemas.

Registered as a console script via pyproject.toml so `aquan` is on
PATH after `uv sync` (no `uv run` overhead per invocation).
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from aquan import __version__
from aquan.cli import experiment, factor, qlib, stock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aquan",
        description="aquan — A-share quantitative analysis toolkit (agent-friendly CLI).",
    )
    parser.add_argument("--version", action="version", version=f"aquan {__version__}")
    sub = parser.add_subparsers(dest="domain", required=True, metavar="<domain>")
    stock.add_parser(sub)
    factor.add_parser(sub)
    experiment.add_parser(sub)
    qlib.add_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    func: Callable[[argparse.Namespace], int] | None = getattr(args, "func", None)
    if func is None:
        # argparse with required subparser shouldn't reach here, but guard anyway.
        parser.print_help()
        return 2

    return int(func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
