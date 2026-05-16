# Playbooks

> Step-by-step checklists for high-frequency additions. Every step is load-bearing — skipping one typically produces a working build that fails at runtime.
>
> Each playbook ends with a **Verify** section. Don't claim done until those commands pass.

## Adding a New Skill

Scope: creating a new skill under `plugins/vertical-plugins/a-share-analysis/skills/<skill-name>/` and wiring it into the system.

### Steps

1. **Create the skill directory:**
   ```
   plugins/vertical-plugins/a-share-analysis/skills/<skill-name>/
   ```
   Use `kebab-case` for the directory name (e.g., `factor-screen`, `backtest-engine`).

2. **Write `SKILL.md`:**
   - **Trigger conditions**: "Triggers when: ..." and "Skips when: ..."
   - **Inputs**: table of parameters (name, type, required, description)
   - **Outputs**: describe the output format (Markdown table, Excel, report)
   - **Tool dependencies**: list MCP tools the skill uses (e.g., `akshare.stock_zh_a_spot`)
   - **Execution steps**: numbered workflow with clear decision points
   - **Common mistakes**: table of what NOT to do
   - **Quality checklist**: bullet list of pre-output checks

   Reference: `docs/交易系统构建设计/02-技能设计.md` for worked examples.

3. **Write `prompt.md`:**
   - Execution prompt template that Claude will follow when the skill is invoked.
   - Include step-by-step instructions referencing the SKILL.md workflow.
   - Define output format explicitly (column names, table structure, file naming).

4. **Add executable scripts (if the skill has domain logic):**
   ```
   skills/<skill-name>/scripts/
   ├── <script>.py         # Domain logic (factor calc, backtest engine, etc.)
   └── test_<script>.py    # Co-located tests
   ```
   - Scripts are invoked by agents via `uv run python <path>`
   - Scripts may use MCP tools' data (passed as file paths or stdin JSON)
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
   ├── input-example.md    # Sample user input
   └── output-example.md   # Expected output
   ```

7. **Register in vertical plugin:**
   Edit `plugins/vertical-plugins/a-share-analysis/plugin.json`:
   - Add skill name to the `skills` array.
   - If the skill has a slash command, also add to `commands` array.

8. **Add command definition (if applicable):**
   Create `plugins/vertical-plugins/a-share-analysis/commands/<cmd>.json`:
   ```json
   {
     "name": "<cmd>",
     "description": "What this command does",
     "trigger": "/<cmd>",
     "usage": "/<cmd> [args]",
     "examples": ["/<cmd> example usage"],
     "skill": "<skill-name>",
     "agent": "<agent-name>",
     "parameters": [
       {
         "name": "param",
         "type": "string",
         "description": "Parameter description",
         "required": true
       }
     ]
   }
   ```

9. **Sync to agents:**
   ```bash
   python scripts/sync-agent-skills.py
   ```
   This copies skill definitions into agent directories that reference them.

10. **Write tests:**
    - At minimum, validate that SKILL.md has required sections.
    - If the skill includes scripts, write co-located `test_*.py` with fixture data.

11. **Update agent references:**
    If existing agents should use this skill, update their `plugin.json` `skills` array.

### Verify

```bash
python scripts/check.py                            # Structure validation
python scripts/sync-agent-skills.py --check         # Skill references in sync
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
   - **Guardrails**: hard rules that must never be violated (A-share exclusions, citation mandate, etc.).

   Reference: `docs/交易系统构建设计/01-Agent设计.md` for worked examples.

3. **Write `system-prompt.md`:**
   - Full system prompt for Claude, including identity, capabilities, available skills, data access pattern, output guidelines, and constraints.
   - Reference the tools available: `mcp__akshare__*`, `mcp__tushare__*`, etc.

   Reference: `docs/交易系统构建设计/04-目录结构与实现指南.md` section 3.3 for template.

4. **Write `plugin.json`:**
   ```json
   {
     "name": "<agent-name>",
     "display_name": "Display Name",
     "description": "One-line description",
     "version": "0.1.0",
     "type": "agent-plugin",
     "skills": [
       "a-share-analysis:<skill-name>"
     ],
     "commands": ["<cmd>"],
     "mcp_dependencies": ["akshare", "tushare", "internal-store"],
     "system_prompt": "system-prompt.md",
     "manifest": "AGENT.md"
   }
   ```

