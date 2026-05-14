# 闭环 Demo：北向资金监控（1 数据源 + 1 Skill + 1 Agent）

## TL;DR

> **Quick Summary**: 用 AKShare 免费 MCP 工具 `stock_hsgt_north_net_flow_in_em` 创建一个北向资金监控 skill + 专属 agent，验证 Agent → Skill → Connector 三层架构的数据闭环。
> 
> **Deliverables**:
> - 新 skill: `plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md`
> - 新 agent: `plugins/agent-plugins/northbound-monitor/` (含 agents/northbound-monitor.md + plugin.json)
> - 垂直插件注册更新: `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json` skills 数组新增条目
> - 同步验证通过: `sync-agent-skills.py` + `validate.py`
> 
> **Estimated Effort**: Quick（3 个实现任务 + 4 个验证任务）
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1/2 (并行) → Task 3 (注册+同步+验证) → Final Verification

---

## Context

### Original Request
用户要求：先完成 1 数据源 + 1 skill + 1 agent 的闭环 demo，必须免费。

### Interview Summary
**Key Discussions**:
- 免费约束 → 只能用 AKShare Server（port 8000），无需 Token
- 场景选择 → 北向资金监控（`stock_hsgt_north_net_flow_in_em`，零参数，数据丰富）
- 输出格式 → 纯 Markdown 报告（参考 market-monitor 模板，不生成 Excel）
- 测试策略 → Demo 不需要单元测试，用 Agent-Executed QA 验证

**Research Findings**:
- AKShare 9 个工具中 7 个未被任何 skill 使用，`stock_hsgt_north_net_flow_in_em` 是其中最简单的（零参数）
- 最简 agent 模板: `market-monitor`（33 行，只读，纯 Markdown）
- Skill 模板: `factor-screen`（152 行，单文件，含完整 Workflow + Guardrails）
- 技能同步机制: `scripts/sync-agent-skills.py` 从垂直插件读取 skills 数组，复制 SKILL.md 到 agent 的 skills/ 目录

### Metis Review
**Identified Gaps** (all addressed):
- market-breadth skill 已存在但只概念性提及北向资金，无实际数据获取 → 新 skill 填补此空白
- 无 `/northbound` 命令 → Demo 不需要命令，agent 直接调用即可
- T+1 延迟 / 非交易日 → Skill 中加入提醒和空数据处理
- 与 market-breadth 命名冲突 → 独立 `northbound-monitor` 作为专用 demo

---

## Work Objectives

### Core Objective
创建一个最小化的三层闭环 demo：Agent 调用 Skill → Skill 调用 AKShare MCP 工具 → 返回北向资金 Markdown 分析报告。

### Concrete Deliverables
- `plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md` — 北向资金监控 skill
- `plugins/agent-plugins/northbound-monitor/.claude-plugin/plugin.json` — Agent 插件元数据
- `plugins/agent-plugins/northbound-monitor/agents/northbound-monitor.md` — Agent 主文件
- `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json` — 更新 skills 数组

### Definition of Done
- [ ] `python scripts/validate.py` 零错误
- [ ] `python scripts/sync-agent-skills.py --check` 显示 northbound-monitor 已注册
- [ ] AKShare server 运行时，agent 能成功调用 `stock_hsgt_north_net_flow_in_em` 并返回 Markdown 报告

### Must Have
- Skill 必须包含 `## Workflow` 和 `## Guardrails` 小节（validate.py 强制要求）
- Agent YAML frontmatter 必须声明 `tools: Read, mcp__akshare__*`
- 所有输出使用中文，技术术语保留英文
- Skill 必须引用 `mcp__akshare__stock_hsgt_north_net_flow_in_em`
- 处理空数据和非交易日的边界情况

