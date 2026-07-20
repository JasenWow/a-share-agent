"""aquan.utils — pure utilities (no domain knowledge).

Utilities may depend on aquan.core (for config/errors) but must not depend
on domain packages (etl, mcp-servers). They are safe to import from anywhere.
"""

__all__: list[str] = []
