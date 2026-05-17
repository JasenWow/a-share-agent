---
name: evolution-loop
description: |
  Evolution loop control for strategy optimization. Manages iteration
  state, detects doom loops, and generates corrective actions.

  Triggers: "/evolution", "evolution loop", "iterative optimization",
  "doom loop detection", "策略迭代"
---

# Evolution Loop Control

## Overview

Controls the evolution loop for iterative strategy optimization. Manages
iteration state, detects doom loops (repeated failures), and generates
corrective actions to guide the optimizer toward better solutions.

**Core Philosophy:** "Detect stagnation, generate corrections, avoid infinite loops."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| iteration | int | Yes | Current iteration number |
| best_return | float | Yes | Best return achieved so far |
| recent_failures | list[str] | Yes | List of recent failure messages |
| failure_signatures | dict[str, int] | Yes | Count of each failure type |
| target_return | float | Yes | Target return to achieve |

---

## Core Functions

### should_continue()

Determines whether evolution should continue.

```python
def should_continue(state: EvolutionState, target_return: float) -> tuple[bool, str|None]:
```

**Returns:** `(should_continue: bool, reason: str|None)`
- `(False, "target_reached")` if `best_return >= target_return`
- `(False, "max_iterations")` if `iteration >= MAX_ITERATIONS`
- `(False, "doom_loop")` if any signature appears >= DOOM_THRESHOLD times
- `(False, "correction_limit")` if total corrections >= CORRECTION_COUNT_LIMIT
- `(True, None)` otherwise

### generate_correction()

Returns a corrective action based on failure pattern.

```python
def generate_correction(failure_signature: str) -> str:
```

**Mappings:**

| Failure Signature | Corrective Action |
|-------------------|-------------------|
| `momentum_concentration` | reduce momentum weight, diversify factors |
| `value_overfit` | increase lookback period, reduce rebalancing frequency |
| `low_sharpe` | add defensive factors (low_vol, quality), reduce position count |
| `high_turnover` | extend holding period, use score threshold for rebalancing |
| (unknown) | review strategy parameters, consider regime change |

---

## Constants

```python
MAX_ITERATIONS = 50
DOOM_THRESHOLD = 3
CORRECTION_COUNT_LIMIT = 5
```

---

## Quality Checklist

- [ ] should_continue returns False when target is reached
- [ ] should_continue returns False at MAX_ITERATIONS
- [ ] should_continue detects doom loops (DOOM_THRESHOLD)
- [ ] should_continue respects CORRECTION_COUNT_LIMIT
- [ ] generate_correction handles all known signatures
- [ ] generate_correction returns fallback for unknown signatures
- [ ] EvolutionState dataclass has all required fields

(End of file - total 72 lines)