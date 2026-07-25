# Agent 编排愿景（Agent Orchestration Vision）

**日期**: 2026-07-19
**状态**: Draft（产品愿景，非实施 spec）
**作者**: jasenwood + ZCode
**关联**: 继 `2026-07-19-data-loop-roadmap-design.md`（数据闭环）之后的**下一阶段愿景**。本文档定义产品方向，不涉及具体实施；每个阶段各自走独立 brainstorm/spec/plan/实施循环。

**参考资料**:
- [earendil-works/pi](https://github.com/earendil-works/pi) — agent runtime
- [openai/symphony](https://github.com/openai/symphony) — 看板/编排参考（不直接用）

---

## 0. 背景与动机

### 0.1 起点

数据闭环已完成（`2026-07-19-data-loop-roadmap-design.md`）：

- ✅ DuckDB + Parquet 数仓（ODS/DWD/DWS/ADS）
- ✅ internal-store MCP（experiments / candidates / factors / backtests）
- ✅ chat-database 看板（/factors、/backtests，只读）
- ✅ 半自动 feedback loop（candidate → promote / reject）
- ✅ meta-strategist.md prompt（但**无 runtime**，只是 markdown）

下一步是让 agent **真正跑起来**，并且**可观察、可交互、可编排**。

### 0.2 目标（一句话）

**让 agent 定期自主跑有价值的工作，人通过看板观察并干预，最终走向 agent 自主管理。**

### 0.3 范围说明

这是一个**产品愿景文档**，不是实施 spec。它定义：

- ✅ 产品方向与终态愿景
- ✅ 三层架构（看板 / agent-runtime / workflow-loop）
- ✅ 分阶段路线图（3 个阶段）
- ✅ 关键技术选型与决策（Pi 作为 runtime、pi-workflow 不存在需自建）
- ✅ 每个阶段的范围边界与验收标准

它**不**定义：

- ❌ 任一阶段的具体技术实现（留给该阶段自己的 spec）
- ❌ 具体 schema、API、文件结构（留给该阶段自己的 plan）

每个阶段走独立循环：brainstorm → spec → plan → 实施 → merge。

---

## 1. 产品愿景与终态

### 1.1 北极星：Agent 自主管理

```
终态：agent 自主管理工作
  ├─ 从任务源拉取工作（不靠人指派）
  ├─ 自己判断优先级与可行性
  ├─ 调度其他 agent 或工具完成
  ├─ 把结果回流到看板
  └─ 人只在关键节点介入（approve / 反馈）
```

这不是 Phase 1 要做的事，但所有设计决策都要**朝这个方向不挡路**。

### 1.2 两条工作主线

进入 loop 的工作分两类，架构要同时支持：

| 类型 | 特征 | 例子 | Phase 1 做法 |
|---|---|---|---|
| **沉淀挖掘型** | 有明确产出物、可评估、可沉淀 | 因子挖掘、策略回测、组合优化 | 规则扫描（不调 LLM）→ candidate |
| **自由探索型** | 无固定产出、开放式、靠 LLM 判断 | 市场观察、研报解读、假设生成 | LLM agent 自由调工具 |

两类共享同一个 runtime、同一个看板，但 loop 触发方式、评估标准、反馈机制不同。

### 1.3 核心抽象

借鉴 Symphony 的三层 loop 模型，落到本项目：

| 层 | 含义 | Symphony 对应 | 本项目目标 |
|---|---|---|---|
| **内层 turn loop** | agent 跑一轮 → 看工具结果 → 跑下一轮，直到完成 | `do_run_codex_turns` | 由 **Pi** 提供（不自己写） |
| **中层 orchestration loop** | 调度器按 cadence poll → spawn agent → retry/blocked/done | `Orchestrator` GenServer（1953 行） | 自己写（轻量版） |
| **外层 feedback loop** | 结果回流到人 → promote/reject → 喂给下一轮 | tracker state machine | internal-store 已有雏形 |

**关键决策：内层不自己写**。Symphony 那 1953 行 orchestrator 很大程度是在 Codex app-server 协议上重新实现 turn loop。Pi 把这件事做好了，我们直接用。

---

## 2. 三层架构

```
┌─────────────────────────────────────────────────────────┐
│  终态：Agent 自主管理（北极星，不在本路线图内实施）       │
└────────────────────┬────────────────────────────────────┘
                     │
┌─────────────────────▼───────────────────────────────────┐
│  第 3 层：Workflow / Loop 引擎                           │
│  ─────────────────────────────────────                  │
│  · 编排两类工作（自由探索 / 沉淀挖掘）                    │
│  · cron 定时触发 + 事件触发                              │
│  · job 状态机（pending/running/blocked/done/failed）     │
│  · 多 agent 协作（阶段 3）                               │
│                                                         │
│  ⚠️ pi-workflow / pi-loop 不存在 → 必须自建或选型         │
│  实现位置：chat-database/packages/server 内              │
└────────────────────┬────────────────────────────────────┘
                     │
┌─────────────────────▼───────────────────────────────────┐
│  第 2 层：Pi agent-runtime                               │
│  ─────────────────────────────────────                  │
│  · @earendil-works/pi-agent-core 作为内核               │
│  · Extension 桥接 MCP 工具（akshare/tushare/internal-store）│
│  · lifecycle 事件转发到 internal-store                   │
│  · 单次 session = 一个 agent run                         │
│                                                         │
│  实现位置：chat-database/packages/server/src/agent-runtime/ │
└────────────────────┬────────────────────────────────────┘
                     │
┌─────────────────────▼───────────────────────────────────┐
│  第 1 层：看板（交互 + 观察）                            │
│  ─────────────────────────────────────                  │
│  · 状态视图（running / blocked / done）— 抄 Symphony     │
│  · 事件流（turn / tool_call / token / error）            │
│  · 交互（Run now / 发消息 / approve / 打断）             │
│  · Loop 级视图（历史 run、成功率、产出）                 │
│                                                         │
│  实现位置：chat-database/packages/web/app/(main)/agents/ │
└─────────────────────────────────────────────────────────┘
```

### 2.1 与现有架构的衔接

本愿景**不改**已有的 L0–L3 分层，而是在其之上加一层 **agent 编排层**：

```
L0  MCP servers  (akshare/tushare/internal-store)   ← 已有，不动
L1  Skills       (factor-mining/backtest/...)       ← 已有，不动
L2  Agents       (meta-strategist/...)              ← prompt 已有，runtime 由 Pi 接管
───────────────────────────────────────────────  ← 新增编排层
L4  Loop Engine  (cron + scheduler + job state)     ← 新增（阶段 2）
L5  Dashboard    (观察 + 交互)                      ← 扩展 chat-database（阶段 1）
```

meta-strategist.md 这份 prompt **不变**，只是它的执行者从"假想的 Claude Code 会话"变成"Pi runtime 里的真实 session"。

---

## 3. 关键决策

### 3.1 Pi 作为 agent runtime（已定）

**决策**：用 `@earendil-works/pi-agent-core` 作为统一 agent runtime。

**理由**：
- Pi 的 turn loop + tool execution + lifecycle 事件是现成的，避免重写 Symphony 那 1953 行
- Pi 的 Extension 机制可以把 MCP 工具桥接进去，不破坏现有 L0
- `pi-agent-core` 比 `pi-coding-agent` 更适合 embedding（无 TUI 依赖）
- 支持多 model provider（阶段 1 用 ZAI Coding Plan，后续可换）

**代价**：
- 引入 TypeScript agent runtime（chat-database 已是 Bun/TS，栈一致）
- Pi 生态年轻（v0.80.x），API 可能变动

### 3.2 pi-workflow 必须自建（重要修正）

**事实**：Pi 生态**没有**叫 `pi-workflow` 或 `pi-loop` 的官方包。Pi 提供的是：
- `pi-coding-agent` — 终端 CLI + TUI
- `pi-agent-core` — 通用 agent 内核（transport + state + attachment）
- **Extensions** — TS 模块，订阅 lifecycle 事件、注册自定义工具

**决策**：第 3 层 workflow 引擎**自建**，在 chat-database server 里实现一个轻量 job scheduler。

**理由**：
- Symphony 已证明这件事可做（orchestrator 本质就是 scheduler + 状态机）
- 自建可以选择性实现（不需要 SSH workers / Burrito 发布这些 Symphony 特性）
- 等 Pi 生态成熟或真出了 pi-workflow，可以替换

**不做的**：
- ❌ 不在阶段 1 做完整 workflow 引擎（过早）
- ❌ 不做多 agent 编排（阶段 3 才考虑）
- ❌ 不照搬 Symphony 的 SSH worker / Burrito 发布

### 3.3 Symphony 的定位：参考，不用

**决策**：Symphony 作为**设计参考**，不集成其代码。

**借鉴的点**：
- 三态视图（running / retrying / blocked）——抄 `presenter.ex` 的 schema
- issue = 工作单元的抽象——在本项目映射成 experiment / candidate
- turn → continue/done/blocked 的状态机——抄 `agent_runner.ex` 的退出条件判断

**不借鉴**：
- ❌ Elixir/OTP runtime（栈不一致）
- ❌ Linear tracker adapter（用 internal-store 替代）
- ❌ Codex app-server（用 Pi 替代）

### 3.4 看板交互层级（分阶段）

| 阶段 | 交互能力 |
|---|---|
| 阶段 1 | 只读观察 + "Run now" 按钮 |
| 阶段 2 | + 发消息给 agent（chat 式干预） |
| 阶段 3 | + approve/reject 工具调用 + 实时打断 |

不在阶段 1 做重交互——Pi Extension 的事件订阅已经能让你看清 agent 在干嘛，重交互等基底稳定再加。

### 3.5 Loop scheduler 位置（已定）

**决策**：放 `chat-database/packages/server` 内，作为 server 启动时拉起的 background job。

**理由**：
- 复用 Bun runtime + Hono server + DuckDB 连接
- 全栈一致（agent runtime + scheduler + 看板 API 都在 TS 侧）
- 避免 a-share-agents Python 侧与 TS 侧割裂

---

## 4. 分阶段路线图

### 阶段 1：打通"看板 ← Pi runtime"最小闭环

**目标**：在网页上看到一个 Pi agent 跑起来、干了什么、能手动触发。

**范围**：
- 装 `@earendil-works/pi-agent-core`
- 写一个 Extension 桥接 internal-store MCP（lifecycle 事件 → `agent_runs` 表）
- chat-database 加 `/agents` 页（三态视图 + 事件流）
- 写一个 Pi session 跑 `meta-strategist.md`，挖一个因子 → candidate
- 加 "Run now" 按钮（手动触发，**不**做 cron）

**不做**：
- ❌ cron / 定时
- ❌ workflow 引擎
- ❌ 多 agent
- ❌ chat 式交互

**验收标准**：
- [ ] 点 "Run now" → 一个 Pi session 启动
- [ ] /agents 页实时显示 session 状态（running → done）
- [ ] session 产出的 candidate 出现在 /factors 页
- [ ] session 的 turn/tool/token 事件记录在 `agent_runs` 表
- [ ] 失败时显示 error + blocked 状态

**预计工作量**：2-3 天

---

### 阶段 2：Loop 调度 + 两类工作

**目标**：cron 定期触发，区分"自由探索"和"沉淀挖掘"两类工作。

**范围**：
- `chat-database/packages/server` 内写 job scheduler
- 定义 `jobs` 表：`type: explore | mine`，`cadence: cron 表达式`
- 沉淀挖掘型 Phase 1：规则扫描（不调 LLM，跑 Python 因子脚本）
- 自由探索型：Pi agent 跑 `meta-strategist.md` 的 `/explore` 模式
- 看板加 `/loops` 页：每个 loop 的历史 run、成功率、产出
- internal-store 加 `loop_runs` 表（区别于单次 `agent_runs`）

**不做**：
- ❌ 多 agent 协作
- ❌ workflow DAG
- ❌ LLM 驱动的沉淀挖掘（留给阶段 3）

**验收标准**：
- [ ] 配置 cron 表达式 → scheduler 按时触发
- [ ] /loops 页显示每个 job 的下次运行时间 + 历史
- [ ] 沉淀挖掘 job 跑完 → candidate 入库 → /factors 可见
- [ ] 自由探索 job 跑完 → experiment 入库 → 可观察
- [ ] 失败 job 自动 retry（指数退避）

**预计工作量**：1-2 周

---

### 阶段 3：Workflow 雏形 + 多 agent（向终态靠拢）

**目标**：工作流编排，agent 之间能协作，向"自主管理"方向走一步。

**范围**（待阶段 2 完成后细化）：
- 抽象 workflow 引擎（节点 + 边 + 状态机）
- 多 agent 协作（参考 Pi to Pi Extension 模式）
- LLM 驱动的沉淀挖掘（从规则扫描升级）
- 看板加 approve/reject 工具调用、实时打断
- agent 自主从任务源拉取工作（部分实现）

**验收标准**：待阶段 2 后定义。

**预计工作量**：1+ 月

---

## 5. 技术栈选型

| 组件 | 选型 | 理由 |
|---|---|---|
| Agent runtime | `@earendil-works/pi-agent-core` | 内核级、可 embedding、无 TUI 依赖 |
| Workflow engine | **自建**（轻量 scheduler） | Pi 无现成 workflow 包；自建可控 |
| 看板 | chat-database (Next.js + Hono) | 已有，扩展 |
| 状态层 | internal-store MCP (SQLite) | 已有 |
| 数据层 | DuckDB + Parquet | 已有 |
| Scheduler 实现 | Bun + setInterval / cron 解析 | 复用 chat-database runtime |
| Model provider | ZAI Coding Plan（阶段 1）| 已在用；Pi 支持多 provider |

---

## 6. 风险与未决问题

### 6.1 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| Pi API 变动（v0.80.x 年轻生态） | runtime 层要返工 | 用 Extension 隔离，core API 稳定后再深入 |
| MCP 桥接复杂度 | 阶段 1 工期不确定 | 先桥接 internal-store 一个 server，验证模式后再加 akshare/tushare |
| Token 成本失控（自由探索型） | 钱包压力 | 阶段 1 不做定时；阶段 2 加 per-run token 上限 |
| 多 agent 协作设计过早 | 阶段 3 返工 | 严格分阶段，阶段 1-2 单 agent |

### 6.2 未决问题（留给阶段 spec）

- [ ] Pi Extension 如何在 server 进程里常驻？（进程模型）
- [ ] MCP 桥接：每 session 一次握手，还是连接池？（复用 `mcp_client.py` 的 session 思路）
- [ ] agent_runs / loop_runs 表 schema？（阶段 1 spec）
- [ ] "自由探索型"工作的评估标准？（阶段 2 spec）

---

## 7. 立即行动

**下一步**：启动**阶段 1** 的独立 spec 循环。

- 阶段 1 spec 文件：`docs/superpowers/specs/2026-07-19-agent-dashboard-pi-runtime-design.md`（待写）
- 走标准流程：brainstorm → spec → plan → 实施 → merge

**本愿景文档**只定方向，不进入阶段 1 实现细节。

---

## 附录 A：参考项目对比

| 维度 | Symphony | Pi | 本项目选型 |
|---|---|---|---|
| 语言 | Elixir/OTP | TypeScript | **TypeScript**（栈一致） |
| Agent runtime | Codex app-server | pi-agent-core | **Pi** |
| Turn loop | 自写（1953 行 orchestrator） | SDK 提供 | **Pi 提供**（不写） |
| Tracker | Linear + Memory | 无内置 | **internal-store**（已有） |
| Dashboard | Phoenix LiveView（只读） | TUI | **Next.js**（可交互） |
| Workflow | Orchestrator GenServer | 无 | **自建轻量 scheduler** |
| 看板交互 | 无（纯只读） | 无（CLI） | **分阶段加** |

## 附录 B：术语表

- **turn loop**：agent 单次会话内的"调工具→看结果→再调"循环
- **orchestration loop**：调度器层面的"poll 任务→spawn agent→看状态"循环
- **feedback loop**：人→agent 的 promote/reject/对话循环
- **Pi Extension**：TS 模块，订阅 Pi lifecycle 事件、注册自定义工具
- **job**：loop 引擎里的一个工作单元（含类型、cadence、状态）
- **candidate**：沉淀挖掘型工作的半成品产出，待人 promote/reject
