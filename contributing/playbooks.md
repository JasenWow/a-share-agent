# Playbooks

> Step-by-step checklists for high-frequency additions. Every step is load-bearing — skipping one typically produces a working build that fails at runtime.
>
> Each playbook ends with a **Verify** section. Don't claim done until those commands pass.

## Adding a New Skill

Scope: creating a new skill under `plugins/vertical-plugins/<vertical>/skills/<skill-name>/` and wiring it into the system.

### Steps

1. **Choose the vertical:**
   Determine which vertical plugin the skill belongs to:

   | Vertical | Skills |
   |----------|--------|
   | `market-data` | Data fetching, factor computation, preprocessing |
   | `equity-research` | Financial analysis, valuation, thesis tracking |
   | `trading-strategy` | Backtest, signals, risk control |
   | `simulation` | Trading simulator, experiment tracking, evolution loop |
   | `market-monitor` | Breadth, northbound, sentiment |

2. **Create the skill directory:**
   ```
   plugins/vertical-plugins/<vertical>/skills/<skill-name>/
   ```
   Use `kebab-case` for the directory name.

3. **Write `SKILL.md`:**
   - **Trigger conditions**: "Triggers when: ..." and "Skips when: ..."
   - **Inputs**: table of parameters (name, type, required, description)
   - **Outputs**: describe the output format
   - **Tool dependencies**: list MCP tools the skill uses
   - **Execution steps**: numbered workflow with clear decision points
   - **Common mistakes**: table of what NOT to do
   - **Quality checklist**: bullet list of pre-output checks

4. **Add executable scripts (if the skill has domain logic):**
   ```
   skills/<skill-name>/scripts/
   ├── <script>.py         # Domain logic
   └── test_<script>.py    # Co-located tests
   ```
   - Scripts are invoked by agents via `uv run python <path>`
   - Scripts must NOT import code from `mcp-servers/`, `plugins/agent-plugins/`, or other skills
   - Scripts follow the same coding standards (ruff, type hints, error handling)

5. **Add references (if the skill has lookup data):**
   ```
   skills/<skill-name>/references/
   └── <topic>.md          # Formulas, thresholds, industry mappings
   ```

6. **Add examples:**
   ```
   skills/<skill-name>/examples/
   ├── input-example.md
   └── output-example.md
   ```

7. **Register in vertical plugin:**
   Edit `plugins/vertical-plugins/<vertical>/.claude-plugin/plugin.json`:
   - Add skill name to the `skills` array.

8. **Add command definition (if applicable):**
   Create `plugins/vertical-plugins/<vertical>/commands/<cmd>.md` with YAML frontmatter.

9. **Sync to agents:**
   ```bash
   uv run python scripts/sync-agent-skills.py
   ```

10. **Write tests:**
    - Validate SKILL.md has required sections.
    - If scripts exist, write co-located `test_*.py` with fixture data.

11. **Update agent references:**
    If existing agents should use this skill, update their `plugin.json` `skills` array.

### Verify

```bash
uv run python scripts/check.py
uv run python scripts/sync-agent-skills.py --check
# Test the skill end-to-end with a sample prompt
```

---

## Adding a New Agent

Scope: creating a new agent plugin under `plugins/agent-plugins/<agent-name>/` with complete wiring.

### Steps

1. **Create the agent directory:**
   ```
   plugins/agent-plugins/<agent-name>/
   ```
   Use `kebab-case` for the directory name.

2. **Write `AGENT.md`** (agent manifest):
   Follow the four-part structure: **Persona → Deliverables → Workflow → Guardrails**.
   - **Persona**: "You are the [Agent Name] — a [role description]."
   - **Deliverables**: numbered list of outputs the agent produces.
   - **Workflow**: numbered execution steps with MCP tool calls.
   - **Guardrails**: hard rules that must never be violated.

3. **Write `system-prompt.md`:**
   - Full system prompt for Claude, including identity, capabilities, available skills, data access pattern, output guidelines, and constraints.
   - Reference the tools available: `mcp__akshare__*`, `mcp__tushare__*`, etc.

4. **Write `plugin.json`:**
   ```json
   {
     "name": "<agent-name>",
     "display_name": "Display Name",
     "description": "One-line description",
     "version": "0.1.0",
     "type": "agent-plugin",
     "skills": [
       "<vertical>:<skill-name>"
     ],
     "commands": ["<cmd>"],
     "mcp_dependencies": ["akshare", "tushare", "internal-store"],
     "system_prompt": "system-prompt.md",
     "manifest": "AGENT.md"
   }
   ```

5. **Register slash commands (if any):**
   Create command definitions in the relevant vertical plugin's `commands/` directory.

