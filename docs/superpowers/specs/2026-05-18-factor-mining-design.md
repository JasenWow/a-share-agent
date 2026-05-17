# Factor Mining with Qlib + DEAP

**Date:** 2026-05-18
**Scope:** L0 qlib-server (new MCP) + L1 factor-mining skill + factor library in internal-store

---

## Overview

Automatic factor discovery pipeline: LLM generates directional hypotheses, DEAP genetic programming searches concrete factor formulas within that direction, Qlib provides data and expression evaluation. Validated factors are stored in a shared factor library for all agents to use.

## Architecture

```
L3  meta-strategist
    | reads factor library for strategy building
    v
L1  factor-mining (new skill, under market-data vertical)
    | LLM direction -> DEAP GP search -> candidate factors
    |
    +-> qlib-server (new L0, port 8003)       data + expression evaluation
    +-> internal-store (existing L0)           factor library + experiment records
    +-> factor-research (existing L1 skill)    IC/ICIR validation of candidates
```

**Data flow:**

```
LLM generates MiningDirection (hypothesis + operator subset + data fields)
  -> DEAP GP evolves expression trees within that direction
    -> Candidate expressions sent to qlib-server for evaluation
      -> IC/ICIR as fitness function
        -> Top-N candidates sent to factor-research for full validation
          -> Validated factors written to factor library
            -> meta-strategist composes strategies from factor library
```

---

## Section 1: qlib-server (L0 MCP Server)

**Port:** 8003
**Dependency:** `qlib` Python package

### MCP Tools

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `qlib_get_data` | `codes[], fields[], start_date, end_date` | DataFrame records | Fetch raw market/financial data |
| `qlib_eval_expression` | `expression, universe, start_date, end_date` | DataFrame records | Evaluate a Qlib expression factor |
| `qlib_list_operators` | (none) | operator list | List available operators with signatures |
| `qlib_get_universe` | `name` | code list | Get stock universe (CSI300, CSI500, etc.) |
| `qlib_init_data` | (none) | status | Initialize/update Qlib local data dump |

### Data Initialization

- Qlib requires a local data dump (`qlib.dump_bin`) before use
- `qlib_init_data` wraps this process, pulling data from akshare/tushare and converting
- First run is slow (full dump), subsequent runs are incremental
- Data stored under `data/qlib/` directory

### Boundary Compliance

- R1: No imports from plugins/
- R4: No cross-server imports
- R6: Data access only, no domain/business logic

---

## Section 2: factor-mining Skill (L1)

**Location:** `plugins/vertical-plugins/market-data/skills/factor-mining/`

### File Structure

```
factor-mining/
  SKILL.md              # Triggers, inputs, outputs, workflow
  prompt.md             # Execution prompt template
  scripts/
    mine_factors.py     # Main mining loop
    gp_engine.py        # DEAP GP engine (population, evolution, selection)
    operators.py        # Qlib operators -> DEAP primitive mapping
    fitness.py          # Fitness function (calls qlib_eval_expression for IC/ICIR)
    factor_library.py   # Factor library CRUD (register, query, dedup)
  references/
    operators.md        # Operator documentation (categories, signatures, examples)
  examples/
    input-example.md
    output-example.md
```

### MiningDirection Input (from LLM)

```json
{
  "hypothesis": "低波动环境下，盈利动量增强",
  "operators": ["Rank", "Ts_Mean", "Ts_Std", "Corr", "/"],
  "data_fields": ["$close", "$volume", "$earnings"],
  "universe": "CSI300",
  "period": "2020-01-01 to 2025-01-01",
  "constraints": {"max_depth": 6, "population": 500, "generations": 50}
}
```

### GP Engine (gp_engine.py)

- Uses DEAP for evolutionary computation
- Each individual = an expression tree (DEAP PrimitiveTree)
- Primitives = Qlib operators mapped from operators.py
- Terminals = data fields ($close, $volume, etc.) + constants
- Evolution operators:
  - Selection: double tournament (by fitness and tree size)
  - Crossover: one-point subtree crossover
  - Mutation: subtree mutation, point mutation, ephemeral constant replacement
- Bloat control: parsimony pressure (penalize large trees), max depth limit

### Operator Set (operators.py)

**Time-series operators:** Ts_Mean, Ts_Std, Ts_Max, Ts_Min, Ts_Rank, Ts_Sum, Ts_Prod, Ts_Corr, Ts_Covariance, Ts_Reg_Residual, Delta, Pct_Change

**Cross-section operators:** Rank, ZScore, Demean, Scale, Power, Sign

**Arithmetic operators:** Add, Sub, Mul, Div, Abs, Log, Exp, Max, Min, Sqrt

**Conditional operators:** If_Else, Clamp

**Data fields:** $open, $high, $low, $close, $volume, $amount, $turnover, $vwap, $earnings, $book_value, $cash_flow, $revenue, $debt

### Fitness Function (fitness.py)

```
fitness = 0.6 * ICIR + 0.2 * mean_IC - 0.2 * turnover
```

- ICIR has highest weight (stability matters more than single high IC)
- Turnover as penalty (high turnover factors cannot survive transaction costs)
- Each individual evaluated by:
  1. Convert expression tree to Qlib expression string
  2. Call `qlib_eval_expression` via MCP
  3. Compute Rank IC series against forward returns
  4. Return fitness score

### Mining Loop (mine_factors.py)

```
for each MiningDirection:
  1. Map operators + data_fields to DEAP primitives/terminals
  2. Initialize population (random trees)
  3. For each generation:
     a. Evaluate fitness for all individuals
     b. Select parents (tournament)
     c. Apply crossover + mutation
     d. Replace population
     e. Track best individual
  4. Output Top-N candidates ranked by fitness
  5. Send candidates to factor-research for full validation
  6. Register validated factors to factor library
```

---

## Section 3: Factor Library (internal-store)

### Schema

```sql
CREATE TABLE factor_library (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    expression    TEXT NOT NULL,
    hypothesis    TEXT,
    operators     TEXT NOT NULL,
    data_fields   TEXT NOT NULL,
    ic            REAL,
    icir          REAL,
    turnover      REAL,
    sharpe        REAL,
    max_drawdown  REAL,
    universe      TEXT,
    period        TEXT,
    walk_forward  TEXT,
    status        TEXT DEFAULT 'active',
    source_experiment_id INTEGER,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

### New MCP Tools (internal-store)

| Tool | Purpose |
|------|---------|
| `register_factor(expression, metrics, ...)` | Register validated factor, auto-dedup by expression hash |
| `list_factors(status, universe)` | Query factor library with filters |
| `deprecate_factor(factor_id, reason)` | Mark factor as deprecated |

---

## Section 4: Integration with Existing Skills

### factor-research (existing)
- Can query factor_library to check if a factor has already been mined (avoid duplicate work)
- Receives candidate factors from factor-mining for full Walk-Forward validation

### factor-screen (existing)
- Loads factors from factor_library for stock screening
- Can use both mined factors and manually defined factors

### meta-strategist (L3, modification)
- Replace 12 hardcoded factors with dynamic read from `list_factors(status='active')`
- Step 2 (Generate Hypothesis) factor library no longer a fixed list
- New trigger: if factor library has too few factors, invoke factor-mining first

---

## Dependencies to Add

```
# pyproject.toml
dependencies = [
    ...,
    "qlib>=0.9",
    "deap>=1.4",
]
```
