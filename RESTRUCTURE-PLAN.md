# Monorepo 重构计划

> **状态**: 进行中（Phase 0–6）
> **起点**: 2026-07-19
> **目标**: 把当前 Python-flat 项目重构为 TS 主体的 monorepo（命名空间 `aquan`）

---

## 1. 目标

把当前 Python-flat 项目重构为 TS 主体的 monorepo：

- **TS 主体**（Bun workspace，根 `packages/`）：`@aquan/{core, orchestrator, pi-runtime, server, web}`
- **Python 副体**（uv workspace，`python/`）：`aquan.{core, utils, metrics, cli}` 公共层 + `mcp-servers/` + `etl/` + `dbt/` 等
- **Legacy**：散件暂存
- **项目级工具**：根 `scripts/`

---

## 2. 终态结构

```
a-share-agents/
├── packages/                  ← Bun workspace（TS 主体）
│   ├── core/                  ← @aquan/core（合并自 shared + 加 work/types/utils）
│   ├── orchestrator/          ← @aquan/orchestrator（Symphony-like 编排引擎）
│   ├── pi-runtime/            ← @aquan/pi-runtime（Pi agent runtime 适配层）
│   ├── server/                ← @aquan/server（原 @chat-database/server）
│   └── web/                   ← @aquan/web（原 @chat-database/web）
│
├── python/                    ← uv workspace 根
│   ├── pyproject.toml
│   ├── aquan/                 ← 公共层根包
│   │   ├── core/              ← types / errors / config / contracts
│   │   ├── utils/             ← io / dates / http / logging / testing
│   │   ├── metrics/           ← 量化指标库（迁自原 metrics/）
│   │   └── cli/               ← `aquan etl *` 统一入口
│   ├── mcp-servers/           ← 4 个独立包（aquan-*-server）
│   ├── etl/                   ← 数据 ETL（迁自 scripts/etl/，改正规包）
│   ├── notebooks/
│   ├── dbt/
│   └── tests/                 ← 项目级集成测试
│
├── legacy/                    ← 散件暂存
├── scripts/                   ← 项目级 dev/CI 工具（check.py 等）
├── plugins/                   ← ZCode/Claude 插件（原位）
├── docs/
├── data/
├── package.json               ← Bun workspace 根
├── bunfig.toml / tsconfig.base.json / bun.lock / .dependency-cruiser.cjs
└── .mcp.json / .gitignore / AGENTS.md / ...
```

---

## 3. 关键决策

| 点 | 决定 |
|---|---|
| 命名空间 | `aquan`（Python: `aquan.*`，TS: `@aquan/*`）|
| shared 处理 | 合并到 `@aquan/core` |
| MCP servers 隔离 | 保持，不 import `aquan.core`（维持 R4 边界）|
| CLI 范围 | 仅 ETL（`aquan etl init/run/report`），check/validate 留根 `scripts/` |
| TS 编排层 | 拆 `orchestrator`（业务）+ `pi-runtime`（适配）两包 |
| 包重命名 | `@chat-database/*` → `@aquan/*` |

---

## 4. 执行阶段（7 个 Phase，每个一个 PR）

### Phase 0 — 骨架 + 文档 ✅

- 写 `RESTRUCTURE-PLAN.md`、`python/README.md`、`packages/README.md`、`legacy/README.md`
- 建空目录：`python/`、`packages/`、`legacy/`
- 写 `scripts/check_migration.py`（跑所有现有测试，记录 baseline）
- **守门**: 守门脚本在旧布局下基线测试全绿 ✅ (174 tests)

### Phase 1 — Python 骨架 + aquan 公共层 ✅

- 建 `python/pyproject.toml`（workspace 根，aquan.* 命名，Phase 1 最小依赖）
- 建 `python/aquan/{core,utils,metrics,cli}/` 骨架 + `__init__.py`
- 复制 `metrics/*` → `python/aquan/metrics/`（原位置保留，Phase 3 才切 import）
- 复制 `etl/common/mcp_client.py` → `python/aquan/utils/http.py`（用 `aquan.core.config`）
- 复制 `etl/common/parquet_writer.py` → `python/aquan/utils/io.py`
- 抽 `meta_fields.params_hash` → `python/aquan/utils/hashing.py`
- 新增 `python/aquan/{core/config,core/errors,utils/dates,utils/logging,cli/main}.py`
- 新增 `python/aquan/tests/test_smoke.py`（8 个骨架守门测试）
- **策略**: 复制 + re-export（原位置保持，Phase 3 迁 ETL 时才切 import）
- **守门**: `cd python && uv run pytest aquan/` 24 tests 全绿 ✅；根守门 174 全绿 ✅

### Phase 2 — 迁 4 个 MCP servers（每 server 一个 commit）

- `git mv mcp-servers/{akshare,tushare,internal,qlib}-server python/mcp-servers/`
- 各 `pyproject.toml` 改 `name = "aquan-*-server"`
- 清理 `prediction-store` drift；补 `qlib-server` 到 `[tool.uv.sources]`
- 更新 `scripts/check.py`：`ROOT/"mcp-servers"` → `ROOT/"python"/"mcp-servers"`
- **守门**: 各 server 的 test_server.py 绿；`scripts/check.py` 通过

