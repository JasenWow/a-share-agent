---
name: script-generator
description: |
  Generates new Python factor or strategy scripts from natural language descriptions.
  Triggers: "generate factor", "create strategy script", "write new script"
---

# Script Generator

## Overview
Generates executable Python scripts for factors and strategies that the Meta-Agent can then use in simulation.

## Inputs
- script_type: "factor" or "strategy"
- description: natural language description of desired computation

## Outputs
- script_path: path to generated Python file
- validation_result: whether script passes basic checks

## Constraints
- Does NOT call any AI/LLM API — template filling only
- Generated scripts go to `script-generator/generated/` — NOT registered as skills
- Collision detection: raises FileExistsError if file exists