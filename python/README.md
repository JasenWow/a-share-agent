# python/

uv workspace — Python data layer of the aquan monorepo.

## Layout

| Path | What |
|---|---|
| `pyproject.toml` | uv workspace root + shared dev deps (pytest, ruff) |
| `aquan/` | public layer: `core/` (config, errors, types), `utils/` (io, http, hashing, dates, logging), `metrics/` (quant metric catalog), `cli/` (`aquan` entry) |
| `mcp-servers/` | 4 L0 MCP connectors, each a workspace member: `aquan-{akshare,tushare,internal-store,qlib}-server` |
| `etl/` | DuckDB + Parquet ETL pipeline (catalog, jobs, quality, ods/* loaders) |
| `notebooks/` | Jupyter notebooks + helpers |
| `dbt/` | dbt-duckdb warehouse models (staging / dwd / dws / ads) |
| `tests/` | project-level integration tests |

## Commands (from this directory)

```bash
uv sync                                 # install aquan + etl + dev deps
uv run pytest                           # full Python test suite
uv run pytest aquan/                    # only the public layer
uv run pytest etl/tests/                # only ETL
uv run pytest --package aquan-akshare-server  # MCP server (own deps)
uv run ruff check . && uv run ruff format .   # lint + format

# Start MCP servers (each in its own terminal):
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# ETL pipeline:
uv run python -m etl.init               # one-time warehouse bootstrap
uv run python -m etl.runner equity_daily --date 20260717

# CLI entry (Phase 1 skeleton, ETL subcommands arrive later):
uv run python -m aquan.cli --version
```

## Imports

The public namespace is `aquan.*`:

```python
from aquan.core.config import WAREHOUSE_ROOT, MCP_AKSHARE_URL
from aquan.core.errors import AquanError
from aquan.utils.http import call as mcp_call          # MCP HTTP client
from aquan.utils.io import write as write_parquet      # idempotent Parquet writer
from aquan.utils.hashing import params_hash
from aquan.metrics import compile_query, list_metrics
```

`etl` is a flat top-level package:

```python
from etl.config import ODS_ROOT, META_DB_PATH, ensure_dirs
from etl.catalog import register, init_catalog
from etl.jobs import init_jobs_table
from etl.quality import run_checks, min_row_count
from etl.meta_fields import inject
from etl.ods.equity_daily import run as run_equity_daily
```

MCP servers stay **isolated** — they must not import `aquan.*` or `etl.*` (R1/R4 boundary rules, enforced by `scripts/check.py` at the repo root).
