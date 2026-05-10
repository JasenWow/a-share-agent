# 自选股次日涨跌幅预测闭环系统

## TL;DR

> **Quick Summary**: 构建全自动自反馈量化预测系统——用户输入自选股列表，系统每日自动预测次日涨跌幅(%)，次日收盘后自动验证准确率并分析误差模式，基于历史表现调整分析策略，形成持续优化的闭环。
> 
> **Deliverables**:
> - `prediction-store` MCP Server (port 8003) — 预测记录持久化 + 准确率计算 + 误差分析
> - `next-day-predict` Skill — 完整预测工作流（数据获取→特征计算→预测生成→存储验证→误差分析）
> - `daily-predictor` Agent — 编排每日闭环，调度 MCP 工具，管理自反馈迭代
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 2 waves + final verification
> **Critical Path**: MCP Server → Agent → Integration → Verification

---

## Context

### Original Request
构建 1 个 MCP + 1 个核心 Skill + 1 个核心 Agent，完成完整的自反馈量化体系，能够全自动地对用户自选股次日价格涨跌幅进行预测，并持续优化准确率。先完成一个简单闭环。

### Interview Summary
**Key Discussions**:
- 预测目标：涨跌幅百分比（如 +1.5%）
- 自选股来源：手动提供股票代码列表，存储在 prediction-store 中
- 特征范围（V1）：仅 OHLCV 价格 + 成交量 + 技术指标（MA/RSI/MACD/Bollinger/量比）
- 反馈机制：每日闭环（预测→次日验证→误差分析→策略调整）
- 自动化程度：全自动
- 学习方法：LLM 基于历史预测上下文的推理调整（非 ML 模型训练）

**Research Findings**:
- 现有 3 个 MCP server：AKShare(8000)、Tushare(8001)、Internal-Store(8002)
- 现有 6 个 agent、7 个 skill，但无预测存储和自反馈编排能力
- **Skills 不调用 MCP 工具**——Agent 直接通过 `mcp__*` 调用，Skill 仅定义工作流
- AKShare `stock_zh_a_hist` 提供后复权 OHLCV，Tushare `daily` 提供高质量日线数据
- A-share 标签公式：Signal(T) → Trade(T+1) → Return = Close(T+2)/Open(T+1) - 1

### Metis Review
**Identified Gaps** (addressed):
- **T+1 标签对齐**: 预测目标简化为 Close(T+1)/Close(T) - 1（次日收盘相对今日收盘），避免 Open(T+1) 数据对齐问题
- **冷启动策略**: 前 30 天无历史时，预测标记为 `baseline=true`，误差分析在累积 ≥20 条后启动
- **上下文污染**: 限制每次加载最近 20 条误差记录，防止历史噪声过度影响
- **交易节假日**: prediction-store 内置交易日历工具
- **停牌/ST/涨跌停**: 预测时自动跳过，返回 null 并标注原因
- **Watchlist 管理**: 存储在 prediction-store，MCP 工具管理增删查
- **Port 8003 独立**: 遵循 R4（MCP server 自包含），不扩展 internal-store
- **调整不持久化**: V1 中"策略调整"仅在 LLM 会话上下文中发生，不存储为模型参数

---

## Work Objectives

### Core Objective
构建 V1 简单闭环：`/predict` 命令触发 daily-predictor agent → 获取自选股 OHLCV → 计算技术指标 → 生成预测 → 存储 → 次日对比实际 → 分析误差 → 调整策略

### Concrete Deliverables
- `mcp-servers/prediction-store/server.py` — 8 个 MCP 工具
- `mcp-servers/prediction-store/pyproject.toml`
- `mcp-servers/prediction-store/test_server.py`
- `mcp-servers/prediction-store/README.md`
- `plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/SKILL.md`
- `plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/prompt.md`
- `plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/examples/`
- `plugins/agent-plugins/daily-predictor/AGENT.md`
- `plugins/agent-plugins/daily-predictor/system-prompt.md`
- `plugins/agent-plugins/daily-predictor/plugin.json`
- `.mcp.json` 更新（新增 prediction-store）
- 垂直插件注册更新

### Definition of Done
- [ ] `python scripts/check.py` 通过（R1-R5 边界检查）
- [ ] `python scripts/validate.py` 通过（插件结构验证）
- [ ] prediction-store server 启动成功，8 个工具可调用
- [ ] daily-predictor agent 能通过 `/predict` 触发完整闭环流程
- [ ] 预测记录正确存储、次日实际值正确对比、准确率正确计算

