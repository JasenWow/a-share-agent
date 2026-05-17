# Phase 3+4: Meta-Agent Phase 1 + Jupyter Notebooks + R6 Fix

## TL;DR

> **Quick Summary**: 实现 Meta-Agent 自主策略探索核心（假设生成 + Agent连接），创建4个可视化Notebook，修复 check.py 的 R6 误报警告。
> 
> **Deliverables**:
> - `generate_hypothesis.py` — 策略假设生成器（随机+利用式），TDD
> - 增强 `meta-strategist` system-prompt + plugin.json（连接模拟技能）
> - `notebooks/simulation.ipynb` — 策略进化可视化
> - `notebooks/factors.ipynb` — 因子分析可视化
> - `notebooks/backtest.ipynb` — 回测结果可视化
> - `notebooks/portfolio.ipynb` — 投资组合可视化
> - `scripts/check.py` R6 规则修复（排除 schema 定义误报）
> - `pyproject.toml` 添加 jupyterlab 依赖
> - `contributing/notebooks.md` — Notebook 编写约定
> 
> **Estimated Effort**: Medium (8 implementation tasks + 4 verification tasks)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: T1 → T3 → T4 → T6-T9 (parallel) → F1-F4

---

## Context

### Original Request
用户要求继续路线图 Phase 3（Meta-Agent Phase 1）和 Phase 4（Jupyter Notebooks），同时修复 check.py 的 R6 误报警告。

### Interview Summary
**Key Discussions**:
- **Scope**: Phase 3 + Phase 4 only（Phase 5-6 不在本次范围）
- **R6 修复**: 确认 internal-store/server.py 无领域逻辑，警告来自表名 "backtest_results" 的子串匹配
- **Notebook 依赖**: jupyterlab 需添加到 pyproject.toml
- **Notebook 验证**: 使用 nbconvert --execute 自动化测试
- **测试策略**: TDD 用于 generate_hypothesis.py，notebook 用 nbconvert 验证

**Research Findings**:
- Meta-strategist 当前是空壳（24行 manifest, 38行 system-prompt, 旧格式 plugin.json 无 skills 引用）
- `system-prompt.md` 已存在（38行），有基本进化循环描述但缺少详细工作流
- Simulation skills（trading-simulator, evolution-loop, experiment-tracker）已完整实现
- `generate_hypothesis.py` 是核心缺失——Meta-Agent 无法自主生成策略假设
- 项目有 plotly 依赖但零可视化代码，Notebook 全部从零开始
- 内部存储有 9 个 MCP 工具供 Notebook 查询数据
- 回测结果格式丰富：daily_nav[], trades[], positions[], performance dict

### Metis Review
**Identified Gaps** (all addressed):
- **假设生成格式**: 路线图已定义具体 schema（factors, weights, universe, rebalance, top_k, stop_loss, max_position）
- **Notebook 数据流**: 通过 MCP internal-store HTTP API 查询（port 8002）
- **Phase 3.3 "Wire" 含义**: 更新 plugin.json skills 引用 + meta-strategist.md 进化循环步骤，Agent 通过 MCP 调用模拟技能
- **R6 修复范围**: 仅排除 SQL schema 定义（CREATE TABLE 语句内的关键词），仍捕获真实领域逻辑
- **Notebook 独立性**: 每个 Notebook 必须独立可执行，不共享 kernel 状态
- **空数据处理**: Notebook 需处理空查询结果（无模拟运行、无回测结果的情况）

---

## Work Objectives

### Core Objective
让 Meta-Strategist Agent 具备自主策略假设生成能力，创建可视化分析 Notebook，修复项目健康检查误报。

### Concrete Deliverables
- `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py`
- `plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py`
- `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json` (updated)
- `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md` (updated)
- `plugins/agent-plugins/meta-strategist/agents/system-prompt.md` (enhanced)
- `notebooks/simulation.ipynb`
- `notebooks/factors.ipynb`
- `notebooks/backtest.ipynb`
- `notebooks/portfolio.ipynb`
- `scripts/check.py` (R6 rule fix)
- `pyproject.toml` (jupyterlab added)
- `contributing/notebooks.md`

### Definition of Done
- [ ] `uv run python scripts/check.py` → exit code 0 (no R6 warnings)
- [ ] `uv run pytest plugins/vertical-plugins/simulation/ -v` → all pass (including hypothesis tests)
- [ ] `jupyter nbconvert --execute notebooks/simulation.ipynb` → success
- [ ] `jupyter nbconvert --execute notebooks/backtest.ipynb` → success
- [ ] Meta-strategist plugin.json has skills array referencing simulation skills

### Must Have
- generate_hypothesis.py 生成有效策略假设（factors + weights 归一化 + universe + rebalance）
- Meta-strategist 完整进化循环描述（假设→模拟→记录→评估→迭代）
- 4 个独立可执行的 Notebook（plotly 可视化）
- R6 规则精确排除 schema 定义误报
- jupyterlab 依赖安装

