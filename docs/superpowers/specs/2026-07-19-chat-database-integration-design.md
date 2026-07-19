# chat-database 整合到 a-share-agents（子项目 ⓿）

**日期**: 2026-07-19
**状态**: Approved
**作者**: jasenwood + ZCode
**关联**:
- 前置：`2026-07-19-data-loop-roadmap-design.md`（总体路线图）
- 本 spec 推翻原路线图决策 D3/D5（详见 §1.1），并新增子项目 ⓿ 作为后续 ❹❺ 的前置

---

## 0. 背景与动机

### 0.1 起点

总体路线图 `2026-07-19-data-loop-roadmap-design.md` 已批准，规划了 6 个子项目（❶ dbt 建模已完成 M1，❷❸❹❺❻ 待做）。原路线图把 a-share-agents（数据生产者）和 chat-database（UI/BI 消费者）作为**两个独立同机项目**，通过 DuckDB adapter 解耦。

### 0.2 为什么整合

用户决定把 chat-database 物理整合到 a-share-agents 单仓库，理由：
- **简化跨仓库协调**：原路线图 §5.2 列的"chat-database 是独立项目，跨仓库协调成本"风险彻底消失
- **单仓库演化**：所有数据闭环相关代码集中一处，git 历史、CI、release 统一
- **DuckDB adapter 和仪表板变同仓库改动**：原子项目 ❹❺ 的"跨仓库"前提消失，实施成本降低

### 0.3 整合不等于一次性做完闭环

**重要**：本 spec **只做物理整合**（子项目 ⓿），不顺手做 ❷❸❹❺❻。每个后续子项目仍走独立 spec→plan→实施→merge，保证可验证、可回滚。

---

## 1. 范围

### 1.1 对原路线图决策的影响

| 原决策 | 原立场 | 整合后 | 处理 |
|---|---|---|---|
| **D3** 接入 chat-database（不重写 UI/Agent） | 两仓库协作 | 单仓库内协作 | **修订**：原决策精神（保护已有 UI 投资、不重写）保留；只是物理形态从"两仓库"变"单仓库" |
| **D4** DuckDB 唯一数仓 | chat-database 加 adapter | 不变 | 保留 |
| **D5** 同机部署 | 两项目同机 | 单仓库同机 | **修订**：原决策精神（共享 Parquet 文件）保留；形态更彻底（同仓库） |

### 1.2 在范围

- 将 chat-database 仓库（commit `ae26512`）完整物理复制到 `a-share-agents/chat-database/`
- 合并根 `.gitignore`（chat-database 忽略规则并入根，删除 `chat-database/.gitignore`）
- `chat-database/.env.example` 加一行 `WAREHOUSE_DUCKDB_PATH=../data/warehouse/meta.db`（默认指向数仓）
- `chat-database/README.md` 顶部加归档说明
- 验证 `bun install` + `bun run db:migrate` + `bun run db:seed` 在新位置能跑通（或记录 Bun 未安装为 known issue）
- 写本 spec 文档

### 1.3 不在范围（每个都是独立子项目）

- ❌ **DuckDB adapter**（子项目 ❹）—— 本 spec 只留出位置，不实现
- ❌ **A 股仪表板**（子项目 ❺）
- ❌ **实验数据入仓**（子项目 ❷）
- ❌ **指标语义层**（子项目 ❸）
- ❌ **Meta-Agent 探索**（子项目 ❻）
- ❌ **目录重构**（用户说"最后做完还要重构目录"，留给所有子项目完成后做一次性重组）
- ❌ **chat-database 的 bug fix / 功能升级**——只搬不改

---

## 2. 目录结构（整合后）

