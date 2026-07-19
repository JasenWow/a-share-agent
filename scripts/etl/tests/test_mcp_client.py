"""Tests for mcp_client. Mock HTTP layer."""
import json
from unittest.mock import patch, MagicMock

import pytest

from common import mcp_client
from common.mcp_client import call, health_check, McpError, get_last_params_hash


def _mock_response(payload, status=200):
    """构造 mock requests.Response。"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    if status < 400:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


def test_call_returns_result_list():
    """正常返回 result.content 里的数据。"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [{"type": "text", "text": json.dumps([{"code": "600519", "close": 1692.0}])}]
        },
    }
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        rows = call("tushare", "daily", {"trade_date": "20260717"})
    assert rows == [{"code": "600519", "close": 1692.0}]


def test_call_sets_params_hash():
    """调用后 get_last_params_hash 返回该次调用的 hash。"""
    payload = {
        "jsonrpc": "2.0", "id": "1",
        "result": {"content": [{"type": "text", "text": "[]"}]},
    }
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        call("tushare", "daily", {"trade_date": "20260717"})
    h = get_last_params_hash()
    assert len(h) == 64


def test_call_raises_on_mcp_error():
    """MCP 返回 error 字段时抛 McpError。"""
    payload = {"jsonrpc": "2.0", "id": "1",
               "error": {"code": -32602, "message": "invalid params"}}
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        with pytest.raises(McpError, match="invalid params"):
            call("tushare", "daily", {})


def test_call_returns_error_dict_from_tool():
    """工具内部错误（[{'error': ...}]）按原样返回（不抛异常，让上层 quality 判断）。"""
    error_text = json.dumps([{"error": "rate limited", "tool": "daily"}])
    payload = {"jsonrpc": "2.0", "id": "1",
               "result": {"content": [{"type": "text", "text": error_text}]}}
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        rows = call("tushare", "daily", {})
    assert rows == [{"error": "rate limited", "tool": "daily"}]


def test_call_retries_on_network_error():
    """网络错误重试 max_retries 次后抛 McpError。

    max_retries=3 → 3 次尝试（attempt 0/1/2），前 2 次失败后 sleep 再重试，
    第 3 次失败后直接抛错。所以 sleep 2 次。
    """
    with patch("common.mcp_client.requests.post",
               side_effect=ConnectionError("network down")):
        with patch("common.mcp_client.time.sleep") as mock_sleep:  # 加速测试
            with pytest.raises(McpError, match="network down"):
                call("tushare", "daily", {}, max_retries=3)
    assert mock_sleep.call_count == 2  # attempt 0 和 1 失败后 sleep，attempt 2 失败直接抛


def test_call_unknown_source_raises():
    """未知数据源立即抛错（不重试）。"""
    with pytest.raises(McpError, match="Unknown MCP source"):
        call("unknown_src", "any", {})


def test_health_check_ok():
    """health_check 成功返回 True。"""
    payload = {
        "jsonrpc": "2.0", "id": "1",
        "result": {"content": [{"type": "text", "text": json.dumps([{"status": "ok"}])}]},
    }
    with patch("common.mcp_client.requests.post", return_value=_mock_response(payload)):
        assert health_check("akshare") is True


def test_health_check_fail():
    """health_check 失败返回 False（不抛异常）。"""
    with patch("common.mcp_client.requests.post",
               side_effect=ConnectionError("down")):
        with patch("common.mcp_client.time.sleep"):
            assert health_check("akshare", max_retries=1) is False
