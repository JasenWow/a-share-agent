---
name: agent-modifier
description: |
  Modifies agent definitions (.md files) and plugin.json based on strategy discoveries.
  Triggers: "modify agent", "update agent behavior", "add skill to agent"
---

# Agent Modifier

## Overview
Enables Meta-Agent Phase 3 to update agent definitions when a strategy discovery suggests better workflows.

## Constraints
- Cannot modify meta-strategist itself (self-modification blocked)
- Cannot change agent persona ("What you produce" section)
- All changes must pass `scripts/check.py` validation
- Changes must include rollback on failure

## Self-Modification Prevention
meta-strategist cannot modify its own plugin.json or manifest files. This is enforced by BLOCKED_AGENTS list.