```
a-share-agents/
├── mcp-servers/              # Python (L0 connectors)
├── scripts/etl/              # Python (数据仓 ETL)
├── dbt/                      # SQL (DWD/DWS/ADS) ✅ M1 已完成
├── plugins/agent-plugins/    # Python (L3 Meta-Agent)
├── chat-database/            # 🆕 TypeScript/Bun (UI/BI 层)
│   ├── packages/
│   │   ├── shared/           # workspace: @chat-database/shared
│   │   ├── server/           # workspace: @chat-database/server (Hono)
│   │   └── web/              # workspace: @chat-database/web (Next.js)
│   ├── package.json          # workspaces root: ["packages/*"]
│   ├── bun.lock
│   ├── tsconfig.base.json
│   ├── .env.example          # 加 WAREHOUSE_DUCKDB_PATH
│   ├── data/                 # chat-database 自己的 SQLite 系统库（用户/会话）
│   ├── contributing/
│   └── README.md             # 加归档说明
├── data/warehouse/           # DuckDB 数仓（两方共享）
├── pyproject.toml
├── package.json              # 仅 @fission-ai/openspec，与 chat-database/package.json 独立
└── ...
```

### 2.1 关键约定

- **两个 package.json 互不干扰**：根 `package.json`（openspec 工具依赖）与 `chat-database/package.json`（app workspace root）是独立 npm 项目
- **bun install 限定在子目录**：`cd chat-database && bun install`，不污染根 `node_modules/`
- **两个 data/ 目录明确区分**：
  - `chat-database/data/*.db` —— chat-database 自己的 SQLite 系统库（用户、会话、dashboard 配置）
  - `data/warehouse/` —— DuckDB 数仓 + Parquet（a-share-agents 产数据，chat-database 通过未来 adapter 只读消费）

---

## 3. 整合步骤（执行顺序）

1. **复制代码**：从 `/Volumes/data/documents/codes/chat-database` 复制下列条目到 `a-share-agents/chat-database/`：
   - `packages/`（shared, server, web 三个 workspace）
   - `bun.lock`
   - `package.json`
   - `tsconfig.base.json`
   - `.env.example`
   - `.gitignore`（内容并入根后删除本文件）
   - `.dependency-cruiser.cjs`
   - `contributing/`
   - `README.md`
   - `CLAUDE.md`

   **排除**：`.git/`, `node_modules/`, `data/*.db`, `packages/web/.next/`, `packages/server/dist/`, `.claude/`, `.deepeval/`

2. **合并 .gitignore**：把 chat-database 的 `.gitignore` 规则追加到 a-share-agents 根 `.gitignore`（用 `# === chat-database (integrated) ===` 注释分隔），删除 `chat-database/.gitignore`

3. **配置默认数仓路径**：编辑 `chat-database/.env.example`，在末尾追加：
   ```
   # ===== A-Share Agents Warehouse (read by future DuckDB adapter) =====
   WAREHOUSE_DUCKDB_PATH=../data/warehouse/meta.db
   ```

4. **加归档说明**：在 `chat-database/README.md` 顶部插入归档区块：
   ```markdown
   > **Archived (2026-07-19)**: 本目录原为独立仓库 [JasenWow/chat-database](https://github.com/JasenWow/chat-database)（commit `ae26512`），已整合到 a-share-agents monorepo 作为 UI/BI 层。后续演化在 a-share-agents 仓库进行，原仓库归档不再同步。
   ```

5. **验证启动**（非阻塞）：
   - 若本机有 Bun：`cd chat-database && bun install && bun run db:migrate && bun run db:seed`，记录输出
   - 若本机无 Bun（整合前 `which bun` 返回空）：在 README 记录为 known issue，不阻塞整合

6. **写本 spec 文档**（已在此处完成）

7. **提交**：`feat: integrate chat-database into a-share-agents monorepo (sub-project ⓿)`

---

