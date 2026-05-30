---
name: comet-open
description: "Comet Phase 1: Open. Invoke with /comet-open. Explore ideas through OpenSpec, create change structure (proposal + design + tasks)."
---

# Comet Phase 1: Open

## Prerequisites

- No active change, or user wants to create a new change

## Steps

### 1. Explore Ideas

**Immediately execute:** Use the Skill tool to load the `openspec-explore` skill. Skipping this step is prohibited.

After the skill loads, freely explore the problem space following its guidance.

### 2. Create Change Structure + Initialize State

**Immediately execute:** Use the Skill tool to load the `openspec-new-change` skill. If the user's intent is unclear and needs proposal formation first, load `openspec-propose` instead. Skipping this step is prohibited.

Confirm the following artifacts have been created:

```
openspec/changes/<name>/
├── .openspec.yaml
├── .comet.yaml
├── proposal.md       # Why + What: problem, goals, scope
├── design.md         # How (high-level): architecture decisions, approach selection
└── tasks.md          # Task checklist (checkboxes)
```

Create `.comet.yaml` state file:

```bash
COMET_SEARCH_ROOTS=("." "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.cursor/skills")
COMET_STATE="${COMET_STATE:-$(find "${COMET_SEARCH_ROOTS[@]}" -path '*/comet/scripts/comet-state.sh' -type f -print -quit 2>/dev/null)}"
COMET_GUARD="${COMET_GUARD:-$(find "${COMET_SEARCH_ROOTS[@]}" -path '*/comet/scripts/comet-guard.sh' -type f -print -quit 2>/dev/null)}"

if [ -z "$COMET_STATE" ] || [ -z "$COMET_GUARD" ]; then
  echo "ERROR: Comet scripts not found. Ensure the comet skill is installed." >&2
  return 1
fi

bash "$COMET_STATE" init <name> full
```

### 3. Entry State Verification

Verify state machine has been correctly initialized:

```bash
bash "$COMET_STATE" check <name> open
```

Proceed to Step 4 after verification passes. The script outputs specific failure reasons when verification fails.

### 4. Content Completeness Check

Confirm the three documents have complete content:
- **proposal.md**: problem background, goals, scope, non-goals
- **design.md**: high-level architecture decisions, approach selection, data flow
- **tasks.md**: task list, each task has a clear description

## Exit Conditions

- proposal.md, design.md, tasks.md all created with complete content
- **Phase guard**: Run `bash "$COMET_GUARD" <change-name> open --apply`; after all PASS, auto-transitions to next phase

Must use `--apply` before exit, otherwise `.comet.yaml` remains at `phase: open` and the next phase entry check will fail.

```bash
bash "$COMET_GUARD" <change-name> open --apply
```

Full workflow auto-transitions to `phase: design`; hotfix/tweak presets auto-transition to `phase: build`.

## Automatic Transition

After exit conditions are met, **proceed immediately to the next phase without waiting for user input**:

> **REQUIRED NEXT SKILL (full workflow):** Invoke `comet-design` skill to enter the deep design phase.
>
> Hotfix/tweak presets are controlled by their corresponding preset skill for subsequent transitions (phase goes directly to build), and do not go through this section.