### Must NOT Have (Guardrails)
- **NO ML/LLM-based 假设生成** — 仅使用随机采样 + 历史最优策略扰动
- **NO Notebook 间依赖** — 每个 Notebook 独立可执行
- **NO 改动 akshare-server 或 tushare-server**
- **NO MCP Server 新增** — Phase 3 仅连接已有 MCP 工具
- **NO convert simulation scripts to MCP servers** — 保持现有脚本调用方式
- **NO interactive widgets** — Phase 4 仅静态可视化图表
- **NO 深度学习/强化学习模型** — generate_hypothesis.py 使用纯随机+启发式方法
- **NO Phase 5-6 内容** — 脚本生成、Agent修改器不在范围

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in pyproject.toml)
- **Automated tests**: YES (TDD for generate_hypothesis.py)
- **Framework**: pytest + nbconvert --execute
- **TDD scope**: generate_hypothesis.py only
- **Notebook validation**: `jupyter nbconvert --execute --ExecutePreprocessor.timeout=120` per notebook

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python TDD**: Use Bash (`uv run pytest`)
- **Notebook execution**: Use Bash (`jupyter nbconvert --execute`)
- **Config verification**: Use Bash (`grep`, `cat`, `uv run python scripts/check.py`)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── T1: Fix check.py R6 rule + add jupyterlab to pyproject.toml [quick]
└── T2: Create contributing/notebooks.md conventions [writing]

Wave 2 (After T1 — core implementation, ALL parallel):
├── T3: generate_hypothesis.py — TDD (random + exploitative) [deep]
├── T4: Enhance meta-strategist agent (system-prompt + plugin.json + manifest) [quick]
└── T5: Create notebook helper module (shared MCP data access utilities) [unspecified-high]

Wave 3 (After T3, T4, T5 — notebooks, ALL parallel):
├── T6: notebooks/simulation.ipynb — strategy evolution visualization [visual-engineering]
├── T7: notebooks/factors.ipynb — factor analysis visualization [visual-engineering]
├── T8: notebooks/backtest.ipynb — backtest results visualization [visual-engineering]
└── T9: notebooks/portfolio.ipynb — portfolio visualization [visual-engineering]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real QA execution (unspecified-high)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: T1 → T3 → T6-T9 → F1-F4
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Waves 2 & 3)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T3 | 1 |
| T2 | — | T6-T9 | 1 |
| T3 | T1 (check.py fixed) | T6 | 2 |
| T4 | — | — | 2 |
| T5 | — | T6-T9 | 2 |
| T6 | T3, T5 | F1-F4 | 3 |
| T7 | T3, T5 | F1-F4 | 3 |
| T8 | T3, T5 | F1-F4 | 3 |
| T9 | T3, T5 | F1-F4 | 3 |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `quick`, T2 → `writing`
- **Wave 2**: 3 tasks — T3 → `deep`, T4 → `quick`, T5 → `unspecified-high`
- **Wave 3**: 4 tasks — T6-T9 → `visual-engineering`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Fix check.py R6 Rule + Add JupyterLab Dependency

  **What to do**:
  - Read `scripts/check.py` lines 122-141 (R6 boundary rule implementation)
  - Modify the R6 check to exclude SQL schema definitions (lines inside `CREATE TABLE`/`INSERT`/column definition strings) from keyword matching
  - Strategy: When scanning MCP server Python files, skip lines that are inside SQL string literals (lines containing `CREATE TABLE`, `INSERT INTO`, or within triple-quoted SQL strings)
  - Verify fix: `uv run python scripts/check.py` should produce 0 R6 warnings for internal-store/server.py
  - Add `"jupyterlab>=4.0"` and `"nbconvert>=7.0"` to `pyproject.toml` dependencies list
  - Run `uv sync` to verify dependency resolution

  **Must NOT do**:
  - Do NOT remove domain keywords from the R6 check list
  - Do NOT weaken R6 to skip all string literals — only SQL schema definitions
  - Do NOT modify internal-store/server.py itself

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single-file logic fix + one-line dependency addition
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `test-driven-development`: Not applicable — modifying a check script, not business logic

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2)
  - **Blocks**: T3 (needs check.py fixed)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `scripts/check.py:122-141` — Current R6 rule: iterates `domain_keywords` (`winsorize, neutralize, factor_cal, backtest, portfolio_optimize, screen_stocks, market_breadth`), checks `kw in content.lower() and "def " in content`. Need to make this smarter to exclude SQL schema strings.
  - `scripts/check.py:100-120` — See how other rules (R1-R5) are implemented for style consistency

  **API/Type References**:
  - `pyproject.toml:16-18` — Current dependencies list where plotly/ipython/ipywidgets are defined. Add jupyterlab and nbconvert here.

  **WHY Each Reference Matters**:
  - `check.py:122-141`: This is THE file to modify. Understand the exact keyword list and matching logic before changing.
  - `pyproject.toml:16-18`: Follow the existing dependency format for adding new packages.

  **Acceptance Criteria**:
  - [ ] `uv run python scripts/check.py` → 0 R6 warnings for internal-store/server.py
  - [ ] `uv run python scripts/check.py` still catches real violations (test with a file containing `def backtest():` in mcp-servers/)
  - [ ] `uv sync` completes successfully with jupyterlab installed
  - [ ] `which jupyter` or `uv run jupyter --version` returns valid output

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: R6 no longer flags internal-store server.py as false positive
    Tool: Bash
    Preconditions: scripts/check.py has been modified
    Steps:
      1. Run: uv run python scripts/check.py 2>&1
      2. Grep output for "R6 WARNING.*internal-store"
    Expected Result: No lines matching "R6 WARNING.*internal-store"
    Failure Indicators: Any R6 WARNING line mentioning internal-store
    Evidence: .sisyphus/evidence/task-1-r6-no-false-positive.txt

  Scenario: R6 still catches real domain logic violations
    Tool: Bash
    Preconditions: Create a temp file mcp-servers/internal-store/test_r6_catch.py with content: `def backtest_strategy(): pass`
    Steps:
      1. Run: uv run python scripts/check.py 2>&1
      2. Grep output for "R6 WARNING.*test_r6_catch"
      3. Remove the temp file
    Expected Result: R6 WARNING found for test_r6_catch.py
    Failure Indicators: No R6 WARNING when real domain function exists
    Evidence: .sisyphus/evidence/task-1-r6-still-catches.txt

  Scenario: JupyterLab installed and available
    Tool: Bash
    Preconditions: uv sync completed
    Steps:
      1. Run: uv run jupyter --version
    Expected Result: Version string printed, exit code 0
    Failure Indicators: Command not found or import error
    Evidence: .sisyphus/evidence/task-1-jupyter-installed.txt
  ```

  **Commit**: YES
  - Message: `fix(scripts): improve R6 rule to exclude SQL schema definitions`
  - Files: `scripts/check.py`, `pyproject.toml`, `uv.lock`
  - Pre-commit: `uv run python scripts/check.py`

- [x] 2. Create Notebook Writing Conventions

  **What to do**:
  - Create `contributing/notebooks.md` documenting Jupyter notebook conventions for the project
  - Include: directory structure (`notebooks/` at root), naming convention, MCP data access pattern (HTTP to localhost:8002), output standards (inline plots, no external file writes), kernel specification (Python 3), independent execution requirement, nbconvert CI validation
  - Reference existing contributing docs style (see `contributing/coding-standards.md` and `contributing/mcp-servers.md` for format)

  **Must NOT do**:
  - Do NOT create actual notebooks yet
  - Do NOT add new architecture rules — document conventions only

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Pure documentation task
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1)
  - **Blocks**: T6-T9 (notebooks follow these conventions)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `contributing/coding-standards.md` — Follow this format for notebook conventions doc
  - `contributing/mcp-servers.md` — See how MCP tool documentation is structured
  - `contributing/README.md` — Table of contents for contributing docs, add notebooks.md reference

  **API/Type References**:
  - `mcp-servers/internal-store/server.py:94-306` — MCP tools available for notebook data access (9 tools, see tool names and parameters for documentation)

  **WHY Each Reference Matters**:
  - `coding-standards.md`: Template for the new doc — match heading structure, code example format.
  - `internal-store/server.py`: Document the actual MCP endpoint and tools notebooks should use.

  **Acceptance Criteria**:
  - [ ] `contributing/notebooks.md` exists with ≥50 lines of convention documentation
  - [ ] Document includes MCP data access pattern (URL + tool names)
  - [ ] Document includes nbconvert execution command for CI
  - [ ] `contributing/README.md` updated with notebooks.md in the table

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Notebooks convention doc covers all required sections
    Tool: Bash
    Preconditions: contributing/notebooks.md created
    Steps:
      1. Run: grep -c "##" contributing/notebooks.md
      2. Verify sections: "Directory Structure", "Data Access", "Execution", "Validation"
      3. Run: grep "nbconvert" contributing/notebooks.md
    Expected Result: ≥4 section headings, nbconvert command present
    Failure Indicators: Missing sections or no nbconvert reference
    Evidence: .sisyphus/evidence/task-2-notebook-conventions.txt

  Scenario: Contributing README references notebooks.md
    Tool: Bash
    Preconditions: contributing/README.md updated
    Steps:
      1. Run: grep "notebooks" contributing/README.md
    Expected Result: Line containing "notebooks" found
    Failure Indicators: No mention of notebooks.md
    Evidence: .sisyphus/evidence/task-2-readme-reference.txt
  ```

  **Commit**: YES
  - Message: `docs: add notebook writing conventions`
  - Files: `contributing/notebooks.md`, `contributing/README.md`

