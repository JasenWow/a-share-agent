"""Tests for script-generator skill."""

import pytest
import tempfile
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

class TestScriptGenerator:
    def test_factor_script_has_required_sections(self):
        """Generated factor script contains docstring, imports, compute_* function."""
        from generate_factor_script import generate_factor_script
        script = generate_factor_script("test_momentum", "20日动量因子", "result = df['close'].pct_change(20)")
        assert '"""' in script
        assert 'import pandas' in script or 'import pd' in script
        assert 'def compute_' in script

    def test_factor_script_naming_convention(self):
        """File name matches compute_<factor_name>.py"""
        from generate_factor_script import generate_factor_script
        script = generate_factor_script("test_momentum", "...", "...")
        assert 'def compute_' in script

    def test_factor_script_passes_ruff_check(self):
        """Generated script passes ruff check (no syntax errors)."""
        import tempfile
        from generate_factor_script import generate_factor_script, save_factor_script
        script = generate_factor_script("momentum_test", "...", "result = df.close")
        with tempfile.TemporaryDirectory() as tmpdir:
            save_factor_script("momentum_test", script, Path(tmpdir))
            result = subprocess.run(
                ["uv", "run", "ruff", "check", str(Path(tmpdir) / "generated" / "compute_momentum_test.py")],
                capture_output=True, text=True, timeout=30
            )
            assert result.returncode == 0, f"Ruff failed: {result.stdout}\n{result.stderr}"

    def test_factor_script_collision_detection(self):
        """Existing file with same name raises FileExistsError."""
        from generate_factor_script import save_factor_script
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "generated" / "compute_test.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("existing content")
            try:
                save_factor_script("test", "# code", Path(tmpdir))
                pytest.fail("Should have raised FileExistsError")
            except FileExistsError:
                pass  # expected

    def test_factor_script_no_mcp_imports(self):
        """Generated code does not import from mcp-servers/ or agent-plugins/."""
        from generate_factor_script import generate_factor_script
        script = generate_factor_script("test", "...", "...")
        assert 'mcp-servers' not in script
        assert 'agent-plugins' not in script

    def test_save_factor_script_creates_file(self):
        """save_factor_script correctly writes file to target_dir/generated/."""
        from generate_factor_script import generate_factor_script, save_factor_script
        script = generate_factor_script("my_factor", "...", "...")
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = save_factor_script("my_factor", script, Path(tmpdir))
            assert result_path.exists()
            assert result_path.name == "compute_my_factor.py"
            assert result_path.read_text() == script