### Phase 3 — 迁 ETL → `python/etl/`

- `git mv scripts/etl python/etl`
- 改正规包：加 `__init__.py`、内部 import 改 `from aquan.utils...` / `from etl.ods...`
- 删 `python/etl/tests/conftest.py` 的 sys.path hack
- 更新 `tests/conftest.py`（根）：移除 `scripts/etl` 注入
- 更新 `scripts/check.py`：warehouse 命令改为 `cd python && uv run python -m etl.init`
- **守门**: `cd python && uv run pytest etl/tests/` 13 文件全绿；warehouse init 能跑

### Phase 4 — 迁剩余 Python（notebooks/dbt/tests）

- `git mv notebooks python/notebooks`
- `git mv dbt python/dbt`（检查 `profiles.yml` 路径相对化）
- `git mv tests python/tests`（更新 `conftest.py` sys.path 注入路径）
- **守门**: 根守门脚本全绿

### Phase 5 — 扁平化 chat-database → `packages/`（最重 PR）

- `git mv chat-database/packages/{web,server,shared} packages/`
- `git mv chat-database/{bun.lock,tsconfig.base.json,.dependency-cruiser.cjs}` → 根
- `git mv chat-database/bunfig.toml packages/server/bunfig.toml`
- 合并 `chat-database/package.json` scripts 到根 `package.json`
- **建 `packages/core/`**：吸收 shared 内容 + 加 `src/{types,work,utils,schemas}/`、`errors.ts`、`constants.ts`
- **建 `packages/orchestrator/`** 骨架（用 memory tracker 跑通三态流转）
- **建 `packages/pi-runtime/`** 骨架（含 TODO，等 Pi SDK API 验证）
- 重命名 `@chat-database/{server,web}` → `@aquan/{server,web}`
- 全局替换 import：`@chat-database/shared` → `@aquan/core`
- 删除空 `chat-database/` 目录
- **守门**: `bun install` + `bun test` + `bun run build` + `bun run dep-check` 全绿；根守门脚本全绿

### Phase 6 — 清理 legacy + 文档收尾

- `legacy/scripts/validate_*.py` 加 deprecated 头注释
- 评估 `legacy/{managed-agent-cookbooks,openspec,skills-lock.json}` 去留
- 重写 `AGENTS.md`、`CONTRIBUTING.md`、`README.md`（反映新布局）
- 更新 `docs/draft/architecture.md`、`docs/draft/README.md` 路径引用
- 删 `scripts/check_migration.py`（完成使命）
- **守门**: `python scripts/check.py` 通过；`bun run dep-check` 通过；所有命令文档可执行

---

## 5. 工作目录约定

| 操作 | 命令前缀 |
|---|---|
| Python 测试 / uvicorn / ETL | `cd python && uv run ...` |
| TS 开发 / 构建 / db 迁移 | 根目录 `bun run ...` |
| 项目级边界检查 | 根目录 `python scripts/check.py` |
| dbt 命令 | `cd python/dbt && dbt ...` |

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| uv workspace 从根迁 python/ → `uv run` 需 `cd python/` | 文档显式说明；考虑 Makefile 包装 |
| ETL import 批量改容易出错 | Phase 3 单独 PR，跑全部 13 个 ETL 测试守门 |
| chat-database 内部 tsconfig extends 路径可能错 | Phase 5 逐个检查每个 `packages/*/tsconfig.json` |
| Pi SDK API 不确定 | `packages/pi-runtime/` Phase 5 只建骨架，等后续 spec 后填 |
| git mv 影响 history | 全程用 `git mv`，GitHub 自动追踪 |
| 新旧布局并存期 CI 混乱 | 每 Phase 独立 PR，CI 末尾必须绿才能进下一 Phase |

---

## 7. 不在本计划范围（out of scope）

- 新建 dashboard / agent-runtime 的业务功能（属 agent-orchestration-vision spec）
- 重写 `validate_*.py` E2E（Phase 6 仅 deprecated）
- 重新设计 `plugins/` 结构（保留原位）
- chat-database 功能演进（仅物理位置迁移）
- Pi SDK API 实际接入（Phase 5 仅骨架）

---

## 8. 进度

| Phase | 状态 | PR |
|---|---|---|
| 0 — 骨架 + 文档 | ✅ 完成 | 56d736f |
| 1 — Python 骨架 + aquan 公共层 | ✅ 完成 | (本 commit) |
| 2 — 迁 MCP servers | ⏳ 待开始 | — |
| 3 — 迁 ETL | ⏳ 待开始 | — |
| 4 — 迁 notebooks/dbt/tests | ⏳ 待开始 | — |
| 5 — 扁平化 chat-database + 建新包 | ⏳ 待开始 | — |
| 6 — 清理 legacy + 文档收尾 | ⏳ 待开始 | — |
