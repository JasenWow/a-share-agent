"""Stable hashing for dicts (used by MCP params_hash, caching keys, etc.).

Provides order-independent sha256 over JSON-serializable dicts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def params_hash(params: dict[str, Any]) -> str:
    """Stable sha256 of a params dict (keys sorted, order-independent).

    Uses default=str to handle non-JSON-native types (datetime, Path, etc.).
    """
    canonical = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
