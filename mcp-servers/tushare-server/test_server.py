import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestDfToJson:
    def test_empty_dataframe(self):
        from server import df_to_json

        assert df_to_json(pd.DataFrame()) == []

    def test_max_rows(self):
        from server import df_to_json

        df = pd.DataFrame({"a": range(100)})
        result = df_to_json(df, max_rows=10)
        assert len(result) == 10


class TestDailyMocked:
    @patch("server.pro.daily")
    def test_returns_list(self, mock_daily):
        mock_daily.return_value = pd.DataFrame(
            {"ts_code": ["000001.SZ", "600519.SH"], "close": [10.5, 1800.0]}
        )
        from server import daily

        result = daily(ts_code="000001.SZ")
        assert len(result) == 2

    @patch("server.pro.daily")
    def test_error_handling(self, mock_daily):
        mock_daily.side_effect = Exception("API error")
        from server import daily

        result = daily(ts_code="000001.SZ")
        assert "error" in result[0]
