# 数据闭环总体路线图

**日期**: 2026-07-19
**状态**: Approved（待 spec review）
**作者**: jasenwood + ZCode
**关联**: 这是"完整数据闭环"的**总体路线图 spec**，不进入任一子项目细节。每个子项目各自走独立 brainstorm/spec/plan/实施循环。后续第一个子项目是 `dbt 建模`。

**前置已完成的 spec**:
- `2026-07-18-data-warehouse-foundation-design.md`（ODS 地基 + ETL）

---

## 0. 背景与动机

### 0.1 起点

`2026-07-18-data-warehouse-foundation-design.md` 完成了数据仓地基：DuckDB + Parquet 的 ODS 层 + 5 段式 ETL 契约 + JobService 任务队列。3 个 ODS 域（equity_daily / index_constituents / financial_income）已实现并通过 78 个单元测试。

### 0.2 目标

在 ODS 地基之上**完整构建数据闭环**：让原始数据 → 可分析 → 可视化 → 可反馈 → 沉淀新实验，形成迭代闭环。

### 0.3 范围说明（重要）

这是一个**路线图 spec**，不是实施 spec。它定义：
- ✅ 整体架构与子项目划分
- ✅ 子项目依赖关系与实施顺序
- ✅ 每个子项目的范围边界与验收标准
- ✅ 路线图层面的决策与风险

它**不**定义：
- ❌ 任一子项目的具体技术实现（留给该子项目自己的 spec）
- ❌ 具体代码、schema、API（留给该子项目自己的 plan）

每个子项目走独立循环：brainstorm → spec → plan → 实施 → merge。

---

## 1. 总体架构与定位

### 1.1 双项目协作架构

```
┌─ a-share-agents（数据生产者）─────────────────────┐
│                                                   │
│  L0  MCP servers (akshare/tushare/internal-store)  │  实时查询
│  L1  Skills (factor-mining/backtest-engine/...)    │  分析能力
│  L2  Agents (strategy-analyst/...)                 │  业务 agent
│  L3  meta-strategist                               │  探索 agent
│                                                   │
│  ┌─ 数据仓（已完成 ODS，待建 DWD/DWS）──────────┐ │
│  │  scripts/etl/                                  │ │
│  │    ↓ MCP HTTP                                  │ │
│  │  DuckDB + Parquet                              │ │
│  │    ODS  ✅ (equity_daily / index / financial)  │ │
│  │    DWD  ❌ (待 dbt 建模)                       │ │
│  │    DWS  ❌ (待 dbt 建模)                       │ │
│  │    ADS  ❌ (待 dbt 建模)                       │ │
│  │    实验数据 ❌ (待 ETL 入仓)                   │ │
│  └────────────────────────────────────────────────┘ │
│         ↑↓ 只读并发查询                              │
└─────────┼─────────────────────────────────────────┘
          │
          │  (chat-database 新增 duckdb adapter)
          │
┌─ chat-database（数据消费者/UI 层）────────────────┐
│                                                   │
│  server                                           │
│    adapters/                                      │
│      postgresql.ts (现有)                          │
│      sqlite.ts (现有)                              │
│      duckdb.ts ❌ (待新增 - 接 a-share-agents)     │
│    ai/                                            │
│      NL→SQL 翻译（自然语言探索分析）              │
│    routes/ (REST API)                             │
│                                                   │
│  web (Next.js)                                    │
│    dashboard     ← 因子对比、回测历史、策略总览    │
│    agent         ← 自然语言对话查询                │
│    data-studio   ← 自定义图表、数据探索            │
│    custom-charts ← A 股特化图表（K 线/IC 曲线等）   │
│                                                   │
└───────────────────────────────────────────────────┘
```

### 1.2 职责分工（清晰的边界）

| 职责 | 归属 | 说明 |
|---|---|---|
| 数据采集 + ODS 落地 | a-share-agents | ✅ 已完成 |
| 因子计算 + 实验运行 | a-share-agents | 现有 skills |
| dbt 建模（DWD/DWS/ADS） | a-share-agents | ❶ 待做 |
| 实验数据入仓 | a-share-agents | ❷ 待做 |
| 指标语义层 | a-share-agents | ❸ 待做 |
| DuckDB adapter | chat-database | ❹ 待做（chat-database 仓库） |
| 仪表板页面 | chat-database | ❺ 待做（A 股特化页面） |
| 自然语言查询 | chat-database | ✅ 已有能力 |
| 反馈回路（半自动） | a-share-agents meta-strategist | ❻ 待做 |

