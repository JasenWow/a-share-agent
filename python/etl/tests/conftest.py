"""ETL test configuration.

Pre-restructure this file injected scripts/etl/ onto sys.path so tests
could use bare `from common.x` / `from ods.x` imports. That hack is no
longer needed: etl and aquan are installed packages now, and tests use
proper `from etl.x` / `from aquan.utils.x` imports.

Kept as a placeholder for future shared fixtures.
"""