### Must Have
- 预测记录的 CRUD（存储、查询、更新实际值）
- 准确率计算（MAE、方向准确率、偏差统计）
- 自选股列表管理（添加、删除、查询）
- 交易日历支持（识别下一交易日）
- 误差分析报告（按股票、按市场状态、按时间段的偏差模式）
- 技术指标计算指导（MA5/10/20、RSI14、MACD、布林带、量比）
- 完整闭环流程（预测→存储→验证→分析→调整）
- A-share 规则遵守（T+1、涨跌停、ST 排除、停牌处理）
- 每日闭环冷启动处理（前 30 天标记 baseline）

### Must NOT Have (Guardrails)
- **无 ML 模型训练** — V1 纯 LLM 推理，不训练任何参数化模型
- **无持久化策略权重** — "调整"仅在 LLM 会话上下文中，不写入数据库
- **无自动交易信号** — 仅预测涨跌幅，不生成买入/卖出指令
- **无基本面因子** — V1 仅使用 OHLCV + 技术指标
- **无市场情绪因子** — 北向资金、龙虎榜等留给 V2
- **无 intra-day 预测** — 仅次日日频预测
- **无超过 20 只股票** — watchlist 硬上限 20
- **Skill 不调用 MCP 工具** — Skill 仅定义工作流步骤，Agent 负责执行
- **Agent 不修改 Skill 文件** — R3 边界规则
- **prediction-store 不导入其他 MCP server 代码** — R4 自包含

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + markers)
- **Automated tests**: Tests-after (MCP server 需要 test_server.py)
- **Framework**: pytest (co-located in mcp-servers/prediction-store/test_server.py)
- **Skill/Agent**: .md 文件，通过实际运行 + agent QA 验证

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **MCP Server**: Use Bash (curl) — 发送请求，断言状态码 + 响应字段
- **Skill/Agent**: Use Bash — 验证文件结构、内容完整性、脚本检查通过

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation, MAX PARALLEL):
├── Task 1: prediction-store MCP server [deep]
└── Task 2: next-day-predict skill [quick]

