# Architecture

> A-Share Agents' static architecture: tech stack, project layout, four-layer architecture, dependency rules, data flow, and component catalogs.

## Tech Stack

- **Language**: Python 3.10+
- **MCP Framework**: FastMCP (`mcp.server.fastmcp`)
- **HTTP Transport**: uvicorn (ASGI)
- **Data Sources**: AKShare (free, real-time), Tushare (token, historical)
- **Local Storage**: SQLite (metadata, experiments, transitions), Parquet (cached data)
- **Visualization**: Jupyter Notebooks + plotly/matplotlib
- **Testing**: pytest, pytest-mock
- **Linting**: ruff
- **Agent Host**: Claude Code with custom plugins

## Project Layout

```
a-share-agents/
├── plugins/
│   ├── agent-plugins/                # L3+L2: Agent plugins
│   │   ├── meta-strategist/          #   Meta-Agent: autonomous strategy exploration
│   │   ├── equity-researcher/        #   Stock screening + deep research + valuation
│   │   ├── strategy-analyst/         #   Factor research + strategy + backtest
│   │   ├── portfolio-manager/        #   Portfolio construction + optimization + monitoring
│   │   └── market-monitor/           #   Market monitoring + northbound flow
│   │
│   └── vertical-plugins/             # L1: Skill groups by domain vertical
│       ├── market-data/              #   Core: quotes, factors, preprocessing
│       ├── equity-research/          #   Fundamentals, financials, valuation
│       ├── trading-strategy/         #   Backtest, signals, risk control
│       ├── simulation/               #   Trading simulator, experiments, evolution
│       └── market-monitor/           #   Breadth, northbound, sentiment
│
├── mcp-servers/                      # L0: MCP data connectors
│   ├── akshare-server/               #   Real-time quotes + historical OHLCV
│   ├── tushare-server/               #   High-quality historical + financials
│   └── internal-store/               #   Cache + experiments + memory (transitions)
│
├── notebooks/                        # Visualization layer (Jupyter)
│   ├── simulation.ipynb              #   Simulation results, strategy evolution tree
│   ├── factors.ipynb                 #   Factor exposure, factor returns
│   ├── backtest.ipynb                #   Backtest results, parameter heatmaps
│   └── portfolio.ipynb               #   Holdings, NAV curve, risk metrics
│
├── scripts/                          # Dev tooling
│   ├── check.py                      # Environment verification + boundary rules
│   ├── validate.py                   # Plugin structure validation
│   └── sync-agent-skills.py          # Sync skills from verticals into agent dirs
│
├── tests/                            # Test suites
├── contributing/                     # This directory
├── docs/                             # Design documents
├── .mcp.json                         # Project-level MCP config (3 servers)
├── pyproject.toml                    # Root uv workspace
└── CLAUDE.md                         # Claude Code project instructions
```

## Four-Layer Architecture

The system is organized into four layers with a **downward-only dependency rule**. Higher layers may reference lower layers; lower layers must never reference higher ones.

```text
L3  Meta-Agent Layer  (autonomous strategy exploration)
    plugins/agent-plugins/meta-strategist/
    ├── AGENT.md              Evolution loop, hypothesis generation, doom loop prevention
    ├── system-prompt.md      System prompt with memory query integration
    └── plugin.json           Skill references, MCP dependencies
    ↓ delegates to
L2  Agent Layer  (workflow orchestration)
    plugins/agent-plugins/<name>/
    ├── AGENT.md              Persona, deliverables, workflow, guardrails
    ├── system-prompt.md      System prompt for Claude
    └── plugin.json           Skills list, commands, MCP dependencies
    ↓ may use
L1  Skill Layer  (domain knowledge + executable scripts)
    plugins/vertical-plugins/<vertical>/skills/<name>/
    ├── SKILL.md              Trigger conditions, inputs, outputs, steps
    ├── prompt.md             Execution prompt template
    ├── scripts/              Domain logic (Python, invoked by agents via Bash)
    ├── references/           Lookup tables, formulas, thresholds
    └── examples/             Input/output examples
    ↓ may use
L0  Connector Layer  (MCP data access only)
    mcp-servers/<name>/server.py
    ├── @mcp.tool()           One function per data endpoint
    └── .mcp.json             Server URL and transport config
```

### Boundary Rules

These rules are enforced by `scripts/check.py` where possible.

| Rule | Statement |
|------|-----------|
| **R1** | MCP Server code (`mcp-servers/`) must not import Agent or Skill code (`plugins/`). |
| **R2** | Skill definitions (`skills/`) must not import or reference Agent code (`agent-plugins/`). |
| **R3** | Agents may reference Skill definitions but must never modify Skill source files. |
| **R4** | Each MCP Server must be self-contained — no cross-server imports between `akshare-server/`, `tushare-server/`, `internal-store/`. |
| **R5** | `mcp-servers/internal-store/` is the only shared data layer. All servers read/write through it, never through each other. |
| **R6** | MCP servers must contain only data access logic — no domain/business logic. Domain logic belongs in skill `scripts/`. |

