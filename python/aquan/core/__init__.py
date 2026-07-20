"""aquan.core — domain core: types, errors, config, contracts.

This package holds the shared vocabulary of the system. It must have zero
dependencies on other aquan subpackages or domain packages (etl, mcp-servers).
Dependencies flow inward: everything may depend on core, core depends on
nothing internal.
"""

from aquan.core.config import (
    DATA_ROOT,
    ROOT,
    WAREHOUSE_ROOT,
)
from aquan.core.errors import AquanError

__all__ = [
    "AquanError",
    "DATA_ROOT",
    "ROOT",
    "WAREHOUSE_ROOT",
]
