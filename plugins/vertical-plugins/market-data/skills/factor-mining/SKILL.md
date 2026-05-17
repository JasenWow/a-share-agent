---
name: factor-mining
description: |
  Automatic factor discovery using LLM-directed GP evolution.
  LLM generates directional hypotheses, DEAP evolves factor expressions,
  Qlib evaluates candidates. Validated factors stored in shared factor library.

  Triggers: "挖掘因子", "mine factors", "factor mining", "自动因子发现",
  "discover alpha", "find new factors"
---

# Factor Mining

## Overview

Automatically discovers new factor formulas through genetic programming.
LLM provides directional hypotheses (which operators + data to focus on),
DEAP evolves concrete expressions, Qlib evaluates fitness via IC/ICIR.

**Core Philosophy:** "LLM directs, GP searches, data validates."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| hypothesis | str | Yes | LLM-generated directional hypothesis |
| operators | list[str] | Yes | Operator names to include in GP search space |
| data_fields | list[str] | Yes | Data fields available as GP terminals |
| universe | str | Yes | Stock universe for evaluation |
| period | str | Yes | Evaluation period "YYYY-MM-DD to YYYY-MM-DD" |
| constraints | dict | No | GP parameters: max_depth, population, generations, top_k |

---

## Tool Dependencies

| Tool | Purpose |
|------|---------|
| `mcp__qlib__qlib_eval_expression` | Evaluate candidate factor expressions |
| `mcp__qlib__qlib_list_operators` | List available operators |
| `mcp__qlib__qlib_get_universe` | Get stock universe codes |
| `mcp__internal-store__register_factor` | Register validated factors |
| `mcp__internal-store__list_factors` | Check for duplicate factors |

---

## Workflow

### Step 1: Validate MiningDirection

Check all required fields are present and non-empty.

### Step 2: Run GP Evolution

Execute `mine_factors.py` with the MiningDirection:
- DEAP evolves expression trees using selected operators + data fields
- Fitness = 0.6 * ICIR + 0.2 * mean_IC - 0.2 * turnover
- Returns top-k candidates ranked by fitness

### Step 3: Evaluate Top Candidates

For each candidate expression:
1. Call `qlib_eval_expression` to get factor values
2. Compute Rank IC series against forward returns
3. Calculate IC, ICIR, turnover

### Step 4: Full Validation via factor-research

Send top candidates to `factor-research` skill for:
- Walk-Forward validation
- Factor scorecard (IC > 0.03, ICIR > 0.5, turnover < 50%, etc.)

### Step 5: Register to Factor Library

Call `register_factor` for candidates that pass the scorecard.

---

## Output

```json
{
  "direction": "低波动环境下盈利动量增强",
  "candidates_evaluated": 500,
  "top_candidates": [
    {
      "expression": "Rank(Ts_Mean($close/$earnings, 20) / Ts_Std($close, 60))",
      "ic": 0.042,
      "icir": 0.68,
      "turnover": 0.35,
      "registered": true
    }
  ],
  "registered_count": 3,
  "total_in_library": 15
}
```

---

## Guardrails

1. **Always validate MiningDirection** before running GP
2. **Never register a factor without full validation** (IC/ICIR + Walk-Forward)
3. **Always check for duplicates** before registering
4. **Respect max_depth** -- deeper trees overfit
5. **Use point-in-time data only** -- no look-ahead bias

---

## Quality Checklist

- [ ] MiningDirection has all required fields
- [ ] GP evolution completed within constraints
- [ ] Top candidates have IC > 0.03 and ICIR > 0.5
- [ ] Walk-Forward validation passed
- [ ] No duplicate expressions in factor library
- [ ] Factor registered with full metrics