## Meta-Agent Architecture

The `meta-strategist` is a self-evolving agent inspired by HuggingFace's ml-intern design. It autonomously explores strategies to maximize simulated trading returns.

### Core Concept

**Single objective**: Given initial capital and a time period, maximize terminal portfolio value. The Meta-Agent may decompose sub-metrics during exploration, but the system only evaluates the final return.

### Evolution Loop

```
meta-strategist receives goal (e.g., ¥1M capital, 2024-01-01 to 2025-01-01, maximize return)
     │
     ▼
┌──────────────────────────────────────────────────────┐
│  Evolution Loop (max N iterations)                    │
│                                                       │
│  1. Query Memory                                      │
│     - get_best_strategies() → historical top-K        │
│     - get_similar_states(current) → analogous markets │
│     - get_failures(proposed) → doom loop prevention   │
│                                                       │
│  2. Generate Hypothesis                               │
│     - Based on memory + market knowledge              │
│     - "Try momentum(0.5) + value(0.3) + quality(0.2)" │
│                                                       │
│  3. Configure Strategy                                │
│     - Phase 1: select existing factors + set params   │
│     - Phase 2: generate new factor Python scripts     │
│     - Phase 3: create new Skills / modify Agents      │
│                                                       │
│  4. Run Simulation                                    │
│     - trading-simulator executes strategy over period │
│     - Records (state, strategy, reward) transitions   │
│                                                       │
│  5. Evaluate                                          │
│     - Only metric: final_nav / initial_capital        │
│     - Compare against historical best                 │
│                                                       │
│  6. Record Experiment                                 │
│     - Write to Experiment Store                       │
│     - Write transitions to Memory Store               │
│                                                       │
│  7. Doom Loop Check                                   │
│     - Detect repeated failed strategies               │
│     - Inject corrective prompt, change direction      │
│                                                       │
│  8. Repeat or Stop                                    │
│     - Stop if target reached or iteration limit hit   │
└──────────────────────────────────────────────────────┘
```

### Meta-Agent Autonomy (Progressive)

| Capability | Phase 1 | Phase 2 | Phase 3 |
|------------|---------|---------|---------|
| Strategy parameter search | ✓ | ✓ | ✓ |
| Factor combination exploration | ✓ | ✓ | ✓ |
| Generate new Skill scripts (Python) | — | ✓ | ✓ |
| Modify Agent definitions (.md) | — | — | ✓ |
| Add MCP tools | — | — | ✓ |
| Experiment recording | ✓ | ✓ | ✓ |

## Trading Simulator

The trading simulator is a sandbox that strictly models A-share trading rules. It is the Meta-Agent's execution environment.

### Core Interface

```python
class TradingSimulator:
    def __init__(self, initial_capital, start_date, end_date): ...

    def submit_orders(self, date, orders: list[Order]) -> list[Execution]:
        """Execute orders with A-share constraints:
        T+1, board price limits, lot size (100 shares), transaction costs."""

    def get_state(self, date) -> PortfolioState:
        """Current cash, positions, NAV, available-to-sell."""

    def get_market_data(self, date) -> MarketSnapshot:
        """Daily market data from cache/MCP."""

    def run(self, strategy_fn) -> SimulationResult:
        """Run full simulation. strategy_fn(date, state, market) -> orders."""

    def get_result(self) -> SimulationResult:
        """Final result: initial_capital, final_nav, nav_curve, trades_log."""
```

### A-Share Constraints Modeled

