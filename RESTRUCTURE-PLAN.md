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

### Phase 2 — 迁 4 个 MCP servers（每 server 一个 commit）✅

- `git mv mcp-servers/{akshare,tushare,internal,qlib}-server python/mcp-servers/`（一次性 mv，避免半状态）
- 各 `pyproject.toml` 改 `name = "aquan-*-server"`
- 顺手修 `tushare-server` 和 `internal-store` 缺失的 `[tool.setuptools.packages.find] exclude`（tushare 的 editable install 失败根因之一）
- 清理 `prediction-store` drift（根 pyproject 不再引用它）
- `python/pyproject.toml` 加入 4 个 MCP servers 为 workspace members + sources
- `qlib-server` 补进 `[tool.uv.sources]`
- 更新 `scripts/check.py`：`ROOT/"mcp-servers"` → `ROOT/"python"/"mcp-servers"`
- 升级 `scripts/check_migration.py`：新增 `runner` 模式（root / package / py-aquan），MCP server 测试用 `uv run --package <pkg> pytest` 在 python/ 跑
- **守门**: 全部 8 suites 198 tests 全绿（174 baseline + 24 aquan 新增）；tushare tolerated（仅剩 TUSHARE_TOKEN，editable install 已修）

### Phase 3 — 迁 ETL → `python/etl/` ✅

- `git mv scripts/etl python/etl`
- **扁平化 common/**：catalog/jobs/quality/meta_fields 提到 `etl/` 顶层；mcp_client/parquet_writer/config 删除（已在 aquan）；`common/` 目录消失
- 新建 `etl/config.py`：ETL 特定路径派生（ODS_ROOT/META_DB_PATH/LOGS_DIR），委托 `aquan.core.config`
- **批量改 import**（22 个文件）：
  - `from common.mcp_client` → `from aquan.utils.http`
  - `from common.parquet_writer` → `from aquan.utils.io`
  - `from common.meta_fields import params_hash` → `from aquan.utils.hashing`
  - `from common.{catalog,jobs,quality,config}` → `from etl.{catalog,jobs,quality,config}`
  - `from ods.X` → `from etl.ods.X`
  - patch 字符串 `"common.mcp_client.X"` → `"aquan.utils.http.X"`、`"ods.X"` → `"etl.ods.X"`
- 删 sys.path hack：`etl/tests/conftest.py`、`etl/{init,runner,report}.py` 全部去掉 `_ETL_ROOT` 注入
- 重写 `etl/tests/test_config.py` 匹配新分层（WAREHOUSE_ROOT/MCP URLs 从 aquan.core，ODS_ROOT 从 etl.config）
- 更新 `python/pyproject.toml`：加 duckdb 依赖、`etl` 进 hatch packages
- 更新 `scripts/check_migration.py`：etl suite 从 `root` 模式改为 `py-aquan` 模式（路径 `etl/tests`）
- 更新 `scripts/check.py`：warehouse 命令提示改为 `cd python && uv run python -m etl.init`
- 更新根 `tests/conftest.py`：移除 `scripts/etl` sys.path 注入
- **守门**: `cd python && uv run pytest etl/tests/` **104 passed**（比 baseline 103 多 1，因 test_config 加了新测试）；总 **199 tests passed** across 8 suites

### Phase 4 — 迁剩余 Python（notebooks/dbt/tests）✅

- `git mv notebooks python/notebooks`
- `git mv dbt python/dbt`（`profiles.yml` 路径 `../data/...` → `../../data/...`）
- `git mv tests python/tests`（`conftest.py` ROOT 改 `parents[2]`；`test_stock_pool_scorecard.py` plugins 路径多 parent 一次）
- `python/notebooks/test_helpers.py` 改用 `from notebooks.helpers import`（删 sys.path hack）
- `python/pyproject.toml`：`notebooks` 进 hatch packages；ruff 排除 `*.ipynb`
- **清理冗余**: 删除原根 `metrics/` 目录（Phase 1 复制后无外部消费者；plugins 里的 `from metrics import` 是同目录引用，与根 metrics/ 包无关）
- `scripts/check_migration.py`：所有 Python suite 迁移到 `py-aquan` runner；`aquan-smoke-and-metrics` 拆为 `metrics`（aquan/metrics/tests）+ `aquan-smoke`（aquan/tests）
- **守门**: 重新记录 baseline = 183 tests（Phase 1 复制策略导致的 metrics 双份计数现已去重）；全部 8 suites 绿
- **dbt 验证**: `dbt parse --project-dir dbt --profiles-dir dbt` 成功

### Phase 5 — 扁平化 chat-database → `packages/`（最重 PR）✅

**清理根目录**：
- `git mv openspec legacy/openspec-content`（移走历史 openspec 工具）
- `git mv package.json legacy/openspec-package.json`（旧 npm 配置）
- `git mv package-lock.json legacy/openspec-package-lock.json`

**扁平化 chat-database**：
- `git mv chat-database/packages/{web,server,shared}` → `packages/{web,server,core-temp}`
- `packages/core-temp` → `packages/core`（shared → core 重命名）
- `git mv chat-database/{bun.lock, tsconfig.base.json, .dependency-cruiser.cjs}` → 根
- `git mv chat-database/{.env.example, CLAUDE.md, README.md, contributing/}` → `docs/` 或根
- 删除空 `chat-database/` 目录

**新根 package.json**：Bun workspace 根（`workspaces: ["packages/*"]`），合并 chat-database scripts（dev/build/db:*/test/dep-check）

