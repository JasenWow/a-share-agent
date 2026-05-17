"""Factor script generator for Meta-Agent Phase 2."""

from pathlib import Path
import subprocess

FACTOR_TEMPLATE = '''"""
Auto-generated factor: {factor_name}
Created by Meta-Agent script-generator
Date: {timestamp}
"""

import pandas as pd
import numpy as np

def compute_{func_name}(df: pd.DataFrame, **params) -> pd.Series:
    """
    {description}

    Args:
        df: DataFrame with columns [date, code, open, high, low, close, volume, ...]
        **params: factor-specific parameters

    Returns:
        pd.Series with index (date, code) and factor values
    """
    {implementation}

    return result
'''

def generate_factor_script(factor_name: str, description: str, implementation: str) -> str:
    """Generate a factor computation script."""
    func_name = factor_name.lower().replace("-", "_").replace(" ", "_").replace("__", "_")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    script = FACTOR_TEMPLATE.format(
        factor_name=factor_name,
        func_name=func_name,
        description=description,
        implementation=implementation,
        timestamp=timestamp
    )
    return script

def validate_factor_script(script: str) -> tuple[bool, str]:
    """Validate generated script: ruff check + forbidden imports check."""
    # Check for forbidden imports
    if 'mcp-servers' in script or 'agent-plugins' in script:
        return False, "Generated code contains forbidden imports (mcp-servers/agent-plugins)"

    # Syntax check via ruff
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        temp_path = f.name

    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", temp_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"Ruff check failed: {result.stdout}"
    finally:
        Path(temp_path).unlink()

    # Naming check
    if 'def compute_' not in script:
        return False, "Missing compute_* function"

    return True, "valid"

def save_factor_script(factor_name: str, script: str, target_dir: Path) -> Path:
    """Save generated script to target_dir/generated/, with collision detection."""
    func_name = factor_name.lower().replace("-", "_").replace(" ", "_").replace("__", "_")
    filename = f"compute_{func_name}.py"
    generated_dir = target_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    file_path = generated_dir / filename

    if file_path.exists():
        raise FileExistsError(f"File already exists: {file_path}")

    file_path.write_text(script)
    return file_path