### Must NOT Have (Guardrails)
- ❌ 不修改 `mcp-servers/akshare-server/server.py`（任何 MCP server 代码）
- ❌ 不创建 Python 包或 `__init__.py`
- ❌ 不生成 Excel 文件
- ❌ 不引用 Tushare 工具
- ❌ 不使用 web search 获取金融数据
- ❌ 不创建 slash command（demo 不需要）
- ❌ 不修改现有 skill 或 agent
- ❌ 不修改 `market-breadth` skill

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + mock patterns in MCP servers)
- **Automated tests**: None (demo scope — 不添加单元测试)
- **Framework**: N/A for this demo
- **Verification**: Agent-executed QA scenarios only

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Structure validation**: `python scripts/validate.py` + `python scripts/sync-agent-skills.py --check`
- **Runtime verification**: Bash (curl) 调用运行中的 AKShare server，验证 tool 响应格式
- **Content verification**: Read 生成的 .md 文件，检查必需 section

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - 并行创建 skill + agent):
├── Task 1: 创建 northbound-monitor skill [quick]
└── Task 2: 创建 northbound-monitor agent [quick]

Wave 2 (After Wave 1 - 注册 + 同步 + 验证):
└── Task 3: 注册 skill + 同步 + 结构验证 [quick]

Wave FINAL (After ALL tasks — 4 并行审查):
├── Task F1: 计划合规审计 (oracle)
├── Task F2: 文件质量审查 (unspecified-high)
├── Task F3: 端到端 QA (unspecified-high)
└── Task F4: 范围保真检查 (deep)
-> Present results -> Get explicit user okay