- [x] 3. Implement Hypothesis Generation (TDD) — generate_hypothesis.py

  **What to do**:
  - **TDD RED**: Write `test_generate_hypothesis.py` first with ≥5 test cases:
    1. `test_random_hypothesis_has_required_fields` — verify output has factors, weights, universe, rebalance, top_k, stop_loss, max_position
    2. `test_random_hypothesis_weights_sum_to_one` — verify weight normalization
    3. `test_random_hypothesis_factor_count_in_range` — verify 1-4 factors per hypothesis
    4. `test_exploitative_from_best_strategy` — verify perturbation of best strategy
    5. `test_exploitative_empty_history_falls_back_to_random` — no historical strategies → random
    6. `test_no_duplicate_factors_in_hypothesis` — verify no repeated factors
    7. `test_seed_reproducibility` — same seed produces same hypothesis
  - **TDD GREEN**: Implement `generate_hypothesis.py` at `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py`
  - Follow the exact spec from the roadmap:
    - Factor library: `["momentum_20d", "momentum_60d", "momentum_120d", "value_pe", "value_pb", "value_pc", "quality_roe", "quality_debt", "quality_growth", "low_vol_20d", "low_vol_60d", "size_log_mcap"]`
    - Universe options: `["全A", "沪深300", "中证500", "中证1000"]`
    - Rebalance options: `["daily", "weekly", "monthly"]`
    - Top-K options: `[20, 30, 50, 100]`
    - Stop loss options: `[0.05, 0.10, 0.15]`
    - Max position options: `[0.05, 0.10, 0.15]`
    - Random: sample 1-4 factors, random weights normalized to sum=1.0, random other params
    - Exploitative: take best strategy, perturb weights ±0.1, clamp to [0.01, 1.0], renormalize
  - **TDD REFACTOR**: Clean up if needed
  - Run all tests: `uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py -v`

  **Must NOT do**:
  - Do NOT use ML/LLM for hypothesis generation — pure random + heuristic only
  - Do NOT import from trading-simulator or other skills — this module is standalone
  - Do NOT add external dependencies beyond Python stdlib + numpy (if needed for random)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core algorithmic component with TDD discipline required
  - **Skills**: [`test-driven-development`]
    - `test-driven-development`: Strict RED-GREEN-REFACTOR cycle for this task

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T4, T5)
  - **Parallel Group**: Wave 2
  - **Blocks**: T6-T9 (notebooks may use hypothesis data)
  - **Blocked By**: T1 (check.py should be fixed first for clean test runs)

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/evolution.py` — Existing evolution module. `generate_hypothesis.py` should complement this, same coding style. Note the `EvolutionState` dataclass pattern.

  **API/Type References**:
  - Roadmap Task 3.2 (lines 956-1052 of the roadmap file) — Exact spec for hypothesis format and generation logic
  - `mcp-servers/internal-store/server.py:217-235` — `get_best_strategies()` returns list of dicts with `strategy` field containing `{"factors": [...], "weights": {...}}` — exploitative generation consumes this format

  **Test References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py` — Existing test file for evolution.py, follow same test structure and import patterns

  **External References**:
  - pytest docs: `https://docs.pytest.org/` — standard test patterns

  **WHY Each Reference Matters**:
  - `evolution.py`: Same directory, same style. Your new file must look like it belongs.
  - Roadmap Task 3.2: The EXACT specification — factor library, universe options, weight normalization rules.
  - `get_best_strategies()`: This is what exploitative generation reads. The dict format must match.
  - `test_evolution.py`: Test file pattern to follow (imports, fixtures, assertions).

  **Acceptance Criteria**:
  - [ ] `test_generate_hypothesis.py` created with ≥7 test cases
  - [ ] `generate_hypothesis.py` implements both `generate_random_hypothesis()` and `generate_exploitative_hypothesis()`
  - [ ] `uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py -v` → all tests PASS
  - [ ] Weights always sum to 1.0 (within 0.01 tolerance)
  - [ ] No duplicate factors in any hypothesis
  - [ ] Seed-based reproducibility works

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All hypothesis generation tests pass
    Tool: Bash
    Preconditions: generate_hypothesis.py and test_generate_hypothesis.py created
    Steps:
      1. Run: uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py -v
    Expected Result: ≥7 tests collected, 0 failures, 0 errors
    Failure Indicators: Any test FAIL or ERROR status
    Evidence: .sisyphus/evidence/task-3-hypothesis-tests.txt

  Scenario: Hypothesis generation produces valid output
    Tool: Bash
    Preconditions: Tests pass
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/evolution-loop/scripts')
         from generate_hypothesis import generate_random_hypothesis
         h = generate_random_hypothesis(seed=42)
         assert 'factors' in h, 'missing factors'
         assert 'weights' in h, 'missing weights'
         assert abs(sum(h['weights'].values()) - 1.0) < 0.01, f'weights do not sum to 1: {sum(h[\"weights\"].values())}'
         assert len(h['factors']) == len(set(h['factors'])), 'duplicate factors'
         print('OK:', h)
         "
    Expected Result: Prints "OK:" followed by valid hypothesis dict
    Failure Indicators: AssertionError or KeyError
    Evidence: .sisyphus/evidence/task-3-hypothesis-output.txt

  Scenario: Exploitative generation falls back to random when no history
    Tool: Bash
    Preconditions: Tests pass
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'plugins/vertical-plugins/simulation/skills/evolution-loop/scripts')
         from generate_hypothesis import generate_exploitative_hypothesis
         h = generate_exploitative_hypothesis(best_strategies=[], seed=42)
         assert 'factors' in h
         assert len(h['factors']) >= 1
         print('OK: fallback to random works')
         "
    Expected Result: "OK: fallback to random works"
    Failure Indicators: Exception or empty result
    Evidence: .sisyphus/evidence/task-3-exploitative-fallback.txt
  ```

  **Commit**: YES
  - Message: `feat(simulation): add hypothesis generation for Meta-Agent`
  - Files: `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py`, `plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py -v`

- [x] 4. Enhance Meta-Strategist Agent Definition

  **What to do**:
  - Update `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json` to include skills array:
    ```json
    {
      "name": "meta-strategist",
      "version": "0.1.0",
      "description": "Autonomous strategy exploration agent. Uses simulation-driven evolution to discover profitable A-share strategies.",
      "author": { "name": "A-Share Quant" },
      "skills": [
        "simulation:trading-simulator",
        "simulation:experiment-tracker",
        "simulation:evolution-loop"
      ],
      "commands": ["/evolve"],
      "mcp_dependencies": ["akshare", "tushare", "internal-store"]
    }
    ```
  - Enhance `plugins/agent-plugins/meta-strategist/agents/system-prompt.md` with:
    - Detailed evolution loop workflow (step-by-step with tool names)
    - Hypothesis generation instructions (reference generate_hypothesis.py patterns)
    - Simulation execution instructions (how to call trading-simulator)
    - Result recording instructions (which internal-store tools to use)
    - Convergence/termination logic (referencing evolution.py `should_continue()`)
    - Doom loop detection details (threshold=3, corrective actions from `generate_correction()`)
  - Update `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md` to reference enhanced system-prompt and include evolution loop steps in the Workflow section

  **Must NOT do**:
  - Do NOT change the agent's fundamental purpose or persona
  - Do NOT add skills not yet implemented (no `script-generator`, no `agent-modifier`)
  - Do NOT create a `/evolve` command file yet — just reference it in plugin.json

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Config updates + markdown writing, no code logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T5)
  - **Parallel Group**: Wave 2
  - **Blocks**: None
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `plugins/agent-plugins/equity-researcher/.claude-plugin/plugin.json` — Existing agent plugin.json format (may or may not have skills array — check and follow convention)
  - `plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md` — Similar agent definition for style reference

  **API/Type References**:
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/evolution.py` — Read the actual `should_continue()`, `generate_correction()` functions to accurately describe them in system-prompt
  - `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py` (from T3) — Reference the factor library and hypothesis format in system-prompt
  - `mcp-servers/internal-store/server.py:178-306` — MCP tool names and signatures to reference in system-prompt (record_experiment, get_best_strategies, record_transition, record_episode_summary)

  **WHY Each Reference Matters**:
  - `equity-researcher/plugin.json`: Match the JSON format convention.
  - `evolution.py`: The system-prompt must accurately describe the actual evolution logic, not invent behavior.
  - `internal-store/server.py`: Tool names in system-prompt must match actual MCP tool names exactly.

  **Acceptance Criteria**:
  - [ ] `plugin.json` has `skills` array with 3 simulation skill references
  - [ ] `plugin.json` has `commands` array with `["/evolve"]`
  - [ ] `plugin.json` has `mcp_dependencies` array
  - [ ] `system-prompt.md` ≥80 lines with detailed evolution loop steps
  - [ ] `system-prompt.md` references exact MCP tool names (e.g., `mcp__internal-store__record_experiment`)
  - [ ] `meta-strategist.md` updated with enhanced workflow

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: plugin.json has required fields
    Tool: Bash
    Preconditions: plugin.json updated
    Steps:
      1. Run: cat plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'skills' in d; assert len(d['skills']) >= 3; assert 'commands' in d; assert '/evolve' in d['commands']; assert 'mcp_dependencies' in d; print('OK: plugin.json valid')"
    Expected Result: "OK: plugin.json valid"
    Failure Indicators: JSON parse error or missing fields
    Evidence: .sisyphus/evidence/task-4-plugin-json.txt

  Scenario: system-prompt.md references actual MCP tools
    Tool: Bash
    Preconditions: system-prompt.md enhanced
    Steps:
      1. Run: grep "mcp__internal-store" plugins/agent-plugins/meta-strategist/agents/system-prompt.md
      2. Verify ≥3 distinct MCP tool references found
    Expected Result: Lines containing mcp__internal-store tool names
    Failure Indicators: No MCP tool references
    Evidence: .sisyphus/evidence/task-4-system-prompt.txt

  Scenario: check.py still passes after plugin changes
    Tool: Bash
    Steps:
      1. Run: uv run python scripts/check.py 2>&1
    Expected Result: No errors related to meta-strategist plugin
    Failure Indicators: Plugin structure errors
    Evidence: .sisyphus/evidence/task-4-check-py.txt
  ```

  **Commit**: YES
  - Message: `feat(meta-strategist): enhance agent with evolution loop integration`
  - Files: `plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json`, `plugins/agent-plugins/meta-strategist/agents/system-prompt.md`, `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`

- [x] 5. Create Notebook Helper Module (Shared MCP Data Access)

  **What to do**:
  - Create `notebooks/__init__.py` (empty)
  - Create `notebooks/helpers.py` with shared utilities for all 4 notebooks:
    - `get_internal_store_url()` — returns internal-store MCP base URL (default `http://localhost:8002`)
    - `query_mcp(tool_name: str, params: dict = None) -> list[dict]` — generic MCP tool call helper via HTTP POST to `http://localhost:8002/mcp`
    - `get_experiments(limit: int = 100) -> pd.DataFrame` — fetch and parse experiments
    - `get_best_strategies(top_k: int = 10) -> pd.DataFrame` — fetch top strategies
    - `get_backtest_results(limit: int = 20) -> pd.DataFrame` — fetch backtest results
    - `get_portfolio(name: str = "default") -> dict` — fetch portfolio state
    - `get_episode_summaries() -> pd.DataFrame` — fetch episode summaries
  - Write `notebooks/test_helpers.py` with tests for:
    - Mock HTTP responses and verify DataFrame parsing
    - Handle empty results (empty list → empty DataFrame)
    - Handle MCP error responses ({"error": "..."})
  - Handle gracefully when MCP server is not running (ConnectionError → informative message)

  **Must NOT do**:
  - Do NOT add heavy dependencies — use only `requests` (or `urllib`) + `pandas` + `json`
  - Do NOT implement MCP protocol — simple HTTP POST to existing endpoint
  - Do NOT add caching logic — notebooks fetch fresh data each execution

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: API integration module with error handling and test mocking
  - **Skills**: [`test-driven-development`]
    - `test-driven-development`: Helper module benefits from TDD approach

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3, T4)
  - **Parallel Group**: Wave 2
  - **Blocks**: T6-T9 (all notebooks depend on helpers)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts/track_experiment.py` — This already does HTTP POST to internal-store MCP (function `store_experiment_via_mcp`). Follow the same HTTP call pattern.

  **API/Type References**:
  - `mcp-servers/internal-store/server.py:94-306` — All MCP tools with exact function signatures, parameter names, and return types
  - Internal-store MCP endpoint: HTTP POST to `http://localhost:8002/mcp` with JSON body `{"tool": "<tool_name>", "arguments": {...}}`

  **Test References**:
  - `plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py` — Existing test file for test pattern reference

  **WHY Each Reference Matters**:
  - `track_experiment.py`: Already implements MCP HTTP calling — copy the pattern, don't reinvent.
  - `server.py:94-306`: Each helper function maps 1:1 to an MCP tool — match parameter names exactly.

  **Acceptance Criteria**:
  - [ ] `notebooks/helpers.py` created with ≥6 data access functions
  - [ ] `notebooks/test_helpers.py` created with mock-based tests
  - [ ] `uv run pytest notebooks/test_helpers.py -v` → all pass
  - [ ] Functions handle empty results and connection errors gracefully

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Helper module tests pass with mocked MCP
    Tool: Bash
    Preconditions: notebooks/helpers.py and test_helpers.py created
    Steps:
      1. Run: uv run pytest notebooks/test_helpers.py -v
    Expected Result: All tests pass, 0 failures
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-5-helpers-tests.txt

  Scenario: Helper module handles MCP server not running
    Tool: Bash
    Preconditions: MCP server is NOT running on port 8002
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'notebooks')
         from helpers import query_mcp
         try:
             result = query_mcp('list_experiments')
             print('Unexpected success:', result)
         except ConnectionError as e:
             print('OK: ConnectionError raised:', str(e))
         except Exception as e:
             print('OK: Other error handled:', type(e).__name__, str(e))
         "
    Expected Result: Error handled gracefully, no unhandled exception
    Failure Indicators: Unhandled exception / traceback
    Evidence: .sisyphus/evidence/task-5-error-handling.txt

  Scenario: Helper functions parse MCP responses into DataFrames
    Tool: Bash
    Preconditions: Tests pass with mocked responses
    Steps:
      1. Run: uv run python -c "
         import sys; sys.path.insert(0, 'notebooks')
         from helpers import get_experiments
         print('Function get_experiments exists and is callable')
         "
    Expected Result: No import error
    Failure Indicators: ImportError or AttributeError
    Evidence: .sisyphus/evidence/task-5-import.txt
  ```

  **Commit**: YES
  - Message: `feat(notebooks): add shared MCP data access helper`
  - Files: `notebooks/__init__.py`, `notebooks/helpers.py`, `notebooks/test_helpers.py`
  - Pre-commit: `uv run pytest notebooks/test_helpers.py -v`

- [x] 6. Create Simulation Results Notebook (notebooks/simulation.ipynb)

  **What to do**:
  - Create `notebooks/simulation.ipynb` — strategy evolution visualization
  - Sections:
    1. **Title + Description**: "策略进化模拟" — 可视化 Meta-Agent 策略进化过程
    2. **Data Loading**: Use `from helpers import get_experiments, get_best_strategies, get_episode_summaries` to fetch data
    3. **NAV Evolution Plot**: Line chart (plotly) — x=iteration, y=final_nav, show strategy performance over evolution
    4. **Sharpe Distribution**: Histogram (plotly) — distribution of Sharpe ratios across experiments
    5. **Best Strategies Table**: Display top-5 strategies with metrics (final_nav, sharpe, max_drawdown)
    6. **Episode Summary**: Bar chart — per-episode final NAV comparison
    7. **Empty State Handling**: If no data, display "暂无模拟数据，请先运行 Meta-Agent 进化循环" message
  - Import helpers from same directory: `import sys; sys.path.insert(0, os.path.dirname(__file__))` or relative import
  - Use plotly for all charts with Chinese labels
  - Each cell must be independently re-runnable

  **Must NOT do**:
  - Do NOT add interactive widgets (ipywidgets) — static visualization only
  - Do NOT hardcode data — all data comes from MCP helpers
  - Do NOT share state with other notebooks

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Notebook creation with plotly visualization
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T8, T9)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: T3 (hypothesis data may be used), T5 (helpers module)

  **References**:

  **Pattern References**:
  - `contributing/notebooks.md` (from T2) — Follow notebook conventions defined there

  **API/Type References**:
  - `notebooks/helpers.py` (from T5) — Data access functions: `get_experiments()`, `get_best_strategies()`, `get_episode_summaries()`
  - Experiment data schema: `{id, name, strategy: JSON, params: JSON, result: {"final_nav": float, "sharpe": float, "max_drawdown": float}, created_at}`
  - Episode summary schema: `{id, period, initial_capital, final_nav, sharpe, max_drawdown, created_at}`

  **External References**:
  - Plotly Express API: `https://plotly.com/python/plotly-express/` — for line charts, histograms, bar charts

  **WHY Each Reference Matters**:
  - `helpers.py`: The ONLY way notebooks access data. Use these functions.
  - Experiment schema: Charts must reference correct field names from the JSON.

  **Acceptance Criteria**:
  - [ ] `notebooks/simulation.ipynb` exists and is valid JSON (nbformat)
  - [ ] Notebook contains ≥4 plotly chart cells
  - [ ] Notebook handles empty data gracefully (no crash on empty DataFrames)
  - [ ] `jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/simulation.ipynb` → success (may show empty-state messages if no MCP server)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Notebook is valid and can be parsed by nbformat
    Tool: Bash
    Preconditions: notebooks/simulation.ipynb created
    Steps:
      1. Run: uv run python -c "import nbformat; nb = nbformat.read('notebooks/simulation.ipynb', as_version=4); print(f'Cells: {len(nb.cells)}'); assert len(nb.cells) >= 5, 'Too few cells'; print('OK')"
    Expected Result: "Cells: N" (N >= 5), then "OK"
    Failure Indicators: nbformat.ValidationError or too few cells
    Evidence: .sisyphus/evidence/task-6-nbformat.txt

  Scenario: Notebook contains plotly imports and charts
    Tool: Bash
    Preconditions: Notebook created
    Steps:
      1. Run: grep -c "plotly" notebooks/simulation.ipynb
    Expected Result: Count >= 4 (at least 4 plotly references for charts)
    Failure Indicators: 0 plotly references
    Evidence: .sisyphus/evidence/task-6-plotly.txt
  ```

  **Commit**: YES
  - Message: `feat(notebooks): add simulation evolution visualization notebook`
  - Files: `notebooks/simulation.ipynb`

- [x] 7. Create Factor Analysis Notebook (notebooks/factors.ipynb)

  **What to do**:
  - Create `notebooks/factors.ipynb` — factor exposure and performance analysis
  - Sections:
    1. **Title + Description**: "因子分析" — 分析因子暴露、收益和换手率
    2. **Data Loading**: Fetch experiments data, parse strategy.factor combinations
    3. **Factor Frequency Chart**: Bar chart — how often each factor appears in successful strategies
    4. **Factor Performance Heatmap**: Heatmap (plotly) — factor vs. metric (sharpe, return, drawdown)
    5. **Weight Distribution**: Box plots — distribution of factor weights across experiments
    6. **Factor Correlation**: Which factors tend to co-occur in strategies
    7. **Empty State Handling**: Display message if no experiment data
  - Import helpers, use plotly with Chinese labels

  **Must NOT do**:
  - Do NOT compute actual factor values from market data — analyze only the factor metadata from experiments
  - Do NOT add interactive widgets

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Visualization notebook
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T8, T9)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: T3 (hypothesis data), T5 (helpers)

  **References**:

  **Pattern References**:
  - `contributing/notebooks.md` (from T2) — Notebook conventions

  **API/Type References**:
  - `notebooks/helpers.py` (from T5) — `get_experiments()`, `get_best_strategies()`
  - Strategy JSON in experiments: `{"factors": ["momentum_20d", "value_pe"], "weights": {"momentum_20d": 0.6, "value_pe": 0.4}, "universe": "沪深300", "rebalance": "weekly", "top_k": 50}`
  - Factor library from `generate_hypothesis.py`: momentum_20d/60d/120d, value_pe/pb/pc, quality_roe/debt/growth, low_vol_20d/60d, size_log_mcap

  **WHY Each Reference Matters**:
  - Strategy JSON: Charts parse factor names and weights from this structure.
  - Factor library: The complete set of factors — frequency chart should cover all 12.

  **Acceptance Criteria**:
  - [ ] `notebooks/factors.ipynb` exists and is valid nbformat
  - [ ] Notebook contains ≥3 plotly chart cells
  - [ ] Handles empty data gracefully
  - [ ] `jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/factors.ipynb` → success

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Notebook is valid nbformat
    Tool: Bash
    Steps:
      1. Run: uv run python -c "import nbformat; nb = nbformat.read('notebooks/factors.ipynb', as_version=4); print(f'Cells: {len(nb.cells)}'); assert len(nb.cells) >= 4; print('OK')"
    Expected Result: Valid notebook with ≥4 cells
    Evidence: .sisyphus/evidence/task-7-nbformat.txt

  Scenario: Notebook contains plotly charts
    Tool: Bash
    Steps:
      1. Run: grep -c "plotly" notebooks/factors.ipynb
    Expected Result: Count >= 3
    Evidence: .sisyphus/evidence/task-7-plotly.txt
  ```

  **Commit**: YES
  - Message: `feat(notebooks): add factor analysis visualization notebook`
  - Files: `notebooks/factors.ipynb`

