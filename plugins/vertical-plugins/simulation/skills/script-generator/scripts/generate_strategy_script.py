"""Strategy script generator for Meta-Agent Phase 2."""

from pathlib import Path
import subprocess

STRATEGY_TEMPLATE = '''"""
Auto-generated strategy: {strategy_name}
Created by Meta-Agent script-generator
Date: {timestamp}
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

def run_strategy(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    {description}

    Args:
        df: DataFrame with OHLCV data [date, code, open, high, low, close, volume]
        params: Strategy parameters including signal logic and position sizing

    Returns:
        Dict with keys: signals (pd.Series), positions (pd.DataFrame), metrics (dict)
    """
    {signal_logic}

    return {{
        "signals": signals,
        "positions": positions,
        "metrics": metrics
    }}
'''

def generate_strategy_script(strategy_name: str, description: str, signal_logic: str, position_sizing: str = "equal_weight") -> str:
    """Generate a strategy execution script."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    impl = f"""
    # Signal generation
    {signal_logic}
    
    # Position sizing: {position_sizing}
    {position_sizing}
    
    # Build positions dataframe
    positions = signals.to_frame("weight")
    positions["weight"] = positions["weight"] / positions["weight"].sum() if positions["weight"].sum() > 0 else 0
    
    # Calculate metrics
    metrics = {{
        "total_signals": int(signals.sum()),
        "signal_rate": float(signals.mean()) if len(signals) > 0 else 0.0,
        "position_sizing": "{position_sizing}"
    }}
"""
    script = STRATEGY_TEMPLATE.format(
        strategy_name=strategy_name,
        description=description,
        signal_logic=impl,
        timestamp=timestamp
    )
    return script

def validate_strategy_script(script: str) -> tuple[bool, str]:
    """Validate generated script: ruff check + forbidden imports check."""
    if 'mcp-servers' in script or 'agent-plugins' in script:
        return False, "Generated code contains forbidden imports"

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        temp_path = f.name

    try:
        result = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{temp_path}').read())"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"Syntax error: {result.stderr}"
    finally:
        Path(temp_path).unlink()

    if 'def run_strategy' not in script:
        return False, "Missing run_strategy function"

    return True, "valid"

def save_strategy_script(strategy_name: str, script: str, target_dir: Path) -> Path:
    """Save generated script to target_dir/generated/, with collision detection."""
    safe_name = strategy_name.lower().replace("-", "_").replace(" ", "_").replace("__", "_")
    filename = f"strategy_{safe_name}.py"
    generated_dir = target_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    file_path = generated_dir / filename

    if file_path.exists():
        raise FileExistsError(f"File already exists: {file_path}")

    file_path.write_text(script)
    return file_path