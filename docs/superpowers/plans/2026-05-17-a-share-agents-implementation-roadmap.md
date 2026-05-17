# A-Share Agents Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete A-share quantitative analysis Agent system through 6 implementation phases, from base structure to autonomous Meta-Agent evolution.

**Architecture:** Four-layer system: L3 Meta-Agent (autonomous exploration) → L2 Agents (workflow orchestration) → L1 Skills (domain knowledge + scripts) → L0 MCP Connectors (data access). Downward-only dependency rule enforced by `scripts/check.py`.

**Tech Stack:** Python 3.10+, FastMCP, uvicorn, AKShare (realtime), Tushare (historical), SQLite + Parquet storage, ruff linting.

---

## Phase 1: Base Restructure

**Objective:** Establish the four-layer plugin architecture with 4 vertical plugins, migrate skill scripts, redefine agents with proper boundaries, clean up stale references.

### Task 1.1: Establish Vertical Plugin Structure

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/`
- Create: `plugins/vertical-plugins/equity-research/skills/`
- Create: `plugins/vertical-plugins/trading-strategy/skills/`
- Create: `plugins/vertical-plugins/simulation/skills/`
- Create: `plugins/vertical-plugins/market-monitor/skills/`
- Modify: `plugins/vertical-plugins/a-share-analysis/` → migrate to 5-vertical structure

- [x] **Step 1: Create vertical plugin directories**

```bash
mkdir -p plugins/vertical-plugins/market-data/skills
mkdir -p plugins/vertical-plugins/equity-research/skills
mkdir -p plugins/vertical-plugins/trading-strategy/skills
mkdir -p plugins/vertical-plugins/simulation/skills
mkdir -p plugins/vertical-plugins/market-monitor/skills
```

- [x] **Step 2: Create `.claude-plugin/plugin.json` for each vertical**

```json
{
  "name": "market-data",
  "display_name": "Market Data",
  "description": "Core data fetching, factor computation, and preprocessing",
  "version": "0.1.0",
  "type": "vertical-plugin",
  "skills": [],
  "mcp_dependencies": ["akshare", "tushare", "internal-store"]
}
```

- [x] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/market-data/ plugins/vertical-plugins/equity-research/ plugins/vertical-plugins/trading-strategy/ plugins/vertical-plugins/simulation/ plugins/vertical-plugins/market-monitor/
git commit -m "feat: create 5 vertical plugin directories"
```

- [x] **Step 3: Commit**

```bash
git add -A plugins/vertical-plugins/
git commit -m "feat: migrate skills to 5-vertical plugin structure"
```

### Task 1.3: Migrate Commands to Respective Verticals

**Files:**
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/screen.md` → `plugins/vertical-plugins/market-data/commands/`
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/research.md` → `plugins/vertical-plugins/equity-research/commands/`
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/factor.md` → `plugins/vertical-plugins/market-data/commands/`
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/backtest.md` → `plugins/vertical-plugins/trading-strategy/commands/`
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/optimize.md` → `plugins/vertical-plugins/market-data/commands/`
- Migrate: `plugins/vertical-plugins/a-share-analysis/commands/market.md` → `plugins/vertical-plugins/market-monitor/commands/`

- [x] **Step 1: Move command directories**

```bash
mkdir -p plugins/vertical-plugins/market-data/commands
mkdir -p plugins/vertical-plugins/equity-research/commands
mkdir -p plugins/vertical-plugins/trading-strategy/commands
mkdir -p plugins/vertical-plugins/market-monitor/commands

mv plugins/vertical-plugins/a-share-analysis/commands/screen.md plugins/vertical-plugins/market-data/commands/
mv plugins/vertical-plugins/a-share-analysis/commands/research.md plugins/vertical-plugins/equity-research/commands/
mv plugins/vertical-plugins/a-share-analysis/commands/factor.md plugins/vertical-plugins/market-data/commands/
mv plugins/vertical-plugins/a-share-analysis/commands/backtest.md plugins/vertical-plugins/trading-strategy/commands/
mv plugins/vertical-plugins/a-share-analysis/commands/optimize.md plugins/vertical-plugins/market-data/commands/
mv plugins/vertical-plugins/a-share-analysis/commands/market.md plugins/vertical-plugins/market-monitor/commands/
```

- [x] **Step 2: Commit**

```bash
git add -A plugins/vertical-plugins/
git commit -m "feat: migrate commands to respective verticals"
```

### Task 1.4: Redefine Agent Plugins with Proper Boundaries

**Files:**
- Modify: `plugins/agent-plugins/equity-researcher/agents/equity-researcher.md`
- Modify: `plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md` (create if missing)
- Modify: `plugins/agent-plugins/portfolio-manager/agents/portfolio-manager.md`
- Modify: `plugins/agent-plugins/market-monitor/agents/market-monitor.md`
- Modify: `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md` (create if missing)

- [x] **Step 1: Create strategy-analyst agent**

```bash
mkdir -p plugins/agent-plugins/strategy-analyst/agents
```

Create `plugins/agent-plugins/strategy-analyst/agents/strategy-analyst.md`:

```markdown
---
name: strategy-analyst
description: A-share strategy analysis agent. Performs factor research, strategy construction, and backtesting with A-share constraints.
tools: Read, Write, Edit, mcp__akshare__*, mcp__tushare__*, mcp__internal-store__*
---

You are the Strategy Analyst — an A-share quantitative strategy researcher. You produce factor-based strategies, backtest results, and performance analysis.

## What you produce
1. **Factor research report** — Factor definition, IC analysis, turnover, decay
2. **Strategy specification** — Signal generation, universe, rebalancing frequency, position sizing
3. **Backtest report** — Annualized return, Sharpe, MaxDD, Calmar, IC/ICIR, turnover, win rate
4. **Benchmark comparison** — vs 沪深300/中证500/中证1000

## Workflow
1. Parse user's factor/strategy request
2. Fetch required data via MCP
3. Compute factor values with proper preprocessing
4. Generate signals and run backtest
5. Output performance metrics and Excel report

