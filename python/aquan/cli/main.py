"""`aquan` command-line entry point.

Phase 1: only `--version`. Real subcommands (`etl`, `check`, `validate`)
are added in later phases as the underlying code migrates in.
"""

from __future__ import annotations

import argparse
import sys

from aquan import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aquan",
        description="aquan — A-share quantitative analysis toolkit",
    )
    parser.add_argument("--version", action="version", version=f"aquan {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
