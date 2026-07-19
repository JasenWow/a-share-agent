"""Centralize sys.path setup so individual test files don't repeat it."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
# 让 tests/ 可以 import scripts/ 及 scripts/etl/ 下的模块
# （scripts/etl/tests/ 下的测试用 `from common.xxx import`，需要 scripts/etl 在 path 上）
for sub in ["scripts", "scripts/etl"]:
    p = ROOT / sub
    if p.exists():
        sys.path.insert(0, str(p))
