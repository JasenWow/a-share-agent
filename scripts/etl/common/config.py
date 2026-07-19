"""ETL 配置：仓库路径、MCP 端点。从 .env 读取，提供合理默认值。"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（scripts/etl/common/config.py 往上 4 级）
ROOT = Path(__file__).resolve().parents[3]

# 数据根目录（与 internal-store 的 DATA_ROOT 复用同一环境变量）
DATA_ROOT = Path(os.environ.get("DATA_ROOT", str(ROOT / "data")))

# 数仓根目录
WAREHOUSE_ROOT = DATA_ROOT / "warehouse"
ODS_ROOT = WAREHOUSE_ROOT / "ods"
META_DB_PATH = WAREHOUSE_ROOT / "meta.db"
LOGS_DIR = WAREHOUSE_ROOT / "_logs"

# MCP server 端点（端口可从环境变量覆盖，与 .env.example 一致）
AKSHARE_PORT = os.environ.get("AKSHARE_PORT", "8000")
TUSHARE_PORT = os.environ.get("TUSHARE_PORT", "8001")
INTERNAL_STORE_PORT = os.environ.get("INTERNAL_STORE_PORT", "8002")

MCP_AKSHARE_URL = f"http://localhost:{AKSHARE_PORT}/mcp"
MCP_TUSHARE_URL = f"http://localhost:{TUSHARE_PORT}/mcp"
MCP_INTERNAL_STORE_URL = f"http://localhost:{INTERNAL_STORE_PORT}/mcp"


def ensure_dirs() -> None:
    """确保数仓目录结构存在。"""
    WAREHOUSE_ROOT.mkdir(parents=True, exist_ok=True)
    ODS_ROOT.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