5. **Register slash commands (if any):**
   - Create command JSON files in `plugins/vertical-plugins/a-share-analysis/commands/`.
   - Set the `"agent"` field to your agent name.

6. **Update vertical plugin:**
   - If adding new commands, update `plugin.json` commands array.

7. **Run checks:**
   ```bash
   python scripts/check.py
   python scripts/sync-agent-skills.py
   ```

8. **Test with sample prompts:**
   - Test the primary use case (e.g., `/screen 沪深300 PE<20 ROE>15`).
   - Test guardrails (e.g., verify ST stocks are excluded).
   - Test error handling (e.g., invalid stock code, data source unavailable).

9. **Verify guardrails hold:**
   - A-share exclusion rules are enforced (see `a-share-rules.md`).
   - Citation mandate: output includes data source and timestamp.
   - No auto-trading language in output.
   - Risk disclaimer present.

### Verify

```bash
python scripts/check.py
python scripts/sync-agent-skills.py --check
# Test agent with 3+ sample prompts covering happy path and guardrails
```

---

## Adding a New MCP Tool

Scope: adding a new `@mcp.tool()` function to an existing MCP server.

### Steps

1. **Define the tool function** in `mcp-servers/<name>/server.py`:
   ```python
   @mcp.tool()
   def new_tool_name(param1: str, param2: str = "default") -> list[dict]:
       """
       Description of what this tool returns.

       Args:
           param1: Required parameter description.
           param2: Optional parameter description.
       """
       try:
           df = data_source.function(param1=param1, param2=param2)
           if df.empty:
               return [{"warning": f"No data for param1={param1}"}]
           return df_to_json(df)
       except Exception as e:
           return [{"error": str(e), "tool": "new_tool_name", "param1": param1}]
   ```

2. **Follow naming conventions:**
   - Tool name matches the upstream API function name (e.g., `stock_zh_a_spot` for `ak.stock_zh_a_spot_em()`).
   - Use `snake_case` for tool names and parameters.

3. **Update server README:**
   Add a row to the tool documentation table:
   | Tool Name | Upstream Function | Description | Key Parameters |

4. **Write tests** in `test_server.py`:
   - Happy path: mock the upstream API, call the tool, assert response shape.
   - Error path: mock a failure, assert error dict is returned.
   - Edge case: mock empty DataFrame, assert warning is returned.

5. **Update agent system prompts** (if agents need the new tool):
   Add the tool to the relevant agent's `system-prompt.md` under available tools.

6. **Update skill files** (if skills reference the new tool):
   Add to the "Tool dependencies" section of relevant SKILL.md files.

### Verify

```bash
# Restart the MCP server
uvicorn mcp-servers/<name>/server:mcp_app --port 800X

# Verify tool is registered
curl http://localhost:800X/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Run tests
pytest mcp-servers/<name>/test_server.py -v
```

---

## Adding a New Slash Command

Scope: creating a new `/command` that triggers a skill and/or agent.

### Steps

1. **Create the command definition:**
   `plugins/vertical-plugins/a-share-analysis/commands/<cmd>.json`
   ```json
   {
     "name": "<cmd>",
     "description": "What this command does",
     "trigger": "/<cmd>",
     "usage": "/<cmd> [args]",
     "examples": [
       "/<cmd> example 1",
       "/<cmd> example 2"
     ],
     "skill": "<skill-name>",
     "agent": "<agent-name>",
     "parameters": [
       {
         "name": "param_name",
         "type": "string",
         "description": "What this parameter controls",
         "default": "default_value"
       }
     ]
   }
   ```

2. **Ensure the linked skill exists:**
   - `"skill"` must match a directory under `skills/`.
   - If the skill doesn't exist yet, follow the "Adding a New Skill" playbook first.

3. **Ensure the linked agent exists:**
   - `"agent"` must match a directory under `agent-plugins/`.
   - The agent's `plugin.json` must include this command in its `commands` array.

4. **Register in vertical plugin:**
   Update `plugins/vertical-plugins/a-share-analysis/plugin.json`:
   - Add command name to the `commands` array.

5. **Update contributing index:**
   Add the command to the slash command table in `contributing/README.md`.

6. **Test invocation:**
   - Type `/<cmd>` with and without arguments.
   - Verify it triggers the correct skill and agent.
   - Verify error handling for invalid arguments.

### Verify

```bash
python scripts/check.py
python scripts/sync-agent-skills.py --check
# Test command invocation manually
```