Wave 2 (After Wave 1 - agent + wiring):
├── Task 3: daily-predictor agent (depends: 1, 2) [unspecified-high]
└── Task 4: Integration wiring (depends: 1, 3) [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: Task 1 → Task 3 → Task 4 → F1-F4 → user okay
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 2 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 3, 4 | 1 |
| 2 | - | 3 | 1 |
| 3 | 1, 2 | 4 | 2 |
| 4 | 1, 3 | F1-F4 | 2 |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `deep`, T2 → `quick`
- **Wave 2**: 2 tasks — T3 → `unspecified-high`, T4 → `quick`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. prediction-store MCP Server (port 8003)

  **What to do**:
  - 创建 `mcp-servers/prediction-store/` 目录结构（server.py, pyproject.toml, test_server.py, README.md）
  - 设计 SQLite 数据模型：
    - `predictions` 表：`id, stock_code, signal_date, predicted_pct, confidence, actual_pct, error, version, baseline, created_at, verified_at`
    - `watchlist` 表：`id, stock_code, stock_name, added_at, is_active`
    - `trading_calendar` 表：`trade_date, is_trading_day`
  - 实现 8 个 `@mcp.tool()` 工具：
    1. `manage_watchlist(action, stock_codes)` — 添加/删除/查询自选股（上限 20 只）
    2. `store_prediction(stock_code, signal_date, predicted_pct, confidence, features_summary)` — 存储单条预测（防重复：同股票+同日期 upsert）
    3. `get_predictions(stock_code=None, signal_date=None, limit=30)` — 查询预测记录
    4. `record_actual(stock_code, signal_date, actual_pct)` — 记录次日实际涨跌幅，自动计算 error=actual-predicted
    5. `batch_record_actual(signal_date, actuals_list)` — 批量记录多只股票实际值
    6. `get_accuracy_report(stock_code=None, days=30)` — 计算 MAE、方向准确率(hit_rate)、平均偏差(bias)、胜率分布
    7. `get_error_analysis(days=30)` — 按股票/按时间段/按偏差方向分析误差模式（如"持续高估小盘股"、"高波动日偏差大"）
    8. `get_next_trading_day(from_date=None)` — 基于内置交易日历返回下一交易日（跳过周末和节假日）
  - 实现输入验证：stock_code 必须为 6 位数字字符串、日期格式 YYYYMMDD、predicted_pct 范围 [-30, 30]
  - 所有工具返回 `list[dict]`，错误返回 `[{"error": "...", "tool": "...", "params": {...}}]`
  - 使用 `logging` 而非 `print()`
  - 编写 `test_server.py`：每个工具至少 1 个 happy path + 1 个 error path 测试
  - 编写 `README.md`：工具列表、参数说明、返回格式

  **Must NOT do**:
  - 不导入 akshare/tushare/internal-store 代码（R4）
  - 不实现 ML 模型或参数存储
  - 不实现自动交易逻辑
  - 不使用 `print()` — 用 `logging`
  - 不返回 `None` — 空 DataFrame 返回 `[]`

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: MCP server 涉及 SQLite schema 设计、8 个工具实现、输入验证、错误处理、测试编写，是本次最复杂的任务
  - **Skills**: `[]`
    - 无需额外 skill，按 FastMCP 标准模式实现

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 3, 4
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `mcp-servers/internal-store/server.py` — MCP server 标准结构（FastMCP app、工具模式、df_to_json、错误处理）
  - `mcp-servers/akshare-server/server.py` — 工具参数定义模式（类型注解、默认值）
  - `mcp-servers/tushare-server/server.py` — Tushare 风格的数据获取模式

  **API/Type References**:
  - `contributing/mcp-servers.md` — FastMCP 工具编写规范、端口分配（下一个可用端口 8003）、mcp_app 导出模式
  - `contributing/coding-standards.md` — ruff 规则、double quotes、120 行宽、import 顺序

  **Test References**:
  - `mcp-servers/internal-store/test_server.py` — MCP server 测试模式
  - `mcp-servers/akshare-server/test_server.py` — happy path + error path 测试结构

  **External References**:
  - FastMCP 官方模式：`mcp = FastMCP("server-name")` → `@mcp.tool()` → `mcp_app = mcp.streamable_http_app()`

  **WHY Each Reference Matters**:
  - `internal-store/server.py` 是最相似的参考——同样用 SQLite 做 persistence，同样有 CRUD 操作
  - `mcp-servers.md` 包含 port assignment 规则和 ASGI export 标准模式
  - 测试文件展示了每个工具至少 2 个测试（成功+失败）的模式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Watchlist CRUD - 添加和查询自选股
    Tool: Bash (curl)
    Preconditions: prediction-store server running on port 8003
    Steps:
      1. curl -X POST http://localhost:8003/tools/call -H "Content-Type: application/json" -d '{"name": "manage_watchlist", "arguments": {"action": "add", "stock_codes": ["000001", "600519", "300750"]}}'
      2. Assert response contains all 3 stocks with status "added"
      3. curl with action="list", assert 3 stocks returned
      4. curl with action="remove", stock_codes=["300750"], assert response shows 2 stocks
      5. curl with action="add", stock_codes=["999999"], assert response contains error "invalid_stock_code"
    Expected Result: Watchlist 增删查正常，非法代码被拒绝
    Failure Indicators: 返回 None、异常未捕获、非法代码被接受
    Evidence: .sisyphus/evidence/task-1-watchlist-crud.txt

  Scenario: 完整预测闭环 - 存储预测→记录实际→计算准确率
    Tool: Bash (curl)
    Preconditions: Watchlist 中有 "000001"
    Steps:
      1. store_prediction(stock_code="000001", signal_date="20260509", predicted_pct=1.5, confidence=0.7)
      2. Assert response contains id, predicted_pct=1.5
      3. record_actual(stock_code="000001", signal_date="20260509", actual_pct=1.2)
      4. Assert response contains error=-0.3
      5. get_accuracy_report(stock_code="000001", days=30)
      6. Assert response contains mae, hit_rate, bias fields
    Expected Result: 预测存储→实际记录→误差计算→准确率报告，全链路正常
    Failure Indicators: error 字段不是 actual-predicted、准确率字段缺失、重复插入报错而非 upsert
    Evidence: .sisyphus/evidence/task-1-prediction-loop.txt

  Scenario: 边界条件 - 重复预测和无效输入
    Tool: Bash (curl)
    Preconditions: 已存在 signal_date="20260509", stock_code="000001" 的预测
    Steps:
      1. 再次 store_prediction 同样的 stock_code+signal_date，predicted_pct=2.0
      2. Assert response shows updated predicted_pct=2.0 (upsert behavior, version incremented)
      3. store_prediction with predicted_pct=50.0 (超出 [-30,30] 范围)
      4. Assert response contains validation error
      5. store_prediction with stock_code="1" (非6位)
      6. Assert response contains validation error
    Expected Result: 重复数据 upsert、超范围值和非法格式被拒绝
    Failure Indicators: 重复插入产生两条记录、超范围值被接受
    Evidence: .sisyphus/evidence/task-1-edge-cases.txt
  ```

  **Evidence to Capture:**
  - [ ] task-1-watchlist-crud.txt
  - [ ] task-1-prediction-loop.txt
  - [ ] task-1-edge-cases.txt

  **Commit**: YES
  - Message: `feat(prediction-store): add prediction persistence MCP server`
  - Files: `mcp-servers/prediction-store/`
  - Pre-commit: `ruff check mcp-servers/prediction-store/`

- [x] 2. next-day-predict Skill（SKILL.md + prompt.md + examples）

  **What to do**:
  - 创建 `plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/` 目录
  - 编写 `SKILL.md`，包含：
    - **触发短语**: `/predict`, "预测", "明天涨跌", "next day predict", "次日预测"
    - **输入表**: 自选股列表（stock_codes）、预测日期（可选，默认今天）
    - **输出**: 预测结果 Markdown 表格 + 准确率趋势 + 误差分析摘要
    - **工具依赖**: `mcp__akshare__stock_zh_a_hist`, `mcp__akshare__stock_zh_a_spot`, `mcp__prediction_store__*`
    - **分步工作流**:
      1. 调用 `manage_watchlist(action="list")` 获取自选股列表
      2. 对每只股票调用 `stock_zh_a_hist` 获取最近 60 天 OHLCV（`adjust="qfq"`）
      3. 计算技术指标（在 LLM 推理中完成，非 MCP 工具）：
         - MA5, MA10, MA20（移动均线）
         - RSI(14)（相对强弱）
         - MACD（DIF, DEA, 柱状线）
         - 布林带（上轨、中轨、下轨）
         - 量比（当日成交量 / 5日平均成交量）
      4. 调用 `get_accuracy_report(days=30)` 获取近期准确率
      5. 调用 `get_error_analysis(days=30)` 获取误差模式
      6. 综合以上信息，对每只股票生成次日涨跌幅预测 + 置信度(0-1)
      7. 对每只股票调用 `store_prediction()` 存储预测
      8. 如果有未验证的历史预测，调用 `stock_zh_a_spot` 获取实际价格，调用 `record_actual()` 记录
      9. 生成预测报告 Markdown
    - **常见错误表**: 涨跌停忘记排除、停牌股票强行预测、前复权数据未使用、预测日期非交易日
    - **质量检查清单**: 股票代码格式、ST/停牌排除、置信度范围 [0,1]、MAE 趋势
  - 编写 `prompt.md`：执行模板，包含上述步骤的 prompt 指令
  - 创建 `examples/input-example.md` 和 `examples/output-example.md`
  - 更新垂直插件 `plugin.json`，在 `skills` 数组中添加 `"next-day-predict"`

  **Must NOT do**:
  - Skill 中不调用任何 MCP 工具（Skill 仅定义工作流，Agent 执行）
  - 不包含 Python 代码（纯 Markdown）
  - 不修改现有 Skill 文件
  - 不定义 ML 训练步骤

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯 Markdown 文件创建，无需编写代码，按现有 skill 模板填充即可
  - **Skills**: `[]`
    - 纯文档任务，无需额外 skill

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/a-share-analysis/skills/factor-screen/SKILL.md` — Skill 标准结构（触发短语、输入表、输出、步骤、常见错误）
  - `plugins/vertical-plugins/a-share-analysis/skills/backtest-engine/SKILL.md` — 回测工作流定义模式（含 A-share 约束）
  - `plugins/vertical-plugins/a-share-analysis/skills/factor-screen/prompt.md` — prompt 模板格式

  **API/Type References**:
  - `contributing/a-share-rules.md` — T+1、涨跌停、交易成本、排除规则
  - `plugins/vertical-plugins/a-share-analysis/plugin.json` — 当前技能列表，需要在此添加新 skill

  **Test References**:
  - `plugins/vertical-plugins/a-share-analysis/skills/factor-screen/examples/` — examples 目录结构

  **WHY Each Reference Matters**:
  - `factor-screen/SKILL.md` 是最完整的 skill 模板参考，包含所有必要结构
  - `backtest-engine/SKILL.md` 展示了如何在工作流中嵌入 A-share 约束
  - `a-share-rules.md` 提供了技术指标计算和排除规则的准确参数

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Skill 文件结构完整性检查
    Tool: Bash
    Preconditions: None
    Steps:
      1. ls plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/
      2. Assert SKILL.md exists
      3. Assert prompt.md exists
      4. Assert examples/ directory exists
      5. grep "trigger" SKILL.md - assert contains "/predict" or "触发"
      6. grep "mcp__prediction_store" SKILL.md - assert references prediction-store tools
      7. grep "stock_zh_a_hist" SKILL.md - assert references AKShare historical data
    Expected Result: 目录结构完整、SKILL.md 包含所有必要段落
    Failure Indicators: 缺少 prompt.md、触发短语缺失、无 MCP 工具引用
    Evidence: .sisyphus/evidence/task-2-skill-structure.txt

  Scenario: 垂直插件注册验证
    Tool: Bash
    Preconditions: plugin.json 已更新
    Steps:
      1. python scripts/validate.py
      2. Assert no errors
      3. grep "next-day-predict" plugins/vertical-plugins/a-share-analysis/plugin.json
      4. Assert skill name found in skills array
    Expected Result: 验证通过，skill 已注册
    Failure Indicators: validate.py 报错、skill 名称未在 plugin.json 中
    Evidence: .sisyphus/evidence/task-2-plugin-registration.txt
  ```

  **Evidence to Capture:**
  - [ ] task-2-skill-structure.txt
  - [ ] task-2-plugin-registration.txt

  **Commit**: YES
  - Message: `feat(skills): add next-day-predict skill`
  - Files: `plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/`, `plugins/vertical-plugins/a-share-analysis/plugin.json`
  - Pre-commit: `python scripts/validate.py`

- [ ] 3. daily-predictor Agent（AGENT.md + system-prompt.md + plugin.json）

  **What to do**:
  - 创建 `plugins/agent-plugins/daily-predictor/` 目录
  - 编写 `AGENT.md`，四段结构：
    - **Persona**: 一位严谨的量化分析师，专注于 A 股次日涨跌幅预测。每日执行预测闭环，基于历史表现持续优化分析策略。
    - **Deliverables**: 
      - 每日预测报告（Markdown 表格：股票代码、当前价、预测涨跌幅、置信度、关键信号）
      - 准确率跟踪报告（MAE 趋势、方向准确率、偏差模式）
      - 误差分析报告（系统性偏差识别、改进建议）
    - **Workflow**:
      1. 获取自选股列表 → 2. 获取 OHLCV 数据 → 3. 计算技术指标 → 4. 查询历史准确率 → 5. 查询误差模式 → 6. 生成预测 → 7. 存储预测 → 8. 验证昨日预测 → 9. 记录实际值 → 10. 生成报告
    - **Guardrails**: 
      - V1 仅使用 OHLCV + 技术指标，不使用基本面/情绪因子
      - 置信度 < 0.3 时输出 "NO_SIGNAL"
      - 排除 ST/*ST、停牌（volume=0）、上市不足 30 天、涨跌停股票
      - 跳过 prediction-store 中无数据的非交易日
      - 每次最多加载最近 20 条误差记录到上下文（防止上下文污染）
      - 冷启动阶段（<20 条历史）标记预测为 baseline，不做深度误差分析
  - 编写 `system-prompt.md`，包含：
    - 身份定义
    - 可用工具列表（`mcp__akshare__*`, `mcp__prediction_store__*`）
    - 技术指标计算指导（MA/RSI/MACD/布林带/量比的公式和解读）
    - A-share 约束（T+1、涨跌停、排除规则）
    - 预测方法论指导（趋势跟踪、均值回归、动量反转等策略概述）
    - 误差分析方法论（偏差归因、时间模式、股票特征模式）
    - 输出格式模板
    - 禁止行为清单
  - 编写 `plugin.json`：
    - name: "daily-predictor"
    - display_name: "Daily Predictor / 次日预测"
    - type: "agent"
    - skills: `["next-day-predict"]`
    - mcp_dependencies: `["akshare", "prediction-store"]`
    - 注册 `/predict` 命令
  - 创建命令文件 `plugins/vertical-plugins/a-share-analysis/commands/predict.md`（如不存在则创建）

  **Must NOT do**:
  - 不修改 next-day-predict SKILL.md（R3）
  - 不实现 ML 模型训练逻辑
  - 不生成自动交易指令
  - 不在 Agent 中硬编码股票列表
  - 不超过 20 只自选股

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Agent 需要综合参考现有 6 个 agent 的结构模式、正确引用 MCP 工具、设计合理的预测方法论，工作量大且需要质量保证
  - **Skills**: `[]`
    - Agent 创建是文档工作，参考现有 agent 模板即可

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Task 4, but T4 depends on T3)
  - **Blocks**: Task 4
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `plugins/agent-plugins/backtester/agents/AGENT.md` — 完整的 agent 四段结构模板
  - `plugins/agent-plugins/factor-analyst/agents/AGENT.md` — 因子分析 agent 的方法论描述模式
  - `plugins/agent-plugins/market-monitor/agents/AGENT.md` — 持续监控型 agent 的设计模式
  - `plugins/agent-plugins/backtester/agents/system-prompt.md` — 完整系统 prompt 模板（含工具列表、A-share 约束、输出格式）
  - `plugins/agent-plugins/backtester/agents/plugin.json` — plugin.json 标准结构

  **API/Type References**:
  - `contributing/a-share-rules.md` — 技术指标在 A-share 语境下的使用注意事项
  - `.mcp.json` — 现有 MCP server 配置，需要新增 prediction-store

  **Test References**:
  - `plugins/agent-plugins/*/agents/plugin.json` — 6 个现有 agent 的 plugin.json 用于参考格式

  **WHY Each Reference Matters**:
  - `backtester` agent 与 daily-predictor 最相似——都涉及策略执行 + 结果验证 + 报告生成
  - `factor-analyst` 展示了如何描述因子方法论（daily-predictor 需要描述技术指标方法论）
  - `market-monitor` 展示了持续运行型 agent 的设计
  - `system-prompt.md` 是 agent 的核心——需要包含完整的工具调用指南和约束

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Agent 文件结构完整性
    Tool: Bash
    Preconditions: Task 1, 2 complete
    Steps:
      1. ls plugins/agent-plugins/daily-predictor/
      2. Assert AGENT.md, system-prompt.md, plugin.json all exist
      3. grep "persona\|Persona\|Workflow\|Guardrail" AGENT.md - assert 4 sections present
      4. grep "mcp__prediction_store" system-prompt.md - assert references prediction-store tools
      5. grep "mcp__akshare" system-prompt.md - assert references AKShare tools
      6. grep "next-day-predict" plugin.json - assert skill reference exists
      7. grep "prediction-store" plugin.json - assert MCP dependency exists
    Expected Result: Agent 三文件完整，包含必要的工具引用和约束
    Failure Indicators: 缺少文件、无 MCP 工具引用、无 skill 引用
    Evidence: .sisyphus/evidence/task-3-agent-structure.txt

  Scenario: 边界规则合规性检查
    Tool: Bash
    Preconditions: All agent files created
    Steps:
      1. python scripts/check.py
      2. Assert all R1-R5 checks pass
      3. grep -r "import.*plugins" mcp-servers/prediction-store/ - assert NO results (R1)
      4. grep -r "daily_predictor\|daily-predictor" plugins/vertical-plugins/a-share-analysis/skills/next-day-predict/ - assert NO agent references (R2)
    Expected Result: 所有边界检查通过，无跨层引用
    Failure Indicators: check.py 失败、发现跨层 import
    Evidence: .sisyphus/evidence/task-3-boundary-check.txt
  ```

  **Evidence to Capture:**
  - [ ] task-3-agent-structure.txt
  - [ ] task-3-boundary-check.txt

  **Commit**: YES
  - Message: `feat(agents): add daily-predictor agent`
  - Files: `plugins/agent-plugins/daily-predictor/`, `plugins/vertical-plugins/a-share-analysis/commands/predict.md`
  - Pre-commit: `python scripts/check.py`

- [ ] 4. 系统集成与注册（.mcp.json + 垂直插件 + 同步）

  **What to do**:
  - 更新 `.mcp.json`，新增 prediction-store 配置：
    ```json
    "prediction-store": {
      "type": "http",
      "url": "http://localhost:8003/mcp"
    }
    ```
  - 更新垂直插件 `plugins/vertical-plugins/a-share-analysis/.mcp.json`（如果存在），添加 prediction-store
  - 运行 `python scripts/sync-agent-skills.py` 将 next-day-predict skill 同步到 daily-predictor agent 目录
  - 运行 `python scripts/check.py` 验证所有 R1-R5 规则通过
  - 运行 `python scripts/validate.py` 验证插件结构
  - 手动验证 prediction-store server 能启动：
    ```bash
    uvicorn mcp-servers.prediction-store.server:mcp_app --port 8003
    ```

  **Must NOT do**:
  - 不修改现有 MCP server 代码
  - 不修改现有 Agent 的文件
  - 不改变现有端口分配

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 主要是配置文件修改和脚本运行，工作量小
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential after Task 3)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1, 3

  **References**:

  **Pattern References**:
  - `.mcp.json` — 现有 MCP server 注册格式
  - `plugins/vertical-plugins/a-share-analysis/.mcp.json` — 垂直插件的 MCP 依赖声明（如果存在）

  **WHY Each Reference Matters**:
  - `.mcp.json` 格式必须完全匹配现有条目，否则 agent 无法连接到新 server

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 全系统检查通过
    Tool: Bash
    Preconditions: All previous tasks complete
    Steps:
      1. python scripts/check.py
      2. Assert exit code 0 and "All checks passed"
      3. python scripts/validate.py
      4. Assert exit code 0
      5. python scripts/sync-agent-skills.py --check
      6. Assert no sync errors
    Expected Result: 所有检查通过
    Failure Indicators: check.py 报错、validate.py 报错、同步失败
    Evidence: .sisyphus/evidence/task-4-system-check.txt

  Scenario: prediction-store server 启动验证
    Tool: Bash
    Preconditions: None
    Steps:
      1. uvicorn mcp-servers.prediction-store.server:mcp_app --port 8003 &
      2. sleep 3
      3. curl -s http://localhost:8003/health (or equivalent endpoint)
      4. Assert server responds
      5. curl manage_watchlist tool with action="list"
      6. Assert returns empty list []
      7. kill background process
    Expected Result: Server 启动正常，工具可调用
    Failure Indicators: Server 启动失败、端口冲突、工具调用超时
    Evidence: .sisyphus/evidence/task-4-server-startup.txt
  ```

  **Evidence to Capture:**
  - [ ] task-4-system-check.txt
  - [ ] task-4-server-startup.txt

  **Commit**: YES
  - Message: `chore: wire prediction-store and daily-predictor into system`
  - Files: `.mcp.json`, `plugins/vertical-plugins/a-share-analysis/.mcp.json`, `plugins/vertical-plugins/a-share-analysis/plugin.json`
  - Pre-commit: `python scripts/check.py && python scripts/validate.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `python scripts/check.py` + `python scripts/validate.py` + `ruff check mcp-servers/prediction-store/`. Review all changed files for: bare `except`, mutable defaults, `print()` in production, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Check [PASS/FAIL] | Validate [PASS/FAIL] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start prediction-store server. Execute full closed loop: store watchlist → generate prediction → store prediction → simulate next-day → record actual → get accuracy report → get error analysis. Verify each step with curl. Save all evidence.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect unaccounted changes. Verify R1-R5 boundary compliance.
  Output: `Tasks [N/N compliant] | Boundaries [CLEAN/N violations] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat(prediction-store): add prediction persistence MCP server` — server.py, pyproject.toml, test_server.py, README.md
- **Task 2**: `feat(skills): add next-day-predict skill` — SKILL.md, prompt.md, examples/
- **Task 3**: `feat(agents): add daily-predictor agent` — AGENT.md, system-prompt.md, plugin.json
- **Task 4**: `chore: wire prediction-store and daily-predictor into system` — .mcp.json, plugin.json updates

---

## Success Criteria

### Verification Commands
```bash
python scripts/check.py          # Expected: All checks passed
python scripts/validate.py       # Expected: All validations passed
ruff check mcp-servers/prediction-store/  # Expected: 0 errors
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] prediction-store 8 tools all callable
- [ ] daily-predictor agent triggered via command
- [ ] Full closed loop (predict→verify→analyze) works end-to-end
- [ ] A-share rules enforced (T+1, exclusions, stock code format)
- [ ] Cold-start handled gracefully
