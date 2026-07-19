"""ETL tests 的 pytest 配置。

让 scripts/etl/tests/ 下的测试可以用 `from common.xxx import` 和
`from ods.xxx import`：把 scripts/etl/ 加到 sys.path。
"""

import sys
from pathlib import Path

# scripts/etl/tests/conftest.py → scripts/etl/
ETL_ROOT = Path(__file__).resolve().parent.parent
if str(ETL_ROOT) not in sys.path:
    sys.path.insert(0, str(ETL_ROOT))
