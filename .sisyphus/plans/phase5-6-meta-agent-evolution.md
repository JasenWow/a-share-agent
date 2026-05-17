# Phase 5+6: Meta-Agent Self-Evolution — Script Generator + Agent/MCP Modifier

## TL;DR

> **Quick Summary**: 实现 Meta-Agent 自我进化能力的最后两个阶段——Phase 5 脚本生成器（让 Meta-Agent 生成新因子/策略 Python 脚本）和 Phase 6 Agent 修改器 + MCP 工具添加器（让 Meta-Agent 修改 Agent 定义和扩展 MCP 服务器）。
> 
> **Deliverables**:
> - `simulation/skills/script-generator/` — 脚本生成技能 (SKILL.md + 2 generator scripts + tests)
> - `simulation/skills/agent-modifier/` — Agent 定义修改技能 (SKILL.md + modify_agent.py + tests)
> - `simulation/skills/mcp-tool-adder/` — MCP 工具添加技能 (SKILL.md + add_mcp_tool.py + tests)
> - `meta-strategist` plugin.json + manifest 更新（新增 script-generator, agent-modifier, mcp-tool-adder 技能引用）
> - `contributing/architecture.md` 更新（Meta-Agent Phase 2+3 自主权表）
> 
> **Estimated Effort**: Medium (6 implementation tasks + 4 verification tasks)
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: T1 → T2 → T3 → T4-T6 (parallel) → F1-F4

---

## Context

### Original Request
用户要求继续 `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md` 路线图实施。Phase 1-4 已全部完成，剩余 Phase 5 (Script Generator) 和 Phase 6 (Meta-Agent Phase 3)。

### Interview Summary
**Key Discussions**:
- **Scope**: Phase 5 + Phase 6（路线图最后两个阶段）
- **实现方式**: 沿用 Phase 2-3 的 TDD 方法
- **技能位置**: 所有新技能放在 `plugins/vertical-plugins/simulation/skills/` 下
- **生成脚本存放**: `simulation/skills/script-generator/generated/` 临时目录，验证通过后可手动迁移到 `market-data/skills/`
- **自修改防护**: meta-strategist 不能修改自身 plugin.json 或 manifest
- **回滚策略**: Phase 6 修改前自动 git commit，失败可 revert
- **R6 合规**: mcp-tool-adder 生成的工具必须通过 R6 检查

**Research Findings**:
- Phase 1-4 全部实现完毕，commit `63a2cfe` 为最新提交
- Trading simulator 完整实现 (305行 simulator.py + 147行 market_rules.py)
- Evolution loop 完整 (evolution.py + generate_hypothesis.py + tests)
- Meta-strategist system-prompt.md 已有130行进化协议描述
- Internal-store 有 experiments, transitions, episode_summaries 6个表
- 测试基础设施: pytest 8.0+, 84个测试用例, 8个测试文件
- 测试命名冲突: 3个 MCP server 的 test_server.py 冲突（不影响新任务）

### Metis Review
**Identified Gaps** (all addressed):
- **CRITICAL — 自修改防护**: meta-strategist 不能修改自己的 plugin.json → modify_agent.py 添加 agent_name == "meta-strategist" 检查，拒绝修改
- **HIGH — 回滚策略**: Phase 6 修改生产文件 → 每次修改前创建 git commit 作为回滚点
- **HIGH — 生成脚本目标目录**: 不明确 → 使用 `simulation/skills/script-generator/generated/`，不注册为正式技能
- **HIGH — Phase 6 缺少 TDD**: 最高风险操作无测试 → 每个 Phase 6 技能都添加测试文件
- **MEDIUM — 碰撞检测**: 脚本名/工具名冲突 → 生成前检查是否已存在，冲突则拒绝
- **MEDIUM — R6 合规验证**: 生成 MCP 工具可能违反 R6 → add_mcp_tool.py 添加 domain keyword 检查
- **MEDIUM — 验收标准模糊**: → 每个任务添加可执行的验收命令

---

## Work Objectives

### Core Objective
让 Meta-Strategist Agent 获得三层自主进化能力：(1) 生成新因子/策略 Python 脚本, (2) 修改 Agent 定义, (3) 扩展 MCP 服务器工具。

### Concrete Deliverables
- `plugins/vertical-plugins/simulation/skills/script-generator/SKILL.md`
- `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_factor_script.py`
- `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_strategy_script.py`
- `plugins/vertical-plugins/simulation/skills/script-generator/test_script_generator.py`
- `plugins/vertical-plugins/simulation/skills/agent-modifier/SKILL.md`
- `plugins/vertical-plugins/simulation/skills/agent-modifier/scripts/modify_agent.py`
- `plugins/vertical-plugins/simulation/skills/agent-modifier/test_modify_agent.py`
- `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/SKILL.md`
- `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts/add_mcp_tool.py`
- `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/test_add_mcp_tool.py`
- `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json` (updated)
- `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md` (updated)
- `plugins/agent-plugins/meta-strategist/agents/system-prompt.md` (updated)
- `contributing/architecture.md` (updated with Phase 2+3 autonomy table)

