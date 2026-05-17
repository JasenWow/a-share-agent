---
name: experiment-tracker
description: |
  Experiment tracking for trading strategy simulations. Records experiment
  configurations, simulation results, and manages experiment lineage.

  Triggers: "/track", "track experiment", "experiment tracker", "实验追踪"
---

# Experiment Tracker

## Overview

Records trading strategy experiments for reproducibility and lineage tracking.
Persists experiment configurations and simulation results via internal-store MCP tools.

**Core Philosophy:** "Every experiment is a data point in the evolution of strategies."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| experiment_name | str | Yes | Human-readable experiment name |
| strategy_config | dict | Yes | Strategy configuration parameters |
| simulation_result | dict | No | Simulation output (metrics, trades, logs) |

---

## Tool Dependencies

| Tool | Purpose |
|------|---------|
| `mcp__internal-store__store_experiment` | Persist experiment to internal store |
| `mcp__internal-store__list_experiments` | Query experiment history |
| `mcp__internal-store__get_experiment` | Retrieve single experiment by ID |

---

## Workflow

### Step 1: Validate Inputs

Check required fields:
- `experiment_name` is non-empty string
- `strategy_config` is a dict with at least one key

### Step 2: Serialize Configuration

Convert `strategy_config` dict to JSON string for storage.

### Step 3: Call MCP Tool

Invoke `mcp__internal-store__store_experiment`:
- `experiment_name`: string
- `strategy_config`: JSON string
- `simulation_result`: JSON string (optional)

### Step 4: Return Experiment ID

Return the generated `experiment_id` and `lineage` information.

---

## Output

| Field | Type | Description |
|-------|------|-------------|
| experiment_id | str | Unique experiment identifier (UUID) |
| lineage | dict | Parent experiment IDs for lineage tracking |

---

## Guardrails

1. **Never skip experiment_name validation** — empty names cause orphaned records
2. **Never bypass MCP tools** — all persistence must go through internal-store
3. **Serialize to JSON** — strategy_config must be JSON-serializable

---

## Common Mistakes

| Mistake | Why It's Wrong | Correct Approach |
|---------|---------------|-------------------|
| Direct SQLite access | Breaks MCP architecture | Use internal-store MCP tools |
| Missing experiment_name | Creates untrackable experiments | Validate before storing |
| Non-JSON-serializable config | Causes serialization errors | Ensure strategy_config is JSON-compatible |

---

## Quality Checklist

- [ ] experiment_name is non-empty string
- [ ] strategy_config is dict with at least one key
- [ ] All persistence goes through MCP tools
- [ ] experiment_id is returned to caller
- [ ] JSON serialization is validated

(End of file - total 82 lines)