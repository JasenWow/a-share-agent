# Phase 1+2: Base Restructure + Trading Simulator

## TL;DR

> **Quick Summary**: Restructure monolithic `a-share-analysis` plugin into 5 vertical plugins, create 2 new agents, delete 5 old agents, update validation scripts. Then build A-share trading simulator with TDD, extend internal-store with memory tables, and create experiment/evolution skills.
> 
> **Deliverables**:
> - 5 vertical plugin directories with migrated skills and commands
> - 2 new agent plugins (strategy-analyst, meta-strategist)
> - Updated `check.py` and `validate.py`
> - Trading simulator with T+1, price limits, transaction costs
> - Internal-store with experiments/transitions/episode_summaries tables
> - Experiment-tracker and evolution-loop skills
> 
> **Estimated Effort**: Large (14 implementation tasks + 4 verification tasks)
> **Parallel Execution**: YES - 6 waves
> **Critical Path**: T1 → T5 → T8 → T9 → T10 → T14 → F1-F4

---

## Context

### Original Request
User wants to implement Phase 1 (Base Restructure) and Phase 2 (Trading Simulator) from the roadmap at `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md`.

### Interview Summary
**Key Discussions**:
- **Scope**: Phase 1 + Phase 2 only (11 roadmap tasks → expanded to 14 plan tasks with cleanup)
- **Old agents**: DELETE stock-screener, factor-analyst, backtester, daily-predictor, northbound-monitor
- **New agents**: CREATE strategy-analyst, meta-strategist
- **Test strategy**: TDD for all Python code
- **check.py**: Include update in Phase 1
- **xlsx-author**: Lives in trading-strategy vertical, agents reference via `plugin.json` skills array

**Research Findings**:
- `check.py` line 55: hardcodes `a-share-analysis`, lines 64-71: hardcodes 6 old agents
- `validate.py` line 92: hardcodes `a-share-analysis`
- `sync-agent-skills.py`: already supports `skills` array in plugin.json but no agent uses it
- `internal-store/server.py`: 158 lines, 3 tables, 3 tools, connect→execute→close pattern
- `internal-store/schema.sql`: exists but NOT used by server.py (duplicate of `_init_db()` schema)
- Agent plugin.json format: `{name, version, description, author}` — simple, no skills array yet
- Only `backtest-engine` skill has Python scripts (6 files); other 8 skills are pure SKILL.md
- `xlsx-author` is referenced by ALL 6 agent cookbooks — will live in trading-strategy
- `managed-agent-cookbooks/`: 6 dirs (3 to delete, 3 to update paths)

### Metis Review
**Identified Gaps** (all addressed):
- **xlsx-author shared skill**: Placed in `trading-strategy/skills/`, agents reference via skills array
- **schema.sql vs _init_db()**: Both will be updated in Phase 2
- **Old agent deletion safety**: Added grep verification before deletion
- **Managed-agent-cookbooks**: 3 deleted with agents, 3 kept with updated skill paths
- **Rollback**: Git provides rollback (all changes are file moves/deletions)
- **No MCP server changes in Phase 1**: Confirmed — Phase 2 only extends internal-store

---

## Work Objectives

### Core Objective
Restructure monolithic plugin architecture into 5 vertical plugins with proper agent boundaries, then build the A-share trading simulator sandbox with full market rules.

### Concrete Deliverables
- `plugins/vertical-plugins/{market-data,equity-research,trading-strategy,simulation,market-monitor}/`
- `plugins/agent-plugins/strategy-analyst/`
- `plugins/agent-plugins/meta-strategist/`
- `plugins/vertical-plugins/simulation/skills/trading-simulator/` (simulator.py, market_rules.py)
- `mcp-servers/internal-store/server.py` (3 new tables + 4 new tools)
- `plugins/vertical-plugins/simulation/skills/experiment-tracker/`
- `plugins/vertical-plugins/simulation/skills/evolution-loop/`

### Definition of Done
- [ ] `uv run python scripts/check.py` → exit code 0
- [ ] `uv run python scripts/validate.py` → exit code 0
- [ ] `uv run pytest plugins/vertical-plugins/simulation/ -v` → all pass
- [ ] `uv run pytest mcp-servers/internal-store/test_server.py -v` → all pass
- [ ] `grep -r "a-share-analysis" plugins/ scripts/` → no matches
- [ ] `grep -r "stock-screener\|factor-analyst\|backtester\|daily-predictor\|northbound-monitor" plugins/` → no matches (except kept market-monitor)

### Must Have
- 5 vertical plugin directories with correct skill/command distribution
- 2 new agent plugins following existing conventions
- check.py and validate.py updated for new structure
- Trading simulator enforcing T+1, price limits (±10%/±20%/±30%/±5%), transaction costs, lot size
- Internal-store with experiments, transitions, episode_summaries tables
- TDD: all Python code has tests written before implementation

### Must NOT Have (Guardrails)
- **NO behavior changes** to existing skills during migration — pure file moves
- **NO changes to akshare-server or tushare-server** in Phase 1 or Phase 2
- **NO modifications to existing internal-store tables** (cache_entries, backtest_results, portfolio_state)
- **NO connection pooling** added to internal-store in this phase
- **NO plugin.json format migration** for existing kept agents (equity-researcher, portfolio-manager, market-monitor)
- **NO domain/business logic in MCP tools** — only data access (R6)
- **NO cross-vertical skill imports** — skills must be self-contained within their vertical
- **NO deleting a-share-analysis** until all skills/commands are confirmed migrated

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in pyproject.toml)
- **Automated tests**: YES (TDD for Phase 2 Python code)
- **Framework**: pytest
- **TDD scope**: All new Python files (simulator.py, market_rules.py, evolution.py, track_experiment.py, new internal-store tools)
- **TDD does NOT apply to**: File moves (Phase 1), SKILL.md creation, config file creation

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **File structure verification**: Use Bash (`ls`, `test -f`, `grep`)
- **Script validation**: Use Bash (`uv run python scripts/check.py`)
- **Python TDD**: Use Bash (`uv run pytest`)
- **API verification**: Use Bash (`curl` to internal-store)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation, ALL parallel):
├── T1:  Create 5 vertical plugin directories + configs [quick]
├── T2:  Create strategy-analyst agent plugin [quick]
├── T3:  Create meta-strategist agent plugin [quick]
└── T4:  Update check.py + validate.py for new structure [quick]

Wave 2 (After T1 — file migrations, parallel):
├── T5:  Migrate skills from a-share-analysis to 5 verticals [quick]
├── T6:  Migrate commands to verticals + create missing commands dirs [quick]
└── T7:  Delete old agents + orphaned cookbooks [quick]

Wave 3 (After T5, T6, T7 — docs + cleanup):
├── T8:  Update contributing documentation [writing]
└── T9:  Delete a-share-analysis + update cookbooks + verify Phase 1 [quick]

Wave 4 (After T9 — Phase 2 core, ALL parallel):
├── T10: Trading simulator core (TDD) [deep]
├── T11: Internal-store memory extension (TDD) [unspecified-high]
├── T12: Evolution loop skill [unspecified-high]
└── T13: Experiment tracker skill [quick]

