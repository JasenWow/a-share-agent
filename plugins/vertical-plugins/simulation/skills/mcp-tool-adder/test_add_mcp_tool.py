import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

class TestMCPToolAdder:
    def test_domain_keywords_rejected(self):
        from add_mcp_tool import validate_tool_code
        valid, reason = validate_tool_code("def backtest_strategy(): pass")
        assert valid == False
        assert "backtest" in reason.lower()

    def test_tool_name_collision_detected(self):
        from add_mcp_tool import add_tool_to_server
        result = add_tool_to_server("internal-store", "list_cache", "limit: int", "List cache", "ak.new_function()")
        assert result == False

    def test_only_internal_store_allowed(self):
        from add_mcp_tool import add_tool_to_server
        result = add_tool_to_server("akshare", "new_tool", "", "desc", "ak.get_data()")
        assert result == False

    def test_validate_tool_code_function_exists(self):
        from add_mcp_tool import validate_tool_code
        assert callable(validate_tool_code)

    def test_add_tool_to_server_function_exists(self):
        from add_mcp_tool import add_tool_to_server
        assert callable(add_tool_to_server)

    def test_update_server_readme_function_exists(self):
        from add_mcp_tool import update_server_readme
        assert callable(update_server_readme)

    def test_invalid_server_rejected(self):
        from add_mcp_tool import add_tool_to_server
        result = add_tool_to_server("nonexistent-server", "tool", "", "desc", "x")
        assert result == False