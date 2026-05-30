---
description: "Factor mining, research, and portfolio evaluation — industry-driven factor discovery, stock ranking, and holding diagnostics"
argument-hint: "[mine <direction> | evaluate <codes> | research <factor>]"
---

# Factor Command

## Subcommands

### `/factor mine <direction>`
Run factor mining on a stock pool.

1. If no stock pool is loaded, ask user to specify an industry theme (triggers stock-pool skill first)
2. Choose mining direction:
   - **低波动** — Low volatility premium
   - **动量趋势** — Momentum and trend following
   - **量价关系** — Volume-price dynamics
   - **均值回归** — Mean reversion
   - **综合探索** — Full search (slower)
3. Run mining pipeline → rank stocks → output report

### `/factor evaluate <stock codes>`
Evaluate a portfolio/holdings list.

Input: space-separated stock codes (e.g., `/factor evaluate 300124.SZ 002472.SZ`)
Output: per-stock scoring + portfolio diagnostics report

### `/factor research <factor>`
(Existing) Load the `factor-research` skill and perform comprehensive factor validation.

If no subcommand specified, default to `mine` and ask user for direction.
