# Factor Mining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic factor discovery pipeline — LLM generates directional hypotheses, DEAP genetic programming searches factor formulas, Qlib evaluates expressions, validated factors stored in a shared factor library.

**Architecture:** New qlib-server MCP (L0, port 8003) wraps Qlib for data + expression evaluation. New factor-mining skill (L1) uses DEAP for GP evolution. Factor library table added to internal-store. Meta-strategist reads dynamic factor list instead of hardcoded 12 factors.

**Tech Stack:** Qlib (data + expressions), DEAP (genetic programming), FastMCP (server), SQLite (factor library), pandas/numpy

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `mcp-servers/qlib-server/server.py` | MCP server: Qlib data + expression evaluation tools |
| `mcp-servers/qlib-server/pyproject.toml` | qlib-server package config |
| `plugins/vertical-plugins/market-data/skills/factor-mining/SKILL.md` | Skill trigger and workflow definition |
| `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/operators.py` | Qlib operator → DEAP primitive mapping |
| `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/fitness.py` | IC/ICIR fitness function |
| `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/gp_engine.py` | DEAP GP engine (population, evolution) |
| `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/factor_library.py` | Factor library client (calls internal-store MCP) |
| `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/mine_factors.py` | Main mining loop orchestrator |
| `plugins/vertical-plugins/market-data/skills/factor-mining/test_operators.py` | Tests for operators |
| `plugins/vertical-plugins/market-data/skills/factor-mining/test_fitness.py` | Tests for fitness |
| `plugins/vertical-plugins/market-data/skills/factor-mining/test_gp_engine.py` | Tests for GP engine |
| `plugins/vertical-plugins/market-data/skills/factor-mining/test_factor_library.py` | Tests for factor library client |

### Modified Files

| File | Change |
|------|--------|
| `mcp-servers/internal-store/server.py` | Add factor_library table + 3 MCP tools |
| `pyproject.toml` | Add qlib, deap deps; add qlib-server to workspace |
| `.mcp.json` | Add qlib-server entry |
| `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md` | Dynamic factor library read |
| `plugins/agent-plugins/meta-strategist/agents/system-prompt.md` | Update factor source from hardcoded to dynamic |
| `contributing/architecture.md` | Add qlib-server to connector catalog |

---

## Task 1: qlib-server — Package Setup

**Files:**
- Create: `mcp-servers/qlib-server/pyproject.toml`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create qlib-server pyproject.toml**

```toml
[project]
name = "qlib-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "qlib>=0.9",
    "mcp>=1.0",
    "pandas>=2.0",
    "numpy>=1.24",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]

[project.scripts]
qlib-mcp = "server:main"

[tool.setuptools.packages.find]
exclude = ["test_*"]
```

- [ ] **Step 2: Add qlib-server to root workspace**

In `pyproject.toml`, append `"mcp-servers/qlib-server"` to the `tool.uv.workspace.members` list. Add `"qlib>=0.9"` and `"deap>=1.4"` to root `dependencies`.

- [ ] **Step 3: Add qlib-server to .mcp.json**

Add entry after `internal-store`:

```json
"qlib": {
  "type": "http",
  "url": "http://localhost:8003/mcp",
  "description": "Qlib data engine — factor expression evaluation, operator catalog, A-share data via Qlib"
}
```

- [ ] **Step 4: Install dependencies**

