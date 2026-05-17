# Learnings - Phase 3+4 Meta-Agent + Notebooks

## Session Summary
Phase 3 (Meta-Agent Phase 1) + Phase 4 (Jupyter Notebooks) + R6 fix completed.
9 implementation tasks + 4 final verification tasks.

## Key Decisions
- R6 false positive: SQL schema strings (CREATE TABLE "backtest_results") inside triple-quoted strings — not actual domain logic
- T3/T5 agent runs: background mode caused silent failures — resolved by re-running with session_id in foreground
- plotly count check: F3 agent's grep methodology was wrong — manual verification showed all 4 notebooks have 5+ plotly references
- check.py exit code 1: TUSHARE_TOKEN warning causes non-zero exit — pre-existing issue, not Phase 3+4 related

## Conventions Established
- Notebooks: 4+ cells, import helpers from same dir, empty data handling with try/except
- generate_hypothesis.py: pure random + heuristic (no ML/LLM)
- Meta-strategist: skills array in plugin.json references simulation skills
- MCP data access: HTTP POST to localhost:8002/mcp

## Files Created/Modified
- scripts/check.py (R6 fix)
- pyproject.toml (jupyterlab, nbconvert)
- contributing/notebooks.md (323 lines)
- notebooks/helpers.py (98 lines, 6 functions)
- notebooks/test_helpers.py (39 lines, 3 tests)
- 4 notebooks: simulation.ipynb, factors.ipynb, backtest.ipynb, portfolio.ipynb
- generate_hypothesis.py + test_generate_hypothesis.py
- meta-strategist: plugin.json, system-prompt.md, meta-strategist.md