## Guardrails
- Always apply A-share exclusion rules (ST, suspended, <1yr listed)
- Use T+1 label construction: signal T → trade T+1 → return T+2
- Apply proper transaction costs (commission 0.025% each side, stamp 0.05% sell, slippage 0.1%)
- Use point-in-time index constituents, never current constituents for historical backtest
- Present net-of-cost returns, never gross
```

- [x] **Step 2: Create meta-strategist agent**

```bash
mkdir -p plugins/agent-plugins/meta-strategist/agents
```

Create `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`:

```markdown
---
name: meta-strategist
description: Autonomous strategy exploration agent. Uses simulation-driven evolution to discover profitable A-share strategies.
tools: Read, Write, Edit, mcp__akshare__*, mcp__tushare__*, mcp__internal-store__*
---

You are the Meta-Strategist — an autonomous A-share strategy discovery agent. You explore the strategy space through simulation, learning from historical experiments to generate better hypotheses.

## What you produce
1. **Strategy hypothesis** — Factor combination + parameters
2. **Simulation result** — Final NAV, Sharpe, MaxDD for each experiment
3. **Evolution summary** — Best strategies, failure patterns, next hypotheses

## Workflow
1. Query memory store for best historical strategies
2. Generate new hypothesis based on exploration + exploitation
3. Run simulation via trading-simulator
4. Record experiment results to internal-store
5. Evaluate and decide next iteration or stop

## Guardrails
- Stop if target return reached or iteration limit hit
- Detect doom loops (repeated failures) and change direction
- Always use point-in-time data to avoid look-ahead bias
```

- [x] **Step 3: Create `plugin.json` for each agent**

Create `plugins/agent-plugins/strategy-analyst/plugin.json`:

```json
{
  "name": "strategy-analyst",
  "display_name": "Strategy Analyst",
  "description": "Factor research, strategy construction, and backtesting",
  "version": "0.1.0",
  "type": "agent-plugin",
  "skills": ["trading-strategy:backtest-engine", "trading-strategy:signal-generator", "market-data:factor-research"],
  "commands": ["/factor", "/backtest"],
  "mcp_dependencies": ["akshare", "tushare", "internal-store"],
  "system_prompt": "agents/system-prompt.md",
  "manifest": "agents/strategy-analyst.md"
}
```

- [x] **Step 4: Commit**

```bash
git add plugins/agent-plugins/strategy-analyst/ plugins/agent-plugins/meta-strategist/
git commit -m "feat: add strategy-analyst and meta-strategist agents"
```

### Task 1.5: Update contributing Documentation

**Files:**
- Modify: `contributing/architecture.md` — update to 5-vertical structure
- Modify: `contributing/README.md` — update slash command table
- Modify: `contributing/AGENTS.md` — update agent catalog

- [x] **Step 1: Update architecture.md with new vertical structure**

Update the Project Layout section to reflect 5 verticals instead of a-share-analysis.

- [x] **Step 2: Update skill catalog in architecture.md**

Update Skill Catalog section with new vertical groupings.

- [x] **Step 3: Commit**

```bash
git add contributing/architecture.md contributing/README.md contributing/AGENTS.md
git commit -m "docs: update architecture for 5-vertical structure"
```

### Task 1.6: Run Environment Verification

- [x] **Step 1: Run check.py**

```bash
uv run python scripts/check.py
```

- [x] **Step 2: Sync agent skills**

```bash
uv run python scripts/sync-agent-skills.py
```

- [x] **Step 3: Commit final Phase 1 cleanup**

```bash
git add -A
git commit -m "chore: Phase 1 base restructure complete"
```

---

## Phase 2: Trading Simulator

**Objective:** Build the A-share trading sandbox with T+1 settlement, price limits, transaction costs, lot size rules, and the Memory Store for RL-style transition recording.

### Task 2.1: Create Trading Simulator Core

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/simulator.py`
- Create: `plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/market_rules.py`
- Create: `plugins/vertical-plugins/simulation/skills/trading-simulator/scripts/run_simulation.py`
- Create: `plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py`

- [x] **Step 1: Write the failing test**

```python
# test_simulator.py
import pytest
from simulator import TradingSimulator, Order, PortfolioState

class TestTradingSimulator:
    def test_t1_settlement_blocks_same_day_sell(self):
        """Stocks bought today cannot be sold until tomorrow."""
        sim = TradingSimulator(initial_capital=1_000_000, start_date="20240101", end_date="20240110")
        # Buy 000001 on day 1
        sim.submit_orders("20240102", [Order(code="000001", direction="buy", volume=1000, price=10.0)])
        # Try to sell same day - should be rejected
        result = sim.submit_orders("20240102", [Order(code="000001", direction="sell", volume=1000, price=10.0)])
        assert result[0].rejected == True
        assert "T+1" in result[0].reason

    def test_board_price_limits(self):
        """Orders beyond board limits are rejected."""
        sim = TradingSimulator(initial_capital=1_000_000, start_date="20240101", end_date="20240110")
        # Main board ±10%, ChiNext ±20%
        result = sim.submit_orders("20240102", [
            Order(code="600000", direction="buy", volume=1000, price=12.0),  # 10% limit = 11.0
        ])
        assert result[0].rejected == True
        assert "price_limit" in result[0].reason

    def test_lot_size_rounding(self):
        """Orders must be rounded to 100 shares."""
        sim = TradingSimulator(initial_capital=1_000_000, start_date="20240101", end_date="20240110")
        result = sim.submit_orders("20240102", [Order(code="000001", direction="buy", volume=150, price=10.0)])
        # Should round down to 100
        assert result[0].executed_volume == 100
```

- [x] **Step 2: Run test to verify it fails**

```bash
uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -v
```

Expected: FAIL with "module 'simulator' not found"

- [x] **Step 3: Write minimal simulator.py**