- [x] 8. Create Backtest Results Notebook (notebooks/backtest.ipynb)

  **What to do**:
  - Create `notebooks/backtest.ipynb` — backtest performance visualization
  - Sections:
    1. **Title + Description**: "回测结果分析" — 回测表现、回撤和交易分析
    2. **Data Loading**: Fetch backtest results via `get_backtest_results()`
    3. **NAV Curve vs Benchmark**: Dual-axis line chart — strategy NAV vs benchmark over time
    4. **Drawdown Chart**: Area chart (plotly) — underwater plot showing drawdown periods
    5. **Performance Metrics Summary**: Table — Sharpe, MaxDD, Annual Return, Win Rate, Turnover
    6. **Trade Analysis**: Scatter plot — buy/sell points on price chart (if trade data available)
    7. **Empty State Handling**: Display message if no backtest data
  - Import helpers, use plotly with Chinese labels

  **Must NOT do**:
  - Do NOT run actual backtests — only visualize existing results
  - Do NOT add interactive widgets

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Visualization notebook
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T7, T9)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: T3, T5

  **References**:

  **Pattern References**:
  - `contributing/notebooks.md` (from T2) — Notebook conventions

  **API/Type References**:
  - `notebooks/helpers.py` (from T5) — `get_backtest_results()`
  - Backtest result schema from `trading-simulator/scripts/run_simulation.py` and `trading-simulator/scripts/simulator.py`:
    - `daily_nav`: `[{trade_date, nav, cash, daily_return, benchmark_return, excess_return, benchmark_value, benchmark_close}]`
    - `trades`: `[{trade_date, stock_code, direction, shares, price, amount, commission, stamp_duty, slippage_cost, total_cost, realized_pnl}]`
    - `positions`: `[{trade_date, stock_code, shares, cost_basis, market_value, unrealized_pnl, weight, sellable}]`
    - Performance: `{total_return, annual_return, sharpe_ratio, max_drawdown, calmar_ratio, win_rate, annual_turnover, ...}`

  **WHY Each Reference Matters**:
  - Backtest schema: Charts must use correct field names (e.g., `daily_return` not `returns`, `benchmark_return` not `benchmark`).

  **Acceptance Criteria**:
  - [ ] `notebooks/backtest.ipynb` exists and is valid nbformat
  - [ ] Notebook contains ≥4 plotly chart cells (NAV curve, drawdown, metrics table, trade scatter)
  - [ ] Handles empty data gracefully
  - [ ] `jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/backtest.ipynb` → success

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Notebook is valid nbformat
    Tool: Bash
    Steps:
      1. Run: uv run python -c "import nbformat; nb = nbformat.read('notebooks/backtest.ipynb', as_version=4); print(f'Cells: {len(nb.cells)}'); assert len(nb.cells) >= 5; print('OK')"
    Expected Result: Valid notebook with ≥5 cells
    Evidence: .sisyphus/evidence/task-8-nbformat.txt

  Scenario: Notebook contains NAV and drawdown charts
    Tool: Bash
    Steps:
      1. Run: grep -c "plotly" notebooks/backtest.ipynb
    Expected Result: Count >= 4
    Evidence: .sisyphus/evidence/task-8-plotly.txt
  ```

  **Commit**: YES
  - Message: `feat(notebooks): add backtest results visualization notebook`
  - Files: `notebooks/backtest.ipynb`

- [x] 9. Create Portfolio Notebook (notebooks/portfolio.ipynb)

  **What to do**:
  - Create `notebooks/portfolio.ipynb` — portfolio holdings and risk visualization
  - Sections:
    1. **Title + Description**: "投资组合分析" — 持仓分布、净值曲线和风险指标
    2. **Data Loading**: Fetch portfolio state via `get_portfolio()`, episode summaries via `get_episode_summaries()`
    3. **Current Holdings Pie Chart**: Pie chart (plotly) — position weights by stock
    4. **NAV History**: Line chart — portfolio NAV over time from episode summaries
    5. **Risk Metrics Dashboard**: Bar charts — Sharpe, MaxDD, Calmar across episodes
    6. **Cash vs Equity Split**: Stacked area — cash vs. invested capital over time
    7. **Empty State Handling**: Display message if no portfolio data
  - Import helpers, use plotly with Chinese labels

  **Must NOT do**:
  - Do NOT run portfolio optimization — only visualize existing state
  - Do NOT add interactive widgets

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Visualization notebook
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T6, T7, T8)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: T3, T5

  **References**:

  **Pattern References**:
  - `contributing/notebooks.md` (from T2) — Notebook conventions

  **API/Type References**:
  - `notebooks/helpers.py` (from T5) — `get_portfolio()`, `get_episode_summaries()`
  - Portfolio state: `{cash, positions: {code: volume}, nav, available_to_sell: {code: volume}}`
  - Episode summary: `{id, period, initial_capital, final_nav, sharpe, max_drawdown, created_at}`

  **WHY Each Reference Matters**:
  - Portfolio schema: Charts use `positions` dict for pie chart weights, `nav` for current value.
  - Episode summaries: Historical NAV data for line chart over time.

  **Acceptance Criteria**:
  - [ ] `notebooks/portfolio.ipynb` exists and is valid nbformat
  - [ ] Notebook contains ≥3 plotly chart cells (holdings pie, NAV line, risk metrics)
  - [ ] Handles empty data gracefully
  - [ ] `jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/portfolio.ipynb` → success

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Notebook is valid nbformat
    Tool: Bash
    Steps:
      1. Run: uv run python -c "import nbformat; nb = nbformat.read('notebooks/portfolio.ipynb', as_version=4); print(f'Cells: {len(nb.cells)}'); assert len(nb.cells) >= 4; print('OK')"
    Expected Result: Valid notebook with ≥4 cells
    Evidence: .sisyphus/evidence/task-9-nbformat.txt

  Scenario: Notebook contains plotly charts
    Tool: Bash
    Steps:
      1. Run: grep -c "plotly" notebooks/portfolio.ipynb
    Expected Result: Count >= 3
    Evidence: .sisyphus/evidence/task-9-plotly.txt
  ```

  **Commit**: YES
  - Message: `feat(notebooks): add portfolio visualization notebook`
  - Files: `notebooks/portfolio.ipynb`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check` + `uv run pytest`. Review all changed files for: unused imports, console.log in prod, commented-out code. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real QA Execution** — `unspecified-high`
  Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Run `jupyter nbconvert --execute` on all 4 notebooks. Run `uv run python scripts/check.py`. Verify no R6 warnings.
  Output: `Scenarios [N/N pass] | Notebooks [4/4] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **T1**: `fix(scripts): improve R6 rule to exclude SQL schema definitions` — scripts/check.py, pyproject.toml
