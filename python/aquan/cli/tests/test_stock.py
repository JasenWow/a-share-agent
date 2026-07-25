"""Tests for ``aquan stock`` — action → MCP tool mapping + arg shaping."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from aquan.cli import stock
from aquan.cli._mcp_proxy import CliMcpError


def _parse(args: list[str]) -> argparse.Namespace:
    """Build a namespace the way `aquan stock ...` would after argparse."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="domain", required=True)
    stock.add_parser(sub)
    ns = parser.parse_args(["stock", *args])
    # argparse attaches func via set_defaults; mirror that for tests calling run() directly.
    ns.func = stock.run
    return ns


class TestActionMap:
    def test_every_action_has_a_mapping(self):
        # Sanity: the choices exposed to argparse match the action map exactly.
        assert set(stock.ACTION_MAP.keys()) == set(
            [
                "spot",
                "hist",
                "daily",
                "financial",
                "financial_report",
                "income",
                "balancesheet",
                "cashflow",
                "fina_indicator",
                "concept",
                "concept_detail",
                "index_cons",
                "index_weight",
                "index_daily",
                "northbound",
                "lhb",
                "health",
            ]
        )

    def test_each_mapping_has_three_tuple(self):
        for action, entry in stock.ACTION_MAP.items():
            assert len(entry) == 3, f"{action} entry must be (source, tool, param_map)"
            source, tool, param_map = entry
            assert source in {"akshare", "tushare"}, f"{action} has unknown source {source}"
            assert isinstance(tool, str) and tool, f"{action} missing tool name"
            assert isinstance(param_map, dict), f"{action} param_map must be dict"


class TestRunDispatch:
    @patch("aquan.cli.stock.mcp_call")
    def test_hist_maps_to_akshare_stock_zh_a_hist(self, mock_call):
        mock_call.return_value = [{"date": "2024-01-02", "close": 1685.5}]
        ns = _parse(["hist", "--code", "600519", "--start", "20240101"])
        rc = stock.run(ns)

        assert rc == 0
        mock_call.assert_called_once_with(
            "akshare",
            "stock_zh_a_hist",
            {"symbol": "600519", "start_date": "20240101"},
        )

    @patch("aquan.cli.stock.mcp_call")
    def test_daily_maps_to_tushare_daily_with_ts_code(self, mock_call):
        mock_call.return_value = []
        ns = _parse(["daily", "--code", "600519.SS", "--limit", "10"])
        stock.run(ns)

        # --code is translated to the tushare-specific ts_code param,
        # and --limit on the CLI maps to the tool's own limit (mcp-limit semantics).
        # Here we didn't pass --mcp-limit so the CLI limit only affects table display.
        mock_call.assert_called_once_with(
            "tushare",
            "daily",
            {"ts_code": "600519.SS"},
        )

    @patch("aquan.cli.stock.mcp_call")
    def test_mcp_limit_passes_through(self, mock_call):
        mock_call.return_value = []
        ns = _parse(["daily", "--code", "X", "--mcp-limit", "5"])
        stock.run(ns)

        mock_call.assert_called_once_with(
            "tushare",
            "daily",
            {"ts_code": "X", "limit": 5},
        )

    @patch("aquan.cli.stock.mcp_call")
    def test_health_takes_no_params(self, mock_call):
        mock_call.return_value = [{"status": "ok"}]
        ns = _parse(["health"])
        stock.run(ns)

        mock_call.assert_called_once_with("akshare", "data_source_health", {})

    @patch("aquan.cli.stock.mcp_call")
    def test_northbound_takes_no_params(self, mock_call):
        mock_call.return_value = [{"date": "2024-01-02", "net": 100}]
        ns = _parse(["northbound"])
        stock.run(ns)

        mock_call.assert_called_once_with("akshare", "stock_hsgt_north_net_flow_in_em", {})


class TestRunErrors:
    @patch("aquan.cli.stock.mcp_call")
    def test_mcp_error_returns_nonzero_and_prints_message(self, mock_call, capsys):
        mock_call.side_effect = CliMcpError("server unreachable")
        ns = _parse(["health"])
        rc = stock.run(ns)

        assert rc == 1
        captured = capsys.readouterr()
        assert "error" in captured.out.lower()
        assert "server unreachable" in captured.out

    def test_unknown_action_is_rejected_by_argparse(self):
        # argparse choices= handles this at parse time, not in run().
        with pytest.raises(SystemExit):
            _parse(["not_a_real_action"])


class TestTableOutput:
    @patch("aquan.cli.stock.mcp_call")
    def test_table_mode_default(self, mock_call, capsys):
        mock_call.return_value = [{"code": "600519", "name": "贵州茅台", "close": 1685.5}]
        ns = _parse(["spot", "--code", "600519"])
        stock.run(ns)

        out = capsys.readouterr().out
        assert "code" in out and "name" in out and "close" in out
        assert "贵州茅台" in out

    @patch("aquan.cli.stock.mcp_call")
    def test_json_mode_outputs_raw_json(self, mock_call, capsys):
        mock_call.return_value = [{"code": "600519"}]
        ns = _parse(["spot", "--code", "600519", "--json"])
        stock.run(ns)

        out = capsys.readouterr().out
        assert out.strip().startswith("[")
        assert '"code"' in out
