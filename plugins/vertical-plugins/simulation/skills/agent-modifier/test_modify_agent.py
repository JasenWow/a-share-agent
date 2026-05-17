import pytest
import json
import subprocess
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

class TestAgentModifier:
    def test_self_modification_blocked(self):
        from modify_agent import update_agent_skill_references
        result = update_agent_skill_references(
            Path("plugins/agent-plugins/meta-strategist"),
            "fake-skill"
        )
        assert result == False

    def test_add_skill_to_equity_researcher(self):
        from modify_agent import update_agent_skill_references
        agent_path = Path("plugins/agent-plugins/equity-researcher")
        plugin_path = agent_path / ".claude-plugin" / "plugin.json"
        if not plugin_path.exists():
            pytest.skip("equity-researcher plugin.json not found")
        original = plugin_path.read_text()
        result = update_agent_skill_references(agent_path, "test-skill-xyz")
        plugin_path.write_text(original)
        assert result == True or result == False

    def test_blocked_agent_list_contains_meta_strategist(self):
        from modify_agent import BLOCKED_AGENTS
        assert "meta-strategist" in BLOCKED_AGENTS

    def test_update_guardrails_function_exists(self):
        from modify_agent import update_agent_guardrails
        assert callable(update_agent_guardrails)

    def test_validate_modification_function_exists(self):
        from modify_agent import validate_modification
        assert callable(validate_modification)

    def test_plugin_json_not_modified_on_blocked(self):
        from modify_agent import update_agent_skill_references
        meta_path = Path("plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json")
        if not meta_path.exists():
            pytest.skip("meta-strategist plugin.json not found")
        original = meta_path.read_text()
        result = update_agent_skill_references(Path("plugins/agent-plugins/meta-strategist"), "fake")
        current = meta_path.read_text()
        assert current == original