### Definition of Done
- [ ] `uv run python scripts/check.py` → exit code 0
- [ ] `uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v` → all pass
- [ ] `uv run pytest plugins/vertical-plugins/simulation/skills/agent-modifier/ -v` → all pass
- [ ] `uv run pytest plugins/vertical-plugins/simulation/skills/mcp-tool-adder/ -v` → all pass
- [ ] meta-strategist plugin.json has all 6 skills (3 existing + 3 new)
- [ ] modify_agent.py rejects self-modification of meta-strategist
- [ ] add_mcp_tool.py rejects tools with domain logic keywords

### Must Have
- script-generator 生成有效的 Python 因子/策略脚本模板（ruff check 通过）
- agent-modifier 修改 plugin.json skills 数组和 .md guardrails（通过 check.py）
- mcp-tool-adder 添加新 @mcp.tool() 到 MCP server（遵循 FastMCP 模式）
- 自修改防护: meta-strategist 不能修改自身定义
- 碰撞检测: 文件名/工具名冲突时拒绝生成
- R6 合规: 生成的 MCP 工具只包含数据访问逻辑

### Must NOT Have (Guardrails)
- **NO ML/LLM 依赖** — 脚本生成器输出模板代码，不调用 AI
- **NO meta-strategist 自修改** — modify_agent.py 必须拒绝修改 meta-strategist
- **NO 修改 check.py** — 不改动边界规则检查器
- **NO 改动 akshare-server 或 tushare-server** — mcp-tool-adder 仅操作 internal-store
- **NO 生成的脚本自动注册为正式技能** — 生成到 `generated/` 子目录，需手动审核后迁移
- **NO 热加载 MCP 工具** — 添加工具后需重启服务器
- **NO 修改已有 MCP 工具** — 只添加新工具，不修改/删除已有工具
- **NO domain logic in MCP tools** — add_mcp_tool.py 模板强制 R6 合规

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest 8.0+)
- **Automated tests**: YES (TDD for all 3 new skills)
- **Framework**: pytest
- **TDD scope**: All Phase 5+6 tasks (script-generator, agent-modifier, mcp-tool-adder)

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python TDD**: Use Bash (`uv run pytest`)
- **Config verification**: Use Bash (`cat`, `grep`, `uv run python scripts/check.py`)
- **File integrity**: Use Bash (`git status`, `git diff`)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── T1: script-generator SKILL.md + generate_factor_script.py (TDD) [deep]
└── T2: script-generator generate_strategy_script.py + integration tests [quick]

Wave 2 (After T1, T2 — core Phase 6, ALL parallel):
├── T3: agent-modifier SKILL.md + modify_agent.py (TDD, self-mod block) [deep]
├── T4: mcp-tool-adder SKILL.md + add_mcp_tool.py (TDD, R6 check) [deep]
└── T5: Update meta-strategist plugin.json + system-prompt.md [quick]