### 1.3 关键设计原则

1. **单一数据源**：DuckDB 是唯一数仓，chat-database 通过 adapter 直读，不做数据复制
2. **职责分离**：a-share-agents 产数据，chat-database 查数据。两者通过 DuckDB 文件 + adapter 解耦
3. **研究员优先**：所有决策以"你能在 chat-database 看清楚、做决策"为第一优先
4. **半自动反馈**：Meta-Agent 探索新假设，入库决策权在人
5. **不重写 UI/Agent**：chat-database 已有的 dashboard/agent/data-studio 直接用
6. **跨项目协作通过契约**：DuckDB adapter 是两个项目的唯一契约点
7. **同机部署**：两个项目跑在同一台机器，共享 Parquet 文件路径

---

## 2. 子项目划分与依赖图

### 2.1 子项目清单

| # | 子项目 | 仓库 | 工作量 | 价值 |
|---|---|---|---|---|
| ① | ✅ ODS 地基 + ETL | a-share-agents | 已完成 | 数据沉淀 |
| ❶ | dbt 建模（DWD/DWS/ADS） | a-share-agents | 中 | 让数据可分析 |
| ❷ | 实验数据入仓 | a-share-agents | 中 | 把因子/回测实验沉淀 |
| ❸ | 指标语义层 | a-share-agents | 中 | 统一 IC/Sharpe 定义 |
| ❹ | DuckDB adapter | chat-database | 小 | 跨项目连接 |
| ❺ | A 股仪表板 | chat-database | 中 | 可视化探索 |
| ❻ | Meta-Agent 探索 | a-share-agents | 中-大 | 半自动闭环 |

### 2.2 依赖图

```
                    ① ODS (✅ 已完成)
                       │
            ┌──────────┴──────────┐
            ↓                     ↓
        ❶ dbt 建模              ❷ 实验数据入仓
       (DWD/DWS/ADS)             (factor/backtest
            │                     experiments)
            │                     │
            ↓                     │
        ❸ 语义层 ←────────────────┘
       (指标统一)
            │
            ↓
        ❹ DuckDB adapter (chat-database)
            │
            ↓
        ❺ A 股仪表板 (chat-database)
       (dashboard/custom-charts)
            │
            ↓
        ❻ Meta-Agent 探索 (半自动闭环)
       (读历史→生成假设→入库)
```

### 2.3 关键依赖关系

- **❶ dbt 建模** 是所有后续的基础（语义层、仪表板都依赖 DWS/ADS）
- **❷ 实验数据入仓** 与 ❶ **可并行**（互不依赖，都是 ODS 之上的加工）
- **❸ 语义层** 依赖 ❶+❷（指标定义要基于已建模的表）
- **❹ DuckDB adapter** 技术上独立，但**实际价值依赖** ❶（连裸 ODS 没意义）
- **❺ 仪表板** 依赖 ❹+❶（要 adapter + 要 DWS 数据才有内容）
- **❻ Meta-Agent** 依赖 ❸+❺（要有语义层 + 要有仪表板观察反馈）

### 2.4 子项目交付独立性

每个子项目**独立 spec → plan → 实施 → merge**，互不阻塞。每个交付后系统都能增量改进，不会出现"全做或全不做"的状态。

---

## 3. 各子项目范围与交付物

### ❶ dbt 建模（DWD/DWS/ADS）

**目标**：在 ODS 之上建可分析的明细层和汇总层。

**范围**：
- 引入 dbt-duckdb adapter（dbt 官方维护）
- 建 dbt 项目骨架（`a-share-agents/dbt/`）
- **DWD 层**（明细宽表）：至少 `dwd_equity_daily`（标准化日线 + 派生字段）、`dwd_financial_quarterly`（财务指标宽表）
- **DWS 层**（轻度汇总）：`dws_factor_daily`（每日因子值）、`dws_industry_monthly`（行业月度收益）
- **ADS 层**（应用）：`ads_strategy_returns`（策略净值序列）
- dbt tests（数据质量：唯一性、非空、关系完整性）
- dbt docs 生成