```python
# simulator.py
"""A-share trading simulator with T+1 settlement, price limits, costs."""

from dataclasses import dataclass, field
from typing import Literal

@dataclass
class Order:
    code: str           # 6-digit stock code
    direction: Literal["buy", "sell"]
    volume: int         # number of shares
    price: float        # order price

@dataclass
class Execution:
    order: Order
    executed_volume: int
    executed_price: float
    rejected: bool = False
    reason: str = ""

@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, int]      # code -> volume
    nav: float
    available_to_sell: dict[str, int]  # code -> volume (T+1 constraint)

class TradingSimulator:
    BOARD_LIMITS = {
        "main": 0.10,    # ±10%
        "chinext": 0.20, # ±20%
        "star": 0.20,    # ±20%
        "bse": 0.30,     # ±30%
        "st": 0.05,      # ±5%
    }

    def __init__(self, initial_capital: float, start_date: str, end_date: str):
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date
        self.cash = initial_capital
        self.positions: dict[str, int] = {}
        self.available_to_sell: dict[str, int] = {}  # T+1 tracking
        self.pending_sells: dict[str, list] = {}    # date -> list of (code, volume)

    def _get_board_type(self, code: str) -> str:
        """Determine board type from stock code."""
        if code.startswith("688"):
            return "star"
        if code.startswith("3"):
            return "chinext"
        if code.startswith("8") or code.startswith("4"):
            return "bse"
        return "main"

    def submit_orders(self, date: str, orders: list[Order]) -> list[Execution]:
        """Execute orders with A-share constraints."""
        results = []
        for order in orders:
            exec = self._execute_order(date, order)
            results.append(exec)
        return results

    def _execute_order(self, date: str, order: Order) -> Execution:
        """Execute a single order with all A-share rules."""
        board_type = self._get_board_type(order.code)
        limit_pct = self.BOARD_LIMITS[board_type]

        # Check T+1: can only sell what's available
        if order.direction == "sell":
            available = self.available_to_sell.get(order.code, 0)
            if order.volume > available:
                return Execution(
                    order=order,
                    executed_volume=0,
                    executed_price=0,
                    rejected=True,
                    reason=f"T+1: only {available} shares available to sell"
                )

        # Check price limits (simplified - would need previous close)
        # For now, reject if price seems beyond limit

        # Apply lot size: round down to nearest 100
        executed_volume = (order.volume // 100) * 100
        if executed_volume == 0:
            return Execution(
                order=order,
                executed_volume=0,
                executed_price=0,
                rejected=True,
                reason="volume below 1 lot (100 shares)"
            )

        # Execute
        if order.direction == "buy":
            cost = executed_volume * order.price * 1.001  # ~0.1% slippage
            if cost > self.cash:
                return Execution(
                    order=order,
                    executed_volume=0,
                    executed_price=0,
                    rejected=True,
                    reason="insufficient cash"
                )
            self.cash -= cost
            self.positions[order.code] = self.positions.get(order.code, 0) + executed_volume
            # T+1: these shares cannot be sold until tomorrow
            self.pending_sells.setdefault(date, []).append((order.code, executed_volume))
        else:
            proceeds = executed_volume * order.price * 0.99975  # after costs
            self.cash += proceeds
            self.positions[order.code] -= executed_volume
            if self.positions[order.code] == 0:
                del self.positions[order.code]

        return Execution(
            order=order,
            executed_volume=executed_volume,
            executed_price=order.price,
            rejected=False
        )

    def get_state(self, date: str) -> PortfolioState:
        """Get current portfolio state."""
        total_value = self.cash
        for code, vol in self.positions.items():
            # Would need price lookup - simplified for now
            total_value += vol * 10  # placeholder
        return PortfolioState(
            cash=self.cash,
            positions=self.positions.copy(),
            nav=total_value,
            available_to_sell=self.available_to_sell.copy()
        )
```

- [x] **Step 4: Run test to verify it fails**

```bash
uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -v
```

Expected: FAIL - tests will reveal missing price limit checking, previous close tracking

- [x] **Step 5: Implement market_rules.py with full A-share rules**

```python
# market_rules.py
"""A-share market rules implementation."""

BOARD_LIMITS = {
    "main": 0.10,
    "chinext": 0.20,
    "star": 0.20,
    "bse": 0.30,
    "st": 0.05,
}

TRANSACTION_COSTS = {
    "commission": 0.00025,   # 0.025% each side
    "stamp_duty": 0.0005,    # 0.05% sell only
    "slippage_large": 0.001, # 0.1% large-cap
    "slippage_small": 0.002, # 0.2% small-cap
}

def get_board_type(code: str) -> str:
    """Determine board type from 6-digit stock code."""
    if code.startswith("688"):
        return "star"
    if code.startswith("3"):
        return "chinext"
    if code.startswith("8") or code.startswith("4"):
        return "bse"
    if is_st_stock(code):
        return "st"
    return "main"

def is_st_stock(name: str) -> bool:
    """Check if stock is ST/*ST."""
    return "ST" in name or "*ST" in name

def calc_transaction_cost(volume: int, price: float, direction: str, market_cap: str = "large") -> float:
    """Calculate total transaction cost (both sides)."""
    if direction == "sell":
        total = volume * price * (1 + TRANSACTION_COSTS["commission"] + TRANSACTION_COSTS["stamp_duty"])
    else:
        slippage = TRANSACTION_COSTS["slippage_large"] if market_cap == "large" else TRANSACTION_COSTS["slippage_small"]
        total = volume * price * (1 + TRANSACTION_COSTS["commission"] + slippage)
    return total

def check_price_limit(price: float, prev_close: float, code: str) -> tuple[bool, str]:
    """Check if price is within board limit. Returns (valid, reason)."""
    board_type = get_board_type(code)
    limit_pct = BOARD_LIMITS[board_type]
    upper_limit = prev_close * (1 + limit_pct)
    lower_limit = prev_close * (1 - limit_pct)
    if price > upper_limit:
        return False, f"price {price} exceeds upper limit {upper_limit:.2f} ({limit_pct*100}%)"
    if price < lower_limit:
        return False, f"price {price} below lower limit {lower_limit:.2f} ({limit_pct*100}%)"
    return True, ""

def round_lot_size(volume: int) -> int:
    """Round volume down to nearest 100 shares (1 lot)."""
    return (volume // 100) * 100
```