Wave 3 (After T3, T4, T5 — integration):
└── T6: Update contributing/architecture.md + run check.py verification [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real QA execution (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T3 → T5 → T6 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 3 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T2, T3 | 1 |
| T2 | T1 | T5 | 1 |
| T3 | — | T5, T6 | 2 |
| T4 | — | T5, T6 | 2 |
| T5 | T1, T3, T4 | T6 | 2 |
| T6 | T5 | F1-F4 | 3 |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `deep`, T2 → `quick`
- **Wave 2**: 3 tasks — T3 → `deep`, T4 → `deep`, T5 → `quick`
- **Wave 3**: 1 task — T6 → `quick`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 1. Script Generator SKILL.md + generate_factor_script.py (TDD)

  **What to do**:
  - **TDD RED**: Write `test_script_generator.py` first with test cases:
    1. `test_factor_script_has_required_sections` — 验证生成的脚本包含 docstring, import, compute_* 函数
    2. `test_factor_script_naming_convention` — 文件名匹配 `compute_<factor_name>.py`
    3. `test_factor_script_passes_ruff_check` — 生成的脚本通过 ruff check
    4. `test_factor_script_collision_detection` — 已有同名文件时拒绝生成
    5. `test_factor_script_no_mcp_imports` — 不引入 mcp-servers/ 或 agent-plugins/ 模块
    6. `test_save_factor_script_creates_file` — save_factor_script 正确写入文件
  - **TDD GREEN**: Implement:
    - Create `plugins/vertical-plugins/simulation/skills/script-generator/SKILL.md` following contributing/playbooks.md template:
      - name: `script-generator`
      - description: 生成新因子/策略 Python 脚本，供 Meta-Agent 在模拟中使用
      - Inputs: script_type ("factor" or "strategy"), description (自然语言描述)
      - Outputs: script_path, validation_result
      - Constraints: 不调用 AI，仅模板填充；碰撞检测；R6 合规
    - Create `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_factor_script.py`:
      - `FACTOR_TEMPLATE` 常量：包含 docstring, pandas/numpy import, `compute_<name>(df, **params)` 函数签名
      - `generate_factor_script(factor_name: str, description: str, implementation: str) -> str`: 生成脚本内容
      - `validate_factor_script(script: str) -> tuple[bool, str]`: ruff check + import 检查 + 命名检查
      - `save_factor_script(factor_name: str, script: str, target_dir: Path) -> Path`: 碰撞检测 + 写入 `target_dir/generated/compute_<name>.py`
    - Create `plugins/vertical-plugins/simulation/skills/script-generator/scripts/__init__.py` (empty)
  - **TDD REFACTOR**: Clean up if needed
  - Create `plugins/vertical-plugins/simulation/skills/script-generator/generated/.gitkeep` (确保目录存在)

  **Must NOT do**:
  - Do NOT 调用任何 AI/LLM API — 仅模板填充
  - Do NOT 自动注册生成的脚本为正式技能
  - Do NOT 将生成脚本放入 `market-data/skills/` — 仅放入 `script-generator/generated/`
  - Do NOT 允许覆盖已有文件 — 碰撞时 raise FileExistsError

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心模块实现 + TDD 纪律
  - **Skills**: [`test-driven-development`]
    - `test-driven-development`: 严格 RED-GREEN-REFACTOR 循环

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T4 in different wave)
  - **Parallel Group**: Wave 1
  - **Blocks**: T2, T5
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/evolution.py` — 同目录下的 skill 脚本模式，遵循相同的 dataclass + 函数风格
  - `plugins/vertical-plugins/simulation/skills/experiment-tracker/SKILL.md` — SKILL.md 模板参考（heading 结构、Inputs/Outputs/Steps 格式）
  - `contributing/playbooks.md` — 添加 skill 的 playbook，SKILL.md 必须遵循此格式

  **API/Type References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py` — 因子库常量 `FACTOR_LIBRARY`（12个因子名），生成的脚本应与此命名对齐
  - `plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/simulator.py:1-40` — 数据类型定义（Order, Execution, PortfolioState），策略脚本可能需要引用

  **Test References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py` — TDD 测试模式参考（imports, assertions, seed-based reproducibility）

  **WHY Each Reference Matters**:
  - `evolution.py`: 同一 simulation/skills/ 下的脚本，风格必须一致
  - `experiment-tracker/SKILL.md`: 遵循已有 SKILL.md 格式，不另创新格式
  - `FACTOR_LIBRARY`: 生成脚本的因子名应与此库对齐

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All script-generator tests pass
    Tool: Bash
    Preconditions: test_script_generator.py and generate_factor_script.py created
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/test_script_generator.py -v
    Expected Result: >=5 tests collected, 0 failures, 0 errors
    Failure Indicators: Any test FAIL or ERROR status
    Evidence: .sisyphus/evidence/task-1-script-gen-tests.txt

  Scenario: Generated factor script is syntactically valid
    Tool: Bash
    Preconditions: generate_factor_script.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/script-generator/scripts')
         from generate_factor_script import generate_factor_script, validate_factor_script
         script = generate_factor_script('test_momentum', '20日动量因子', 'result = df["close"].pct_change(20)')
         valid, reason = validate_factor_script(script)
         assert valid, f'Validation failed: {reason}'
         print('OK: generated script is valid')
         print(script[:200])
         "
    Expected Result: "OK: generated script is valid" + script preview
    Failure Indicators: AssertionError or import error
    Evidence: .sisyphus/evidence/task-1-generated-script.txt

  Scenario: Collision detection prevents overwrite
    Tool: Bash
    Preconditions: generate_factor_script.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/script-generator/scripts')
         from generate_factor_script import save_factor_script
         from pathlib import Path
         import tempfile, os
         with tempfile.TemporaryDirectory() as tmpdir:
             # Create existing file
             target = Path(tmpdir) / 'compute_test.py'
             target.write_text('existing')
             try:
                 save_factor_script('test', 'placeholder', Path(tmpdir))
                 print('FAIL: should have raised FileExistsError')
             except FileExistsError:
                 print('OK: collision detected, overwrite prevented')
         "
    Expected Result: "OK: collision detected, overwrite prevented"
    Failure Indicators: File silently overwritten
    Evidence: .sisyphus/evidence/task-1-collision-detection.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add script-generator skill for Meta-Agent Phase 2`
  - Files: `plugins/vertical-plugins/simulation/skills/script-generator/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v`

- [ ] 2. Script Generator generate_strategy_script.py + Integration Tests

  **What to do**:
  - Create `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_strategy_script.py`:
    - `STRATEGY_TEMPLATE` 常量：包含 docstring, import, `run_strategy(params: dict) -> dict` 函数签名
    - `generate_strategy_script(strategy_name: str, description: str, signal_logic: str, position_sizing: str) -> str`
    - `validate_strategy_script(script: str) -> tuple[bool, str]`: ruff check + import 检查
    - `save_strategy_script(strategy_name: str, script: str, target_dir: Path) -> Path`: 碰撞检测
  - Add tests to `test_script_generator.py`:
    - `test_strategy_script_has_required_sections` — docstring, import, run_strategy 函数
    - `test_strategy_script_passes_ruff_check` — 生成的脚本通过 ruff
    - `test_strategy_script_collision_detection` — 碰撞检测
  - Verify all tests pass together: `uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v`

  **Must NOT do**:
  - Do NOT 复制 generate_factor_script.py 的代码 — 共享的碰撞检测逻辑可提取为 helper
  - Do NOT 添加对外部信号库的依赖（如 ta-lib）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 与 T1 同结构，仅需适配模板
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (follows T1)
  - **Parallel Group**: Wave 1 (sequential with T1)
  - **Blocks**: T5
  - **Blocked By**: T1

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_factor_script.py` (from T1) — 完全相同的模式，仅替换模板内容

  **API/Type References**:
  - `plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/run_simulation.py` — 策略脚本应与 run_simulation 的接口对齐（接收参数 → 返回回测结果）

  **WHY Each Reference Matters**:
  - `generate_factor_script.py`: 直接复用碰撞检测和验证模式
  - `run_simulation.py`: 策略脚本的输入/输出格式应与此对齐

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All script-generator tests pass including strategy tests
    Tool: Bash
    Preconditions: generate_strategy_script.py created
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v
    Expected Result: All tests pass (factor + strategy), 0 failures
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-2-all-tests.txt

  Scenario: Generated strategy script is valid
    Tool: Bash
    Preconditions: generate_strategy_script.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/script-generator/scripts')
         from generate_strategy_script import generate_strategy_script, validate_strategy_script
         script = generate_strategy_script('momentum_long', '动量多头策略', 'signal = df.close.pct_change(20)', 'equal_weight = 1/n')
         valid, reason = validate_strategy_script(script)
         assert valid, f'Validation failed: {reason}'
         print('OK: strategy script valid')
         "
    Expected Result: "OK: strategy script valid"
    Failure Indicators: Validation failure or import error
    Evidence: .sisyphus/evidence/task-2-strategy-script.txt
  ```

  **Commit**: YES (grouped with T1 if sequential)
  - Message: `feat(simulation): add script-generator skill for Meta-Agent Phase 2`
  - Files: `plugins/vertical-plugins/simulation/skills/script-generator/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v`

- [ ] 3. Agent Modifier SKILL.md + modify_agent.py (TDD + Self-Modification Prevention)

  **What to do**:
  - **TDD RED**: Write `test_modify_agent.py` first with test cases:
    1. `test_add_skill_to_plugin_json` — 成功添加 skill 引用到 plugin.json
    2. `test_add_skill_no_duplicate` — 已有 skill 时不重复添加
    3. `test_add_skill_invalid_agent` — 不存在的 agent 返回 False
    4. `test_add_guardrail_to_manifest` — 成功添加 guardrail 到 .md 文件
    5. `test_self_modification_blocked` — meta-strategist 修改自身被拒绝
    6. `test_rollback_on_failure` — 修改失败时恢复原文件
    7. `test_check_py_passes_after_modification` — 修改后 check.py 通过
    8. `test_persona_section_unchanged` — "What you produce" 和 "## Guardrails" 以外的 persona 不变
  - **TDD GREEN**: Implement:
    - Create `plugins/vertical-plugins/simulation/skills/agent-modifier/SKILL.md`:
      - name: `agent-modifier`
      - description: 修改 Agent 定义（添加 skill 引用、guardrails），受自修改防护和 check.py 约束
      - Constraints: 不能修改 meta-strategist 自身；修改后必须通过 check.py；只能修改 skill 引用和 guardrails
    - Create `plugins/vertical-plugins/simulation/skills/agent-modifier/scripts/modify_agent.py`:
      - `BLOCKED_AGENTS = ["meta-strategist"]` — 自修改防护列表
      - `update_agent_skill_references(agent_dir: Path, new_skill: str) -> bool`: 添加 skill 到 plugin.json
        - 检查 agent_name not in BLOCKED_AGENTS
        - 读取 plugin.json，解析 JSON
        - 检查 skill 是否已存在（去重）
        - 添加 skill（格式 `<vertical>:<skill-name>`）
        - 写回 plugin.json
        - 运行 check.py 验证
        - 如果 check.py 失败，回滚到原内容
      - `update_agent_guardrails(agent_md_path: Path, new_guardrail: str) -> bool`: 添加 guardrail
        - 备份原文件
        - 在 "## Guardrails" section 添加新条目
        - 如果没有 Guardrails section，创建 "## Additional Guardrails"
        - 运行 check.py 验证
        - 失败则回滚
      - `validate_modification(agent_dir: Path) -> bool`: 运行 check.py 验证
    - Create `plugins/vertical-plugins/simulation/skills/agent-modifier/scripts/__init__.py` (empty)
  - **TDD REFACTOR**: Clean up

  **Must NOT do**:
  - Do NOT 允许修改 meta-strategist — BLOCKED_AGENTS 硬编码
  - Do NOT 修改 agent persona（"What you produce", Workflow 描述等核心内容）
  - Do NOT 跳过 check.py 验证 — 每次修改后必须通过
  - Do NOT 添加无 rollback 的操作

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 高风险自修改逻辑 + 回滚机制 + TDD
  - **Skills**: [`test-driven-development`]
    - `test-driven-development`: 严格 RED-GREEN-REFACTOR，这是最高风险模块

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T4, T5)
  - **Parallel Group**: Wave 2
  - **Blocks**: T5, T6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `plugins/agent-plugins/equity-researcher/.claude-plugin/plugin.json` — plugin.json 格式，了解 skills 数组结构
  - `plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md` — Agent manifest 格式，找到 Guardrails section 的位置

  **API/Type References**:
  - `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json` — 必须阻止修改的目标文件，了解当前 skills 数组
  - `scripts/check.py:1-170` — 边界规则检查器，了解 R1-R6 验证逻辑，确保修改后的 plugin.json 能通过检查

  **Test References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py` — TDD 测试模式参考

  **External References**:
  - `contributing/architecture.md:R1-R6` — 边界规则定义，理解哪些修改是允许的

  **WHY Each Reference Matters**:
  - `equity-researcher/plugin.json`: 修改目标格式，必须与此结构一致
  - `meta-strategist/plugin.json`: 自修改防护的测试目标
  - `check.py`: 每次修改后必须通过此检查，理解其逻辑才能生成合规的修改

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All agent-modifier tests pass
    Tool: Bash
    Preconditions: test_modify_agent.py and modify_agent.py created
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/skills/agent-modifier/test_modify_agent.py -v
    Expected Result: >=7 tests, 0 failures, 0 errors
    Failure Indicators: Any test FAIL or ERROR
    Evidence: .sisyphus/evidence/task-3-agent-modifier-tests.txt

  Scenario: Self-modification of meta-strategist is blocked
    Tool: Bash
    Preconditions: modify_agent.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/agent-modifier/scripts')
         from modify_agent import update_agent_skill_references
         from pathlib import Path
         result = update_agent_skill_references(Path('plugins/agent-plugins/meta-strategist'), 'fake-skill')
         assert result == False, 'Self-modification should be blocked!'
         print('OK: meta-strategist self-modification blocked')
         "
    Expected Result: "OK: meta-strategist self-modification blocked"
    Failure Indicators: result == True (modification allowed)
    Evidence: .sisyphus/evidence/task-3-self-mod-block.txt

  Scenario: Adding skill to equity-researcher passes check.py
    Tool: Bash
    Preconditions: modify_agent.py implemented, equity-researcher plugin.json exists
    Steps:
      1. Run: uv run python -c "
         import sys, json; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/agent-modifier/scripts')
         from modify_agent import update_agent_skill_references
         from pathlib import Path
         # Backup
         p = Path('plugins/agent-plugins/equity-researcher/.claude-plugin/plugin.json')
         backup = p.read_text()
         # Test add
         result = update_agent_skill_references(Path('plugins/agent-plugins/equity-researcher'), 'test-temp-skill')
         print(f'Add result: {result}')
         # Restore
         p.write_text(backup)
         print('OK: restored')
         "
    Expected Result: "Add result: True" (or False with reason if check.py rejects)
    Failure Indicators: Exception or corrupted JSON
    Evidence: .sisyphus/evidence/task-3-add-skill.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add agent-modifier skill with self-modification prevention`
  - Files: `plugins/vertical-plugins/simulation/skills/agent-modifier/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/agent-modifier/ -v`