Wave 5 (After T10, T11, T12, T13 — integration):
└── T14: Integration test — full simulation cycle [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: T1 → T5 → T9 → T10 → T14 → F1-F4 → user okay
Max Concurrent: 4 (Waves 1 and 4)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| T1 | — | T5, T6, T9 | 1 |
| T2 | — | T9 | 1 |
| T3 | — | T9 | 1 |
| T4 | — | T9 | 1 |
| T5 | T1 | T8, T9 | 2 |
| T6 | T1 | T8, T9 | 2 |
| T7 | — | T8, T9 | 2 |
| T8 | T5, T6, T7 | — | 3 |
| T9 | T1-T8 | T10-T14 | 3 |
| T10 | T9 | T14 | 4 |
| T11 | T9 | T13, T14 | 4 |
| T12 | T9 | T14 | 4 |
| T13 | T9 | T14 | 4 |
| T14 | T10, T11, T12, T13 | F1-F4 | 5 |
| F1-F4 | T14 | user okay | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1-T3 → `quick`, T4 → `quick`
- **Wave 2**: 3 tasks — T5-T7 → `quick`
- **Wave 3**: 2 tasks — T8 → `writing`, T9 → `quick`
- **Wave 4**: 4 tasks — T10 → `deep`, T11 → `unspecified-high`, T12 → `unspecified-high`, T13 → `quick`
- **Wave 5**: 1 task — T14 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Create 5 Vertical Plugin Directories with Configs

  **What to do**:
  - Create 5 directories under `plugins/vertical-plugins/`: `market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor`
  - Each directory needs: `.claude-plugin/plugin.json`, `.mcp.json`, `AGENTS.md`, `skills/`, `commands/`, `hooks/hooks.json`
  - Copy `.mcp.json` from existing `a-share-analysis/.mcp.json` (same MCP server config)
  - Create per-vertical `plugin.json` with correct skill lists and MCP dependencies
  - Create minimal per-vertical `AGENTS.md` (placeholder with vertical name and purpose)
  - Create empty `hooks/hooks.json` (`[]`)
  - Skill distribution per vertical:
    - **market-data**: factor-screen, factor-research, portfolio-optimize
    - **equity-research**: financial-analysis
    - **trading-strategy**: backtest-engine, xlsx-author
    - **simulation**: (empty for now, Phase 2 adds skills)
    - **market-monitor**: market-breadth, next-day-predict, northbound-monitor

  **Must NOT do**:
  - Do NOT move any skill files yet (that's T5)
  - Do NOT delete a-share-analysis
  - Do NOT create any Python code

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T2, T3, T4)
  - **Blocks**: T5, T6, T9
  - **Blocked By**: None

  **References**:
  **Pattern References**:
  - `plugins/vertical-plugins/a-share-analysis/.claude-plugin/plugin.json` — existing plugin.json format to follow
  - `plugins/vertical-plugins/a-share-analysis/.mcp.json` — MCP server config to replicate
  - `plugins/vertical-plugins/a-share-analysis/AGENTS.md` — AGENTS.md format to follow
  - `plugins/vertical-plugins/a-share-analysis/hooks/hooks.json` — empty hooks format (`[]`)
  - `contributing/architecture.md:29-34` — vertical plugin definitions and skill groupings
  - `contributing/architecture.md:336-378` — Skill Catalog with per-vertical skill lists

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: All 5 vertical directories exist
    Tool: Bash
    Steps:
      1. ls plugins/vertical-plugins/
    Expected Result: Output contains "market-data", "equity-research", "trading-strategy", "simulation", "market-monitor" (5 dirs + a-share-analysis still exists)
    Evidence: .sisyphus/evidence/task-1-verticals-exist.txt

  Scenario: Each vertical has required subdirectories and config
    Tool: Bash
    Steps:
      1. for dir in market-data equity-research trading-strategy simulation market-monitor; do test -f plugins/vertical-plugins/$dir/.claude-plugin/plugin.json && echo "$dir: plugin.json OK" || echo "$dir: MISSING plugin.json"; done
      2. for dir in market-data equity-research trading-strategy simulation market-monitor; do test -d plugins/vertical-plugins/$dir/skills && echo "$dir: skills/ OK" || echo "$dir: MISSING skills/"; done
      3. for dir in market-data equity-research trading-strategy simulation market-monitor; do test -d plugins/vertical-plugins/$dir/commands && echo "$dir: commands/ OK" || echo "$dir: MISSING commands/"; done
    Expected Result: All 5 verticals have plugin.json, skills/, commands/
    Evidence: .sisyphus/evidence/task-1-structure-check.txt

  Scenario: plugin.json has correct skill lists
    Tool: Bash
    Steps:
      1. python3 -c "import json; d=json.load(open('plugins/vertical-plugins/market-data/.claude-plugin/plugin.json')); assert 'factor-screen' in d.get('skills',[]); assert 'factor-research' in d.get('skills',[]); print('market-data skills OK')"
      2. python3 -c "import json; d=json.load(open('plugins/vertical-plugins/trading-strategy/.claude-plugin/plugin.json')); assert 'backtest-engine' in d.get('skills',[]); assert 'xlsx-author' in d.get('skills',[]); print('trading-strategy skills OK')"
      3. python3 -c "import json; d=json.load(open('plugins/vertical-plugins/market-monitor/.claude-plugin/plugin.json')); assert 'market-breadth' in d.get('skills',[]); assert 'northbound-monitor' in d.get('skills',[]); print('market-monitor skills OK')"
    Expected Result: All assertions pass
    Evidence: .sisyphus/evidence/task-1-plugin-json-check.txt
  ```

  **Commit**: YES
  - Message: `feat: create 5 vertical plugin directories with configs`
  - Files: `plugins/vertical-plugins/{market-data,equity-research,trading-strategy,simulation,market-monitor}/`

- [x] 2. Create Strategy-Analyst Agent Plugin

  **What to do**:
  - Create `plugins/agent-plugins/strategy-analyst/` with `.claude-plugin/plugin.json` and `agents/strategy-analyst.md`
  - `plugin.json` follows existing convention: `{name, version, description, author}`
  - `strategy-analyst.md` uses YAML frontmatter + `## What you produce` + `## Workflow` + `## Guardrails`
  - Strategy-analyst combines functionality from old `factor-analyst` + `backtester` agents
  - Triggers: `/factor`, `/backtest`
  - Tools: Read, Write, Edit, Bash, mcp__akshare__*, mcp__tushare__*, mcp__internal-store__*

  **Must NOT do**:
  - Do NOT create `system-prompt.md` (not required, only daily-predictor has it)
  - Do NOT add `skills` array to plugin.json yet (format migration is separate)
  - Do NOT delete old agents (that's T7)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T3, T4)
  - **Blocks**: T9
  - **Blocked By**: None

  **References**:
  **Pattern References**:
  - `plugins/agent-plugins/backtester/.claude-plugin/plugin.json` — canonical plugin.json format (`{name, version, description, author}`)
  - `plugins/agent-plugins/backtester/agents/backtester.md` — canonical agent .md format (YAML frontmatter + 3 sections)
  - `plugins/agent-plugins/equity-researcher/agents/equity-researcher.md` — another agent .md example

  **API/Type References**:
  - `contributing/architecture.md:329` — strategy-analyst in Agent Catalog table
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:143-180` — roadmap's strategy-analyst definition with workflow and guardrails

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: strategy-analyst directory exists with required files
    Tool: Bash
    Steps:
      1. test -f plugins/agent-plugins/strategy-analyst/.claude-plugin/plugin.json && echo "plugin.json OK" || echo "MISSING"
      2. test -f plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "agent.md OK" || echo "MISSING"
    Expected Result: Both files exist
    Evidence: .sisyphus/evidence/task-2-strategy-analyst-exists.txt

  Scenario: agent .md has required sections
    Tool: Bash
    Steps:
      1. grep -q "## What you produce" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "OK" || echo "MISSING 'What you produce'"
      2. grep -q "## Workflow" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "OK" || echo "MISSING 'Workflow'"
      3. grep -q "## Guardrails" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "OK" || echo "MISSING 'Guardrails'"
      4. grep -q "^name: strategy-analyst" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "frontmatter OK" || echo "MISSING frontmatter"
    Expected Result: All 4 checks pass
    Evidence: .sisyphus/evidence/task-2-strategy-analyst-content.txt

  Scenario: A-share constraints in guardrails
    Tool: Bash
    Steps:
      1. grep -qi "T+1" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "T+1 OK" || echo "MISSING T+1 guardrail"
      2. grep -qi "transaction cost" plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md && echo "costs OK" || echo "MISSING transaction cost guardrail"
    Expected Result: Both A-share guardrails present
    Evidence: .sisyphus/evidence/task-2-guardrails.txt
  ```

  **Commit**: YES
  - Message: `feat: add strategy-analyst agent plugin`
  - Files: `plugins/agent-plugins/strategy-analyst/`

- [x] 3. Create Meta-Strategist Agent Plugin

  **What to do**:
  - Create `plugins/agent-plugins/meta-strategist/` with `.claude-plugin/plugin.json`, `agents/meta-strategist.md`, and `agents/system-prompt.md`
  - Meta-strategist is L3 Meta-Agent for autonomous strategy exploration
  - `system-prompt.md` defines evolution loop, doom loop prevention, memory query integration
  - `meta-strategist.md` defines persona, deliverables, workflow, guardrails
  - Triggers: `/evolve`
  - Tools: Read, Write, Edit, Bash, mcp__akshare__*, mcp__tushare__*, mcp__internal-store__*

  **Must NOT do**:
  - Do NOT wire to simulation skills yet (that's Phase 3 roadmap scope)
  - Do NOT create simulation skills (Phase 2 tasks)
  - Do NOT add skills array to plugin.json yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T4)
  - **Blocks**: T9
  - **Blocked By**: None

  **References**:
  **Pattern References**:
  - `plugins/agent-plugins/daily-predictor/agents/system-prompt.md` — example of system-prompt.md format
  - `plugins/agent-plugins/backtester/.claude-plugin/plugin.json` — canonical plugin.json format
  - `plugins/agent-plugins/backtester/agents/backtester.md` — canonical agent .md format

  **API/Type References**:
  - `contributing/architecture.md:104-166` — Meta-Agent Architecture, Evolution Loop, Autonomy Table
  - `contributing/architecture.md:327` — meta-strategist in Agent Catalog
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:189-213` — roadmap's meta-strategist definition

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: meta-strategist directory exists with required files
    Tool: Bash
    Steps:
      1. test -f plugins/agent-plugins/meta-strategist/.claude-plugin/plugin.json && echo "plugin.json OK" || echo "MISSING"
      2. test -f plugins/agent-plugins/meta-strategist/agents/meta-strategist.md && echo "agent.md OK" || echo "MISSING"
      3. test -f plugins/agent-plugins/meta-strategist/agents/system-prompt.md && echo "system-prompt OK" || echo "MISSING"
    Expected Result: All 3 files exist
    Evidence: .sisyphus/evidence/task-3-meta-strategist-exists.txt

  Scenario: system-prompt.md describes evolution loop
    Tool: Bash
    Steps:
      1. grep -qi "evolution loop\|evolution Loop" plugins/agent-plugins/meta-strategist/agents/system-prompt.md && echo "OK" || echo "MISSING evolution loop"
      2. grep -qi "doom loop\|doom_loop" plugins/agent-plugins/meta-strategist/agents/system-prompt.md && echo "OK" || echo "MISSING doom loop prevention"
      3. grep -qi "internal-store\|MemoryStore\|memory store" plugins/agent-plugins/meta-strategist/agents/system-prompt.md && echo "OK" || echo "MISSING memory store reference"
    Expected Result: All 3 concepts present
    Evidence: .sisyphus/evidence/task-3-system-prompt-content.txt

  Scenario: agent .md has required sections and guardrails
    Tool: Bash
    Steps:
      1. grep -q "## What you produce" plugins/agent-plugins/meta-strategist/agents/meta-strategist.md && echo "OK" || echo "MISSING"
      2. grep -q "## Workflow" plugins/agent-plugins/meta-strategist/agents/meta-strategist.md && echo "OK" || echo "MISSING"
      3. grep -q "## Guardrails" plugins/agent-plugins/meta-strategist/agents/meta-strategist.md && echo "OK" || echo "MISSING"
      4. grep -qi "point-in-time\|look-ahead" plugins/agent-plugins/meta-strategist/agents/meta-strategist.md && echo "OK" || echo "MISSING look-ahead bias guardrail"
    Expected Result: All checks pass
    Evidence: .sisyphus/evidence/task-3-guardrails.txt
  ```

  **Commit**: YES
  - Message: `feat: add meta-strategist agent plugin`
  - Files: `plugins/agent-plugins/meta-strategist/`

- [x] 4. Update check.py and validate.py for New Structure

  **What to do**:
  - Update `scripts/check.py` `check_plugin_structure()` function (lines 50-82):
    - Change vertical plugin check from `a-share-analysis` to check ALL 5 verticals: `market-data`, `equity-research`, `trading-strategy`, `simulation`, `market-monitor`
    - Each vertical must have: `.claude-plugin`, `skills`, `commands`
    - Update agent list from 6 old agents to 5 target agents: `equity-researcher`, `strategy-analyst`, `portfolio-manager`, `market-monitor`, `meta-strategist`
  - Update `scripts/validate.py` `main()` function (line 92):
    - Change from validating single `a-share-analysis` to iterating over ALL directories in `plugins/vertical-plugins/`
    - Keep existing `validate_vertical_plugin()` logic (it's generic enough)
  - Verify both scripts still import correctly after changes

  **Must NOT do**:
  - Do NOT change the boundary rule checking logic (R1-R6 checks are correct)
  - Do NOT change the MCP server checking logic
  - Do NOT change `sync-agent-skills.py` (it's already generic)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with T1, T2, T3)
  - **Blocks**: T9
  - **Blocked By**: None

  **References**:
  **Pattern References**:
  - `scripts/check.py:50-82` — `check_plugin_structure()` function to update (hardcoded `a-share-analysis` at line 55, hardcoded agent list at lines 64-71)
  - `scripts/validate.py:85-125` — `main()` function to update (hardcoded `a-share-analysis` at line 92)
  - `contributing/architecture.md:325-331` — target Agent Catalog (5 agents)
  - `contributing/architecture.md:29-34` — target vertical plugin list (5 verticals)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: check.py references new structure
    Tool: Bash
    Steps:
      1. grep -q "market-data" scripts/check.py && echo "market-data found" || echo "MISSING market-data"
      2. grep -q "trading-strategy" scripts/check.py && echo "trading-strategy found" || echo "MISSING trading-strategy"
      3. grep -q "simulation" scripts/check.py && echo "simulation found" || echo "MISSING simulation"
      4. grep -q "meta-strategist" scripts/check.py && echo "meta-strategist found" || echo "MISSING meta-strategist"
      5. grep -q "strategy-analyst" scripts/check.py && echo "strategy-analyst found" || echo "MISSING strategy-analyst"
      6. grep -q "a-share-analysis" scripts/check.py && echo "OLD REFERENCE STILL EXISTS" || echo "old reference removed OK"
    Expected Result: Lines 1-5 OK, line 6 shows old reference removed
    Evidence: .sisyphus/evidence/task-4-check-py-updated.txt

  Scenario: validate.py validates all vertical plugins
    Tool: Bash
    Steps:
      1. grep -q "a-share-analysis" scripts/validate.py && echo "OLD REFERENCE STILL EXISTS" || echo "old reference removed OK"
      2. grep -q "vertical_plugins\|vertical-plugins" scripts/validate.py && echo "generic vertical iteration found" || echo "MISSING generic iteration"
    Expected Result: Old reference removed, new generic iteration present
    Evidence: .sisyphus/evidence/task-4-validate-py-updated.txt

  Scenario: Scripts import without errors
    Tool: Bash
    Steps:
      1. uv run python -c "import importlib.util; spec=importlib.util.spec_from_file_location('check','scripts/check.py'); mod=importlib.util.module_from_spec(spec); print('check.py imports OK')"
      2. uv run python -c "import importlib.util; spec=importlib.util.spec_from_file_location('validate','scripts/validate.py'); mod=importlib.util.module_from_spec(spec); print('validate.py imports OK')"
    Expected Result: Both scripts import without errors
    Evidence: .sisyphus/evidence/task-4-imports.txt
  ```

  **Commit**: YES
  - Message: `refactor: update check.py and validate.py for 5-vertical structure`
  - Files: `scripts/check.py`, `scripts/validate.py`

- [x] 5. Migrate Skills from a-share-analysis to 5 Verticals

  **What to do**:
  - Move 9 skill directories from `plugins/vertical-plugins/a-share-analysis/skills/` to their target verticals:
    - `factor-screen` → `plugins/vertical-plugins/market-data/skills/`
    - `factor-research` → `plugins/vertical-plugins/market-data/skills/`
    - `portfolio-optimize` → `plugins/vertical-plugins/market-data/skills/`
    - `financial-analysis` → `plugins/vertical-plugins/equity-research/skills/`
    - `backtest-engine` → `plugins/vertical-plugins/trading-strategy/skills/`
    - `xlsx-author` → `plugins/vertical-plugins/trading-strategy/skills/`
    - `market-breadth` → `plugins/vertical-plugins/market-monitor/skills/`
    - `next-day-predict` → `plugins/vertical-plugins/simulation/skills/`
    - `northbound-monitor` → `plugins/vertical-plugins/market-monitor/skills/`
  - Use `git mv` for each move to preserve history
  - Do NOT move `__pycache__/` directories (let them be recreated)
  - Verify each SKILL.md is accessible at its new location after move

  **Must NOT do**:
  - Do NOT modify any SKILL.md content (pure file move)
  - Do NOT modify any Python scripts (pure file move)
  - Do NOT delete a-share-analysis directory yet (T9)
  - Do NOT update references in other files yet (T8, T9)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T6, T7)
  - **Blocks**: T8, T9
  - **Blocked By**: T1 (vertical directories must exist)

  **References**:
  **Pattern References**:
  - `plugins/vertical-plugins/a-share-analysis/skills/` — source directory (9 skill subdirectories)
  - `contributing/architecture.md:337-378` — Skill Catalog showing which skills belong to which vertical

  **WHY**: The executor needs to know exact source → target mapping. Each skill is a self-contained directory with SKILL.md and optionally scripts/, examples/, references/. The move preserves all contents.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: All skills moved to correct verticals
    Tool: Bash
    Steps:
      1. test -d plugins/vertical-plugins/market-data/skills/factor-screen && echo "factor-screen OK" || echo "MISSING factor-screen in market-data"
      2. test -d plugins/vertical-plugins/market-data/skills/factor-research && echo "factor-research OK" || echo "MISSING"
      3. test -d plugins/vertical-plugins/market-data/skills/portfolio-optimize && echo "portfolio-optimize OK" || echo "MISSING"
      4. test -d plugins/vertical-plugins/equity-research/skills/financial-analysis && echo "financial-analysis OK" || echo "MISSING"
      5. test -d plugins/vertical-plugins/trading-strategy/skills/backtest-engine && echo "backtest-engine OK" || echo "MISSING"
      6. test -d plugins/vertical-plugins/trading-strategy/skills/xlsx-author && echo "xlsx-author OK" || echo "MISSING"
      7. test -d plugins/vertical-plugins/market-monitor/skills/market-breadth && echo "market-breadth OK" || echo "MISSING"
      8. test -d plugins/vertical-plugins/market-monitor/skills/northbound-monitor && echo "northbound-monitor OK" || echo "MISSING"
      9. test -d plugins/vertical-plugins/simulation/skills/next-day-predict && echo "next-day-predict OK" || echo "MISSING"
    Expected Result: All 9 skills at correct locations
    Evidence: .sisyphus/evidence/task-5-skills-moved.txt

  Scenario: SKILL.md files are intact after move
    Tool: Bash
    Steps:
      1. for skill in factor-screen factor-research portfolio-optimize; do test -f plugins/vertical-plugins/market-data/skills/$skill/SKILL.md && echo "$skill SKILL.md OK" || echo "MISSING $skill SKILL.md"; done
      2. test -f plugins/vertical-plugins/trading-strategy/skills/backtest-engine/SKILL.md && echo "backtest-engine SKILL.md OK" || echo "MISSING"
      3. test -f plugins/vertical-plugins/trading-strategy/skills/backtest-engine/scripts/engine.py && echo "engine.py OK" || echo "MISSING engine.py"
    Expected Result: All SKILL.md files accessible, backtest-engine Python scripts intact
    Evidence: .sisyphus/evidence/task-5-skill-md-intact.txt

  Scenario: Old location is empty (skills moved out)
    Tool: Bash
    Steps:
      1. ls plugins/vertical-plugins/a-share-analysis/skills/ 2>/dev/null | wc -l
    Expected Result: 0 (or directory doesn't exist)
    Evidence: .sisyphus/evidence/task-5-old-empty.txt
  ```

  **Commit**: YES
  - Message: `feat: migrate skills from a-share-analysis to 5 verticals`
  - Files: `plugins/vertical-plugins/`

- [x] 6. Migrate Commands to Respective Verticals

  **What to do**:
  - Move 7 command files from `plugins/vertical-plugins/a-share-analysis/commands/` to their target verticals:
    - `screen.md` → `plugins/vertical-plugins/market-data/commands/`
    - `factor.md` → `plugins/vertical-plugins/market-data/commands/`
    - `optimize.md` → `plugins/vertical-plugins/market-data/commands/`
    - `research.md` → `plugins/vertical-plugins/equity-research/commands/`
    - `backtest.md` → `plugins/vertical-plugins/trading-strategy/commands/`
    - `market.md` → `plugins/vertical-plugins/market-monitor/commands/`
    - `predict.md` → `plugins/vertical-plugins/simulation/commands/`
  - Use `git mv` for each move

  **Must NOT do**:
  - Do NOT modify command content
  - Do NOT create new commands (only move existing ones)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T5, T7)
  - **Blocks**: T8, T9
  - **Blocked By**: T1 (vertical directories with commands/ must exist)

  **References**:
  **Pattern References**:
  - `plugins/vertical-plugins/a-share-analysis/commands/` — source directory (7 command files)
  - `contributing/README.md:20-28` — slash command table showing which commands belong to which agent/vertical

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: All commands moved to correct verticals
    Tool: Bash
    Steps:
      1. test -f plugins/vertical-plugins/market-data/commands/screen.md && echo "screen OK" || echo "MISSING"
      2. test -f plugins/vertical-plugins/market-data/commands/factor.md && echo "factor OK" || echo "MISSING"
      3. test -f plugins/vertical-plugins/market-data/commands/optimize.md && echo "optimize OK" || echo "MISSING"
      4. test -f plugins/vertical-plugins/equity-research/commands/research.md && echo "research OK" || echo "MISSING"
      5. test -f plugins/vertical-plugins/trading-strategy/commands/backtest.md && echo "backtest OK" || echo "MISSING"
      6. test -f plugins/vertical-plugins/market-monitor/commands/market.md && echo "market OK" || echo "MISSING"
      7. test -f plugins/vertical-plugins/simulation/commands/predict.md && echo "predict OK" || echo "MISSING"
    Expected Result: All 7 commands at correct locations
    Evidence: .sisyphus/evidence/task-6-commands-moved.txt
  ```

  **Commit**: YES
  - Message: `feat: migrate commands to respective vertical plugins`
  - Files: `plugins/vertical-plugins/`

- [x] 7. Delete Old Agents and Orphaned Cookbooks

  **What to do**:
  - Delete 5 old agent plugin directories:
    - `plugins/agent-plugins/stock-screener/`
    - `plugins/agent-plugins/factor-analyst/`
    - `plugins/agent-plugins/backtester/`
    - `plugins/agent-plugins/daily-predictor/`
    - `plugins/agent-plugins/northbound-monitor/`
  - Delete 3 corresponding managed-agent-cookbooks:
    - `managed-agent-cookbooks/stock-screener/`
    - `managed-agent-cookbooks/factor-analyst/`
    - `managed-agent-cookbooks/backtester/`
  - Before deletion, grep codebase for any remaining references to deleted agent names that would break
  - Use `git rm -r` for each deletion

  **Must NOT do**:
  - Do NOT delete kept agents: `equity-researcher`, `portfolio-manager`, `market-monitor`
  - Do NOT delete kept cookbooks: `equity-researcher/`, `portfolio-manager/`, `market-monitor/`
  - Do NOT delete a-share-analysis yet (T9)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with T5, T6)
  - **Blocks**: T8, T9
  - **Blocked By**: None (deletion is independent of file moves)

  **References**:
  **Pattern References**:
  - `plugins/agent-plugins/` — current 8 agent directories
  - `managed-agent-cookbooks/` — current 6 cookbook directories

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Old agents deleted, kept agents intact
    Tool: Bash
    Steps:
      1. for agent in stock-screener factor-analyst backtester daily-predictor northbound-monitor; do test -d plugins/agent-plugins/$agent && echo "FAIL: $agent still exists" || echo "OK: $agent deleted"; done
      2. for agent in equity-researcher portfolio-manager market-monitor; do test -d plugins/agent-plugins/$agent && echo "OK: $agent kept" || echo "FAIL: $agent missing"; done
    Expected Result: 5 old agents gone, 3 kept agents intact
    Evidence: .sisyphus/evidence/task-7-agents-deleted.txt

  Scenario: Old cookbooks deleted, kept cookbooks intact
    Tool: Bash
    Steps:
      1. for book in stock-screener factor-analyst backtester; do test -d managed-agent-cookbooks/$book && echo "FAIL: $book still exists" || echo "OK: $book deleted"; done
      2. for book in equity-researcher portfolio-manager market-monitor; do test -d managed-agent-cookbooks/$book && echo "OK: $book kept" || echo "FAIL: $book missing"; done
    Expected Result: 3 old cookbooks gone, 3 kept cookbooks intact
    Evidence: .sisyphus/evidence/task-7-cookbooks-deleted.txt

  Scenario: No broken references to deleted agents
    Tool: Bash
    Steps:
      1. grep -r "stock-screener\|factor-analyst\|backtester\|daily-predictor\|northbound-monitor" plugins/ --include="*.md" --include="*.json" -l 2>/dev/null | grep -v "market-monitor" || echo "No broken references found"
    Expected Result: No references to deleted agents (except legitimate "market-monitor" references to northbound-monitor skill)
    Failure Indicators: Any file references deleted agent names
    Evidence: .sisyphus/evidence/task-7-no-broken-refs.txt
  ```

  **Commit**: YES
  - Message: `chore: remove deprecated agent plugins and cookbooks`
  - Files: `plugins/agent-plugins/`, `managed-agent-cookbooks/`

- [x] 8. Update Contributing Documentation

  **What to do**:
  - Update `contributing/architecture.md` — already describes target state, verify no stale `a-share-analysis` references remain
  - Update `contributing/README.md` — verify slash command table matches new verticals
  - Update `AGENTS.md` at project root — verify agent catalog matches new structure
  - Update `README.md` at project root — verify project structure, commands, agent list
  - Scan all docs for references to deleted agents or `a-share-analysis` and update them
  - Verify docs accurately reflect the new 5-vertical, 5-agent structure

  **Must NOT do**:
  - Do NOT add new documentation sections (only update existing references)
  - Do NOT modify contributing/mcp-servers.md, contributing/testing.md, contributing/coding-standards.md (these are correct)
  - Do NOT rewrite entire docs — only fix stale references

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs T5, T6, T7 complete to know final state)
  - **Parallel Group**: Wave 3 (with T9, but T9 should wait for T8)
  - **Blocks**: T9
  - **Blocked By**: T5, T6, T7

  **References**:
  **Pattern References**:
  - `contributing/architecture.md` — target architecture (may already be correct)
  - `contributing/README.md` — slash command table
  - `AGENTS.md` — project root agent catalog
  - `README.md` — project root overview

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: No stale a-share-analysis references in docs
    Tool: Bash
    Steps:
      1. grep -r "a-share-analysis" contributing/ README.md AGENTS.md --include="*.md" -n
    Expected Result: Zero matches (all references updated)
    Evidence: .sisyphus/evidence/task-8-no-stale-refs.txt

  Scenario: Docs list correct 5 agents
    Tool: Bash
    Steps:
      1. grep -c "meta-strategist" contributing/architecture.md && echo "meta-strategist found"
      2. grep -c "strategy-analyst" contributing/architecture.md && echo "strategy-analyst found"
      3. grep -c "equity-researcher" contributing/architecture.md && echo "equity-researcher found"
      4. grep -c "portfolio-manager" contributing/architecture.md && echo "portfolio-manager found"
      5. grep -c "market-monitor" contributing/architecture.md && echo "market-monitor found"
    Expected Result: All 5 target agents mentioned in architecture docs
    Evidence: .sisyphus/evidence/task-8-agent-catalog.txt

  Scenario: Docs list correct 5 verticals
    Tool: Bash
    Steps:
      1. grep -c "market-data" contributing/architecture.md && echo "market-data found"
      2. grep -c "equity-research" contributing/architecture.md | head -1 && echo "equity-research vertical found"
      3. grep -c "trading-strategy" contributing/architecture.md && echo "trading-strategy found"
      4. grep -c "simulation" contributing/architecture.md | head -1 && echo "simulation found"
      5. grep -c "market-monitor" contributing/architecture.md | head -1 && echo "market-monitor vertical found"
    Expected Result: All 5 verticals mentioned
    Evidence: .sisyphus/evidence/task-8-vertical-catalog.txt
  ```

  **Commit**: YES
  - Message: `docs: update contributing docs for 5-vertical structure`
  - Files: `contributing/`, `README.md`, `AGENTS.md`

- [x] 9. Delete a-share-analysis + Update Kept Cookbooks + Verify Phase 1

  **What to do**:
  - Delete `plugins/vertical-plugins/a-share-analysis/` with `git rm -r`
  - Update 3 kept managed-agent-cookbooks to reference new skill paths:
    - `managed-agent-cookbooks/equity-researcher/agent.yaml` — update skill paths from `a-share-analysis/skills/X` to new vertical paths
    - `managed-agent-cookbooks/portfolio-manager/agent.yaml` — update skill paths
    - `managed-agent-cookbooks/market-monitor/agent.yaml` — update skill paths
  - Run full Phase 1 verification:
    - `uv run python scripts/check.py` → exit 0
    - `uv run python scripts/validate.py` → exit 0
    - `uv run python scripts/sync-agent-skills.py --check` → no errors
  - If any verification fails, fix issues before proceeding to Phase 2

  **Must NOT do**:
  - Do NOT proceed to Phase 2 if verification fails
  - Do NOT modify any Python code in skills/ or MCP servers
  - Do NOT add skills arrays to kept agents' plugin.json (out of scope)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on all previous tasks)
  - **Parallel Group**: Wave 3 (after T8)
  - **Blocks**: T10, T11, T12, T13 (all Phase 2 tasks)
  - **Blocked By**: T1-T8

  **References**:
  **Pattern References**:
  - `managed-agent-cookbooks/equity-researcher/agent.yaml` — needs skill path update
  - `managed-agent-cookbooks/portfolio-manager/agent.yaml` — needs skill path update
  - `managed-agent-cookbooks/market-monitor/agent.yaml` — needs skill path update
  - `scripts/check.py` — updated in T4, should now pass
  - `scripts/validate.py` — updated in T4, should now pass
  - `scripts/sync-agent-skills.py` — generic, uses `plugin:skill` format

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: a-share-analysis fully deleted
    Tool: Bash
    Steps:
      1. test -d plugins/vertical-plugins/a-share-analysis && echo "FAIL: still exists" || echo "OK: deleted"
    Expected Result: Directory does not exist
    Evidence: .sisyphus/evidence/task-9-deleted.txt

  Scenario: check.py passes
    Tool: Bash
    Steps:
      1. uv run python scripts/check.py
    Expected Result: Exit code 0, "All checks passed!"
    Failure Indicators: Exit code 1, "Found N issue(s)"
    Evidence: .sisyphus/evidence/task-9-check-py.txt

  Scenario: validate.py passes
    Tool: Bash
    Steps:
      1. uv run python scripts/validate.py
    Expected Result: Exit code 0, "All validations passed!"
    Failure Indicators: Exit code 1
    Evidence: .sisyphus/evidence/task-9-validate-py.txt

  Scenario: No references to a-share-analysis remain
    Tool: Bash
    Steps:
      1. grep -r "a-share-analysis" plugins/ scripts/ --include="*.py" --include="*.json" --include="*.md" -l 2>/dev/null || echo "No references found"
    Expected Result: "No references found"
    Failure Indicators: Any file still references a-share-analysis
    Evidence: .sisyphus/evidence/task-9-no-a-share-analysis-refs.txt
  ```

  **Commit**: YES
  - Message: `chore: remove a-share-analysis, update cookbooks, verify Phase 1`
  - Files: `plugins/vertical-plugins/a-share-analysis/`, `managed-agent-cookbooks/`

- [x] 10. Trading Simulator Core (TDD)

  **What to do**:
  - Create `plugins/vertical-plugins/simulation/skills/trading-simulator/` with:
    - `SKILL.md` — skill definition following contributing/playbooks.md template
    - `scripts/market_rules.py` — A-share market rules (board limits, transaction costs, lot size, ST detection)
    - `scripts/simulator.py` — TradingSimulator class with T+1 settlement, order execution, portfolio tracking
    - `scripts/run_simulation.py` — Full simulation runner (strategy_fn → simulation loop → result)
    - `test_simulator.py` — Co-located tests (TDD: write FIRST, then implement)
  - **TDD workflow**:
    1. Write `test_simulator.py` with failing tests for: T+1 same-day sell rejection, price limit rejection, lot size rounding, transaction cost calculation, cash insufficiency
    2. Write `market_rules.py` to pass rule-related tests
    3. Write `simulator.py` to pass simulator tests
    4. Write `run_simulation.py` with strategy function interface
    5. Run all tests to verify GREEN
  - Key A-share rules to implement:
    - T+1: stocks bought today cannot be sold until tomorrow
    - Board price limits: main ±10%, ChiNext/STAR ±20%, BSE ±30%, ST ±5%
    - Transaction costs: commission 0.025% each side, stamp duty 0.05% sell-only, slippage ~0.05-0.1%
    - Lot size: 100 shares minimum, round down
    - Exclusions: ST/*ST stocks

  **Must NOT do**:
  - Do NOT connect to real market data (simulator uses injected price data)
  - Do NOT add MCP server dependencies (simulator is pure Python)
  - Do NOT import from other plugins or skills (standalone)
  - Do NOT add connection pooling or async (simple synchronous Python)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: Complex domain logic with multiple interrelated A-share rules. Requires careful TDD iteration.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T11, T12, T13)
  - **Blocks**: T14
  - **Blocked By**: T9 (Phase 1 must be complete)

  **References**:
  **Pattern References**:
  - `contributing/playbooks.md:7-87` — "Adding a New Skill" playbook (SKILL.md template, scripts/ structure)
  - `contributing/a-share-rules.md` — A-share market rules reference (T+1, price limits, costs)
  - `contributing/architecture.md:167-200` — Trading Simulator architecture (interface, constraints)

  **API/Type References**:
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:291-566` — roadmap's simulator code (reference implementation, may need improvements)
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:297-333` — test cases to implement

  **External References**:
  - A-share board types: 6xxxxx=main, 3xxxxx=ChiNext, 688xxx=STAR, 8xxxxx/4xxxxx=BSE
  - ST stocks identified by name containing "ST" or "*ST"

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: `test_simulator.py`
  - [ ] `uv run pytest test_simulator.py -v` → ALL PASS

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: T+1 constraint enforced — same-day sell rejected
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py::test_t1_settlement_blocks_same_day_sell -v
    Expected Result: PASS — simulator rejects selling shares bought on same day with "T+1" in reason
    Failure Indicators: Test fails or T+1 not enforced
    Evidence: .sisyphus/evidence/task-10-t1-test.txt

  Scenario: Price limit enforcement — order beyond board limit rejected
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py::test_board_price_limits -v
    Expected Result: PASS — main board ±10%, ChiNext ±20%, ST ±5%
    Evidence: .sisyphus/evidence/task-10-price-limits.txt

  Scenario: Lot size rounding — 150 shares rounds to 100
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py::test_lot_size_rounding -v
    Expected Result: PASS — volume rounds down to nearest 100
    Evidence: .sisyphus/evidence/task-10-lot-size.txt

  Scenario: Transaction costs applied correctly
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -k "cost" -v
    Expected Result: PASS — commission 0.025% + stamp 0.05% sell + slippage
    Evidence: .sisyphus/evidence/task-10-costs.txt

  Scenario: All tests pass
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -v
    Expected Result: All tests pass (0 failures)
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-10-all-tests.txt

  Scenario: SKILL.md follows playbook template
    Tool: Bash
    Steps:
      1. grep -q "## Workflow" plugins/vertical-plugins/simulation/skills/trading-simulator/SKILL.md && echo "OK" || echo "MISSING Workflow"
      2. grep -q "## Guardrails" plugins/vertical-plugins/simulation/skills/trading-simulator/SKILL.md && echo "OK" || echo "MISSING Guardrails"
    Expected Result: SKILL.md has required sections
    Evidence: .sisyphus/evidence/task-10-skill-md.txt
  ```

  **Commit**: YES
  - Message: `feat: add A-share trading simulator with T+1 settlement`
  - Files: `plugins/vertical-plugins/simulation/skills/trading-simulator/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -v`

- [x] 11. Internal-Store Memory Extension (TDD)

  **What to do**:
  - Extend `mcp-servers/internal-store/server.py` with 3 new tables and 4 new MCP tools:
    - **New tables** in `_init_db()` (insert after line 58, before `conn.commit()`):
      - `experiments`: id, name, strategy (JSON), params (JSON), result (JSON), lineage_id, created_at
      - `transitions`: id, experiment_id, state (JSON), strategy (JSON), reward (JSON), next_state (JSON), created_at
      - `episode_summaries`: id, period, initial_capital, final_nav, sharpe, max_drawdown, total_turnover, created_at
    - **New tools** (insert after `get_portfolio` at line 149, before ASGI marker):
      - `record_experiment(name, strategy, params, result)` → `list[dict]`
      - `get_best_strategies(top_k=5)` → `list[dict]` — ordered by result.final_nav DESC
      - `record_transition(experiment_id, state, strategy, reward, next_state)` → `list[dict]`
      - `record_episode_summary(period, initial_capital, final_nav, sharpe, max_drawdown)` → `list[dict]`
  - Update `mcp-servers/internal-store/schema.sql` to match (add same 3 tables)
  - Update `mcp-servers/internal-store/test_server.py` with new test classes
  - Update `mcp-servers/internal-store/README.md` with new tool table entries
  - **TDD workflow**:
    1. Write tests for new tools in `test_server.py`
    2. Add new table schemas to `_init_db()` and test fixture
    3. Implement new tools
    4. Run tests to verify GREEN

  **Must NOT do**:
  - Do NOT modify existing tables (cache_entries, backtest_results, portfolio_state)
  - Do NOT change existing tools (query_cache, list_backtest_results, get_portfolio)
  - Do NOT add connection pooling (keep connect→execute→close pattern)
  - Do NOT add domain/business logic to tools (R6: data access only)
  - Do NOT add dependencies to akshare-server or tushare-server

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: Modifying existing MCP server requires understanding existing patterns, TDD adds complexity.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T10, T12, T13)
  - **Blocks**: T13 (experiment tracker references these tools), T14
  - **Blocked By**: T9 (Phase 1 must be complete)

  **References**:
  **Pattern References**:
  - `mcp-servers/internal-store/server.py:25-62` — `_init_db()` function (insert new tables after line 58)
  - `mcp-servers/internal-store/server.py:68-149` — existing tool pattern (connect→row_factory→execute→close→return)
  - `mcp-servers/internal-store/server.py:152` — ASGI marker (insert new tools before this)
  - `mcp-servers/internal-store/server.py:104-121` — `list_backtest_results` tool as reference pattern
  - `mcp-servers/internal-store/test_server.py:8-48` — `temp_db` fixture (add new tables to fixture)
  - `mcp-servers/internal-store/test_server.py:51-66` — existing test classes as reference

  **API/Type References**:
  - `mcp-servers/internal-store/schema.sql` — add same 3 tables here (keep in sync with _init_db)
  - `contributing/architecture.md:387-397` — Internal Store Schema showing target tables
  - `contributing/mcp-servers.md:27-41` — tool definition pattern to follow

  **WHY**: The executor needs exact line numbers for insertion points and the exact connection/error handling pattern to replicate.

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test cases written for all 4 new tools
  - [ ] `uv run pytest mcp-servers/internal-store/test_server.py -v` → ALL PASS

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: New tables created in database
    Tool: Bash
    Steps:
      1. uv run python -c "import sqlite3, tempfile, os; from pathlib import Path; os.environ['DATA_ROOT']=tempfile.mkdtemp(); from mcp_servers.internal_store.server import _init_db; _init_db(); db=Path(os.environ['DATA_ROOT'])/'cache'/'meta.db'; conn=sqlite3.connect(str(db)); tables=[r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]; assert 'experiments' in tables; assert 'transitions' in tables; assert 'episode_summaries' in tables; print('All 3 new tables created:', tables)"
    Expected Result: "All 3 new tables created" with experiments, transitions, episode_summaries in list
    Evidence: .sisyphus/evidence/task-11-new-tables.txt

  Scenario: record_experiment tool works
    Tool: Bash
    Steps:
      1. uv run pytest mcp-servers/internal-store/test_server.py::TestMemoryStore::test_record_experiment -v
    Expected Result: PASS
    Evidence: .sisyphus/evidence/task-11-record-experiment.txt

  Scenario: get_best_strategies returns ordered results
    Tool: Bash
    Steps:
      1. uv run pytest mcp-servers/internal-store/test_server.py::TestMemoryStore::test_get_best_strategies -v
    Expected Result: PASS — results ordered by final_nav DESC
    Evidence: .sisyphus/evidence/task-11-best-strategies.txt

  Scenario: record_transition tool works
    Tool: Bash
    Steps:
      1. uv run pytest mcp-servers/internal-store/test_server.py::TestMemoryStore::test_record_transition -v
    Expected Result: PASS
    Evidence: .sisyphus/evidence/task-11-record-transition.txt

  Scenario: All internal-store tests pass (including existing)
    Tool: Bash
    Steps:
      1. uv run pytest mcp-servers/internal-store/test_server.py -v
    Expected Result: All tests pass (0 failures) — both old and new
    Failure Indicators: Any regression in existing tests
    Evidence: .sisyphus/evidence/task-11-all-tests.txt

  Scenario: schema.sql in sync with _init_db
    Tool: Bash
    Steps:
      1. grep -c "experiments" mcp-servers/internal-store/schema.sql && echo "experiments in schema.sql"
      2. grep -c "transitions" mcp-servers/internal-store/schema.sql && echo "transitions in schema.sql"
      3. grep -c "episode_summaries" mcp-servers/internal-store/schema.sql && echo "episode_summaries in schema.sql"
    Expected Result: All 3 tables present in schema.sql
    Evidence: .sisyphus/evidence/task-11-schema-sql.txt
  ```

  **Commit**: YES
  - Message: `feat: extend internal-store with memory schema and tools`
  - Files: `mcp-servers/internal-store/server.py`, `mcp-servers/internal-store/schema.sql`, `mcp-servers/internal-store/test_server.py`, `mcp-servers/internal-store/README.md`
  - Pre-commit: `uv run pytest mcp-servers/internal-store/test_server.py -v`

- [x] 12. Evolution Loop Skill

  **What to do**:
  - Create `plugins/vertical-plugins/simulation/skills/evolution-loop/` with:
    - `SKILL.md` — skill definition following playbook template
    - `scripts/evolution.py` — EvolutionState dataclass + should_continue() + generate_correction()
    - `test_evolution.py` — Co-located tests
  - Core logic:
    - `should_continue(state, target_return)` → `(bool, str|None)` — checks target reached, max iterations, doom loop
    - `generate_correction(failure_signature)` → `str` — suggests corrective actions for repeated failures
    - Doom loop detection: track failure signatures, if same signature >3 times → inject correction
    - Constants: MAX_ITERATIONS=50, DOOM_THRESHOLD=3, CORRECTION_COUNT_LIMIT=5

  **Must NOT do**:
  - Do NOT connect to MCP servers (pure logic module)
  - Do NOT import from other skills or plugins
  - Do NOT add async patterns (synchronous Python)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: New skill with Python logic, requires understanding of Meta-Agent evolution concept.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T10, T11, T13)
  - **Blocks**: T14
  - **Blocked By**: T9

  **References**:
  **Pattern References**:
  - `contributing/playbooks.md:7-87` — "Adding a New Skill" playbook
  - `contributing/architecture.md:111-153` — Evolution Loop architecture

  **API/Type References**:
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:792-888` — roadmap's evolution.py code

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: should_continue returns False when target reached
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py -k "target" -v
    Expected Result: PASS — should_continue returns (False, "target_return reached")
    Evidence: .sisyphus/evidence/task-12-target-reached.txt

  Scenario: Doom loop detection triggers
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py -k "doom" -v
    Expected Result: PASS — should_continue returns (False, "doom_loop_detected")
    Evidence: .sisyphus/evidence/task-12-doom-loop.txt

  Scenario: generate_correction returns actionable advice
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py -k "correction" -v
    Expected Result: PASS — returns specific correction string for known failure signatures
    Evidence: .sisyphus/evidence/task-12-correction.txt

  Scenario: All tests pass
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/ -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-12-all-tests.txt
  ```

  **Commit**: YES
  - Message: `feat: add evolution-loop skill with doom loop detection`
  - Files: `plugins/vertical-plugins/simulation/skills/evolution-loop/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/ -v`

- [x] 13. Experiment Tracker Skill

  **What to do**:
  - Create `plugins/vertical-plugins/simulation/skills/experiment-tracker/` with:
    - `SKILL.md` — skill definition (inputs: experiment_name, strategy_config, simulation_result; outputs: experiment_id, lineage)
    - `scripts/track_experiment.py` — wrapper script that serializes strategy config and calls internal-store MCP tool
  - The script is a thin CLI wrapper — actual persistence goes through internal-store MCP tools
  - Track experiment records: name, strategy (JSON), params (JSON), result (JSON)
  - Support querying best strategies via `get_best_strategies()`

  **Must NOT do**:
  - Do NOT implement direct SQLite access (must go through MCP tools)
  - Do NOT add business logic beyond serialization and tool invocation

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with T10, T11, T12)
  - **Blocks**: T14
  - **Blocked By**: T9

  **References**:
  **Pattern References**:
  - `contributing/playbooks.md:7-87` — "Adding a New Skill" playbook

  **API/Type References**:
  - `docs/superpowers/plans/2026-05-17-a-share-agents-implementation-roadmap.md:707-786` — roadmap's experiment tracker
  - Task 11 (this plan) — new internal-store tools the skill will reference

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: SKILL.md follows playbook template
    Tool: Bash
    Steps:
      1. test -f plugins/vertical-plugins/simulation/skills/experiment-tracker/SKILL.md && echo "OK" || echo "MISSING"
      2. grep -q "## Workflow" plugins/vertical-plugins/simulation/skills/experiment-tracker/SKILL.md && echo "Workflow OK" || echo "MISSING"
      3. grep -q "## Guardrails" plugins/vertical-plugins/simulation/skills/experiment-tracker/SKILL.md && echo "Guardrails OK" || echo "MISSING"
    Expected Result: SKILL.md exists with required sections
    Evidence: .sisyphus/evidence/task-13-skill-md.txt

  Scenario: track_experiment.py is importable and runs
    Tool: Bash
    Steps:
      1. uv run python -c "import sys; sys.path.insert(0,'plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts'); from track_experiment import record_experiment; print('import OK')"
    Expected Result: "import OK"
    Evidence: .sisyphus/evidence/task-13-import.txt

  Scenario: CLI interface works (help/usage)
    Tool: Bash
    Steps:
      1. uv run python plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts/track_experiment.py 2>&1 || true
    Expected Result: Shows usage message (exit code 1 with "Usage:" is acceptable)
    Evidence: .sisyphus/evidence/task-13-cli.txt
  ```

  **Commit**: YES
  - Message: `feat: add experiment-tracker skill`
  - Files: `plugins/vertical-plugins/simulation/skills/experiment-tracker/`

- [x] 14. Integration Test — Full Simulation Cycle

  **What to do**:
  - Create `plugins/vertical-plugins/simulation/tests/test_simulation_integration.py`
  - Test the complete cycle: create simulator → submit orders across multiple days → verify T+1 releases → check portfolio state → record experiment to internal-store
  - Use `@pytest.mark.integration` marker
  - Test scenarios:
    - Multi-day trading: buy day 1, hold day 2, sell day 3 (T+1 correctly allows)
    - Portfolio state tracking: verify NAV calculation, position tracking, cash tracking
    - Edge case: attempt to sell before T+1 release (should fail)
    - Edge case: attempt to buy with insufficient cash (should fail)
    - Edge case: volume below 100 shares (should be rejected)
  - This test ties together simulator (T10) + market rules (T10) + internal-store (T11)

  **Must NOT do**:
  - Do NOT require running MCP servers (use direct Python imports)
  - Do NOT use real market data (create mock price data)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: Integration testing requires understanding of multiple components.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after all Wave 4 tasks)
  - **Blocks**: F1-F4
  - **Blocked By**: T10, T11, T12, T13

  **References**:
  **Pattern References**:
  - `contributing/testing.md` — pytest conventions for this project
  - `plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py` — unit tests to build on
  - `mcp-servers/internal-store/test_server.py` — internal-store test patterns

  **API/Type References**:
  - Task 10 (this plan) — TradingSimulator, Order, Execution, PortfolioState classes
  - Task 11 (this plan) — record_experiment, get_best_strategies tools

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Full multi-day trading cycle works
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/tests/test_simulation_integration.py -v -k "multi_day"
    Expected Result: PASS — buy day 1, T+1 blocks same-day sell, sell day 2 succeeds
    Evidence: .sisyphus/evidence/task-14-multi-day.txt

  Scenario: All integration tests pass
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/tests/test_simulation_integration.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-14-all-integration.txt

  Scenario: Full simulation test suite passes
    Tool: Bash
    Steps:
      1. uv run pytest plugins/vertical-plugins/simulation/ -v
    Expected Result: All tests pass (unit + integration)
    Failure Indicators: Any test failure
    Evidence: .sisyphus/evidence/task-14-full-suite.txt
  ```

  **Commit**: YES
  - Message: `test: add simulation integration tests`
  - Files: `plugins/vertical-plugins/simulation/tests/`
  - Pre-commit: `uv run pytest plugins/vertical-plugins/simulation/ -v`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. Plan Compliance Audit — oracle: APPROVE (Must Have 6/6, Must NOT Have 8/8, Tasks 14/14)
- [x] F2. Code Quality Review — unspecified-high: APPROVE (Lint PASS, Tests 61 pass, Files clean)
- [x] F3. Real Manual QA — unspecified-high: APPROVE (Scenarios 42/42, Integration PASS, Edge Cases 7/7)
- [x] F4. Scope Fidelity Check — deep: APPROVE (Tasks 14/14 compliant, Unaccounted 5 files are internal state/evidence)

---

## Commit Strategy

- **T1**: `feat: create 5 vertical plugin directories with configs` — plugins/vertical-plugins/*/
- **T2**: `feat: add strategy-analyst agent plugin` — plugins/agent-plugins/strategy-analyst/
- **T3**: `feat: add meta-strategist agent plugin` — plugins/agent-plugins/meta-strategist/
- **T4**: `refactor: update check.py and validate.py for 5-vertical structure` — scripts/
- **T5**: `feat: migrate skills from a-share-analysis to 5 verticals` — plugins/vertical-plugins/
- **T6**: `feat: migrate commands to respective vertical plugins` — plugins/vertical-plugins/
- **T7**: `chore: remove deprecated agent plugins and cookbooks` — plugins/agent-plugins/, managed-agent-cookbooks/
- **T8**: `docs: update contributing docs for 5-vertical structure` — contributing/
- **T9**: `chore: remove a-share-analysis, update cookbooks, verify Phase 1` — plugins/, managed-agent-cookbooks/
- **T10**: `feat: add A-share trading simulator with T+1 settlement` — plugins/vertical-plugins/simulation/
- **T11**: `feat: extend internal-store with memory schema and tools` — mcp-servers/internal-store/
- **T12**: `feat: add evolution-loop skill with doom loop detection` — plugins/vertical-plugins/simulation/
- **T13**: `feat: add experiment-tracker skill` — plugins/vertical-plugins/simulation/
- **T14**: `test: add simulation integration tests` — plugins/vertical-plugins/simulation/

---

## Success Criteria

### Verification Commands
```bash
uv run python scripts/check.py                    # Expected: exit 0
uv run python scripts/validate.py                 # Expected: exit 0
uv run python scripts/sync-agent-skills.py --check # Expected: no errors
uv run pytest plugins/vertical-plugins/simulation/ -v   # Expected: all pass
uv run pytest mcp-servers/internal-store/test_server.py -v  # Expected: all pass
uv run ruff check .                               # Expected: no errors
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] No references to `a-share-analysis` in plugins/ or scripts/
- [ ] No references to deleted agents (except market-monitor which is kept)
- [ ] 5 vertical plugin dirs exist with skills/ and commands/
- [ ] Trading simulator rejects T+1 violations, price limit violations