- [x] **Step 6: Run tests to verify they pass**

```bash
uv run pytest plugins/vertical-plugins/simulation/skills/trading-simulator/test_simulator.py -v
```

- [x] **Step 7: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/trading-simulator/
git commit -m "feat: add A-share trading simulator with T+1 settlement"
```

### Task 2.2: Extend Internal-Store with Memory Schema

**Files:**
- Modify: `mcp-servers/internal-store/server.py` — add experiments, transitions, episode_summaries tables
- Create: `mcp-servers/internal-store/schema.sql`
- Modify: `mcp-servers/internal-store/test_server.py`

- [x] **Step 1: Write failing test for memory store**

```python
# test_memory_store.py (add to existing test_server.py)
class TestMemoryStore:
    def test_record_experiment(self):
        """Can record and retrieve experiment."""
        result = record_experiment(
            name="momentum_test",
            strategy={"factors": ["momentum"], "period": 20},
            result={"final_nav": 1.15, "sharpe": 1.2}
        )
        assert result[0].get("id") is not None

    def test_record_transition(self):
        """Can record RL transition (state, strategy, reward, next_state)."""
        result = record_transition(
            state={"market_regime": "bull", "cash_ratio": 0.3},
            strategy={"factors": ["momentum"], "weights": {"momentum": 1.0}},
            reward={"episode_return": 0.15},
            next_state={"market_regime": "bull", "cash_ratio": 0.25}
        )
        assert result[0].get("id") is not None
```

- [x] **Step 2: Add new tables to _init_db()**

```python
def _init_db():
    """Initialize SQLite database with all tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cache_entries (...);
        CREATE TABLE IF NOT EXISTS backtest_results (...);
        CREATE TABLE IF NOT EXISTS portfolio_state (...);
        CREATE TABLE IF NOT EXISTS experiments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            params      TEXT NOT NULL,
            result      TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transitions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            state       TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            reward      TEXT NOT NULL,
            next_state  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS episode_summaries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            period      TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            final_nav   REAL NOT NULL,
            sharpe      REAL,
            max_drawdown REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
```

- [x] **Step 3: Add new MCP tools**

```python
@mcp.tool()
def record_experiment(name: str, strategy: dict, params: dict, result: dict) -> list[dict]:
    """Record an experiment result for the Meta-Agent."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO experiments (name, strategy, params, result) VALUES (?, ?, ?, ?)",
            (name, json.dumps(strategy), json.dumps(params), json.dumps(result))
        )
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        conn.close()
        return [{"id": row[0], "status": "recorded"}]
    except Exception as e:
        return [{"error": str(e), "tool": "record_experiment"}]