- [ ] 4. MCP Tool Adder SKILL.md + add_mcp_tool.py (TDD + R6 Enforcement)

  **What to do**:
  - **TDD RED**: Write `test_add_mcp_tool.py` first with test cases:
    1. `test_tool_template_is_valid_python` — 模板生成的代码是有效 Python
    2. `test_add_tool_creates_function` — add_tool_to_server 在 server.py 中插入 @mcp.tool() 函数
    3. `test_tool_name_collision_detected` — 已有同名工具时拒绝添加
    4. `test_domain_keywords_rejected` — 包含 "backtest"/"portfolio_optimize" 等域关键词时拒绝
    5. `test_readme_updated` — update_server_readme 成功添加工具到 README 表格
    6. `test_invalid_server_name` — 不存在的 server 返回 False
    7. `test_rollback_on_failure` — 添加失败时恢复原 server.py
  - **TDD GREEN**: Implement:
    - Create `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/SKILL.md`:
      - name: `mcp-tool-adder`
      - description: 扩展 MCP 服务器工具，遵循 FastMCP 模式和 R6 边界规则
      - Constraints: 仅操作 internal-store；生成的工具只包含数据访问逻辑；需重启服务器生效
    - Create `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts/add_mcp_tool.py`:
      - `DOMAIN_KEYWORDS = ["backtest", "portfolio_optimize", "screen_stocks", "market_breadth", "factor_cal", "winsorize", "neutralize"]` — R6 禁止词
      - `MCP_TOOL_TEMPLATE` 常量：标准 @mcp.tool() 模板，使用 df_to_json 返回
      - `validate_tool_code(tool_code: str) -> tuple[bool, str]`: 检查 DOMAIN_KEYWORDS，检查语法有效性
      - `add_tool_to_server(server_name: str, tool_name: str, params: str, description: str, upstream_call: str) -> bool`:
        - 验证 server_name 存在于 `mcp-servers/` 目录
        - 检查工具名碰撞（grep 现有 def 名称）
        - 生成工具代码
        - 验证工具代码（R6 检查 + 语法检查）
        - 备份 server.py
        - 在 `# --- ASGI App ---` 标记前插入代码
        - 运行 ruff check 验证
        - 失败则回滚
      - `update_server_readme(server_name: str, tool_name: str, description: str) -> bool`
    - Create `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts/__init__.py` (empty)
  - **TDD REFACTOR**: Clean up

  **Must NOT do**:
  - Do NOT 修改 akshare-server 或 tushare-server — 仅允许 internal-store
  - Do NOT 删除或修改已有 MCP 工具 — 只添加新工具
  - Do NOT 添加包含域逻辑的工具 — R6 强制检查
  - Do NOT 假设服务器会热加载 — SKILL.md 中明确需重启

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 修改生产代码（server.py）+ R6 合规 + 回滚 + TDD
  - **Skills**: [`test-driven-development`]
    - `test-driven-development`: 严格 RED-GREEN-REFACTOR，修改生产代码风险最高

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T5)
  - **Parallel Group**: Wave 2
  - **Blocks**: T5, T6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `mcp-servers/internal-store/server.py:94-306` — 现有 MCP 工具的 @mcp.tool() 模式，df_to_json 返回模式，error handling 模式
  - `mcp-servers/internal-store/server.py:280-310` — `# --- ASGI App ---` 标记位置，新工具插入点

  **API/Type References**:
  - `mcp-servers/internal-store/server.py:1-30` — 导入和 df_to_json helper 函数
  - `mcp-servers/internal-store/README.md` — README 工具表格格式
  - `scripts/check.py:122-141` — R6 边界规则实现，DOMAIN_KEYWORDS 列表

  **Test References**:
  - `mcp-servers/internal-store/test_server.py` — MCP server 测试模式参考（mock, async patterns）

  **External References**:
  - `contributing/mcp-servers.md` — MCP server 编写约定，FastMCP 模式说明

  **WHY Each Reference Matters**:
  - `server.py:94-306`: 这是被修改的文件，必须理解其结构和模式
  - `server.py:280-310`: 插入点标记位置
  - `check.py:122-141`: R6 规则定义了哪些关键词在 MCP server 中被禁止
  - `mcp-servers.md`: 新工具必须遵循此文档中的约定

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All mcp-tool-adder tests pass
    Tool: Bash
    Preconditions: test_add_mcp_tool.py and add_mcp_tool.py created
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/skills/mcp-tool-adder/test_add_mcp_tool.py -v
    Expected Result: >=6 tests, 0 failures, 0 errors
    Failure Indicators: Any test FAIL or ERROR
    Evidence: .sisyphus/evidence/task-4-mcp-tool-adder-tests.txt

  Scenario: Domain keywords are rejected in tool code
    Tool: Bash
    Preconditions: add_mcp_tool.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts')
         from add_mcp_tool import validate_tool_code
         bad_code = 'def backtest_strategy(): pass'
         valid, reason = validate_tool_code(bad_code)
         assert not valid, 'Domain keyword should be rejected!'
         assert 'domain' in reason.lower() or 'R6' in reason, f'Unexpected reason: {reason}'
         print(f'OK: domain keyword rejected: {reason}')
         "
    Expected Result: "OK: domain keyword rejected: ..."
    Failure Indicators: Domain keyword accepted
    Evidence: .sisyphus/evidence/task-4-r6-check.txt

  Scenario: Tool name collision detected
    Tool: Bash
    Preconditions: add_mcp_tool.py implemented
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts')
         from add_mcp_tool import add_tool_to_server
         # 'list_cache' already exists in internal-store
         result = add_tool_to_server('internal-store', 'list_cache', 'limit: int', 'List cache', 'ak.new_function()')
         assert result == False, 'Collision should be detected!'
         print('OK: tool name collision detected')
         "
    Expected Result: "OK: tool name collision detected"
    Failure Indicators: Existing tool overwritten
    Evidence: .sisyphus/evidence/task-4-collision.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add mcp-tool-adder skill with R6 enforcement`
  - Files: `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/mcp-tool-adder/ -v`

- [ ] 5. Update Meta-Strategist Plugin + System Prompt

  **What to do**:
  - Update `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json`:
    - Add to skills array: `"simulation:script-generator"`, `"simulation:agent-modifier"`, `"simulation:mcp-tool-adder"`
    - Now should have 6 skills total (3 existing + 3 new)
  - Update `plugins/agent-plugins/meta-strategist/agents/system-prompt.md`:
    - Add Phase 2 section: "## Phase 2: Script Generation" — 描述如何使用 script-generator 生成因子/策略脚本
    - Add Phase 3 section: "## Phase 3: Agent & Tool Modification" — 描述如何使用 agent-modifier 和 mcp-tool-adder
    - Reference exact skill script paths and function names
    - Add constraints: self-modification prevention, R6 compliance for MCP tools, rollback on failure
  - Update `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`:
    - Update autonomy table to show Phase 2 and Phase 3 capabilities as enabled
    - Add Phase 2+3 tools to the "## What you produce" section

  **Must NOT do**:
  - Do NOT 修改 Phase 1 的进化循环逻辑
  - Do NOT 添加 Phase 2+3 的 skill 引用到非 meta-strategist 的 Agent

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Config + markdown 更新，无新代码逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T4)
  - **Parallel Group**: Wave 2
  - **Blocks**: T6
  - **Blocked By**: T1, T3, T4 (need skill names and descriptions from those tasks)

  **References**:

  **Pattern References**:
  - `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json` — 当前 plugin.json 格式，已有 3 个 skills
  - `plugins/agent-plugins/meta-strategist/agents/system-prompt.md` — 当前 system-prompt 结构（130行），在其末尾添加 Phase 2+3 sections

  **API/Type References**:
  - `plugins/vertical-plugins/simulation/skills/script-generator/SKILL.md` (from T1) — script-generator 的技能描述和接口
  - `plugins/vertical-plugins/simulation/skills/agent-modifier/SKILL.md` (from T3) — agent-modifier 的技能描述和约束
  - `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/SKILL.md` (from T4) — mcp-tool-adder 的技能描述和约束

  **WHY Each Reference Matters**:
  - `plugin.json`: 直接修改此文件，添加新的 skill 引用
  - `system-prompt.md`: 在现有 Phase 1 描述后追加 Phase 2+3 描述
  - 新 SKILL.md 文件: system-prompt 中引用的工具名和接口必须与实际 SKILL.md 一致

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: plugin.json has 6 skills
    Tool: Bash
    Preconditions: plugin.json updated
    Steps:
      1. Run: cat plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json | python3 -c "import json,sys; d=json.load(sys.stdin); assert len(d['skills']) >= 6, f'Expected >=6, got {len(d[\"skills\"])}'; assert 'simulation:script-generator' in d['skills']; assert 'simulation:agent-modifier' in d['skills']; assert 'simulation:mcp-tool-adder' in d['skills']; print('OK: 6+ skills')"
    Expected Result: "OK: 6+ skills"
    Failure Indicators: JSON error or missing skills
    Evidence: .sisyphus/evidence/task-5-plugin-json.txt

  Scenario: system-prompt has Phase 2 and Phase 3 sections
    Tool: Bash
    Preconditions: system-prompt.md updated
    Steps:
      1. Run: grep -c "Phase 2" plugins/agent-plugins/meta-strategist/agents/system-prompt.md
      2. Run: grep -c "Phase 3" plugins/agent-plugins/meta-strategist/agents/system-prompt.md
      3. Run: grep -c "script-generator" plugins/agent-plugins/meta-strategist/agents/system-prompt.md
    Expected Result: Phase 2 >=1, Phase 3 >=1, script-generator >=1
    Failure Indicators: No Phase 2/3 sections
    Evidence: .sisyphus/evidence/task-5-system-prompt.txt

  Scenario: check.py passes after plugin changes
    Tool: Bash
    Steps:
      1. Run: uv run python scripts/check.py 2>&1
    Expected Result: No errors related to meta-strategist plugin
    Failure Indicators: Plugin structure errors or R1-R6 violations
    Evidence: .sisyphus/evidence/task-5-check-py.txt
  ```

  **Commit**: YES
  - Message: `feat(meta-strategist): integrate Phase 2+3 evolution skills`
  - Files: `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json`, `plugins/agent-plugins/meta-strategist/agents/system-prompt.md`, `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`