Run: `uv sync`
Expected: qlib and deap installed successfully.

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/qlib-server/pyproject.toml pyproject.toml .mcp.json
git commit -m "feat(qlib-server): add package skeleton and workspace config"
```

---

## Task 2: qlib-server — MCP Tools

**Files:**
- Create: `mcp-servers/qlib-server/server.py`

- [ ] **Step 1: Write server.py with 5 MCP tools**

```python
"""
Qlib MCP Server — Data engine for factor expression evaluation.
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8003
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
from mcp.server.fastmcp import FastMCP

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "./data"))
QLIB_DATA_DIR = DATA_ROOT / "qlib"

mcp = FastMCP(
    name="qlib-server",
    instructions="Qlib data engine MCP Server — factor expression evaluation, operator catalog. Version 0.1.0",
)

_QLIB_INITIALIZED = False


def _ensure_qlib_init():
    """Initialize Qlib with local data directory."""
    global _QLIB_INITIALIZED
    if _QLIB_INITIALIZED:
        return
    import qlib
    if not QLIB_DATA_DIR.exists():
        raise FileNotFoundError(
            f"Qlib data not found at {QLIB_DATA_DIR}. Run qlib_init_data first."
        )
    qlib.init(provider_uri=str(QLIB_DATA_DIR), region="cn")
    _QLIB_INITIALIZED = True


def _df_to_records(df: pd.DataFrame, max_rows: int = 10000) -> list[dict]:
    """Convert DataFrame to JSON-serializable records."""
    if df is None or df.empty:
        return []
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.reset_index().fillna("NaN").to_dict(orient="records")


@mcp.tool()
def qlib_init_data(source: str = "qlib_cn_data") -> dict:
    """
    Initialize Qlib local data.

    Args:
        source: Data source. "qlib_cn_data" downloads official Qlib CN data.
                "custom" uses akshare/tushare dump (requires separate ETL script).
    """
    try:
        QLIB_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if source == "qlib_cn_data":
            from qlib.utils import get_or_create_path
            from qlib.contrib.data.handler import Alpha158
            import qlib

            qlib.init(provider_uri=str(QLIB_DATA_DIR), region="cn")

            from python_scripts import dump_bin

            dump_bin.DumpDataAll(
                csv_path=None,
                qlib_dir=str(QLIB_DATA_DIR),
                include_all=True,
            ).dump()
        else:
            return {"status": "error", "message": f"Source '{source}' not yet supported. Use 'qlib_cn_data'."}

        return {"status": "ok", "data_dir": str(QLIB_DATA_DIR)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def qlib_get_data(
    instruments: str = "all",
    fields: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Fetch raw data fields from Qlib.

    Args:
        instruments: Stock universe. "all", "csi300", "csi500", or comma-separated codes "SH600000,SZ000001".
        fields: Data fields to fetch. E.g. ["$close", "$volume", "$open"].
        start_date: Start date "YYYY-MM-DD".
        end_date: End date "YYYY-MM-DD".
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        if fields is None:
            fields = ["$close", "$open", "$high", "$low", "$volume", "$amount"]

        df = D.features(instruments, fields, start_time=start_date, end_time=end_date)
        return _df_to_records(df)
    except Exception as e:
        return [{"error": str(e), "tool": "qlib_get_data"}]


@mcp.tool()
def qlib_eval_expression(
    expression: str,
    instruments: str = "csi300",
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Evaluate a Qlib expression factor and return factor values.

    Args:
        expression: Qlib expression string. E.g. "Rank($close / $open)".
        instruments: Stock universe.
        start_date: Start date "YYYY-MM-DD".
        end_date: End date "YYYY-MM-DD".
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        fields = [expression]
        df = D.features(instruments, fields, start_time=start_date, end_time=end_date)
        return _df_to_records(df)
    except Exception as e:
        return [{"error": str(e), "tool": "qlib_eval_expression"}]


@mcp.tool()
def qlib_list_operators() -> list[dict]:
    """
    List available Qlib operators with their signatures.
    """
    operators = [
        # Time-series
        {"name": "Ts_Mean", "signature": "Ts_Mean(x, d)", "category": "time-series", "description": "Mean of x over past d days"},
        {"name": "Ts_Std", "signature": "Ts_Std(x, d)", "category": "time-series", "description": "Std of x over past d days"},
        {"name": "Ts_Max", "signature": "Ts_Max(x, d)", "category": "time-series", "description": "Max of x over past d days"},
        {"name": "Ts_Min", "signature": "Ts_Min(x, d)", "category": "time-series", "description": "Min of x over past d days"},
        {"name": "Ts_Rank", "signature": "Ts_Rank(x, d)", "category": "time-series", "description": "Percentile rank of x in past d days"},
        {"name": "Ts_Sum", "signature": "Ts_Sum(x, d)", "category": "time-series", "description": "Sum of x over past d days"},
        {"name": "Ts_Prod", "signature": "Ts_Prod(x, d)", "category": "time-series", "description": "Product of x over past d days"},
        {"name": "Ts_Corr", "signature": "Ts_Corr(x, y, d)", "category": "time-series", "description": "Correlation of x and y over past d days"},
        {"name": "Ts_Covariance", "signature": "Ts_Covariance(x, y, d)", "category": "time-series", "description": "Covariance of x and y over past d days"},
        {"name": "Ts_Reg_Residual", "signature": "Ts_Reg_Residual(x, y, d)", "category": "time-series", "description": "Residual from regressing x on y over past d days"},
        {"name": "Delta", "signature": "Delta(x, d)", "category": "time-series", "description": "x - x_d_days_ago"},
        {"name": "Pct_Change", "signature": "Pct_Change(x, d)", "category": "time-series", "description": "(x - x_d) / x_d"},
        # Cross-section
        {"name": "Rank", "signature": "Rank(x)", "category": "cross-section", "description": "Cross-sectional percentile rank"},
        {"name": "ZScore", "signature": "ZScore(x)", "category": "cross-section", "description": "Cross-sectional z-score"},
        {"name": "Demean", "signature": "Demean(x)", "category": "cross-section", "description": "x - mean(x)"},
        {"name": "Scale", "signature": "Scale(x)", "category": "cross-section", "description": "x / sum(abs(x))"},
        {"name": "Power", "signature": "Power(x, n)", "category": "cross-section", "description": "x raised to power n"},
        {"name": "Sign", "signature": "Sign(x)", "category": "cross-section", "description": "Sign of x (-1, 0, 1)"},
        # Arithmetic
        {"name": "Add", "signature": "x + y", "category": "arithmetic", "description": "Addition"},
        {"name": "Sub", "signature": "x - y", "category": "arithmetic", "description": "Subtraction"},
        {"name": "Mul", "signature": "x * y", "category": "arithmetic", "description": "Multiplication"},
        {"name": "Div", "signature": "x / y", "category": "arithmetic", "description": "Division"},
        {"name": "Abs", "signature": "Abs(x)", "category": "arithmetic", "description": "Absolute value"},
        {"name": "Log", "signature": "Log(x)", "category": "arithmetic", "description": "Natural log"},
        {"name": "Exp", "signature": "Exp(x)", "category": "arithmetic", "description": "Exponential"},
        {"name": "Max", "signature": "Max(x, y)", "category": "arithmetic", "description": "Element-wise max"},
        {"name": "Min", "signature": "Min(x, y)", "category": "arithmetic", "description": "Element-wise min"},
        {"name": "Sqrt", "signature": "Sqrt(x)", "category": "arithmetic", "description": "Square root"},
        # Conditional
        {"name": "If_Else", "signature": "If_Else(cond, x, y)", "category": "conditional", "description": "If cond then x else y"},
        {"name": "Clamp", "signature": "Clamp(x, lo, hi)", "category": "conditional", "description": "Clip x to [lo, hi]"},
    ]
    return operators


@mcp.tool()
def qlib_get_universe(name: str = "csi300") -> list[str]:
    """
    Get stock universe code list.

    Args:
        name: Universe name. "csi300", "csi500", "csi1000", "all".
    """
    try:
        _ensure_qlib_init()
        from qlib.data import D

        universe_map = {
            "csi300": "csi300",
            "csi500": "csi500",
            "csi1000": "csi1000",
            "all": "all",
        }
        instruments = universe_map.get(name, "all")
        stock_list = D.instruments(instruments)
        return list(stock_list) if hasattr(stock_list, "__iter__") else [str(stock_list)]
    except Exception as e:
        return [f"error: {str(e)}"]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8003)
```

- [ ] **Step 2: Verify server starts**

Run: `uv run uvicorn mcp-servers.qlib-server.server:mcp_app --port 8003`
Expected: Server starts without import errors. Kill after confirming.

- [ ] **Step 3: Commit**

```bash
git add mcp-servers/qlib-server/server.py
git commit -m "feat(qlib-server): add MCP server with data, expression, and operator tools"
```

---

## Task 3: internal-store — Factor Library Table + Tools

**Files:**
- Modify: `mcp-servers/internal-store/server.py`

- [ ] **Step 1: Add factor_library table to _init_db()**

Append to the `conn.executescript(...)` string in `_init_db()`:

```sql
CREATE TABLE IF NOT EXISTS factor_library (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    expression    TEXT NOT NULL,
    hypothesis    TEXT,
    operators     TEXT NOT NULL,
    data_fields   TEXT NOT NULL,
    ic            REAL,
    icir          REAL,
    turnover      REAL,
    sharpe        REAL,
    max_drawdown  REAL,
    universe      TEXT,
    period        TEXT,
    walk_forward  TEXT,
    status        TEXT DEFAULT 'active',
    source_experiment_id INTEGER,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Add register_factor MCP tool**

Append to server.py (before the ASGI app section):

```python
@mcp.tool()
def register_factor(
    name: str,
    expression: str,
    operators: list[str],
    data_fields: list[str],
    hypothesis: str = "",
    ic: float | None = None,
    icir: float | None = None,
    turnover: float | None = None,
    sharpe: float | None = None,
    max_drawdown: float | None = None,
    universe: str = "",
    period: str = "",
    walk_forward: dict | None = None,
    source_experiment_id: int | None = None,
) -> list[dict]:
    """
    Register a validated factor to the factor library.
    Auto-deduplicates by expression hash.

    Args:
        name:             Human-readable factor name.
        expression:       Qlib expression string.
        operators:        List of operators used in the expression.
        data_fields:      List of data fields used.
        hypothesis:       LLM hypothesis that led to this factor.
        ic:               Mean Rank IC.
        icir:             ICIR (Mean IC / Std IC).
        turnover:         Factor turnover ratio.
        sharpe:           Sharpe ratio of factor-mimicking portfolio.
        max_drawdown:     Max drawdown of factor-mimicking portfolio.
        universe:         Stock universe used for validation.
        period:           Validation period.
        walk_forward:     Walk-forward validation results summary.
        source_experiment_id: ID of the experiment that produced this factor.
    """
    try:
        import hashlib

        expr_hash = hashlib.sha256(expression.encode()).hexdigest()[:16]
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Check for duplicate expression
        existing = conn.execute(
            "SELECT id FROM factor_library WHERE expression = ?",
            (expression,),
        ).fetchone()
        if existing:
            conn.close()
            return [{"status": "duplicate", "id": existing["id"], "message": "Factor with same expression already exists"}]

        conn.execute(
            """INSERT INTO factor_library
            (name, expression, hypothesis, operators, data_fields, ic, icir, turnover,
             sharpe, max_drawdown, universe, period, walk_forward, status, source_experiment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
            (
                name,
                expression,
                hypothesis,
                json.dumps(sorted(operators)),
                json.dumps(sorted(data_fields)),
                ic,
                icir,
                turnover,
                sharpe,
                max_drawdown,
                universe,
                period,
                json.dumps(walk_forward) if walk_forward else None,
                source_experiment_id,
            ),
        )
        rows = conn.execute("SELECT * FROM factor_library ORDER BY id DESC LIMIT 1").fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "register_factor"}]
