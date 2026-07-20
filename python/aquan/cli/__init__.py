"""aquan.cli — command-line entry point.

Phase 1: skeleton only. The `aquan` command currently has just `--version`.
Phase 3 adds `aquan etl init|run|report` subcommands.
Phase 5 adds `aquan check` / `aquan validate` (optional).
"""

from aquan.cli.main import main

__all__ = ["main"]
