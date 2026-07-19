"""Centralize sys.path setup so individual test files don't repeat it."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
# 让 tests/ 可以 import scripts/ 下的模块
scripts_dir = ROOT / "scripts"
if scripts_dir.exists():
    sys.path.insert(0, str(scripts_dir))