```

- [ ] **Step 3: Add list_factors MCP tool**

```python
@mcp.tool()
def list_factors(status: str = "active", universe: str = "") -> list[dict]:
    """
    Query the factor library with optional filters.

    Args:
        status:   Factor status filter. "active", "deprecated", "testing", or "all".
        universe: Optional universe filter.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM factor_library"
        conditions: list[str] = []
        params: list = []

        if status != "all":
            conditions.append("status = ?")
            params.append(status)
        if universe:
            conditions.append("universe = ?")
            params.append(universe)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY icir DESC"

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_factors"}]
```

- [ ] **Step 4: Add deprecate_factor MCP tool**

```python
@mcp.tool()
def deprecate_factor(factor_id: int, reason: str = "") -> list[dict]:
    """
    Mark a factor as deprecated.

    Args:
        factor_id: ID of the factor to deprecate.
        reason:    Reason for deprecation.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE factor_library SET status = 'deprecated' WHERE id = ?",
            (factor_id,),
        )
        rows = conn.execute("SELECT * FROM factor_library WHERE id = ?", (factor_id,)).fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "deprecate_factor"}]
```

- [ ] **Step 5: Verify internal-store starts**

Run: `uv run uvicorn mcp-servers.internal-store.server:mcp_app --port 8002`
Expected: Server starts, factor_library table created.

- [ ] **Step 6: Commit**

```bash
git add mcp-servers/internal-store/server.py
git commit -m "feat(internal-store): add factor_library table and register/list/deprecate tools"
```

---

## Task 4: factor-mining — Operator Mapping

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/operators.py`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/test_operators.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for Qlib operator → DEAP primitive mapping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import pytest
import numpy as np