- **T2**: `docs: add notebook writing conventions` — contributing/notebooks.md
- **T3**: `feat(simulation): add hypothesis generation for Meta-Agent` — evolution-loop/scripts/generate_hypothesis.py, test_generate_hypothesis.py
- **T4**: `feat(meta-strategist): enhance agent with evolution loop integration` — meta-strategist plugin files
- **T5**: `feat(notebooks): add shared MCP data access helper` — notebooks/helpers.py
- **T6-T9**: `feat(notebooks): add {name} visualization notebook` — notebooks/{name}.ipynb

---

## Success Criteria

### Verification Commands
```bash
# R6 fix
uv run python scripts/check.py  # Expected: 0 issues, no R6 warnings

# Hypothesis generation TDD
uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py -v
# Expected: >=5 tests, 0 failures

# All simulation tests
uv run pytest plugins/vertical-plugins/simulation/ -v  # Expected: all pass

# Notebook execution
jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/simulation.ipynb
jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/factors.ipynb
jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/backtest.ipynb
jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/portfolio.ipynb
# Expected: each produces output cells without errors

# Meta-strategist integration
cat plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json | grep "skills"
# Expected: array with simulation skill references
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] All 4 notebooks execute successfully via nbconvert
- [ ] check.py shows 0 issues
