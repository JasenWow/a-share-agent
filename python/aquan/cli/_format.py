"""Output formatting for the aquan CLI.

The CLI surfaces MCP tool results to two audiences:
- humans glancing at terminal output
- the LLM agent (via the pi-runtime cli-tools)

Both benefit from compact, scannable text rather than raw JSON. This
module turns the canonical MCP shape (list[dict]) into a fixed-width
table by default, and falls back to JSON via the --json flag.

Design goals:
- keep total output small (token-efficient for the agent)
- truncate long cells (URLs, big numbers, text blobs)
- cap row count by default (override with --limit)
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_ROW_LIMIT = 20
MAX_CELL_WIDTH = 40


def format_output(
    rows: list[dict] | dict | None,
    *,
    json_out: bool = False,
    limit: int = DEFAULT_ROW_LIMIT,
) -> str:
    """Format MCP tool output for terminal/agent display.

    Args:
        rows:      MCP tool result (list of dicts, single dict, or None).
        json_out:  if True, emit compact JSON instead of a table.
        limit:     max rows to show in table mode (JSON mode is uncapped).

    Returns:
        A string ready to print. Always returns a string (never raises).
    """
    if rows is None:
        return "(no data)"

    if isinstance(rows, dict):
        # Single-record tools (e.g. get_portfolio): show as two-column key/value.
        if json_out:
            return _json(rows)
        return _kv_table(rows)

    if not isinstance(rows, list):
        # Unexpected shape — best-effort JSON so the caller sees something.
        return _json(rows)

    if not rows:
        return "(no rows)"

    if json_out:
        return _json(rows)

    return _table(rows, limit=limit)


def _table(rows: list[dict], *, limit: int) -> str:
    """Render list[dict] as a fixed-width table with header + truncated cells."""
    capped = rows[:limit] if limit > 0 else rows
    truncated_note = ""
    if limit > 0 and len(rows) > limit:
        truncated_note = f"\n({len(rows) - limit} more rows, raise --limit to see)"

    # Collect column names from all rows (preserving first-seen order).
    cols: list[str] = []
    seen: set[str] = set()
    for row in capped:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                cols.append(key)

    if not cols:
        return "(rows have no fields)"

    # Compute column widths (header text vs cell content).
    widths: dict[str, int] = {c: len(c) for c in cols}
    rendered_cells: list[dict[str, str]] = []
    for row in capped:
        rendered: dict[str, str] = {}
        for col in cols:
            text = _stringify(row.get(col))
            if len(text) > MAX_CELL_WIDTH:
                text = text[: MAX_CELL_WIDTH - 1] + "…"
            rendered[col] = text
            widths[col] = max(widths[col], len(text))
        rendered_cells.append(rendered)

    # Build lines: "col1   col2   col3"  (two-space gutters).
    def fmt_row(values: dict[str, str]) -> str:
        return "  ".join(values[c].ljust(widths[c]) for c in cols).rstrip()

    header = fmt_row({c: c for c in cols})
    separator = "  ".join("-" * widths[c] for c in cols)
    body = "\n".join(fmt_row(r) for r in rendered_cells)
    return f"{header}\n{separator}\n{body}{truncated_note}"


def _kv_table(row: dict) -> str:
    """Render a single dict as a two-column key/value table."""
    if not row:
        return "(empty)"
    items = list(row.items())
    key_w = max(len(str(k)) for k, _ in items)
    lines = []
    for k, v in items:
        text = _stringify(v)
        if len(text) > MAX_CELL_WIDTH:
            text = text[: MAX_CELL_WIDTH - 1] + "…"
        lines.append(f"{str(k).ljust(key_w)}  {text}")
    return "\n".join(lines)


def _json(value: Any) -> str:
    """Compact JSON (ASCII forced off so Chinese characters render correctly)."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _stringify(value: Any) -> str:
    """Best-effort conversion of any cell value to a short display string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        # Trim long floats but keep ints readable.
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".") or "0"
        return str(value)
    if isinstance(value, str):
        return value
    # dicts/lists → compact JSON
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)
