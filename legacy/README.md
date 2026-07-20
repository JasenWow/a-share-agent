# legacy/

Items parked here have been **moved out of the active code paths** during the monorepo restructure. Each has a documented fate. This directory should shrink over time — nothing should live here indefinitely.

## Status by item

| Path | Origin | Fate |
|---|---|---|
| `scripts/validate_factor_mining.py` | root `scripts/` | **Deprecated.** E2E driver that reached into `plugins/vertical-plugins/market-data/skills/` via sys.path hacks. The Phase 3 migration broke those couplings. Replacement: an orchestrator-driven E2E test (TBD via agent-orchestration spec). Do not run as-is. |
| `scripts/validate_evolution_loop.py` | root `scripts/` | **Deprecated.** Same story as above; reached into `plugins/vertical-plugins/simulation/skills/`. Replacement: same orchestrator-driven test. |
| `managed-agent-cookbooks/` | root | **Reference only.** Deployment cookbooks (`agent.yaml`) for managed-agent deployments of equity-researcher / market-monitor / portfolio-manager. Still useful as documentation; will be either revived under `docs/` or moved into each agent's plugin folder in a follow-up. |
| `openspec-content/` | root `openspec/` | **Historical.** Two archived openspec changes (factor-mining-mvp, signal-eval-redesign) from 2026-05. Workflow superseded by `docs/superpowers/specs/`. Kept for provenance; safe to delete after 2026-Q4. |
| `openspec-package.json` | root `package.json` | **Historical.** npm config that existed only to install `@fission-ai/openspec`. Deleted from active tree. |
| `openspec-package-lock.json` | root `package-lock.json` | **Historical.** Same as above. |
| `skills-lock.json` | root | **Stale.** Output of the pre-restructure skill sync. Regenerate via `scripts/sync-agent-skills.py` if the skills workflow is revived. |

## Principle

- Every entry has a documented fate in this README.
- `deprecated` files carry a DEPRECATED banner in their module docstring.
- `legacy/` is **not** a long-term home — Phase 6 is the last phase that adds here. Future work either revives items (and moves them out) or deletes them.