**包重命名**：
- `@chat-database/shared` → `@aquan/core`
- `@chat-database/server` → `@aquan/server`
- `@chat-database/web` → `@aquan/web`
- 全局替换 import `@chat-database/shared` → `@aquan/core`（18 个源文件）

**`.dependency-cruiser.cjs` 升级**：新增 `no-core-to-impl`（core 不依赖 server/web/orchestrator/pi-runtime）+ `no-runtime-to-app`（orchestrator/pi-runtime 不依赖 server/web）

**`packages/core/` 扩展**（吸收 shared + 加新内容）：
- `types/`：加 `market.ts`（Ticker/Universe/FactorName）、`backtest.ts`（BacktestResult）
- `work/`：新建 `work-item.ts`（WorkItem/RunState/TrackedWork）、`agent-event.ts`（AgentEvent/RunTokens）
- `constants/`：升级为目录模块（含原 ai-providers + 新 MCP_PORTS/SERVER_PORT/RUN_STATE_META）
- `errors.ts`：AquanError 体系（含 WorkItemNotFound/AgentRuntimeError）
- `utils/`：dates.ts（nowIso/normalizeDate）、ids.ts（workId/sessionId）

**`packages/orchestrator/` 新建**（Symphony-like 编排引擎骨架）：
- `orchestrator.ts`：主 poll-run-record 循环
- `agent-runner.ts`：单 WorkItem 的 turn loop（调 AgentRuntime，最多 N 轮）
- `state-store.ts`：TrackedWork 内存存储 + 状态转换
- `presenter.ts`：state → HTTP response（counts + per-state lists）
- `http.ts`：Bun.serve 暴露 `/api/v1/state`、`/api/v1/work/:id`、`/api/v1/tick`
- `prompt-builder.ts`：初始 prompt + continuation guidance
- `workspace.ts`：per-WorkItem 工作目录
- `runtime.ts`：AgentRuntime 接口 + StubRuntime（测试用）
- `trackers/`：Tracker 接口 + MemoryTracker + FactorMiningTracker/FreeExplorationTracker stubs
- `orchestrator.test.ts`：4 个 smoke 测试（prompt 构建 + tick 流转 + state 投影 + 空循环）

**`packages/pi-runtime/` 新建**（Pi agent runtime 适配层骨架）：
- `runtime.ts`：PiRuntime（implements AgentRuntime）
- `session.ts`：PiSession（implements AgentSession）
- `events.ts`：Pi SDK 事件 → AgentEvent 转换器
- `tools.ts`：MCP 工具注册接口 + NullToolRegistration（bootstrap）

**守门**：
- `bun run test` → **56 tests pass**（15 core + 4 orchestrator + 37 server）
- `bun run dep-check` → **0 violations**（663 modules, 1897 deps）
- Python 守门仍 183 全绿
- `chat-database/` 目录已消失

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
| 1 — Python 骨架 + aquan 公共层 | ✅ 完成 | (phase-1 branch) |
| 2 — 迁 MCP servers | ✅ 完成 | (phase-2 branch) |
| 3 — 迁 ETL | ✅ 完成 | (phase-3 branch) |
| 4 — 迁 notebooks/dbt/tests | ✅ 完成 | (phase-4 branch) |
| 5 — 扁平化 chat-database + 建新包 | ✅ 完成 | (本 commit) |
| 6 — 清理 legacy + 文档收尾 | ⏳ 待开始 | — |
