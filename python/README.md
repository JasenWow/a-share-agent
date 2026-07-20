# python/

Python 副体（uv workspace 根）。重构完成后本目录包含全部 Python 代码。

## 状态

🚧 **建设中** — 见根目录 `RESTRUCTURE-PLAN.md`

当前为空目录。Phase 1 开始填充：

- `pyproject.toml` — uv workspace 根
- `aquan/` — 公共层（core / utils / metrics / cli）
- `mcp-servers/` — 4 个 L0 connectors（Phase 2 迁入）
- `etl/` — 数据 ETL（Phase 3 迁入）
- `notebooks/` `dbt/` `tests/`（Phase 4 迁入）

## 命令约定（迁移完成后）

```bash
cd python
uv sync
uv run pytest
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
uv run python -m etl.init
```
