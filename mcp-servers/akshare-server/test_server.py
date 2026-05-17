import pytest
from unittest.mock import patch
import pandas as pd
from server import df_to_json, stock_zh_a_spot


class TestDfToJson:
    @pytest.mark.parametrize(
        "input_data,expected",
        [
            ({"a": [1, 2], "b": [3, 4]}, 2),
            ({"a": [float("nan")]}, 1),
            ({}, 0),
        ],
    )
    def test_row_count(self, input_data, expected):
        df = pd.DataFrame(input_data) if input_data else pd.DataFrame()
        result = df_to_json(df)
        assert len(result) == expected

    def test_max_rows_truncation(self):
        df = pd.DataFrame({"a": range(100)})
        result = df_to_json(df, max_rows=10)
        assert len(result) == 10

    def test_nan_to_string(self):
        df = pd.DataFrame({"a": [float("nan")]})
        result = df_to_json(df)
        assert result[0]["a"] == "NaN"


class TestStockZhASpotMocked:
    @patch("server.ak.stock_zh_a_spot_em")
    def test_returns_list_of_dicts(self, mock_func):
        mock_func.return_value = pd.DataFrame(
            {"代码": ["000001", "600519"], "名称": ["平安银行", "贵州茅台"], "最新价": [10.5, 1800.0]}
        )
        result = stock_zh_a_spot()
        assert len(result) == 2
        assert result[0]["代码"] == "000001"

    @patch("server.ak.stock_zh_a_spot_em")
    def test_filters_by_symbol(self, mock_func):
        mock_func.return_value = pd.DataFrame(
            {"代码": ["000001", "600519"], "名称": ["平安银行", "贵州茅台"]}
        )
        result = stock_zh_a_spot(symbol="600519")
        assert len(result) == 1
        assert result[0]["代码"] == "600519"

    @patch("server.ak.stock_zh_a_spot_em")
    def test_error_handling(self, mock_func):
        mock_func.side_effect = Exception("API error")
        result = stock_zh_a_spot()
        assert len(result) == 1
        assert "error" in result[0]


class TestStockBoardConceptCons:
    @patch("server.ak.stock_board_concept_cons_em")
    def test_returns_constituent_list(self, mock_func):
        mock_func.return_value = pd.DataFrame({
            "代码": ["000001", "600519"],
            "名称": ["平安银行", "贵州茅台"],
        })
        from server import stock_board_concept_cons
        result = stock_board_concept_cons(symbol="人工智能")
        assert len(result) == 2
        assert result[0]["代码"] == "000001"