- [ ] 6. Update Architecture Docs + Final Verification

  **What to do**:
  - Update `contributing/architecture.md`:
    - 更新 Meta-Agent 自主权表，标记 Phase 2 (Generate new Skill scripts) 和 Phase 3 (Modify Agent definitions + Add MCP tools) 为已实现 ✓
    - 更新 Skill Catalog，添加 script-generator, agent-modifier, mcp-tool-adder 到 simulation vertical
    - 更新 Agent Catalog 中 meta-strategist 的技能列表
  - Run `uv run python scripts/check.py` — 确认 0 issues
  - Run `uv run python scripts/sync-agent-skills.py` — 同步技能注册
  - Run `uv run pytest plugins/vertical-plugins/simulation/ -v` — 确认所有测试通过（包括新技能）

  **Must NOT do**:
  - Do NOT 修改 R1-R6 边界规则
  - Do NOT 添加新的架构规则 — 仅更新文档反映已实现的功能

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 纯文档更新 + 验证命令
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (final integration task)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: T5

  **References**:

  **Pattern References**:
  - `contributing/architecture.md` — 当前架构文档，找到 Meta-Agent 自主权表和 Skill Catalog 位置
  - `contributing/README.md` — 确保文档目录是最新的

  **WHY Each Reference Matters**:
  - `architecture.md`: 直接修改此文件，更新自主权表和技能目录

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: check.py passes with 0 issues
    Tool: Bash
    Steps:
      1. Run: uv run python scripts/check.py 2>&1
    Expected Result: Exit code 0, no warnings or errors
    Failure Indicators: Any R1-R6 violation or missing plugin errors
    Evidence: .sisyphus/evidence/task-6-check-py.txt

  Scenario: All simulation tests pass
    Tool: Bash
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/ -v --tb=short 2>&1 | tail -20
    Expected Result: All tests pass, 0 failures
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-6-all-tests.txt

  Scenario: Architecture doc has Phase 2+3 autonomy entries
    Tool: Bash
    Steps:
      1. Run: grep -c "script-generator\|agent-modifier\|mcp-tool-adder" contributing/architecture.md
    Expected Result: Count >= 3 (each skill mentioned at least once)
    Failure Indicators: Missing skill references
    Evidence: .sisyphus/evidence/task-6-arch-doc.txt
  ```

  **Commit**: YES
  - Message: `docs: update architecture for Meta-Agent Phase 2+3`
  - Files: `contributing/architecture.md`
  - Pre-commit: `uv run python scripts/check.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check` + `uv run pytest`. Review all changed files for: `as any`/type ignores, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real QA Execution** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Run `uv run python scripts/check.py`. Verify no R6 warnings. Test modify_agent.py self-modification block. Test add_mcp_tool.py R6 enforcement.
  Output: `Scenarios [N/N pass] | check.py [PASS/FAIL] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **T1+T2**: `feat(simulation): add script-generator skill for Meta-Agent Phase 2` — script-generator/