**不在范围**：
- 实验数据入仓（留给 ❷）
- 语义层指标定义（留给 ❸）
- 自定义业务转换（如复权算法、行业映射）放在 staging 层

**验收**：`dbt run` 全过；`dbt test` 全过；`dbt docs generate` 能生成文档；至少 1 个 DWD + 1 个 DWS + 1 个 ADS 表可查。

### ❷ 实验数据入仓

**目标**：把因子挖掘、回测、策略实验的结果沉淀到数仓，可跨实验分析。

**范围**：
- 新 ETL 脚本（仿 ODS 五段式契约）：
  - `ods_factor_experiments`（因子实验：表达式 + IC/ICIR/turnover）
  - `ods_backtest_runs`（回测运行：参数 + Sharpe/MaxDD/净值序列）
  - `ods_strategy_hypotheses`（策略假设：factors/weights/universe）
- 数据源：`internal-store` 的 `factor_library` / `experiments` / `episode_summaries` 表
- 通过 MCP HTTP 调 `internal-store` 工具拉数据（保持单一数据入口原则）

**不在范围**：
- 不动 internal-store 表结构（只读它的数据）
- 不做实验数据的 DWD 建模（留给 ❶ 的 dbt 扩展）
- 不做 MLflow 集成（已决定走数仓路线）

**验收**：3 张实验表入仓；`report --jobs` 能看到 ETL 历史；chat-database 能查 `ods_backtest_runs`。

### ❸ 指标语义层

**目标**：统一 IC/Sharpe/MaxDD/换手率 等量化指标的定义，避免"同名异义"。

**范围**（技术选项留给该子项目 brainstorm）：
- **选项 A**：dbt Semantic Layer（dbt 官方，需 dbt Cloud 付费或 MetricFlow）
- **选项 B**：Cube.dev（开源、独立部署、与 chat-database 易集成）
- 定义至少 10 个核心指标（IC_1d / IC_20d / Sharpe_annualized / MaxDD / turnover_monthly / win_rate / ...）
- 每个指标带：定义公式、计算口径、单位、适用场景、维度（universe/period/...）

**不在范围**：
- 不做指标的可视化（留给 ❺）
- 不做指标告警（YAGNI）

**验收**：能通过语义层 API 查询"动量因子在中证500的 IC_20d"；chat-database agent 能调用语义层而非裸 SQL。

### ❹ DuckDB adapter（chat-database 仓库）

**目标**：让 chat-database 能直连 a-share-agents 的 DuckDB 数仓。

**范围**：
- 新文件 `packages/server/src/adapters/duckdb.ts`
- 实现 `DatabaseAdapter` 接口（与 postgresql.ts/sqlite.ts 同构）
- 用 `duckdb-async` 或 `@duckdb/node-api` Node binding
- 支持只读模式（BI 场景，避免与 ETL 写入冲突）
- 连接管理：复用 `pool-manager.ts` 模式
- 配置：通过 chat-database 的 database 配置页指定 DuckDB 文件路径
- 测试：用 a-share-agents 的实际 Parquet 数据做集成测试

**不在范围**：
- 不改 chat-database 的其他 adapter
- 不做写支持（只读）
- 不做远程 DuckDB（同机部署）

**验收**：在 chat-database 的 database 管理页能添加 DuckDB 数据源；agent 能对该数据源跑自然语言查询。

### ❺ A 股仪表板（chat-database 仓库）

**目标**：研究员日常看数据的工作台。

**范围**：
- 至少 4 个 A 股特化页面（在 `packages/web/app/(main)/`）：
  - **因子对比**：多因子 IC 曲线、分层收益、衰减曲线
  - **回测历史**：所有回测的 Sharpe/MaxDD 散点图、净值曲线对比
  - **策略总览**：当前策略列表 + 假设 + 历史表现
  - **市场观察**：北向资金、行业涨跌、龙头股（可选）
- 自定义图表组件（`custom-charts/`）：K 线、IC 时序、回撤曲线等 A 股特化
- 利用 chat-database 现有 dashboard 框架，不重写

