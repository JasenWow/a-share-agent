"""Centralize sys.path setup so individual test files don't repeat it."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
# 让 tests/ 可以 import scripts/ 下的模块
#（scripts/etl/ 已于 Phase 3 迁到 python/etl/，不再需要 sys.path 注入）
for sub in ["scripts"]:
    p = ROOT / sub
    if p.exists():
        sys.path.insert(0, str(p))