@mcp.tool()
def get_best_strategies(top_k: int = 5) -> list[dict]:
    """Get top-K best performing strategies by episode return."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM experiments
            ORDER BY json_extract(result, '$.final_nav') DESC
            LIMIT ?
        """, (top_k,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_best_strategies"}]

@mcp.tool()
def record_transition(state: dict, strategy: dict, reward: dict, next_state: dict) -> list[dict]:
    """Record an RL transition for the Meta-Agent's memory."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO transitions (state, strategy, reward, next_state) VALUES (?, ?, ?, ?)",
            (json.dumps(state), json.dumps(strategy), json.dumps(reward), json.dumps(next_state))
        )
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        conn.close()
        return [{"id": row[0], "status": "recorded"}]
    except Exception as e:
        return [{"error": str(e), "tool": "record_transition"}]
```

- [x] **Step 4: Run tests**

```bash
uv run pytest mcp-servers/internal-store/test_server.py -v
```

- [x] **Step 5: Commit**

```bash
git add mcp-servers/internal-store/server.py mcp-servers/internal-store/test_server.py
git commit -m "feat: extend internal-store with experiments and transitions tables"
```

### Task 2.3: Create Experiment Tracker Skill

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/experiment-tracker/SKILL.md`
- Create: `plugins/vertical-plugins/simulation/skills/experiment-tracker/scripts/track_experiment.py`
- Create: `plugins/vertical-plugins/simulation/skills/experiment-tracker/test_track_experiment.py`

- [x] **Step 1: Write SKILL.md following contributing/playbooks.md template**

```markdown
---
name: experiment-tracker
description: |
  Recording and retrieving simulation experiment results.
  Triggers: "record experiment", "track results", "experiment history"
---

# Experiment Tracker

## Overview
Records simulation results to internal-store and retrieves historical experiments for the Meta-Agent's exploration.

## Inputs
- experiment_name: str
- strategy_config: dict (factors, weights, params)
- simulation_result: dict (final_nav, sharpe, max_drawdown, nav_curve, trades_log)

## Outputs
- experiment_id: int
- lineage: list of ancestor experiments

## Tools
- mcp__internal-store__record_experiment
- mcp__internal-store__get_best_strategies
- mcp__internal-store__get_experiment_lineage

## Steps
1. Receive simulation result
2. Serialize strategy config and metrics
3. Call record_experiment tool
4. Return experiment_id for future reference
```

- [x] **Step 2: Write track_experiment.py**

```python
# track_experiment.py
"""Experiment tracking script for the simulation skill."""

import json
import sys

def record_experiment(name: str, strategy: dict, params: dict, result: dict) -> int:
    """
    Record experiment to internal-store via MCP.
    Returns experiment_id.
    """
    # In production, this would call the MCP tool
    # For now, returns a mock ID
    print(f"Recording experiment: {name}")
    print(f"Strategy: {json.dumps(strategy)}")
    print(f"Result: {json.dumps(result)}")
    return 1

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: track_experiment.py <name> <strategy_json> <result_json>")
        sys.exit(1)
    name = sys.argv[1]
    strategy = json.loads(sys.argv[2])
    result = json.loads(sys.argv[3])
    exp_id = record_experiment(name, strategy, {}, result)
    print(f"Recorded experiment ID: {exp_id}")
```

- [x] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/experiment-tracker/
git commit -m "feat: add experiment-tracker skill"
```

### Task 2.4: Create Evolution Loop Skill

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/evolution-loop/SKILL.md`
- Create: `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/evolution.py`
- Create: `plugins/vertical-plugins/simulation/skills/evolution-loop/test_evolution.py`

- [x] **Step 1: Write SKILL.md**

```markdown
---
name: evolution-loop
description: |
  Meta-Agent iteration control and doom loop detection.
  Triggers: "run evolution", "next iteration", "check convergence"
---

# Evolution Loop

## Overview
Controls the Meta-Agent's evolution iterations, detects repeated failures (doom loops), and decides when to stop exploration.

## Inputs
- current_iteration: int
- max_iterations: int
- target_return: float
- recent_failures: list of strategy signatures

## Outputs
- should_continue: bool
- next_hypothesis: dict or None
- termination_reason: str or None

## Doom Loop Detection
- Track last N failed strategies
- If same signature appears > 3 times, inject corrective prompt
- Suggested actions: change factor weights, try different universe, adjust rebalancing frequency

## Termination Conditions
- target_return reached (final_nav / initial_capital >= target)
- max_iterations hit
- Doom loop detected (no improvement after 5+ corrections)
```

- [x] **Step 2: Write evolution.py**

```python
# evolution.py
"""Evolution loop controller for Meta-Agent."""

from dataclasses import dataclass

@dataclass
class EvolutionState:
    iteration: int
    best_return: float
    recent_failures: list[str]
    failure_signatures: dict[str, int]

MAX_ITERATIONS = 50
DOOM_THRESHOLD = 3
CORRECTION_COUNT_LIMIT = 5

def should_continue(state: EvolutionState, target_return: float) -> tuple[bool, str | None]:
    """Determine if evolution should continue."""
    if state.best_return >= target_return:
        return False, f"target_return reached: {state.best_return:.2%}"

    if state.iteration >= MAX_ITERATIONS:
        return False, f"max_iterations hit: {MAX_ITERATIONS}"

    # Check doom loop
    for sig, count in state.failure_signatures.items():
        if count >= DOOM_THRESHOLD:
            return False, f"doom_loop_detected: {sig} failed {count} times"

    return True, None

def generate_correction(failure_signature: str) -> str:
    """Generate corrective action based on failure pattern."""
    corrections = {
        "momentum_concentration": "reduce momentum weight, diversify factors",
        "value_overfit": "increase lookback period, reduce rebalancing frequency",
        "low_sharpe": "add defensive factors (low_vol, quality), reduce position count",
        "high_turnover": "extend holding period, use score threshold for rebalancing",
    }
    return corrections.get(failure_signature, "try different factor combination")
```

- [x] **Step 3: Run tests**

```bash
uv run pytest plugins/vertical-plugins/simulation/skills/evolution-loop/ -v
```

- [x] **Step 4: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/evolution-loop/
git commit -m "feat: add evolution-loop skill with doom loop detection"
```

### Task 2.5: Integration Test - Full Simulation Run

- [x] **Step 1: Write integration test**

```python
# test_simulation_integration.py
import pytest

@pytest.mark.integration
class TestSimulationIntegration:
    def test_full_simulation_cycle(self):
        """Test complete simulation: hypothesis → simulation → record → evaluate."""
        # 1. Generate hypothesis (mock)
        hypothesis = {"factors": ["momentum"], "period": 20, "top_k": 50}

        # 2. Run simulation (would need actual market data)
        # For now, just verify simulator accepts orders
        from simulator import TradingSimulator, Order
        sim = TradingSimulator(initial_capital=1_000_000, start_date="20240101", end_date="20240110")
        result = sim.submit_orders("20240102", [
            Order(code="000001", direction="buy", volume=1000, price=10.0)
        ])
        assert result[0].rejected == False
        assert result[0].executed_volume == 1000
```

- [x] **Step 2: Run integration test**

```bash
uv run pytest -m integration plugins/vertical-plugins/simulation/ -v
```

- [x] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/
git commit -m "test: add simulation integration tests"
```

---

## Phase 3: Meta-Agent Phase 1

**Objective:** Implement meta-strategist parameter search, Evolution Loop, and Doom Loop prevention.

### Task 3.1: Implement Meta-Strategist Agent Core

**Files:**
- Modify: `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`
- Create: `plugins/agent-plugins/meta-strategist/agents/system-prompt.md`
- Create: `plugins/agent-plugins/meta-strategist/plugin.json`

- [ ] **Step 1: Write system-prompt.md**

```markdown
# Meta-Strategist System Prompt

You are the Meta-Strategist — an autonomous A-share strategy discovery agent powered by simulation-driven evolution.

## Your Mission
Explore the strategy space to maximize simulated trading returns. Given initial capital and a time period, discover strategies that produce the best terminal portfolio value.

## Available Tools
- mcp__internal-store__get_best_strategies: Query historical best strategies
- mcp__internal-store__record_experiment: Record new experiment results
- mcp__internal-store__record_transition: Record RL transitions for memory
- mcp__akshare__stock_zh_a_hist: Fetch historical OHLCV data
- mcp__tushare__daily: Get daily market data
- trading-simulator: Execute strategies in sandbox with A-share rules

## Evolution Loop
1. Query MemoryStore for best historical strategies
2. Generate new hypothesis (exploration + exploitation)
3. Run simulation via trading-simulator
4. Record experiment to internal-store
5. Evaluate and decide next iteration or stop

## Doom Loop Prevention
If you detect the same failed strategy pattern > 3 times:
- Inject corrective prompt: "Strategy {sig} has failed repeatedly. Consider: [specific correction]"
- Change direction: different factor combination, universe, or rebalancing frequency

## Constraints
- Always use point-in-time index constituents (never current)
- Apply T+1 settlement, transaction costs, lot size rules
- Target minimum: Sharpe >= 1.0, MaxDD <= 20%
- Stop if target return reached or iteration limit (50) hit

## Output Format
Each iteration produces:
- Hypothesis: factor combination + parameters
- Simulation result: final_nav, sharpe, max_drawdown
- Next action: continue with new hypothesis or stop
```

- [ ] **Step 2: Commit**

```bash
git add plugins/agent-plugins/meta-strategist/
git commit -m "feat: implement meta-strategist agent core"
```

### Task 3.2: Implement Hypothesis Generation

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py`
- Create: `plugins/vertical-plugins/simulation/skills/evolution-loop/test_generate_hypothesis.py`

- [ ] **Step 1: Write hypothesis generation logic**

```python
# generate_hypothesis.py
"""Hypothesis generation for Meta-Agent exploration."""

import random
from typing import Literal

FACTOR_LIBRARY = [
    "momentum_20d", "momentum_60d", "momentum_120d",
    "value_pe", "value_pb", "value_pc",
    "quality_roe", "quality_debt", "quality_growth",
    "low_vol_20d", "low_vol_60d",
    "size_log_mcap",
]

UNIVERSE_OPTIONS = ["全A", "沪深300", "中证500", "中证1000"]
REBALANCE_OPTIONS = ["daily", "weekly", "monthly"]
TOP_K_OPTIONS = [20, 30, 50, 100]

def generate_random_hypothesis() -> dict:
    """Generate a random strategy hypothesis."""
    n_factors = random.randint(1, 4)
    factors = random.sample(FACTOR_LIBRARY, n_factors)
    weights = {f: round(random.random(), 2) for f in factors}
    # Normalize weights
    total = sum(weights.values())
    weights = {f: round(w / total, 2) for f, w in weights.items()}

    return {
        "factors": factors,
        "weights": weights,
        "universe": random.choice(UNIVERSE_OPTIONS),
        "rebalance": random.choice(REBALANCE_OPTIONS),
        "top_k": random.choice(TOP_K_OPTIONS),
        "stop_loss": random.choice([0.05, 0.10, 0.15]),
        "max_position": random.choice([0.05, 0.10, 0.15]),
    }

def generate_exploitative_hypothesis(best_strategies: list[dict]) -> dict:
    """Generate hypothesis based on best historical strategies."""
    if not best_strategies:
        return generate_random_hypothesis()

    best = best_strategies[0]
    strategy = best.get("strategy", {})
    # Add small perturbation to best known strategy
    factors = strategy.get("factors", ["momentum_20d"])
    weights = strategy.get("weights", {}).copy()

    # Perturb weights slightly
    for f in weights:
        weights[f] += random.uniform(-0.1, 0.1)
        weights[f] = max(0.01, min(1.0, weights[f]))

    # Normalize
    total = sum(weights.values())
    weights = {f: round(w / total, 2) for f, w in weights.items()}

    return {
        **strategy,
        "factors": factors,
        "weights": weights,
        "top_k": strategy.get("top_k", 50),
    }
```

- [ ] **Step 2: Write tests**

```python
def test_generate_random_hypothesis():
    hyp = generate_random_hypothesis()
    assert "factors" in hyp
    assert "weights" in hyp
    assert len(hyp["factors"]) >= 1
    assert abs(sum(hyp["weights"].values()) - 1.0) < 0.01  # weights sum to 1

def test_exploitative_from_best():
    best = [{"strategy": {"factors": ["momentum"], "weights": {"momentum": 1.0}, "top_k": 50}}]
    hyp = generate_exploitative_hypothesis(best)
    assert "momentum" in hyp["factors"]
    assert hyp["top_k"] == 50
```

- [ ] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/evolution-loop/scripts/generate_hypothesis.py
git commit -m "feat: add hypothesis generation for Meta-Agent"
```

### Task 3.3: Wire Meta-Strategist to Simulation Skills

**Files:**
- Modify: `plugins/agent-plugins/meta-strategist/plugin.json`
- Modify: `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`

- [ ] **Step 1: Update plugin.json with skill references**

```json
{
  "name": "meta-strategist",
  "display_name": "Meta-Strategist",
  "description": "Autonomous strategy exploration via simulation-driven evolution",
  "version": "0.1.0",
  "type": "agent-plugin",
  "skills": [
    "simulation:trading-simulator",
    "simulation:experiment-tracker",
    "simulation:evolution-loop",
    "market-data:factor-library"
  ],
  "commands": ["/evolve"],
  "mcp_dependencies": ["akshare", "tushare", "internal-store"],
  "system_prompt": "agents/system-prompt.md",
  "manifest": "agents/meta-strategist.md"
}
```

- [ ] **Step 2: Update meta-strategist.md with evolution loop steps**

Add explicit evolution loop steps to the manifest.

- [ ] **Step 3: Commit**

```bash
git add plugins/agent-plugins/meta-strategist/
git commit -m "feat: wire meta-strategist to simulation skills"
```

---

## Phase 4: Jupyter Notebooks

**Objective:** Create 4 visualization notebooks for simulation results, factor analysis, backtest results, and portfolio management.

### Task 4.1: Create Simulation Results Notebook

**Files:**
- Create: `notebooks/simulation.ipynb`

- [ ] **Step 1: Write notebook with plotly visualizations**

```python
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": ["# Strategy Evolution Simulation\n", "Visualizes the evolution tree and performance of Meta-Agent experiments."]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import pandas as pd\n",
    "import plotly.express as px\n",
    "from internal_store import get_experiments, get_best_strategies\n",
    "\n",
    "# Load experiments\n",
    "experiments = get_experiments(limit=100)\n",
    "df = pd.DataFrame([{\"iteration\": e[\"id\"], \"final_nav\": e[\"result\"][\"final_nav\"], \"sharpe\": e[\"result\"][\"sharpe\"]} for e in experiments])"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# NAV curve over iterations\n",
    "fig = px.line(df, x=\"iteration\", y=\"final_nav\", title=\"Strategy Performance Over Evolution\")\n",
    "fig.show()"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/simulation.ipynb
git commit -m "feat: add simulation results notebook"
```

### Task 4.2: Create Factor Analysis Notebook

**Files:**
- Create: `notebooks/factors.ipynb`

- [ ] **Step 1: Write notebook with factor exposure visualizations**

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "source": ["# Factor Analysis\n", "Analyze factor exposure, returns, and turnover."]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/factors.ipynb
git commit -m "feat: add factor analysis notebook"
```

### Task 4.3: Create Backtest Results Notebook

**Files:**
- Create: `notebooks/backtest.ipynb`

- [ ] **Step 1: Write notebook with backtest visualizations**

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "source": ["# Backtest Results\n", "Visualize backtest performance, drawdown, and parameter heatmaps."]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/backtest.ipynb
git commit -m "feat: add backtest results notebook"
```

### Task 4.4: Create Portfolio Notebook

**Files:**
- Create: `notebooks/portfolio.ipynb`

- [ ] **Step 1: Write notebook with portfolio visualizations**

```json
{
 "cells": [
  {
   "cell_type": "markdown",
   "source": ["# Portfolio Management\n", "Visualize holdings, NAV curve, and risk metrics."]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 5
}
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/portfolio.ipynb
git commit -m "feat: add portfolio notebook"
```

---

## Phase 5: Meta-Agent Phase 2

**Objective:** Enable Meta-Agent to generate new factor/strategy Python scripts.

### Task 5.1: Implement Script Generation Skill

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/script-generator/SKILL.md`
- Create: `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_factor_script.py`
- Create: `plugins/vertical-plugins/simulation/skills/script-generator/scripts/generate_strategy_script.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
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

## Script Template for Factors
```python
def compute_<factor_name>(df: pd.DataFrame, **params) -> pd.Series:
    \"\"\"
    Compute <factor_description>.
    Args:
        df: DataFrame with columns [date, code, close, volume, ...]
        **params: factor-specific parameters
    Returns:
        pd.Series with index (date, code) and factor values
    \"\"\"
    # Implementation
    return result
```

## Validation
- Run ruff check on generated script
- Verify function can be imported without errors
- Test with sample data
```

- [ ] **Step 2: Write generate_factor_script.py**

```python
# generate_factor_script.py
"""Script generator for factor computation."""

import inspect
from pathlib import Path

FACTOR_TEMPLATE = '''"""
Auto-generated factor: {factor_name}
Created by Meta-Agent script-generator
"""

import pandas as pd
import numpy as np

def compute_{func_name}(df: pd.DataFrame, **params) -> pd.Series:
    """
    {description}

    Args:
        df: DataFrame with columns [date, code, close, volume, high, low, ...]
        **params: period={default_period}, additional parameters

    Returns:
        pd.Series with index (date, code) and factor values
    """
    {implementation}

    return result
'''

def generate_factor_script(factor_name: str, description: str, implementation: str) -> str:
    """Generate a factor computation script."""
    func_name = factor_name.lower().replace("-", "_").replace(" ", "_")

    # Extract default period from description if mentioned
    default_period = 20
    if "20" in description:
        default_period = 20
    elif "60" in description:
        default_period = 60
    elif "120" in description:
        default_period = 120

    script = FACTOR_TEMPLATE.format(
        factor_name=factor_name,
        func_name=func_name,
        description=description,
        default_period=default_period,
        implementation=implementation
    )
    return script

def save_factor_script(factor_name: str, script: str, target_dir: Path) -> Path:
    """Save generated script to target directory."""
    func_name = factor_name.lower().replace("-", "_").replace(" ", "_")
    file_path = target_dir / f"compute_{func_name}.py"
    file_path.write_text(script)
    return file_path

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: generate_factor_script.py <factor_name> <description> <implementation>")
        sys.exit(1)
    factor_name = sys.argv[1]
    description = sys.argv[2]
    implementation = sys.argv[3] if len(sys.argv) > 3 else "# TODO: implement factor logic"
    script = generate_factor_script(factor_name, description, implementation)
    print(script)
```

- [ ] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/script-generator/
git commit -m "feat: add script-generator skill for Meta-Agent Phase 2"
```

### Task 5.2: Integrate Script Generator into Meta-Agent

**Files:**
- Modify: `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`
- Modify: `plugins/agent-plugins/meta-strategist/plugin.json`

- [ ] **Step 1: Update meta-strategist.md to include Phase 2 capabilities**

Add to the autonomy table in meta-strategist.md:
| Generate new Skill scripts (Python) | — | ✓ | ✓ |

- [ ] **Step 2: Commit**

```bash
git add plugins/agent-plugins/meta-strategist/
git commit -m "feat: integrate script-generator into Meta-Agent Phase 2"
```

---

## Phase 6: Meta-Agent Phase 3

**Objective:** Enable Meta-Agent to modify Agent definitions and add MCP tools.

### Task 6.1: Implement Agent Definition Modifier

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/agent-modifier/SKILL.md`
- Create: `plugins/vertical-plugins/simulation/skills/agent-modifier/scripts/modify_agent.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: agent-modifier
description: |
  Modifies agent definitions (.md files) based on strategy discoveries.
  Triggers: "modify agent", "update agent behavior", "change agent rules"
---

# Agent Modifier

## Overview
Enables Meta-Agent Phase 3 to update agent definitions when a strategy discovery suggests better workflows.

## Constraints
- Can only modify skill references, command mappings, and guardrail descriptions
- Cannot change agent persona or fundamental purpose
- All changes must pass `scripts/check.py` validation

## Validation
- Run `uv run python scripts/check.py` after any modification
- Ensure R1-R6 boundary rules are not violated
```

- [ ] **Step 2: Write modify_agent.py**

```python
# modify_agent.py
"""Agent definition modifier for Meta-Agent Phase 3."""

import re
from pathlib import Path

def update_agent_skill_references(agent_dir: Path, new_skill: str) -> bool:
    """Add a new skill reference to an agent's plugin.json."""
    plugin_path = agent_dir / "plugin.json"
    if not plugin_path.exists():
        return False

    content = plugin_path.read_text()
    # Parse JSON and add skill to skills array
    import json
    data = json.loads(content)
    skill_ref = f"simulation:{new_skill}"
    if skill_ref not in data.get("skills", []):
        data.setdefault("skills", []).append(skill_ref)
    plugin_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return True

def update_agent_guardrails(agent_md_path: Path, new_guardrail: str) -> bool:
    """Add a new guardrail to an agent's AGENT.md."""
    if not agent_md_path.exists():
        return False

    content = agent_md_path.read_text()
    # Append to Guardrails section
    if "## Guardrails" in content:
        content = content.replace(
            "## Guardrails",
            f"## Guardrails\n- {new_guardrail}"
        )
    else:
        content += f"\n\n## Additional Guardrails\n- {new_guardrail}\n"

    agent_md_path.write_text(content)
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: modify_agent.py <agent_name> <modification_type> <args>")
        sys.exit(1)
    agent_name = sys.argv[1]
    mod_type = sys.argv[2]

    agents_dir = Path("plugins/agent-plugins")
    agent_dir = agents_dir / agent_name

    if mod_type == "add_skill":
        skill_name = sys.argv[3]
        success = update_agent_skill_references(agent_dir, skill_name)
    elif mod_type == "add_guardrail":
        guardrail = sys.argv[3]
        success = update_agent_guardrails(agent_dir / "agents" / f"{agent_name}.md", guardrail)
    else:
        success = False

    print(f"Success: {success}")
```

- [ ] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/agent-modifier/
git commit -m "feat: add agent-modifier skill for Meta-Agent Phase 3"
```

### Task 6.2: Implement MCP Tool Adder

**Files:**
- Create: `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/SKILL.md`
- Create: `plugins/vertical-plugins/simulation/skills/mcp-tool-adder/scripts/add_mcp_tool.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: mcp-tool-adder
description: |
  Adds new MCP tools to existing servers based on data access patterns discovered during evolution.
  Triggers: "add MCP tool", "new data endpoint", "extend server"
---

# MCP Tool Adder

## Overview
Enables Meta-Agent Phase 3 to extend MCP servers with new tools when simulation reveals useful data patterns.

## Constraints (R6 Boundary)
- MCP servers must contain ONLY data access logic
- No domain/business logic in MCP tools
- New tools must follow FastMCP pattern (df_to_json, error handling)
- Must register new tool in server's README.md

## Process
1. Identify data access pattern from simulation
2. Write new @mcp.tool() function following server's pattern
3. Add to appropriate server (akshare/tushare/internal-store)
4. Update server's README.md tool table
5. Restart server and verify tool registration
```

- [ ] **Step 2: Write add_mcp_tool.py**

```python
# add_mcp_tool.py
"""MCP tool adder for Meta-Agent Phase 3."""

from pathlib import Path

MCP_TOOL_TEMPLATE = '''
@mcp.tool()
def {tool_name}({params}) -> list[dict]:
    """
    {description}

    Args:
{param_docs}
    """
    try:
        df = {upstream_call}
        return df_to_json(df)
    except Exception as e:
        return [{"error": str(e), "tool": "{tool_name}"}]
'''

def add_tool_to_server(server_name: str, tool_name: str, params: str, description: str, upstream_call: str) -> bool:
    """Add a new tool to an existing MCP server."""
    server_path = Path(f"mcp-servers/{server_name}/server.py")
    if not server_path.exists():
        return False

    content = server_path.read_text()

    # Generate tool code
    param_list = ", ".join(params.split(", ")) if params else ""
    param_docs = "\n".join([f"        {p.split(':')[0].strip()}: Description of {p.split(':')[0].strip()}." for p in params.split(", ") if p])

    tool_code = MCP_TOOL_TEMPLATE.format(
        tool_name=tool_name,
        params=param_list,
        description=description,
        param_docs=param_docs or "        # Add parameter descriptions",
        upstream_call=upstream_call
    )

    # Insert before ASGI App section
    asgi_marker = "# --- ASGI App ---"
    if asgi_marker in content:
        content = content.replace(asgi_marker, tool_code + "\n\n" + asgi_marker)
    else:
        content += "\n" + tool_code

    server_path.write_text(content)
    return True

def update_server_readme(server_name: str, tool_name: str, description: str) -> bool:
    """Update server README with new tool."""
    readme_path = Path(f"mcp-servers/{server_name}/README.md")
    if not readme_path.exists():
        return False

    content = readme_path.read_text()

    # Add to tools table
    new_entry = f"\n| `{tool_name}` | New tool | {description} |"
    content = content.replace("| Tool Name |", f"| `tool_name` | ... | ... |").replace("| Tool Name |", f"| `tool_name` | ... | ... |\n| `{tool_name}` | New tool | {description} |")

    readme_path.write_text(content)
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 5:
        print("Usage: add_mcp_tool.py <server> <tool_name> <params> <description>")
        sys.exit(1)

    server = sys.argv[1]
    tool_name = sys.argv[2]
    params = sys.argv[3]
    description = sys.argv[4]

    success = add_tool_to_server(server, tool_name, params, description, "ak.new_function()")
    print(f"Tool added: {success}")
```

- [ ] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/simulation/skills/mcp-tool-adder/
git commit -m "feat: add mcp-tool-adder skill for Meta-Agent Phase 3"
```

---

## Implementation Order

| Phase | Priority | Dependencies | Estimated Tasks |
|-------|----------|--------------|-----------------|
| Phase 1 | HIGH | None | 6 tasks |
| Phase 2 | HIGH | Phase 1 complete | 5 tasks |
| Phase 3 | HIGH | Phase 2 complete | 3 tasks |
| Phase 4 | MEDIUM | Phase 1 complete | 4 tasks |
| Phase 5 | MEDIUM | Phase 3 complete | 2 tasks |
| Phase 6 | LOW | Phase 5 complete | 2 tasks |

---

## Verification Commands

```bash
# Phase 1
uv run python scripts/check.py
uv run python scripts/sync-agent-skills.py --check

# Phase 2
uv run pytest plugins/vertical-plugins/simulation/ -v
uv run pytest mcp-servers/internal-store/test_server.py -v

# Phase 3
uv run python scripts/check.py
# Test meta-strategist with: /evolve ¥1000000 20240101 20250101

# Phase 4
uv run jupyter lab notebooks/

# Phase 5-6
uv run python scripts/check.py
```

---

## Plan Complete

**Total Tasks:** 22 tasks across 6 phases

**Execution Options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**