Critical Path: T1/T2 (并行) → T3 → F1-F4 → user okay
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 2 (Wave 1) + 4 (Final)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 3 | 1 |
| 2 | - | 3 | 1 |
| 3 | 1, 2 | F1-F4 | 2 |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `quick`, T2 → `quick`
- **Wave 2**: 1 task — T3 → `quick`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. 创建 northbound-monitor Skill

  **What to do**:
  - 创建目录 `plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/`
  - 创建 `SKILL.md`，包含完整的 YAML frontmatter、Workflow、Guardrails
  - Skill 内容要点：
    - 调用 `mcp__akshare__stock_hsgt_north_net_flow_in_em`（零参数）
    - 解析返回字段：日期、当日净买入额、当日资金余额、沪股通/深股通分拆
    - 计算：当日净流入、近5日累计净流入、近20日累计净流入、趋势判断（连续流入/流出天数）
    - 输出 Markdown 报告模板：标题、核心数据、趋势分析、风险提示
    - 处理空数据：返回 "今日暂无北向资金数据（可能为非交易日）" 而非报错
    - 语言：中文为主，技术术语保留英文

  **Must NOT do**:
  - 不引用 Tushare 工具
  - 不生成 Excel
  - 不创建 prompt.md 或 examples/（Demo 阶段不需要）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件创建，模式明确，只需复制现有模板并修改内容
  - **Skills**: []
    - 无需额外 skill，只需 Read 现有模板文件

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `plugins/vertical-plugins/a-share-analysis/skills/factor-screen/SKILL.md` — **主模板**。复制 YAML frontmatter 格式、Workflow 结构、Guardrails 写法、输出格式。注意此 skill 的复杂度远超 demo 需要，只取结构框架，精简内容。
  - `plugins/vertical-plugins/a-share-analysis/skills/market-breadth/SKILL.md` — **参考**。此 skill 已概念性提及北向资金但未实际获取数据。参考其对北向资金的描述方式，但用真实 API 调用替代。

  **API/Type References** (contracts to implement against):
  - `mcp-servers/akshare-server/server.py:130-150` — `stock_hsgt_north_net_flow_in_em()` 函数定义。注意：零参数，返回 DataFrame 经 `df_to_json()` 转换后的 JSON。字段名来自 AKShare 原始列名（日期、当日净买入等）。最大 5000 行。
  - `mcp-servers/akshare-server/server.py:15-30` — `df_to_json()` 工具函数。理解返回格式：`{"data": [...], "count": N}` 或空列表 `[]`。

  **Test References**: N/A（无单元测试）

  **External References**: N/A

  **WHY Each Reference Matters**:
  - `factor-screen/SKILL.md`: 提供完整的 skill 结构模板——YAML frontmatter 的 name/description 格式、Workflow 步骤编号风格、Guardrails bullet point 风格
  - `market-breadth/SKILL.md`: 已有北向资金的中文描述和概念框架，可直接复用分析思路
  - `server.py:130-150`: 必须精确了解 tool 返回的 JSON 字段名，否则 skill 无法正确解析数据

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Skill 文件结构完整性
    Tool: Bash (file check)
    Preconditions: Task 1 已完成
    Steps:
      1. test -f plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md
      2. grep -q "^name:" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md
      3. grep -q "## Workflow" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md
      4. grep -q "## Guardrails" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md
      5. grep -q "mcp__akshare__stock_hsgt_north_net_flow_in_em" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md
    Expected Result: 所有检查返回 exit code 0
    Failure Indicators: 任何一步返回非零退出码
    Evidence: .sisyphus/evidence/task-1-skill-structure.txt

  Scenario: Skill 不包含禁止内容
    Tool: Bash (grep)
    Preconditions: SKILL.md 已创建
    Steps:
      1. grep -c "tushare" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md → 应为 0
      2. grep -c "\.xlsx" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md → 应为 0
      3. grep -c "web_search" plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md → 应为 0
    Expected Result: 所有计数为 0
    Failure Indicators: 任何计数 > 0
    Evidence: .sisyphus/evidence/task-1-skill-guardrails.txt

  Scenario: 运行时数据获取验证（需 AKShare server 运行）
    Tool: Bash (curl)
    Preconditions: AKShare server 运行在 port 8000
    Steps:
      1. curl -s http://localhost:8000/tools/stock_hsgt_north_net_flow_in_em -X POST -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={len(d.get(\"data\",[]))}'); assert len(d.get('data',[])) > 0, 'Empty data'"
    Expected Result: count > 0，输出数据行数
    Failure Indicators: count=0 或 connection refused 或 assert failure
    Evidence: .sisyphus/evidence/task-1-runtime-data.json
  ```

  **Commit**: NO (groups with Task 3)

- [x] 2. 创建 northbound-monitor Agent

  **What to do**:
  - 创建目录 `plugins/agent-plugins/northbound-monitor/.claude-plugin/`
  - 创建 `.claude-plugin/plugin.json`（参考 market-monitor 的格式，8 行 JSON）
  - 创建 `plugins/agent-plugins/northbound-monitor/agents/` 目录
  - 创建 `agents/northbound-monitor.md`，参考 `market-monitor.md` 模板
  - Agent 内容要点：
    - YAML frontmatter: `name: northbound-monitor`, `description: 北向资金监控代理...`, `tools: Read, mcp__akshare__*`
    - 角色描述：北向资金监控专属代理
    - 工作流：加载 northbound-monitor skill → 调用 AKShare 工具 → 生成 Markdown 报告
    - 输出：纯 Markdown（不写文件，不生成 Excel）
    - 语言：中文为主

  **Must NOT do**:
  - 不创建 `__init__.py`
  - 不声明 `Write` 或 `Edit` 工具（只读 agent）
  - 不引用 Tushare 工具
  - 不创建 skills/ 目录下的文件（由 sync 脚本自动生成）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 复制 market-monitor 模板修改，3 个文件创建
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `plugins/agent-plugins/market-monitor/agents/market-monitor.md` — **主模板**。复制 YAML frontmatter 格式（name/description/tools）、Agent 角色描述风格、Workflow 编号格式。这是最简 agent（33 行），在此基础上修改。
  - `plugins/agent-plugins/market-monitor/.claude-plugin/plugin.json` — **plugin.json 模板**。直接复制并修改 name 和 description 字段。

  **API/Type References**:
  - `mcp-servers/akshare-server/server.py:130-150` — 确认 tool 名称 `stock_hsgt_north_net_flow_in_em`，确保 agent YAML 的 `tools` 字段使用 `mcp__akshare__*` 通配符即可覆盖。

  **External References**: N/A

  **WHY Each Reference Matters**:
  - `market-monitor/agents/market-monitor.md`: 提供最简 agent 模板——只读、纯 Markdown 输出、无 Excel。直接基于此修改角色描述和工作流。
  - `market-monitor/.claude-plugin/plugin.json`: 8 行标准格式，照抄改 name/desc 即可。

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Agent 文件结构完整性
    Tool: Bash (file check)
    Preconditions: Task 2 已完成
    Steps:
      1. test -f plugins/agent-plugins/northbound-monitor/.claude-plugin/plugin.json
      2. test -f plugins/agent-plugins/northbound-monitor/agents/northbound-monitor.md
      3. grep -q "^name: northbound-monitor" plugins/agent-plugins/northbound-monitor/agents/northbound-monitor.md
      4. grep -q "mcp__akshare__" plugins/agent-plugins/northbound-monitor/agents/northbound-monitor.md
    Expected Result: 所有检查返回 exit code 0
    Failure Indicators: 任何文件不存在或 grep 无匹配
    Evidence: .sisyphus/evidence/task-2-agent-structure.txt

  Scenario: Agent 不声明 Write/Edit 工具
    Tool: Bash (grep)
    Preconditions: agent .md 文件已创建
    Steps:
      1. head -10 plugins/agent-plugins/northbound-monitor/agents/northbound-monitor.md | grep -c "Write\|Edit" → 应为 0
    Expected Result: 计数为 0
    Failure Indicators: 计数 > 0（agent 不应有写权限）
    Evidence: .sisyphus/evidence/task-2-agent-read-only.txt

  Scenario: Plugin.json 格式正确
    Tool: Bash (python)
    Preconditions: plugin.json 已创建
    Steps:
      1. python3 -c "import json; d=json.load(open('plugins/agent-plugins/northbound-monitor/.claude-plugin/plugin.json')); assert d['name']=='northbound-monitor'; assert 'version' in d; assert 'description' in d; print('OK')"
    Expected Result: 输出 "OK"
    Failure Indicators: JSON 解析失败或 assert 失败
    Evidence: .sisyphus/evidence/task-2-plugin-json.txt
  ```

  **Commit**: NO (groups with Task 3)