**MVP 与全量划分**（与 §4.2 里程碑对应）：
- **MVP（M3）**：因子对比 + 回测历史 两个页面，验证 adapter + 仪表板管线打通
- **全量（M6）**：扩展到策略总览 + 市场观察，完整工作台

**不在范围**：
- 不做实时行情（已有 akshare-server MCP，无需重复）
- 不做交易下单（YAGNI）
- 不做用户协作/分享（YAGNI）

**验收**：4 个页面可用；能对比至少 5 个因子的 IC；能查任一回测的净值曲线。

### ❻ Meta-Agent 探索（a-share-agents 仓库）

**目标**：半自动探索新因子/参数，入库决策权在人。

**范围**：
- 重构 `meta-strategist` agent（现有的 7 步协议）：
  - **探索模式**：自主跑 GP 因子挖掘 + 回测新假设，但只生成"候选"
  - **推荐模式**：基于历史实验，推荐"下一个值得试的方向"（Markdown 报告）
  - **不自动入库**：候选写入 `ods_factor_experiments`（status=`candidate`），入库需人工审批
- 利用 ❸ 语义层查询历史
- 利用 ❺ 仪表板呈现候选

**不在范围**：
- 不做全自动进化（与"研究员优先"矛盾）
- 不做实盘交易（YAGNI）
- 不做强化学习的完整 state/action/reward 建模（现有 `transitions` 表够用）

**验收**：能跑一次完整"探索→生成候选→推到仪表板→你审批→入库"流程。

---

## 4. 实施顺序与里程碑

### 4.1 推荐实施顺序

```
Phase 1: 让数据可分析（2-3 周）
   ❶ dbt 建模 (DWD/DWS/ADS)
       ↓
Phase 2: 让数据可看见（1-2 周，与 Phase 1 部分并行）
   ❹ DuckDB adapter
       ↓
   ❺ A 股仪表板（MVP：只做因子对比 + 回测历史两页）

Phase 3: 让实验沉淀（1 周，与 Phase 1-2 并行）
   ❷ 实验数据入仓

Phase 4: 让指标统一（1 周）
   ❸ 指标语义层

Phase 5: 让闭环成立（2-3 周）
   ❺ 仪表板扩展（策略总览 + 市场观察）
   ❻ Meta-Agent 探索
```

### 4.2 里程碑

| 里程碑 | 完成子项目 | 你能做什么 | 估计时间 |
|---|---|---|---|
| **M0** ✅ | ① ODS 地基 | 数据已沉淀（但还没分析） | 已完成 |
| **M1** | ❶ dbt 建模 | 在 DuckDB 里写 SQL 分析 A 股（DWD/DWS 视图） | 2-3 周 |
| **M2** | ❶ + ❹ DuckDB adapter | 在 chat-database 里自然语言查 A 股数据 | +1-2 周 |
| **M3** | M2 + ❺ MVP 仪表板 | 在 chat-database 看因子对比 + 回测历史 | +1 周 |
| **M4** | M3 + ❷ 实验入仓 | 看历史所有因子/回测实验 | +1 周（可与 M2-M3 并行） |
| **M5** | M4 + ❸ 语义层 | 统一指标口径，agent 用语义层而非裸 SQL | +1 周 |
| **M6** | M5 + ❺ 全仪表板 + ❻ Meta-Agent | **完整闭环**：看→决策→机器探索→你审批→入库 | +2-3 周 |

**总估计**：6-10 周。

### 4.3 并行机会

- **❶ dbt 建模** 与 **❷ 实验数据入仓** 完全独立，可并行
- **❹ DuckDB adapter** 可在 ❶ 进行中就开始（技术不依赖 ❶，只是实际价值依赖 ❶）
- **❺ 仪表板 MVP** 可在 ❶ 完成 DWD/DWS 第一版后立即启动（不等全部表建完）

### 4.4 优先做 dbt 建模的理由

1. **它是所有后续的基础**：仪表板、语义层、Meta-Agent 都依赖 DWS/ADS
2. **价值立竿见影**：建好 DWD 后立即能用 SQL 分析
3. **能验证数仓设计**：dbt 建模过程会暴露 ODS 设计的不足，早暴露早修
4. **风险隔离**：如果 dbt 建模发现 DuckDB 不合适，现在改比后面建了一堆 UI 后改便宜