## 4. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | **本机无 Bun**（整合前 `which bun` 返回空） | 高 | 中 | 整合不依赖 Bun 可执行；验证步骤非阻塞；在 README 记录安装指引 |
| R2 | **根 package.json 与 chat-database/package.json 概念冲突** | 低 | 低 | 两者职责不同（根=openspec 工具，chat-database=app workspace），文档说明清楚 |
| R3 | **两个 data/ 目录混淆** | 中 | 低 | chat-database 系统库在 `chat-database/data/*.db`，数仓在根 `data/warehouse/`；README 明确区分 |
| R4 | **未来 DuckDB Node binding 在 Bun 下不兼容**（影响 ❹） | 中 | 高 | 本 spec 不解决；在风险表记录；❹ 子项目 spec 第一步做 PoC，失败则改用 Node runtime 跑 server（chat-database 是 Bun-first 但 Node 兼容） |
| R5 | **目录重构延后**（用户说最后还要重构） | 低 | 低 | 接受。当前先平铺，所有子项目完成后再一次性重组 |
| R6 | **chat-database 复制后路径引用断裂**（如 web 里写死的 API URL） | 低 | 低 | chat-database 原本就是独立 workspace，内部用相对包名 `@chat-database/*` 引用，不依赖外部路径；复制后零修改即可工作 |

---

## 5. 验收标准

整合 ⓿ 完成的硬指标：

1. ✅ `chat-database/` 目录存在，包含 `packages/shared`, `packages/server`, `packages/web` 三个 workspace
2. ✅ 根 `.gitignore` 包含 chat-database 的忽略规则（`.next/`, `dist/`, `*.db`, `packages/server/data/*.db` 等）
3. ✅ `chat-database/.env.example` 含 `WAREHOUSE_DUCKDB_PATH=../data/warehouse/meta.db`
4. ✅ `chat-database/README.md` 含归档说明（含原仓库链接 + commit hash）
5. ✅ 若本机有 Bun：`cd chat-database && bun install && bun run db:migrate && bun run db:seed` 成功；若本机无 Bun：README 有 known issue 记录
6. ✅ `git status` 干净，commit message 含 `(sub-project ⓿)` 标识
7. ✅ 本 spec 文档存在并在 commit 中引用

---

## 6. 后续子项目映射（整合如何改变原路线图）

整合完成后，原路线图的子项目位置更新：

| 原子项目 | 原定位 | 新位置 | 变化 |
|---|---|---|---|
| ❶ dbt 建模 | a-share-agents/dbt/ | 不变 | ✅ 已完成（M1） |
| ❷ 实验数据入仓 | a-share-agents/scripts/etl/ods/ | 不变 | 待做 |
| ❸ 指标语义层 | a-share-agents/dbt/ 或独立目录 | 不变 | 待做 |
| ❹ DuckDB adapter | ~~chat-database 仓库~~ | `a-share-agents/chat-database/packages/server/src/adapters/duckdb.ts` | **从跨仓库变同仓库** |
| ❺ A 股仪表板 | ~~chat-database 仓库~~ | `a-share-agents/chat-database/packages/web/app/(main)/` | **从跨仓库变同仓库** |
| ❻ Meta-Agent 探索 | a-share-agents/plugins/agent-plugins/meta-strategist/ | 不变 | 待做 |

### 6.1 推荐下一步

整合 ⓿ 完成后，按原路线图 §4.1 推荐顺序：
- **❹ DuckDB adapter**（R4 风险最高，先做 PoC 验证 Bun+native binding 可行性）
- 或 **❷ 实验数据入仓**（与 ❹ 完全独立，可并行）

---

## 7. 决策记录

| # | 决策 | 备选 | 理由 |
|---|---|---|---|
| D-⓿-1 | **完整复制为子目录**（非 submodule/subtree） | submodule / subtree | 用户选择；自包含、可独立 bun dev、单仓库演化 |
| D-⓿-2 | 目录位置 `chat-database/`（根目录平铺，最终会重构） | `web/chat-database/` | 用户选择"先复制过来，最后做完还要重构目录" |
| D-⓿-3 | 原仓库归档（不再同步） | 保留双向同步 / 镜像备份 | 用户选择；避免双向同步地狱 |
| D-⓿-4 | 本次只做物理整合，不顺手做 ❹ | 整合 + DuckDB adapter 一起做 | 用户选择；两件不同性质工作分开，可独立 review/回滚 |
| D-⓿-5 | 独立 .env + 默认指向数仓 | 合并两套 .env | 用户选择；Python uv 与 TS bun 各自独立，避免命名冲突 |