- [x] 3. 注册 Skill + 同步 + 结构验证

  **What to do**:
  - 编辑 `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json`，在 `skills` 数组中添加 `"northbound-monitor"`
  - 运行 `python scripts/sync-agent-skills.py` 同步 skill 到 agent 的 `skills/` 目录
  - 运行 `python scripts/validate.py` 验证所有文件结构合规
  - 检查 `plugins/agent-plugins/northbound-monitor/skills/` 目录下是否生成了同步的 SKILL.md

  **Must NOT do**:
  - 不修改 sync 脚本或 validate 脚本
  - 不手动在 agent 的 skills/ 目录下创建文件（由 sync 脚本自动生成）
  - 不修改现有 skill 的注册顺序

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 编辑 1 个 JSON 文件 + 运行 2 个脚本 + 验证
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential after Wave 1)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 1, Task 2

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json` — **必须编辑的文件**。读取当前 `skills` 数组，在末尾追加 `"northbound-monitor"`。注意保持 JSON 格式正确（逗号、缩进）。

  **API/Type References**:
  - `scripts/sync-agent-skills.py` — 理解同步逻辑：从垂直插件 plugin.json 读取 skills 列表 → 找到对应 SKILL.md → 复制到每个 agent 的 skills/ 目录。运行无参数版本执行同步。
  - `scripts/validate.py` — 验证规则：skill 必须有 `## Workflow` 和 `## Guardrails`；agent 必须有 YAML frontmatter；plugin.json 格式正确。

  **External References**: N/A

  **WHY Each Reference Matters**:
  - `vertical-plugin plugin.json`: 这是 skill 注册的入口。如果漏加或格式错误，sync 不会同步 skill，agent 无法使用。
  - `sync-agent-skills.py`: 理解同步机制，确保运行后 agent/skills/ 下有正确的文件。
  - `validate.py`: 最终验证关卡——如果 validate 不通过，所有工作白费。

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Skill 注册成功
    Tool: Bash (python)
    Preconditions: Task 1, 2 已完成，plugin.json 已编辑
    Steps:
      1. python3 -c "import json; d=json.load(open('plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json')); skills=d.get('skills',[]); assert 'northbound-monitor' in skills; print(f'skills count={len(skills)}')"
    Expected Result: skills count 增加 1，northbound-monitor 在列表中
    Failure Indicators: assert 失败或 JSON 解析错误
    Evidence: .sisyphus/evidence/task-3-registration.txt

  Scenario: Sync 同步成功
    Tool: Bash
    Preconditions: plugin.json 已更新
    Steps:
      1. python scripts/sync-agent-skills.py
      2. test -f plugins/agent-plugins/northbound-monitor/skills/northbound-monitor.md
      3. diff plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md plugins/agent-plugins/northbound-monitor/skills/northbound-monitor.md → exit code 0
    Expected Result: agent skills/ 下有同步的文件，内容与源文件一致
    Failure Indicators: 文件不存在或内容不一致
    Evidence: .sisyphus/evidence/task-3-sync.txt

  Scenario: Validate 全通过
    Tool: Bash
    Preconditions: 所有文件就位，sync 已执行
    Steps:
      1. python scripts/validate.py 2>&1
    Expected Result: 退出码 0，无 ERROR 输出
    Failure Indicators: 退出码非 0 或输出包含 "ERROR"
    Evidence: .sisyphus/evidence/task-3-validate.txt

  Scenario: 不存在未追踪的修改
    Tool: Bash (git)
    Preconditions: 所有修改完成
    Steps:
      1. git diff --name-only
    Expected Result: 只有以下文件被修改/新增：
      - plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md (new)
      - plugins/agent-plugins/northbound-monitor/ (new directory)
      - plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json (modified)
      - plugins/agent-plugins/northbound-monitor/skills/northbound-monitor.md (synced)
    Failure Indicators: 出现 mcp-servers/ 下文件或 __init__.py
    Evidence: .sisyphus/evidence/task-3-git-status.txt
  ```

  **Commit**: YES
  - Message: `feat(plugins): add northbound-monitor skill and agent for closed-loop demo`
  - Files: `plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md`, `plugins/agent-plugins/northbound-monitor/**`, `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json`
  - Pre-commit: `python scripts/validate.py && python scripts/sync-agent-skills.py --check`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — oracle
  Output: `Must Have [6/6] | Must NOT Have [5/5] | Tasks [3/3] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — unspecified-high
  Output: `Files [3 clean / 0 issues] | VERDICT: CLEAN`

- [x] F3. **Real Manual QA** — unspecified-high
  Output: `Scenarios [2/4 pass] | VERDICT: PARTIAL` (AKShare FastMCP version bug is pre-existing, not scope of this plan; file-based checks all PASS)

- [x] F4. **Scope Fidelity Check** — deep
  Output: `Tasks [2/2 compliant] | Unaccounted [CLEAN] | VERDICT: PASS`

---

## Commit Strategy

- **Single commit** after all tasks + final verification pass:
  `feat(plugins): add northbound-monitor skill and agent for closed-loop demo`
  - Files: `plugins/vertical-plugins/a-share-analysis/skills/northbound-monitor/SKILL.md`, `plugins/agent-plugins/northbound-monitor/**`, `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json`
  - Pre-commit: `python scripts/validate.py && python scripts/sync-agent-skills.py --check`

---

## Success Criteria

### Verification Commands
```bash
python scripts/validate.py          # Expected: 0 errors
python scripts/sync-agent-skills.py --check  # Expected: northbound-monitor listed
ls plugins/agent-plugins/northbound-monitor/skills/  # Expected: SKILL.md synced
```

### Final Checklist
- [ ] Skill 文件存在且有 Workflow + Guardrails sections
- [ ] Agent 文件存在且有正确的 YAML frontmatter
- [ ] plugin.json 注册正确
- [ ] sync + validate 通过
- [ ] 无 MCP server 代码修改
- [ ] 无 Python 包创建
- [ ] 所有输出中文
