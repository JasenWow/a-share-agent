"""aquan error hierarchy.

All aquan-specific exceptions derive from AquanError so callers can catch
the entire family with a single except clause. Subclasses live with the
code that raises them; only the base is defined here.
"""

from __future__ import annotations


class AquanError(Exception):
    """Base for all aquan-specific errors."""