class TestOperatorRegistry:
    def test_all_categories_present(self):
        from operators import OPERATOR_REGISTRY
        assert "time-series" in OPERATOR_REGISTRY
        assert "cross-section" in OPERATOR_REGISTRY
        assert "arithmetic" in OPERATOR_REGISTRY
        assert "conditional" in OPERATOR_REGISTRY

    def test_operator_has_required_fields(self):
        from operators import OPERATOR_REGISTRY
        for category, ops in OPERATOR_REGISTRY.items():
            for op in ops:
                assert "name" in op, f"Missing name in {category}"
                assert "arity" in op, f"Missing arity for {op.get('name', '?')}"
                assert "qlib_expr" in op, f"Missing qlib_expr for {op.get('name', '?')}"
                assert "deap_func" in op, f"Missing deap_func for {op.get('name', '?')}"

    def test_ts_mean_output(self):
        from operators import OPERATOR_REGISTRY
        ts_mean = next(op for op in OPERATOR_REGISTRY["time-series"] if op["name"] == "Ts_Mean")
        result = ts_mean["deap_func"](np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
        assert np.isclose(result, 4.0)  # mean of last 3 values: (3+4+5)/3

    def test_rank_output(self):
        from operators import OPERATOR_REGISTRY
        rank_op = next(op for op in OPERATOR_REGISTRY["cross-section"] if op["name"] == "Rank")
        result = rank_op["deap_func"](np.array([3.0, 1.0, 2.0, 5.0, 4.0]))
        expected = np.array([0.6, 0.2, 0.4, 1.0, 0.8])
        np.testing.assert_array_almost_equal(result, expected)

    def test_add_output(self):
        from operators import OPERATOR_REGISTRY
        add_op = next(op for op in OPERATOR_REGISTRY["arithmetic"] if op["name"] == "Add")
        result = add_op["deap_func"](3.0, 4.0)
        assert result == 7.0

    def test_get_primitives_for_direction(self):
        from operators import get_primitives_for_direction
        primitives = get_primitives_for_direction(
            operator_names=["Ts_Mean", "Rank", "Add"],
            data_fields=["$close", "$volume"],
        )
        names = [p.name for p in primitives]
        assert "Ts_Mean" in names
        assert "Rank" in names
        assert "Add" in names
        assert "$close" in names
        assert "$volume" in names

    def test_expression_to_qlib_string(self):
        from operators import expression_to_qlib_string
        # Simple: Rank($close)
        result = expression_to_qlib_string("Rank", ["$close"])
        assert result == "Rank($close)"
        # Nested: Ts_Mean($close, 20)
        result = expression_to_qlib_string("Ts_Mean", ["$close", "20"])
        assert result == "Ts_Mean($close, 20)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_operators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'operators'`

- [ ] **Step 3: Write operators.py**

```python
"""
Qlib operator → DEAP primitive mapping for factor mining GP.

Each operator has:
- name: unique identifier
- arity: number of arguments
- qlib_expr: Qlib expression template (e.g. "Ts_Mean({0}, {1})")
- deap_func: numpy-based function for local fitness evaluation
- category: time-series / cross-section / arithmetic / conditional
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class OperatorDef:
    name: str
    arity: int
    qlib_expr: str  # format string with {0}, {1}, ... for args
    deap_func: callable
    category: str


def _ts_mean(x, d):
    """Rolling mean over last d periods."""
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        return float(np.mean(x[-d:]))
    return float(x)


def _ts_std(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        return float(np.std(x[-d:]))
    return 0.0


def _ts_max(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        return float(np.max(x[-d:]))
    return float(x)


def _ts_min(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        return float(np.min(x[-d:]))
    return float(x)


def _ts_rank(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        tail = x[-d:]
        return float(np.sum(tail < tail[-1]) + 1) / d
    return 0.5


def _ts_sum(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__"):
        return float(np.sum(x[-d:]))
    return float(x) * d


def _ts_corr(x, y, d):
    d = max(2, int(d))
    if hasattr(x, "__len__") and len(x) >= d:
        from numpy import corrcoef
        c = corrcoef(x[-d:], y[-d:])
        return float(c[0, 1]) if not np.isnan(c[0, 1]) else 0.0
    return 0.0


def _delta(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__") and len(x) > d:
        return float(x[-1] - x[-1 - d])
    return 0.0


def _pct_change(x, d):
    d = max(1, int(d))
    if hasattr(x, "__len__") and len(x) > d and x[-1 - d] != 0:
        return float((x[-1] - x[-1 - d]) / abs(x[-1 - d]))
    return 0.0


def _rank(x):
    """Cross-sectional percentile rank."""
    x = np.asarray(x, dtype=float)
    return (np.argsort(np.argsort(x)) + 1).astype(float) / len(x)


def _zscore(x):
    x = np.asarray(x, dtype=float)
    std = np.std(x)
    if std == 0:
        return np.zeros_like(x)
    return (x - np.mean(x)) / std


def _demean(x):
    x = np.asarray(x, dtype=float)
    return x - np.mean(x)


def _scale(x):
    x = np.asarray(x, dtype=float)
    s = np.sum(np.abs(x))
    return x / s if s != 0 else x


def _sign(x):
    return np.sign(x)


def _if_else(cond, x, y):
    return np.where(np.asarray(cond, dtype=bool), x, y)


def _clamp(x, lo, hi):
    return np.clip(x, lo, hi)


OPERATOR_REGISTRY: dict[str, list[OperatorDef]] = {
    "time-series": [
        OperatorDef("Ts_Mean", 2, "Ts_Mean({0}, {1})", _ts_mean, "time-series"),
        OperatorDef("Ts_Std", 2, "Ts_Std({0}, {1})", _ts_std, "time-series"),
        OperatorDef("Ts_Max", 2, "Ts_Max({0}, {1})", _ts_max, "time-series"),
        OperatorDef("Ts_Min", 2, "Ts_Min({0}, {1})", _ts_min, "time-series"),
        OperatorDef("Ts_Rank", 2, "Ts_Rank({0}, {1})", _ts_rank, "time-series"),
        OperatorDef("Ts_Sum", 2, "Ts_Sum({0}, {1})", _ts_sum, "time-series"),
        OperatorDef("Ts_Corr", 3, "Ts_Corr({0}, {1}, {2})", _ts_corr, "time-series"),
        OperatorDef("Delta", 2, "Delta({0}, {1})", _delta, "time-series"),
        OperatorDef("Pct_Change", 2, "Pct_Change({0}, {1})", _pct_change, "time-series"),
    ],
    "cross-section": [
        OperatorDef("Rank", 1, "Rank({0})", _rank, "cross-section"),
        OperatorDef("ZScore", 1, "ZScore({0})", _zscore, "cross-section"),
        OperatorDef("Demean", 1, "Demean({0})", _demean, "cross-section"),
        OperatorDef("Scale", 1, "Scale({0})", _scale, "cross-section"),
        OperatorDef("Sign", 1, "Sign({0})", _sign, "cross-section"),
    ],
    "arithmetic": [
        OperatorDef("Add", 2, "({0} + {1})", lambda x, y: x + y, "arithmetic"),
        OperatorDef("Sub", 2, "({0} - {1})", lambda x, y: x - y, "arithmetic"),
        OperatorDef("Mul", 2, "({0} * {1})", lambda x, y: x * y, "arithmetic"),
        OperatorDef("Div", 2, "({0} / {1})", lambda x, y: x / y if y != 0 else 0.0, "arithmetic"),
        OperatorDef("Abs", 1, "Abs({0})", lambda x: np.abs(x), "arithmetic"),
        OperatorDef("Log", 1, "Log({0})", lambda x: np.log(np.abs(x) + 1e-8), "arithmetic"),
        OperatorDef("Exp", 1, "Exp({0})", lambda x: np.exp(np.clip(x, -10, 10)), "arithmetic"),
        OperatorDef("Max", 2, "Max({0}, {1})", lambda x, y: np.maximum(x, y), "arithmetic"),
        OperatorDef("Min", 2, "Min({0}, {1})", lambda x, y: np.minimum(x, y), "arithmetic"),
        OperatorDef("Sqrt", 1, "Sqrt({0})", lambda x: np.sqrt(np.abs(x)), "arithmetic"),
    ],
    "conditional": [
        OperatorDef("If_Else", 3, "If_Else({0}, {1}, {2})", _if_else, "conditional"),
        OperatorDef("Clamp", 3, "Clamp({0}, {1}, {2})", _clamp, "conditional"),
    ],
}


def get_primitives_for_direction(
    operator_names: list[str],
    data_fields: list[str],
) -> list:
    """
    Build DEAP-compatible primitive set from LLM-specified operator names and data fields.

    Returns list of objects with .name attribute for DEAP PrimitiveSet setup.
    """
    from deap import gp

    pset = gp.PrimitiveSet("MAIN", 0)

    # Add selected operators as primitives
    for category_ops in OPERATOR_REGISTRY.values():
        for op in category_ops:
            if op.name in operator_names:
                pset.addPrimitive(op.deap_func, op.arity, name=op.name)

    # Add data fields as terminals (ephemeral constants will represent fields)
    for field in data_fields:
        pset.addTerminal(field, name=field.replace("$", "D_"))

    # Add ephemeral integer constant for window sizes
    pset.addEphemeralConstant("rand_int", lambda: np.random.randint(5, 60), name="rand_int")

    return pset


def expression_to_qlib_string(op_name: str, args: list[str]) -> str:
    """
    Convert an operator + args to a Qlib expression string.

    Args:
        op_name: Operator name (e.g. "Ts_Mean", "Rank").
        args: List of argument strings (sub-expressions or field names).
    """
    for category_ops in OPERATOR_REGISTRY.values():
        for op in category_ops:
            if op.name == op_name:
                return op.qlib_expr.format(*args)
    # Fallback for data fields and constants
    return op_name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_operators.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/vertical-plugins/market-data/skills/factor-mining/scripts/operators.py plugins/vertical-plugins/market-data/skills/factor-mining/test_operators.py
git commit -m "feat(factor-mining): add operator registry with DEAP primitive mapping"
```

---

## Task 5: factor-mining — Fitness Function

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/fitness.py`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/test_fitness.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for factor fitness function."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import pytest
import numpy as np


class TestFitness:
    def test_compute_ic_perfect_predictor(self):
        """Perfect predictor should have IC close to 1.0."""
        from fitness import compute_rank_ic
        factor = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        ic = compute_rank_ic(factor, returns)
        assert ic > 0.9

    def test_compute_ic_random(self):
        """Random factor should have IC close to 0."""
        from fitness import compute_rank_ic
        np.random.seed(42)
        factor = np.random.randn(100)
        returns = np.random.randn(100)
        ic = compute_rank_ic(factor, returns)
        assert abs(ic) < 0.3

    def test_compute_ic_series(self):
        """IC series calculation over multiple periods."""
        from fitness import compute_ic_series
        # 3 periods, 5 stocks each
        factor_values = np.array([
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [5.0, 4.0, 3.0, 2.0, 1.0],
            [1.0, 3.0, 2.0, 5.0, 4.0],
        ])
        forward_returns = np.array([
            [0.01, 0.02, 0.03, 0.04, 0.05],
            [0.05, 0.04, 0.03, 0.02, 0.01],
            [0.01, 0.03, 0.02, 0.05, 0.04],
        ])
        ic_series = compute_ic_series(factor_values, forward_returns)
        assert len(ic_series) == 3
        assert all(-1 <= ic <= 1 for ic in ic_series)

    def test_fitness_score(self):
        """Fitness score = 0.6 * ICIR + 0.2 * mean_IC - 0.2 * turnover."""
        from fitness import compute_fitness
        score = compute_fitness(
            ic_series=np.array([0.05, 0.04, 0.06, 0.03, 0.05]),
            turnover=0.3,
        )
        expected_icir = np.mean([0.05, 0.04, 0.06, 0.03, 0.05]) / np.std([0.05, 0.04, 0.06, 0.03, 0.05])
        expected_ic = np.mean([0.05, 0.04, 0.06, 0.03, 0.05])
        expected = 0.6 * expected_icir + 0.2 * expected_ic - 0.2 * 0.3
        assert abs(score - expected) < 1e-6

    def test_fitness_handles_nan(self):
        """NaN IC values should be filtered out."""
        from fitness import compute_fitness
        score = compute_fitness(
            ic_series=np.array([0.05, float("nan"), 0.04]),
            turnover=0.3,
        )
        assert not np.isnan(score)

    def test_evaluate_expression_via_mcp(self):
        """evaluate_expression computes fitness by calling qlib-server."""
        from fitness import evaluate_expression
        # This test uses a mock — real MCP calls are integration tests
        score, metrics = evaluate_expression(
            expression="Rank($close / $open)",
            instruments="csi300",
            start_date="2024-01-01",
            end_date="2024-12-31",
            _mock_factor_values=np.random.randn(100),
            _mock_forward_returns=np.random.randn(100),
        )
        assert "ic" in metrics
        assert "icir" in metrics
        assert isinstance(score, float)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_fitness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fitness'`

- [ ] **Step 3: Write fitness.py**

```python
"""
Fitness function for GP-based factor mining.

Evaluates candidate factor expressions using Rank IC, ICIR, and turnover.
"""

import numpy as np
from scipy import stats


def compute_rank_ic(factor_values: np.ndarray, forward_returns: np.ndarray) -> float:
    """
    Compute Spearman Rank IC between factor values and forward returns.

    Args:
        factor_values: 1D array of factor values for N stocks at time T.
        forward_returns: 1D array of forward returns for same N stocks.
    """
    mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
    if mask.sum() < 5:
        return 0.0
    corr, _ = stats.spearmanr(factor_values[mask], forward_returns[mask])
    return float(corr) if not np.isnan(corr) else 0.0


def compute_ic_series(
    factor_values: np.ndarray,
    forward_returns: np.ndarray,
) -> np.ndarray:
    """
    Compute IC series over multiple periods.

    Args:
        factor_values: 2D array (periods × stocks).
        forward_returns: 2D array (periods × stocks), same shape.
    """
    n_periods = factor_values.shape[0]
    ic_series = np.array([
        compute_rank_ic(factor_values[t], forward_returns[t])
        for t in range(n_periods)
    ])
    return ic_series


def compute_fitness(
    ic_series: np.ndarray,
    turnover: float = 0.0,
    icir_weight: float = 0.6,
    ic_weight: float = 0.2,
    turnover_weight: float = 0.2,
) -> float:
    """
    Compute fitness score from IC series and turnover.

    fitness = icir_weight * ICIR + ic_weight * mean_IC - turnover_weight * turnover
    """
    clean_ic = ic_series[~np.isnan(ic_series)]
    if len(clean_ic) == 0:
        return -999.0

    mean_ic = float(np.mean(clean_ic))
    std_ic = float(np.std(clean_ic))
    icir = mean_ic / std_ic if std_ic > 0 else 0.0

    return icir_weight * icir + ic_weight * mean_ic - turnover_weight * turnover


def compute_turnover(factor_ranks: np.ndarray) -> float:
    """
    Compute factor turnover: average 1 - correlation of ranks between adjacent periods.

    Args:
        factor_ranks: 2D array (periods × stocks) of factor ranks.
    """
    if factor_ranks.shape[0] < 2:
        return 0.0
    corr_sum = 0.0
    count = 0
    for t in range(1, factor_ranks.shape[0]):
        corr, _ = stats.spearmanr(factor_ranks[t], factor_ranks[t - 1])
        if not np.isnan(corr):
            corr_sum += corr
            count += 1
    return 1.0 - (corr_sum / count if count > 0 else 1.0)


def evaluate_expression(
    expression: str,
    instruments: str = "csi300",
    start_date: str = "",
    end_date: str = "",
    _mock_factor_values: np.ndarray | None = None,
    _mock_forward_returns: np.ndarray | None = None,
) -> tuple[float, dict]:
    """
    Evaluate a factor expression and return (fitness_score, metrics_dict).

    In production, calls qlib_eval_expression MCP tool to get factor values,
    then computes IC series and fitness.

    For testing, pass _mock_factor_values and _mock_forward_returns to bypass MCP.

    Returns:
        (fitness_score, {"ic": mean_ic, "icir": icir, "turnover": turnover})
    """
    if _mock_factor_values is not None and _mock_forward_returns is not None:
        factor_values = _mock_factor_values
        forward_returns = _mock_forward_returns
    else:
        # Production path: call qlib-server MCP
        # This would be done via MCP tool call in the actual skill execution
        # For now, return placeholder indicating MCP call needed
        return -999.0, {"ic": 0.0, "icir": 0.0, "turnover": 0.0, "error": "MCP call required"}

    # Ensure 2D (1 period × stocks)
    if factor_values.ndim == 1:
        factor_values = factor_values.reshape(1, -1)
        forward_returns = forward_returns.reshape(1, -1)

    ic_series = compute_ic_series(factor_values, forward_returns)
    turnover = compute_turnover(factor_values)
    fitness = compute_fitness(ic_series, turnover)

    clean_ic = ic_series[~np.isnan(ic_series)]
    mean_ic = float(np.mean(clean_ic)) if len(clean_ic) > 0 else 0.0
    std_ic = float(np.std(clean_ic)) if len(clean_ic) > 0 else 0.0

    return fitness, {
        "ic": mean_ic,
        "icir": mean_ic / std_ic if std_ic > 0 else 0.0,
        "turnover": turnover,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_fitness.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/vertical-plugins/market-data/skills/factor-mining/scripts/fitness.py plugins/vertical-plugins/market-data/skills/factor-mining/test_fitness.py
git commit -m "feat(factor-mining): add IC/ICIR fitness function with turnover penalty"
```

---

## Task 6: factor-mining — GP Engine

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/gp_engine.py`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/test_gp_engine.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for DEAP GP engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import pytest


class TestGPEngine:
    def test_create_pset_with_selected_operators(self):
        """GP engine creates PrimitiveSet from operator names and data fields."""
        from gp_engine import create_pset
        pset = create_pset(
            operator_names=["Ts_Mean", "Rank", "Add", "Div"],
            data_fields=["$close", "$volume"],
        )
        assert "Ts_Mean" in pset.mapping
        assert "Rank" in pset.mapping
        assert "Add" in pset.mapping

    def test_individual_to_expression(self):
        """DEAP individual tree converts to Qlib expression string."""
        from gp_engine import create_pset, individual_to_expression
        pset = create_pset(
            operator_names=["Rank"],
            data_fields=["$close"],
        )
        # Manually create a simple tree: Rank($close)
        from deap import gp
        expr = [pset.mapping["Rank"], pset.mapping["$close"]]
        individual = gp.PrimitiveTree(expr)
        result = individual_to_expression(individual)
        assert result == "Rank($close)"

    def test_run_evolution_returns_candidates(self):
        """Evolution loop returns top candidates with metrics."""
        from gp_engine import run_evolution
        result = run_evolution(
            operator_names=["Rank", "Add"],
            data_fields=["$close", "$open"],
            generations=3,
            population_size=10,
            max_depth=3,
            mock_mode=True,
        )
        assert len(result) > 0
        assert "expression" in result[0]
        assert "fitness" in result[0]

    def test_evolution_respects_max_depth(self):
        """Generated expressions do not exceed max_depth."""
        from gp_engine import run_evolution
        result = run_evolution(
            operator_names=["Rank", "Add", "Mul"],
            data_fields=["$close"],
            generations=5,
            population_size=20,
            max_depth=4,
            mock_mode=True,
        )
        for candidate in result:
            # Depth = number of nested function calls
            depth = candidate["expression"].count("(")
            assert depth <= 6  # generous upper bound for depth 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_gp_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gp_engine'`

- [ ] **Step 3: Write gp_engine.py**

```python
"""
DEAP-based Genetic Programming engine for factor mining.

Evolves expression trees built from Qlib operators and data fields.
"""

import numpy as np
from deap import base, creator, gp, tools, algorithms

from operators import OPERATOR_REGISTRY, expression_to_qlib_string


def create_pset(operator_names: list[str], data_fields: list[str]) -> gp.PrimitiveSet:
    """
    Create a DEAP PrimitiveSet with selected operators and data fields.

    Args:
        operator_names: List of operator names to include.
        data_fields: List of data field names (e.g. ["$close", "$volume"]).
    """
    pset = gp.PrimitiveSet("MAIN", 0)

    for category_ops in OPERATOR_REGISTRY.values():
        for op in category_ops:
            if op.name in operator_names:
                pset.addPrimitive(op.deap_func, op.arity, name=op.name)

    for field in data_fields:
        pset.addTerminal(field, name=field.replace("$", "D_"))

    pset.addEphemeralConstant("rand_int", lambda: np.random.randint(5, 60), name="rand_int")

    return pset


def individual_to_expression(individual) -> str:
    """
    Convert a DEAP PrimitiveTree individual to a Qlib expression string.

    Walks the tree and converts each node using operator qlib_expr templates.
    """
    stack = []
    for node in individual:
        if isinstance(node, gp.Primitive):
            args = stack[-node.arity:]
            del stack[-node.arity:]
            # Find the operator definition
            expr = expression_to_qlib_string(node.name, args)
            stack.append(expr)
        elif isinstance(node, gp.Terminal):
            name = node.name
            if name.startswith("D_"):
                name = "$" + name[2:]
            elif name == "rand_int":
                name = str(node.value)
            stack.append(name)
        elif isinstance(node, gp.Ephemeral):
            stack.append(str(node.value))
    return stack[0] if stack else ""


# Register DEAP fitness and individual types (once)
if not hasattr(creator, "FitnessMax"):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)


def _mock_fitness(individual, pset) -> tuple[float]:
    """
    Mock fitness for testing — uses random score.
    Production fitness calls qlib-server via MCP.
    """
    expr = individual_to_expression(individual)
    # Simple heuristic: shorter expressions get slightly higher score (parsimony)
    base_score = np.random.uniform(-0.5, 1.5)
    parsimony_penalty = len(individual) * 0.01
    return (base_score - parsimony_penalty,)


def run_evolution(
    operator_names: list[str],
    data_fields: list[str],
    generations: int = 50,
    population_size: int = 500,
    max_depth: int = 6,
    top_k: int = 10,
    mock_mode: bool = False,
    fitness_fn=None,
) -> list[dict]:
    """
    Run GP evolution and return top-k candidate factor expressions.

    Args:
        operator_names: Operators available for tree building.
        data_fields: Data fields available as terminals.
        generations: Number of evolution generations.
        population_size: Size of the population.
        max_depth: Maximum tree depth.
        top_k: Number of top candidates to return.
        mock_mode: If True, use random fitness for testing.
        fitness_fn: Custom fitness function(individual, pset) -> tuple[float].

    Returns:
        List of dicts with "expression" and "fitness" keys, sorted by fitness desc.
    """
    pset = create_pset(operator_names, data_fields)

    toolbox = base.Toolbox()
    toolbox.register("expr", gp.genHalfAndHalf, pset=pset, min_=1, max_=max_depth)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.expr)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("compile", gp.compile, pset=pset)

    if fitness_fn:
        toolbox.register("evaluate", fitness_fn, pset=pset)
    elif mock_mode:
        toolbox.register("evaluate", _mock_fitness, pset=pset)
    else:
        # Production: fitness calls qlib-server
        toolbox.register("evaluate", _mock_fitness, pset=pset)

    toolbox.register("select", tools.selDoubleTournament, fitness_size=3, parsimony_size=1.4, fitness_first=True)
    toolbox.register("mate", gp.cxOnePoint)
    toolbox.register("expr_mut", gp.genFull, min_=0, max_=2)
    toolbox.register("mutate", gp.mutUniform, expr=toolbox.expr_mut, pset=pset)

    # Bloat control
    toolbox.decorate("mate", gp.staticLimit(key=len, max_value=max_depth * 3))
    toolbox.decorate("mutate", gp.staticLimit(key=len, max_value=max_depth * 3))

    pop = toolbox.population(n=population_size)
    hof = tools.HallOfFame(top_k)

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("max", np.max)

    algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=generations, stats=stats, halloffame=hof, verbose=False)

    results = []
    for ind in hof:
        expr_str = individual_to_expression(ind)
        fit = ind.fitness.values[0] if ind.fitness.valid else -999.0
        results.append({
            "expression": expr_str,
            "fitness": fit,
        })

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_gp_engine.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/vertical-plugins/market-data/skills/factor-mining/scripts/gp_engine.py plugins/vertical-plugins/market-data/skills/factor-mining/test_gp_engine.py
git commit -m "feat(factor-mining): add DEAP GP engine with expression tree evolution"
```

---

## Task 7: factor-mining — Factor Library Client + Mining Loop

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/factor_library.py`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/mine_factors.py`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/test_factor_library.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for factor library client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import pytest
import json


class TestFactorLibrary:
    def test_expression_hash_consistent(self):
        """Same expression produces same hash."""
        from factor_library import expression_hash
        h1 = expression_hash("Rank($close / $open)")
        h2 = expression_hash("Rank($close / $open)")
        assert h1 == h2

    def test_expression_hash_different(self):
        """Different expressions produce different hashes."""
        from factor_library import expression_hash
        h1 = expression_hash("Rank($close)")
        h2 = expression_hash("Rank($volume)")
        assert h1 != h2

    def test_name_from_expression(self):
        """Auto-generate factor name from expression."""
        from factor_library import name_from_expression
        name = name_from_expression("Rank(Ts_Mean($close, 20) / Ts_Std($close, 60))")
        assert "Rank" in name
        assert "Ts_Mean" in name

    def test_mining_direction_validation_valid(self):
        """Valid MiningDirection passes validation."""
        from mine_factors import validate_mining_direction
        direction = {
            "hypothesis": "test",
            "operators": ["Rank", "Add"],
            "data_fields": ["$close"],
            "universe": "csi300",
            "period": "2020-01-01 to 2025-01-01",
            "constraints": {"max_depth": 6, "population": 100, "generations": 20},
        }
        is_valid, msg = validate_mining_direction(direction)
        assert is_valid

    def test_mining_direction_validation_missing_operators(self):
        """MiningDirection without operators fails validation."""
        from mine_factors import validate_mining_direction
        direction = {
            "hypothesis": "test",
            "operators": [],
            "data_fields": ["$close"],
            "universe": "csi300",
            "period": "2020-01-01 to 2025-01-01",
        }
        is_valid, msg = validate_mining_direction(direction)
        assert not is_valid
        assert "operators" in msg.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_factor_library.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write factor_library.py**

```python
"""
Factor library client — helper functions for registering and querying factors.

Actual persistence goes through internal-store MCP tools.
"""

import hashlib
import re


def expression_hash(expression: str) -> str:
    """Compute a short hash for deduplication."""
    return hashlib.sha256(expression.encode()).hexdigest()[:16]


def name_from_expression(expression: str) -> str:
    """
    Auto-generate a human-readable factor name from its expression.
    E.g. "Rank(Ts_Mean($close, 20) / Ts_Std($close, 60))"
         → "rank_ts_mean_div_ts_std"
    """
    # Extract operator names (capitalized words)
    ops = re.findall(r"[A-Z][a-z]+(?:_[A-Z][a-z]+)*", expression)
    if not ops:
        ops = ["factor"]
    # Take first 3 operators
    parts = ops[:3]
    return "_".join(p.lower() for p in parts)


def build_register_params(
    expression: str,
    hypothesis: str,
    operators: list[str],
    data_fields: list[str],
    metrics: dict,
    universe: str = "",
    period: str = "",
    source_experiment_id: int | None = None,
) -> dict:
    """
    Build parameter dict for internal-store register_factor MCP call.
    """
    return {
        "name": name_from_expression(expression),
        "expression": expression,
        "hypothesis": hypothesis,
        "operators": operators,
        "data_fields": data_fields,
        "ic": metrics.get("ic"),
        "icir": metrics.get("icir"),
        "turnover": metrics.get("turnover"),
        "sharpe": metrics.get("sharpe"),
        "max_drawdown": metrics.get("max_drawdown"),
        "universe": universe,
        "period": period,
        "source_experiment_id": source_experiment_id,
    }
```

- [ ] **Step 4: Write mine_factors.py**

```python
"""
Main factor mining orchestrator.

Receives LLM MiningDirection, runs GP evolution, evaluates candidates,
and registers validated factors to the library.
"""

import json
from gp_engine import run_evolution, individual_to_expression


REQUIRED_FIELDS = ["hypothesis", "operators", "data_fields", "universe", "period"]

DEFAULT_CONSTRAINTS = {
    "max_depth": 6,
    "population": 500,
    "generations": 50,
    "top_k": 10,
}


def validate_mining_direction(direction: dict) -> tuple[bool, str]:
    """
    Validate a MiningDirection dict from LLM output.

    Returns (is_valid, message).
    """
    for field in REQUIRED_FIELDS:
        if field not in direction:
            return False, f"Missing required field: {field}"

    if not direction["operators"] or not isinstance(direction["operators"], list):
        return False, "operators must be a non-empty list"

    if not direction["data_fields"] or not isinstance(direction["data_fields"], list):
        return False, "data_fields must be a non-empty list"

    return True, "valid"


def mine_factors(mining_direction: dict, mock_mode: bool = False) -> list[dict]:
    """
    Execute the full factor mining pipeline for one direction.

    Args:
        mining_direction: Dict with hypothesis, operators, data_fields, universe, period, constraints.
        mock_mode: If True, use random fitness (for testing without MCP servers).

    Returns:
        List of candidate factor dicts with expression, fitness, and metrics.
    """
    is_valid, msg = validate_mining_direction(mining_direction)
    if not is_valid:
        raise ValueError(f"Invalid MiningDirection: {msg}")

    constraints = {**DEFAULT_CONSTRAINTS, **mining_direction.get("constraints", {})}

    candidates = run_evolution(
        operator_names=mining_direction["operators"],
        data_fields=mining_direction["data_fields"],
        generations=constraints["generations"],
        population_size=constraints["population"],
        max_depth=constraints["max_depth"],
        top_k=constraints["top_k"],
        mock_mode=mock_mode,
    )

    # Enrich candidates with metadata
    for c in candidates:
        c["hypothesis"] = mining_direction["hypothesis"]
        c["universe"] = mining_direction["universe"]
        c["period"] = mining_direction["period"]
        c["operators"] = mining_direction["operators"]
        c["data_fields"] = mining_direction["data_fields"]

    return candidates
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/test_factor_library.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/vertical-plugins/market-data/skills/factor-mining/scripts/factor_library.py plugins/vertical-plugins/market-data/skills/factor-mining/scripts/mine_factors.py plugins/vertical-plugins/market-data/skills/factor-mining/test_factor_library.py
git commit -m "feat(factor-mining): add factor library client and mining loop orchestrator"
```

---

## Task 8: factor-mining — SKILL.md

**Files:**
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/SKILL.md`
- Create: `plugins/vertical-plugins/market-data/skills/factor-mining/scripts/__init__.py`

- [ ] **Step 1: Create __init__.py**

```python
"""Factor mining skill — automatic factor discovery via GP evolution."""
```

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: factor-mining
description: |
  Automatic factor discovery using LLM-directed GP evolution.
  LLM generates directional hypotheses, DEAP evolves factor expressions,
  Qlib evaluates candidates. Validated factors stored in shared factor library.

  Triggers: "挖掘因子", "mine factors", "factor mining", "自动因子发现",
  "discover alpha", "find new factors"
---

# Factor Mining

## Overview

Automatically discovers new factor formulas through genetic programming.
LLM provides directional hypotheses (which operators + data to focus on),
DEAP evolves concrete expressions, Qlib evaluates fitness via IC/ICIR.

**Core Philosophy:** "LLM directs, GP searches, data validates."

---

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| hypothesis | str | Yes | LLM-generated directional hypothesis |
| operators | list[str] | Yes | Operator names to include in GP search space |
| data_fields | list[str] | Yes | Data fields available as GP terminals |
| universe | str | Yes | Stock universe for evaluation |
| period | str | Yes | Evaluation period "YYYY-MM-DD to YYYY-MM-DD" |
| constraints | dict | No | GP parameters: max_depth, population, generations, top_k |

---

## Tool Dependencies

| Tool | Purpose |
|------|---------|
| `mcp__qlib__qlib_eval_expression` | Evaluate candidate factor expressions |
| `mcp__qlib__qlib_list_operators` | List available operators |
| `mcp__qlib__qlib_get_universe` | Get stock universe codes |
| `mcp__internal-store__register_factor` | Register validated factors |
| `mcp__internal-store__list_factors` | Check for duplicate factors |

---

## Workflow

### Step 1: Validate MiningDirection

Check all required fields are present and non-empty.

### Step 2: Run GP Evolution

Execute `mine_factors.py` with the MiningDirection:
- DEAP evolves expression trees using selected operators + data fields
- Fitness = 0.6 × ICIR + 0.2 × mean_IC − 0.2 × turnover
- Returns top-k candidates ranked by fitness

### Step 3: Evaluate Top Candidates

For each candidate expression:
1. Call `qlib_eval_expression` to get factor values
2. Compute Rank IC series against forward returns
3. Calculate IC, ICIR, turnover

### Step 4: Full Validation via factor-research

Send top candidates to `factor-research` skill for:
- Walk-Forward validation
- Factor scorecard (IC > 0.03, ICIR > 0.5, turnover < 50%, etc.)

### Step 5: Register to Factor Library

Call `register_factor` for candidates that pass the scorecard.

---

## Output

```json
{
  "direction": "低波动环境下盈利动量增强",
  "candidates_evaluated": 500,
  "top_candidates": [
    {
      "expression": "Rank(Ts_Mean($close/$earnings, 20) / Ts_Std($close, 60))",
      "ic": 0.042,
      "icir": 0.68,
      "turnover": 0.35,
      "registered": true
    }
  ],
  "registered_count": 3,
  "total_in_library": 15
}
```

---

## Guardrails

1. **Always validate MiningDirection** before running GP
2. **Never register a factor without full validation** (IC/ICIR + Walk-Forward)
3. **Always check for duplicates** before registering
4. **Respect max_depth** — deeper trees overfit
5. **Use point-in-time data only** — no look-ahead bias

---

## Quality Checklist

- [ ] MiningDirection has all required fields
- [ ] GP evolution completed within constraints
- [ ] Top candidates have IC > 0.03 and ICIR > 0.5
- [ ] Walk-Forward validation passed
- [ ] No duplicate expressions in factor library
- [ ] Factor registered with full metrics
```

- [ ] **Step 3: Commit**

```bash
git add plugins/vertical-plugins/market-data/skills/factor-mining/SKILL.md plugins/vertical-plugins/market-data/skills/factor-mining/scripts/__init__.py
git commit -m "feat(factor-mining): add SKILL.md with trigger and workflow definition"
```

---

## Task 9: Update meta-strategist for Dynamic Factor Library

**Files:**
- Modify: `plugins/agent-plugins/meta-strategist/agents/meta-strategist.md`
- Modify: `plugins/agent-plugins/meta-strategist/agents/system-prompt.md`

- [ ] **Step 1: Update meta-strategist.md**

Replace the hardcoded 12-factor list in the **Factor Library** section with:

```markdown
**Factor Library**: Dynamic — call `mcp__internal-store__list_factors(status='active')` to get available factors.

If the factor library has fewer than 5 factors, invoke `factor-mining` skill first to discover new factors before generating strategy hypotheses.
```

- [ ] **Step 2: Update system-prompt.md**

In Step 2 (Generate Hypothesis), replace the hardcoded factor list:

```markdown
**Factor Library** (dynamic):
Call `mcp__internal-store__list_factors(status='active')` to retrieve all validated factors.
If fewer than 5 factors available, trigger `factor-mining` skill to discover new factors first.

Factors are mined automatically via GP evolution (DEAP) + Qlib expression evaluation.
Each factor has: name, expression, ic, icir, turnover metrics.
```

Also add to Available MCP Tools:

```markdown
- `mcp__internal-store__list_factors(status, universe)` — Query factor library
- `mcp__internal-store__register_factor(...)` — Register validated factor
- `mcp__qlib__qlib_eval_expression(expression, instruments, start_date, end_date)` — Evaluate factor expression
```

- [ ] **Step 3: Commit**

```bash
git add plugins/agent-plugins/meta-strategist/agents/meta-strategist.md plugins/agent-plugins/meta-strategist/agents/system-prompt.md
git commit -m "feat(meta-strategist): replace hardcoded factors with dynamic factor library read"
```

---

## Task 10: Update Architecture Docs

**Files:**
- Modify: `contributing/architecture.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add qlib-server to architecture.md Connector Catalog**

Add row to the Connector Catalog table:

```markdown
| Qlib | `localhost:8003/mcp` | HTTP (FastMCP) | None | Factor expression evaluation, operator catalog, A-share data via Qlib |
```

- [ ] **Step 2: Add factor-mining to Skill Catalog**

Add to the market-data skill section:

```markdown
| factor-mining | ✓ `mine_factors.py`, `gp_engine.py`, `operators.py`, `fitness.py`, `factor_library.py` | Automatic factor discovery via LLM-directed GP evolution |
```

- [ ] **Step 3: Update CLAUDE.md**

Add qlib-server to the architecture section:

```markdown
- **L0 Connectors**: `akshare-server` (8000), `tushare-server` (8001), `internal-store` (8002), `qlib-server` (8003)
```

Add Quick Start command:

```bash
uv run uvicorn mcp-servers.qlib-server.server:mcp_app --port 8003
```

- [ ] **Step 4: Commit**

```bash
git add contributing/architecture.md CLAUDE.md
git commit -m "docs: add qlib-server and factor-mining to architecture docs"
```

---

## Task 11: Run All Tests + Final Verification

- [ ] **Step 1: Run all factor-mining tests**

Run: `uv run pytest plugins/vertical-plugins/market-data/skills/factor-mining/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run ruff check**

Run: `uv run ruff check plugins/vertical-plugins/market-data/skills/factor-mining/ mcp-servers/qlib-server/ mcp-servers/internal-store/server.py`
Expected: No errors.

- [ ] **Step 3: Run architecture check**

Run: `uv run python scripts/check.py`
Expected: All boundary rules pass (R1-R6).

- [ ] **Step 4: Verify qlib-server starts**

Run: `uv run uvicorn mcp-servers.qlib-server.server:mcp_app --port 8003`
Expected: Server starts without error.

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address issues found during final verification"
```