### 4.5 不推荐的顺序（避免陷阱）

- ❌ **先做 ❻ Meta-Agent**：没有 ❶❸，agent 没数据查、没语义层用，只能做 demo
- ❌ **先做 ❹ adapter**：技术上独立但实际无价值（连裸 ODS 给用户看没意义）
- ❌ **同时做 ❶❷❸**：三个都做但都半成品，无法验证任何一条线

---

## 5. 风险与决策记录

### 5.1 关键决策记录（路线图层面）

| # | 决策 | 备选 | 理由 |
|---|---|---|---|
| D1 | 闭环主消费者是**研究员（你）** | Meta-Agent 自主 / 终端用户 | UI 是主要交付物、Meta-Agent 是辅助 |
| D2 | 反馈强度选**半自动**（机器探索 + 人决策） | 弱反馈 / 强反馈 | 平衡探索广度与判断质量 |
| D3 | **接入 chat-database**（不重写 UI/Agent） | 自建 Streamlit / 独立 Meta-Agent | 保护已有产品投资，不重复造轮子 |
| D4 | DuckDB 作为**唯一数仓**（chat-database 加 adapter） | 加 PG 中间层 / 换 PG | 单一数据源、保护 DuckDB 投资、OLAP 性能保留 |
| D5 | **同机部署**（共享 Parquet 文件） | 网络盘 / 多机 | DuckDB adapter 直连零障碍 |
| D6 | 从 **dbt 建模** 开始实施 | adapter / 仪表板 / Meta-Agent | dbt 是所有后续的基础，价值立竿见影 |

### 5.2 主要风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| **DuckDB 单连接** 在 chat-database 多查询时阻塞 | 中 | 中 | adapter 用只读模式（支持只读并发）+ 连接池 |
| **DuckDB Node binding 不稳定** | 低 | 高 | 选成熟库，早期做集成 PoC |
| **dbt-duckdb 不支持某些 PG 特性** | 中 | 低 | dbt-duckdb 官方维护，少数特性用 macro 替代 |
| **chat-database 是独立项目**，跨仓库协调成本 | 中 | 中 | 每个跨项目子项目（❹❺）独立 spec，明确接口契约 |
| **半自动 Meta-Agent 误推荐**（生成垃圾候选） | 中 | 低 | 候选全部走人工审批，不自动入库；推荐报告附置信度 |
| **范围蔓延**（每子项目 brainstorm 加需求） | 高 | 中 | §3 的"不在范围"清单是硬约束，每个子项目 spec 不得越界 |
| **Parquet 文件路径变化** 导致 chat-database 找不到数据 | 低 | 中 | adapter 配置走环境变量 + 检查脚本 |

### 5.3 不做的事（明确排除）

- ❌ **多用户/权限系统**：你是唯一用户，YAGNI
- ❌ **实时行情入仓**：MCP server 已提供实时查询，数仓只存历史
- ❌ **实盘交易**：研究平台，非交易系统
- ❌ **MLflow / Langfuse**：已决定走数仓路线
- ❌ **PostgreSQL / PGlite / pgboss**：已定 DuckDB 路线（除非 M6 后真有多用户需求）
- ❌ **强化学习完整建模**：现有 `transitions` 表够用

### 5.4 后续演进路径（M6 之后）

如果完整闭环跑通后还有需求：

- **多用户协作** → DuckDB 之上加 PostgreSQL 同步层
- **更高性能查询** → 引入 DuckDB 的 `httpfs` 扩展支持 S3 远程 Parquet
- **更复杂的 agent 推理** → 引入 Langfuse 监控 LLM call
- **实盘对接** → 单独立项（与数仓闭环解耦）

---

## 6. 后续行动

本路线图 spec 批准后，下一步是启动**第一个子项目 ❶ dbt 建模**的独立 brainstorm 循环：

1. brainstorm `dbt-建模-design.md`
2. writing-plans `dbt-建模.md`
3. 实施
4. merge，达到 **M1 里程碑**
5. 启动 ❹ DuckDB adapter 的 brainstorm（可与 ❷ 并行）

每个子项目 spec 在 `## 0. 背景与动机` 引用本路线图为前置上下文。