6. **Run checks:**
   ```bash
   uv run python scripts/check.py
   uv run python scripts/sync-agent-skills.py
   ```

7. **Test with sample prompts:**
   - Test the primary use case.
   - Test guardrails (A-share exclusion rules, citation mandate).
   - Test error handling.

### Verify

```bash
uv run python scripts/check.py
uv run python scripts/sync-agent-skills.py --check
# Test agent with 3+ sample prompts
```

---

## Adding a New MCP Tool

Scope: adding a new `@mcp.tool()` function to an existing MCP server.

### Steps

1. **Define the tool function** in `mcp-servers/<name>/server.py`:
   ```python
   @mcp.tool()
   def new_tool_name(param1: str, param2: str = "default") -> list[dict]:
       """Description of what this tool returns."""
       try:
           df = data_source.function(param1=param1)
           if df.empty:
               return [{"warning": f"No data for param1={param1}"}]
           return df_to_json(df)
       except Exception as e:
           return [{"error": str(e), "tool": "new_tool_name", "param1": param1}]
   ```

2. **Follow naming conventions:**
   - Tool name matches the upstream API function name.
   - Use `snake_case` for tool names and parameters.

3. **Update server README.**

4. **Write tests** in `test_server.py`:
   - Happy path, error path, edge case.

5. **Update agent system prompts and skill files** if they reference the new tool.

### Verify

```bash
uv run uvicorn mcp-servers/<name>/server:mcp_app --port 800X
curl http://localhost:800X/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
uv run pytest mcp-servers/<name>/test_server.py -v
```

---

## Adding a New Slash Command

Scope: creating a new `/command` that triggers a skill and/or agent.

### Steps

1. **Create the command definition** in the relevant vertical plugin's `commands/` directory.

2. **Ensure the linked skill and agent exist.**

3. **Register in vertical plugin's `plugin.json`.**

4. **Update `contributing/README.md`** slash command table.

5. **Test invocation** with and without arguments.

### Verify

```bash
uv run python scripts/check.py
uv run python scripts/sync-agent-skills.py --check
```

---

## Adding a Simulation Component

Scope: extending the trading simulator or memory store in `plugins/vertical-plugins/simulation/`.

### Steps

1. **Identify the target skill:**

   | Skill | Purpose |
   |-------|---------|
   | `trading-simulator` | Core simulation engine (simulator.py, market_rules.py) |
   | `experiment-tracker` | Experiment recording + lineage (track_experiment.py) |
   | `evolution-loop` | Iteration control + doom loop detection (evolution.py) |

2. **Write or modify scripts:**
   - Scripts in `simulation/skills/<skill>/scripts/` are standalone Python executables.
   - They may read/write to `internal-store` via SQLite directly (not through MCP, for performance).
   - They must NOT import code from other vertical plugins or agent plugins.

3. **Update internal-store schema if needed:**
   - Add new tables to `mcp-servers/internal-store/schema.sql`.
   - Add corresponding MCP tools for querying new data.
   - Update `contributing/AGENTS.md` Internal Store Schema section.

4. **Write tests:**
   - Test with fixture data (simulated market data).
   - Verify A-share rules are enforced (T+1, limits, costs).
   - Verify transitions are recorded correctly.

5. **Update notebooks** if the new data should be visualized.

### Verify

```bash
uv run python scripts/check.py
uv run pytest plugins/vertical-plugins/simulation/ -v
# Run a test simulation end-to-end
uv run python plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/run_simulation.py \
  --capital 1000000 --start 20240101 --end 20250101 --config test_config.json
```

---

## Adding a New Factor

Scope: adding a new alpha factor to `market-data/factor-library/` and its computation logic.

### Steps

1. **Document the factor:**
   Create `market-data/skills/factor-library/references/<factor-name>.md`:
   - Formula (with LaTeX)
   - Input data requirements (which MCP tools)
   - Lookback period
   - Expected range and distribution
   - Known issues (survivorship bias, lookahead bias, etc.)

2. **Add computation logic:**
   Add a function to `market-data/skills/factor-compute/scripts/compute_factors.py`:
   - Input: DataFrame with required columns
   - Output: Series with factor values
   - Apply MAD Winsorization (3σ) and ZScore

3. **Register in factor library:**
   Update `market-data/skills/factor-library/SKILL.md` with the new factor entry.

4. **Write tests:**
   - Test with known input → expected output.
   - Test NaN handling.
   - Test with A-share exclusion rules applied.

5. **Make available to Meta-Agent:**
   The Meta-Agent's strategy space automatically includes new factors once they are in the factor library.

### Verify

```bash
uv run python -c "
from plugins.vertical-plugins.market-data.skills.factor-compute.scripts.compute_factors import compute_<factor>
import pandas as pd
# test with sample data
"
```
