"""Tests for mcp_client. Mock HTTP layer (MCP streamable-http protocol)."""

import json
from unittest.mock import patch, MagicMock

import pytest

from common.mcp_client import (
    call,
    health_check,
    McpError,
    get_last_params_hash,
    reset_session,
)


def _sse(payload) -> str:
    """构造 SSE 流文本：'data: <json>\\n\\n'。"""
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


def _mock_response(
    payload=None,
    sse_text=None,
    status=200,
    session_id="test-session-123",
    raw_text=None,
):
    """构造 mock requests.Response。

    Args:
        payload:    要作为 SSE data 返回的 dict（与 sse_text 二选一）
        sse_text:   完整的 SSE 文本（与 payload 二选一）
        status:     HTTP 状态码
        session_id: 模拟 initialize 响应头里的 mcp-session-id
        raw_text:   直接指定 resp.text（与 payload/sse_text 互斥）
    """
    resp = MagicMock()
    resp.status_code = status
    if status < 400:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")

    # headers 字段（供 _ensure_session 读 mcp-session-id）
    resp.headers = {"mcp-session-id": session_id} if session_id else {}

    if raw_text is not None:
        resp.text = raw_text
    elif sse_text is not None:
        resp.text = sse_text
    elif payload is not None:
        resp.text = _sse(payload)
    else:
        resp.text = _sse({})
    return resp


def _mock_post_sequence(*responses):
    """构造 side_effect：按顺序返回多个 response（模拟 initialize → notif → call）。"""
    return responses


def test_call_returns_result_list():
    """正常返回 result.content 里的数据（经过 SSE 解析）。"""
    # 调用链：initialize → notif → tools/call（3 次 POST）
    init_resp = _mock_response(
        payload={"jsonrpc": "2.0", "id": "1", "result": {"capabilities": {}}}
    )
    notif_resp = _mock_response(payload=None, raw_text="")
    call_resp = _mock_response(
        payload={
            "jsonrpc": "2.0",
            "id": "2",
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps([{"code": "600519", "close": 1692.0}])}
                ]
            },
        }
    )
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[init_resp, notif_resp, call_resp],
    ):
        reset_session("tushare")
        rows = call("tushare", "daily", {"trade_date": "20260717"})
    assert rows == [{"code": "600519", "close": 1692.0}]


def test_call_sets_params_hash():
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {"content": [{"type": "text", "text": "[]"}]},
    }
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("tushare")
        call("tushare", "daily", {"trade_date": "20260717"})
    h = get_last_params_hash()
    assert len(h) == 64


def test_call_raises_on_mcp_error():
    """MCP 返回 error 字段时抛 McpError。"""
    payload = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32602, "message": "invalid params"}}
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("tushare")
        with pytest.raises(McpError, match="invalid params"):
            call("tushare", "daily", {})


def test_call_returns_error_dict_from_tool():
    """工具内部错误 [{'error': ...}] 原样返回（不抛异常，让上层 quality 判断）。"""
    error_text = json.dumps([{"error": "rate limited", "tool": "daily"}])
    payload = {"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": error_text}]}}
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("tushare")
        rows = call("tushare", "daily", {})
    assert rows == [{"error": "rate limited", "tool": "daily"}]


def test_call_retries_on_network_error():
    """网络错误重试 max_retries 次后抛 McpError。

    每次重试会重做 initialize 握手（session 失败也走重试）。
    max_retries=3 → 3 次尝试，前 2 次失败后 sleep，第 3 次失败直接抛。
    sleep 2 次。
    """
    with patch("common.mcp_client.requests.post", side_effect=ConnectionError("network down")):
        with patch("common.mcp_client.time.sleep") as mock_sleep:
            reset_session("tushare")
            with pytest.raises(McpError, match="network down"):
                call("tushare", "daily", {}, max_retries=3)
    assert mock_sleep.call_count == 2


def test_call_unknown_source_raises():
    """未知数据源立即抛错（不重试）。"""
    with pytest.raises(McpError, match="Unknown MCP source"):
        call("unknown_src", "any", {})


def test_call_handles_multi_chunk_content():
    """internal-store 每行一个 JSON text，content 多段要全部合并。"""
    chunk1 = json.dumps({"id": 1, "name": "exp1"})
    chunk2 = json.dumps({"id": 2, "name": "exp2"})
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "content": [
                {"type": "text", "text": chunk1},
                {"type": "text", "text": chunk2},
            ]
        },
    }
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("internal-store")
        rows = call("internal-store", "list_experiments", {})
    assert len(rows) == 2
    assert rows[0]["name"] == "exp1"
    assert rows[1]["name"] == "exp2"


def test_health_check_ok():
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {"content": [{"type": "text", "text": json.dumps([{"status": "ok"}])}]},
    }
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("akshare")
        assert health_check("akshare") is True


def test_health_check_fail():
    with patch("common.mcp_client.requests.post", side_effect=ConnectionError("down")):
        with patch("common.mcp_client.time.sleep"):
            reset_session("akshare")
            assert health_check("akshare", max_retries=1) is False


def test_session_cached_across_calls():
    """同一 source 的 session 握手只做一次，后续直接复用。"""
    payload = {"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": "[]"}]}}
    responses = [
        _mock_response(payload={"jsonrpc": "2.0", "id": "i", "result": {}}),  # init
        _mock_response(raw_text=""),  # notif
        _mock_response(payload=payload),  # call 1
        # 第二次 call 不应该再有 init/notif
        _mock_response(payload=payload),  # call 2
    ]
    with patch("common.mcp_client.requests.post", side_effect=responses) as mock_post:
        reset_session("tushare")
        call("tushare", "daily", {})
        call("tushare", "daily", {})
    # 第二次只多了 1 次 POST（session 复用，不重做握手）
    assert mock_post.call_count == 4


def test_session_reset_clears_cache():
    """reset_session 后下次 call 会重新握手。"""
    payload = {"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": "[]"}]}}
    with patch(
        "common.mcp_client.requests.post",
        side_effect=[
            _mock_response(payload={"jsonrpc": "2.0", "id": "i1", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
            _mock_response(payload={"jsonrpc": "2.0", "id": "i2", "result": {}}),
            _mock_response(raw_text=""),
            _mock_response(payload=payload),
        ],
    ):
        reset_session("tushare")
        call("tushare", "daily", {})
        reset_session("tushare")  # 清缓存
        call("tushare", "daily", {})  # 应重新握手
