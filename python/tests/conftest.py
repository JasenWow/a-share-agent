"""Centralize sys.path setup so individual test files don't repeat it."""

import sys
from pathlib import Path

# python/tests/conftest.py -> repo_root (parents[2])
REPO_ROOT = Path(__file__).resolve().parents[2]
# 让 tests/ 可以 import scripts/ 下的模块（validate_*.py 等）
for sub in ["scripts"]:
    p = REPO_ROOT / sub
    if p.exists():
        sys.path.insert(0, str(p))