- **T3**: `feat(simulation): add agent-modifier skill with self-modification prevention` — agent-modifier/
- **T4**: `feat(simulation): add mcp-tool-adder skill with R6 enforcement` — mcp-tool-adder/
- **T5**: `feat(meta-strategist): integrate Phase 2+3 evolution skills` — meta-strategist plugin files
- **T6**: `docs: update architecture for Meta-Agent Phase 2+3` — contributing/architecture.md

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
uv run pytest plugins/vertical-plugins/simulation/skills/script-generator/ -v  # Expected: all pass
uv run pytest plugins/vertical-plugins/simulation/skills/agent-modifier/ -v  # Expected: all pass
uv run pytest plugins/vertical-plugins/simulation/skills/mcp-tool-adder/ -v  # Expected: all pass

# Architecture check
uv run python scripts/check.py  # Expected: 0 issues, no R6 warnings

# Meta-strategist has all 6 skills
cat plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json | python3 -c "import json,sys; d=json.load(sys.stdin); assert len(d['skills']) >= 6, f'Expected >=6 skills, got {len(d[\"skills\"])}'"

# Self-modification prevention
uv run python -c "
import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/agent-modifier/scripts')
from modify_agent import update_agent_skill_references
from pathlib import Path
result = update_agent_skill_references(Path('plugins/agent-plugins/meta-strategist'), 'test-skill')
assert result == False, 'Self-modification should be blocked!'
print('OK: self-modification blocked')
"
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] check.py shows 0 issues
- [ ] meta-strategist has 6 skills in plugin.json
- [ ] modify_agent.py blocks self-modification
- [ ] add_mcp_tool.py enforces R6 compliance