- **T+1**: stocks bought today cannot be sold until tomorrow
- **Board price limits**: main ±10%, ChiNext/STAR ±20%, BSE ±30%, ST ±5%
- **Transaction costs**: commission 0.025% each side, stamp duty 0.05% sell-only, slippage ~0.05%
- **Lot size**: 100 shares minimum, round down when buying
- **Exclusions**: ST/*ST, suspended, limit-up/limit-down stocks cannot be traded

## Memory Store

RL-style transition storage for the Meta-Agent's learning. Stored in `internal-store` SQLite.

### State-Strategy-Reward Model

```
State_t ──→ Strategy_t ──→ Reward_t ──→ State_{t+1}
   │             │             │             │
   ▼             ▼             ▼             ▼
market_state  factors +     episode/      next market +
portfolio     weights +     step return   portfolio
factor_exp    params                      state
```

### State Definition

```python
@dataclass
class State:
    # Market state
    market_regime: str          # bull / bear / sideways / crash
    market_breadth: float       # advancing stocks ratio
    volatility_index: float     # market volatility
    northbound_flow: float      # net northbound capital flow
    # Portfolio state
    cash_ratio: float           # cash / total NAV
    position_count: int         # number of holdings
    sector_concentration: float # HHI of sector allocation
    unrealized_pnl: float       # unrealized P&L ratio
    # Factor exposure
    factor_exposure: dict       # {"momentum": 0.8, "value": -0.3, ...}
```

### Strategy Definition

```python
@dataclass
class Strategy:
    name: str                   # strategy identifier
    factors: list[str]          # selected factors
    weights: dict[str, float]   # factor weights
    params: dict                # rebalance_days, max_stocks, etc.
    risk_rules: dict            # stop_loss, max_position, etc.
    code_path: str | None       # Phase 2+: custom script path
```

### Reward Definition

```python
@dataclass
class Reward:
    episode_return: float       # final_nav / initial_capital - 1
    step_return: float          # nav_{t+1} / nav_t - 1
    # Optional self-recorded auxiliary metrics (not optimization targets)
    sharpe: float | None
    max_drawdown: float | None
    turnover: float | None
    win_rate: float | None
```

### Memory Query Interface

| Method | Purpose |
|--------|---------|
| `record_transition(state, strategy, reward, next_state)` | Store one transition |
| `get_best_strategies(top_k)` | Historical best by episode_return |
| `get_similar_states(current_state, top_k)` | Find analogous market states |
| `get_failures(strategy_signature)` | Failed attempts for doom loop prevention |
| `get_transition_matrix()` | Full (state, strategy) → avg_reward mapping |
| `get_lineage(experiment_id)` | Full evolution history for one branch |

## Data Flow

### Complete Exploration Cycle

```
User: "¥1M, 2024-01-01 to 2025-01-01, maximize return"
  │
  ▼
meta-strategist (L3)
  │
  ├──→ Query MemoryStore (L0 via internal-store MCP)
  ├──→ Generate Hypothesis
  ├──→ Configure Strategy
  │
  ▼
trading-simulator (L1 Skill script)
  │
  │   for each trading day:
  ├──→ factor-compute scripts    (L1 Skill)
  ├──→ signal-generator scripts  (L1 Skill)
  ├──→ risk-control scripts      (L1 Skill)
  ├──→ submit_orders → check A-share rules
  ├──→ record transition to MemoryStore
  │
  ▼
SimulationResult (final_nav, nav_curve, trades_log)
  │
  ▼
meta-strategist records experiment → reflects → generates next hypothesis
```

### Direct Agent Usage (Non-Meta)

```
User (CLI / slash command)
  │
  ▼
Agent Layer (L2) — parses intent, orchestrates workflow
  │
  ▼
Skill Layer (L1) — domain knowledge + executable scripts
  │
  ▼
Connector Layer (L0) — MCP data access
  ├──→ AKShare (localhost:8000)     — real-time quotes, northbound flow
  ├──→ Tushare (localhost:8001)     — financials, index weights
  └──→ Internal Store (localhost:8002) — cache, experiments, transitions
```

## Agent Catalog

| Agent | Directory | Trigger | Description |
|-------|-----------|---------|-------------|
| meta-strategist | `agent-plugins/meta-strategist/` | `/evolve` | Autonomous strategy exploration, simulation-driven evolution |
| equity-researcher | `agent-plugins/equity-researcher/` | `/screen`, `/research` | Stock screening + deep research + valuation |
| strategy-analyst | `agent-plugins/strategy-analyst/` | `/factor`, `/backtest` | Factor research + strategy construction + backtest |
| portfolio-manager | `agent-plugins/portfolio-manager/` | `/optimize` | Portfolio optimization + risk management |
| market-monitor | `agent-plugins/market-monitor/` | `/market` | Market breadth + northbound flow + regime detection |

## Skill Catalog

Skills are grouped by domain vertical under `plugins/vertical-plugins/<vertical>/skills/`.

### market-data (Core Layer)

| Skill | Scripts | Description |
|-------|---------|-------------|
| data-fetch | ✓ `fetch_data.py` | Unified data fetching (routes to AKShare/Tushare) |
| factor-compute | ✓ `compute_factors.py`, `preprocess.py`, `neutralize.py` | Factor calculation engine (MAD → ZScore → neutralization) |
| factor-library | — | Factor formula reference (momentum, value, quality, volatility...) |
| data-preprocess | ✓ `filter_stocks.py` | ST/suspended/newly-listed/limit filter |
| factor-mining | ✓ `mine_factors.py`, `gp_engine.py`, `operators.py`, `fitness.py`, `factor_library.py` | Automatic factor discovery via LLM-directed GP evolution |

### equity-research

| Skill | Scripts | Description |
|-------|---------|-------------|
| financial-analysis | ✓ `parse_financials.py` | Financial report parsing, key metric extraction |
| valuation | — | PE/PB/DCF valuation frameworks |
| thesis-tracker | — | Investment thesis tracking |
| sector-overview | — | Industry landscape analysis |

### trading-strategy

| Skill | Scripts | Description |
|-------|---------|-------------|
| backtest-engine | ✓ `run_backtest.py`, `engine.py`, `performance.py`, `cost_model.py` | Backtest execution engine |
| signal-generator | ✓ `generate_signals.py` | Multi-factor scoring → ranking → portfolio construction |
| risk-control | ✓ `risk_rules.py` | Stop-loss, take-profit, position sizing |
| strategy-templates | — | Strategy template library (momentum, mean-reversion, multi-factor...) |

### simulation

| Skill | Scripts | Description |
|-------|---------|-------------|
| trading-simulator | ✓ `simulator.py`, `market_rules.py`, `run_simulation.py` | A-share trading sandbox (T+1, limits, costs) |
| experiment-tracker | ✓ `track_experiment.py` | Experiment recording + lineage management |
| evolution-loop | ✓ `evolution.py` | Iteration control, doom loop detection |
| script-generator | ✓ `generate_factor_script.py`, `generate_strategy_script.py` | Generate Python factor/strategy scripts |
| agent-modifier | ✓ `modify_agent.py` | Modify agent plugin.json + guardrails (self-mod blocked) |
| mcp-tool-adder | ✓ `add_mcp_tool.py` | Add MCP tools to internal-store (R6 enforcement) |

### market-monitor

| Skill | Scripts | Description |
|-------|---------|-------------|
| market-breadth | — | Market breadth indicators |
| northbound-monitor | — | Northbound capital flow monitoring |

## Connector Catalog

| Server | URL | Transport | Auth | Data |
|--------|-----|-----------|------|------|
| AKShare | `localhost:8000/mcp` | HTTP (FastMCP) | None | Real-time quotes, OHLCV, northbound flow, dragon-tiger, Shenwan classification |
| Tushare | `localhost:8001/mcp` | HTTP (FastMCP) | Token (`TUSHARE_TOKEN`) | Financial statements, index weights (point-in-time), concept sectors |
| Internal Store | `localhost:8002/mcp` | HTTP (FastMCP) | None | Cache, experiments, transitions, episode summaries, portfolio state |
| Qlib | `localhost:8003/mcp` | HTTP (FastMCP) | None | Factor expression evaluation, operator catalog, A-share data via Qlib |

### Internal Store Schema

```
SQLite tables:
├── query_cache            # API response cache (TTL-based)
├── backtest_results       # Backtest outputs
├── portfolio              # Portfolio state
├── experiments            # Experiment records (hypothesis, params, result, lineage)
├── transitions            # RL transitions (state, strategy, reward, next_state)
└── episode_summaries      # Simulation run summaries (period, capital, final_nav)
```

## Common Commands

```bash
# Environment (managed by uv)
uv sync                                           # Install all dependencies
uv run python scripts/check.py                    # Verify environment + boundary rules
uv run python scripts/validate.py                 # Validate plugin structure
uv run python scripts/sync-agent-skills.py        # Sync skills into agent dirs
uv run python scripts/sync-agent-skills.py --check # Check sync status

# MCP Servers
uv run uvicorn mcp-servers.akshare-server.server:mcp_app --port 8000
TUSHARE_TOKEN=xxx uv run uvicorn mcp-servers.tushare-server.server:mcp_app --port 8001
uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002

# Code quality
uv run ruff check .
uv run ruff format .

# Testing
uv run pytest                    # Unit tests
uv run pytest -m integration     # Integration tests (MCP servers must be running)
uv run pytest -m e2e             # End-to-end tests

# Notebooks
uv run jupyter lab notebooks/
```

## Implementation Phases

| Phase | Content | Deliverables |
|-------|---------|--------------|
| **Phase 1** | Base restructure | 4 vertical plugins, skill script migration, agent redefinition, cleanup stale refs |
| **Phase 2** | Trading Simulator | Simulation engine + A-share rules + Memory Store + Experiment Store |
| **Phase 3** | Meta-Agent Phase 1 | meta-strategist parameter search + Evolution Loop + Doom Loop |
| **Phase 4** | Jupyter Notebooks | 4 visualization notebooks |
| **Phase 5** | Meta-Agent Phase 2 | Code generation (write new factor/strategy Python scripts) |
| **Phase 6** | Meta-Agent Phase 3 | System self-evolution (modify Agent definitions, add MCP tools) |
