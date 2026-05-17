# Meta-Agent "Make It Work" — Full Fix + Validate

**Date:** 2026-05-17
**Approach:** Bottom-up fix & test (L0 → L1 → L3 validation)
**Scope:** Fix all known gaps, run end-to-end evolution loop with real A-share data

---

## Section 1: L0 — Connector Fixes

### 1a. Remove template artifact in internal-store

`mcp-servers/internal-store/server.py` lines 310-321 contain a broken `list_cache` tool referencing `ak.new_function()` and `df_to_json` — leftover from mcp-tool-adder template. This will fail at runtime.

**Action:** Delete the dead code.

### 1b. Implement missing memory query tools

The architecture doc describes a Memory Query Interface with three tools not yet implemented. All query against existing `experiments` and `transitions` tables — no schema changes needed.

| Tool | Signature | Purpose |
|------|-----------|---------|
| `get_similar_states` | `(state_vector: dict, top_k: int) -> list[dict]` | Find historically similar market states by matching state fields against experiment `params` JSON. Returns top-k ranked by similarity (field overlap count). |
| `get_failures` | `(experiment_id: str \| None, limit: int) -> list[dict]` | Retrieve experiments with negative returns or doom-loop signatures. Optionally filter by parent experiment. |
| `get_transition_matrix` | `(state_vector: dict) -> dict` | Aggregate `transitions` table rows matching similar states. Returns `{strategy_hash: {avg_reward, count}}` for strategy selection. |

**Implementation:** Pure SQL queries in `server.py`. Similarity is field-overlap scoring on JSON fields (no vector DB needed at this scale).

---

## Section 2: L1 — Skill Fixes

### 2a. Dynamic factor registration

**Problem:** `generate_hypothesis.py` has 12 hardcoded factors. Script-generator creates new factor scripts but never registers them.

**Solution:** Create `factor_registry.json` in the simulation vertical. Script-generator appends new entries after validation. `generate_hypothesis.py` loads both hardcoded base factors and registered custom factors.

**Registry entry format:**
```json
{
  "custom_factors": [
    {"name": "momentum_30d", "script": "generated/compute_momentum_30d.py", "registered_at": "2026-05-17"}
  ]
}
```

### 2b. Enrich EvolutionState

**Problem:** Architecture describes a rich state (market_regime, market_breadth, volatility_index, northbound_flow, etc.) but `EvolutionState` only has `iteration`, `best_return`, `recent_failures`, `failure_signatures`.

**Solution:** Add fields as `Optional` with `None` defaults:
- `market_regime: Optional[str]` — bull/bear/range
- `market_breadth: Optional[float]` — advancing/declining ratio
- `volatility_index: Optional[float]` — realized vol proxy
- `cash_ratio: Optional[float]` — portfolio cash / total value
- `position_count: Optional[int]`
- `sector_concentration: Optional[float]` — herfindahl index
- `unrealized_pnl: Optional[float]`

The evolution loop populates what it can from simulation results and internal-store queries. Fields without data sources stay `None`. No blocking on missing data.

### 2c. Update stale AGENTS.md

Simulation vertical's AGENTS.md lists 3 skills but there are now 7. Update to match reality.

### 2d. Pluggable universe system

**Problem:** `generate_hypothesis.py` has 4 hardcoded universe options (all-A, CSI300, CSI500, CSI1000). No way to target specific sectors.

**Solution:** Universe parameter becomes a structured type:

```python
# In generate_hypothesis.py
UNIVERSE_CONFIGS = {
    "all-A":    {"type": "index", "name": "all-A"},
    "CSI300":   {"type": "index", "name": "000300.SH"},
    "CSI500":   {"type": "index", "name": "000905.SH"},
    "CSI1000":  {"type": "index", "name": "000852.SH"},
    "AI-concept": {"type": "concept", "name": "人工智能"},
    "custom":   {"type": "custom", "codes": []},
}
```

New helper `resolve_universe(config)`:
- `"index"` — use existing index constituent fetching
- `"concept"` — call akshare to get concept board constituents (e.g., `ak.stock_board_concept_cons_em(symbol="人工智能")`)
- `"custom"` — use the provided codes list directly

The `run_simulation.py` pipeline calls `resolve_universe()` to get the stock code list before loading signals.

---

## Section 3: L3 — Validation Run

### 3a. End-to-end evolution loop with real A-share data

After all fixes are complete, run a full meta-strategist evolution loop:

| Parameter | Value |
|-----------|-------|
| Universe | AI concept board (dynamic via akshare) + manual fallback list |
| Period | 2025-01-01 to 2025-05-17 |
| Iterations | 10 |
| Data source | akshare (real market data) |

### 3b. Validation criteria

- Loop completes without errors across all 10 iterations
- Experiments recorded correctly in internal-store (`experiments`, `transitions`, `episode_summaries` tables)
- Failure detection fires appropriately (if any strategies fail)
- Doom loop prevention triggers when >=3 same-signature failures occur
- NAV sequence and trades are sensible (no negative prices, T+1 respected, price limits respected)
- Custom universe resolves correctly for AI concept board

### 3c. Deliverables

- Fixed code across all layers (connector, skills, meta-strategist)
- One complete evolution loop output stored in internal-store
- Any bugs discovered during the validation run, fixed
