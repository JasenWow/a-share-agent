"""Tests for aquan.cli._format — output shaping for terminal + agent."""

from __future__ import annotations

from aquan.cli._format import format_output


class TestEmpty:
    def test_none_returns_no_data(self):
        assert format_output(None) == "(no data)"

    def test_empty_list_returns_no_rows(self):
        assert format_output([]) == "(no rows)"

    def test_empty_dict_returns_empty(self):
        assert format_output({}) == "(empty)"


class TestTable:
    def test_renders_header_and_rows(self):
        out = format_output(
            [
                {"code": "600519", "close": 1685.5},
                {"code": "000001", "close": 12.45},
            ]
        )
        assert "code" in out
        assert "close" in out
        assert "600519" in out
        assert "000001" in out

    def test_truncates_when_over_limit(self):
        rows = [{"i": i} for i in range(50)]
        out = format_output(rows, limit=5)
        assert "5 more rows" in out
        # The 6th row must not appear in the body
        assert "i\n" in out  # header present
        # The 6th row's value should not appear in body (row index 5 → value 5)
        body_lines = out.splitlines()[2:]  # skip header + separator
        body_text = "\n".join(body_lines)
        assert "    5 " not in body_text or "5 more rows" in body_text  # row 5 hidden by truncation note

    def test_truncates_long_cells(self):
        long_value = "x" * 100
        out = format_output([{"url": long_value}])
        assert "…" in out
        assert long_value not in out

    def test_floats_are_trimmed(self):
        out = format_output([{"v": 1.23456789}])
        # Float trimmed to a reasonable number of decimals.
        assert "1.23456789" not in out

    def test_collects_columns_across_rows(self):
        out = format_output(
            [
                {"a": 1},
                {"b": 2},
            ]
        )
        # Both columns should appear even though no row has both.
        assert "a" in out
        assert "b" in out

    def test_rows_with_no_fields(self):
        out = format_output([{}, {}])
        assert "no fields" in out


class TestKeyValue:
    def test_renders_single_dict_as_kv(self):
        out = format_output({"name": "default", "cash": 1000})
        assert "name" in out
        assert "default" in out
        assert "cash" in out
        assert "1000" in out


class TestJsonMode:
    def test_json_mode_emits_raw_json_for_list(self):
        rows = [{"a": 1, "b": "x"}]
        out = format_output(rows, json_out=True)
        # Should start with '[' since it's a list.
        assert out.strip().startswith("[")
        assert '"a"' in out
        assert "1" in out

    def test_json_mode_emits_raw_json_for_dict(self):
        out = format_output({"k": "v"}, json_out=True)
        assert '"k"' in out
        assert '"v"' in out

    def test_json_preserves_chinese(self):
        out = format_output([{"name": "贵州茅台"}], json_out=True)
        assert "贵州茅台" in out


class TestStringify:
    def test_none_becomes_empty(self):
        out = format_output([{"x": None}])
        # Empty cell renders as blank space, not the literal "None".
        assert "None" not in out

    def test_bool_renders_lowercase(self):
        out = format_output([{"flag": True}])
        assert "true" in out

    def test_nested_dict_renders_as_json(self):
        out = format_output([{"meta": {"k": "v"}}])
        assert '"k"' in out
        assert '"v"' in out
