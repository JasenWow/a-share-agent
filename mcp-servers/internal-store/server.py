"""
Internal Data Store MCP Server — Local data management
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8002
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
import pandas as pd

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "./data"))
DB_PATH = DATA_ROOT / "cache" / "meta.db"

mcp = FastMCP(
    name="internal-store",
    instructions="Local data store MCP Server — cache query, backtest management. Version 0.1.0",
)


def _init_db():
    """Initialize SQLite database if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            source      TEXT NOT NULL,
            tool_name   TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            fetched_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            row_count   INTEGER DEFAULT 0,
            PRIMARY KEY (source, tool_name, params_hash)
        );
        CREATE TABLE IF NOT EXISTS backtest_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            start_date  TEXT NOT NULL,
            end_date    TEXT NOT NULL,
            sharpe      REAL,
            max_drawdown REAL,
            annual_return REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            holdings    TEXT NOT NULL,
            cash        REAL DEFAULT 0,
            updated_at  TEXT DEFAULT (datetime('now'))
        );
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
            experiment_id INTEGER NOT NULL,
            state       TEXT NOT NULL,
            strategy    TEXT NOT NULL,
            reward      TEXT NOT NULL,
            next_state  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS episode_summaries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            period          TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            final_nav       REAL NOT NULL,
            sharpe          REAL NOT NULL,
            max_drawdown    REAL NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS experiment_steps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id   INTEGER NOT NULL,
            step_index      INTEGER NOT NULL,
            step_type       TEXT NOT NULL,
            hypothesis      TEXT NOT NULL,
            signals_summary TEXT,
            simulation_result TEXT,
            state_snapshot  TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
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
    """
    )
    conn.commit()
    conn.close()


_init_db()


@mcp.tool()
def query_cache(source: str, tool_name: str, params: dict = {}) -> list[dict]:
    """
    Query local cache data. Returns cached data if not expired, otherwise returns empty with status.

    Args:
        source:    Data source name ("akshare" or "tushare").
        tool_name: MCP tool name.
        params:    Parameters dict used in original query.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

        row = conn.execute(
            "SELECT * FROM cache_entries WHERE source=? AND tool_name=? AND params_hash=?",
            (source, tool_name, params_hash),
        ).fetchone()
        conn.close()

        if not row:
            return [{"status": "cache_miss", "message": "No cache entry found"}]

        if row["expires_at"] < datetime.now().isoformat():
            return [{"status": "cache_expired", "message": "Cache entry has expired"}]

        file_path = DATA_ROOT / row["file_path"]
        if file_path.exists():
            df = pd.read_parquet(str(file_path))
            return df.to_dict(orient="records")
        return [{"status": "file_missing", "message": "Cache file not found"}]
    except Exception as e:
        return [{"error": str(e), "tool": "query_cache"}]


@mcp.tool()
def list_backtest_results(limit: int = 20) -> list[dict]:
    """
    List all backtest results.

    Args:
        limit: Maximum number of results to return.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_backtest_results"}]


@mcp.tool()
def get_portfolio(name: str = "default") -> dict:
    """
    Get current portfolio state.

    Args:
        name: Portfolio name (default: "default").
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM portfolio_state WHERE name=? ORDER BY updated_at DESC LIMIT 1",
            (name,),
        ).fetchone()
        conn.close()
        if not row:
            return {"status": "not_found", "holdings": [], "cash": 0}
        return {
            "name": row["name"],
            "holdings": json.loads(row["holdings"]),
            "cash": row["cash"],
            "updated_at": row["updated_at"],
        }
    except Exception as e:
        return {"error": str(e), "tool": "get_portfolio"}


@mcp.tool()
def record_experiment(name: str, strategy: dict, params: dict, result: dict) -> list[dict]:
    """
    Record an experiment run.

    Args:
        name:     Experiment name.
        strategy: Strategy configuration dict.
        params:   Strategy parameters dict.
        result:   Result metrics dict (final_nav, sharpe, max_drawdown).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO experiments (name, strategy, params, result) VALUES (?, ?, ?, ?)",
            (name, json.dumps(strategy), json.dumps(params), json.dumps(result)),
        )
        rows = conn.execute("SELECT * FROM experiments ORDER BY id DESC LIMIT 1").fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "record_experiment"}]


@mcp.tool()
def list_experiments() -> list[dict]:
    """List all recorded experiments."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_experiments"}]


@mcp.tool()
def get_best_strategies(top_k: int = 5) -> list[dict]:
    """
    Get top-k strategies ordered by final_nav descending.

    Args:
        top_k: Number of top strategies to return.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT *, json_extract(result, '$.final_nav') AS final_nav FROM experiments ORDER BY CAST(json_extract(result, '$.final_nav') AS REAL) DESC LIMIT ?",
            (top_k,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_best_strategies"}]


@mcp.tool()
def record_transition(
    experiment_id: int, state: dict, strategy: dict, reward: dict, next_state: dict
) -> list[dict]:
    """
    Record a state transition for RL-based strategies.

    Args:
        experiment_id: ID of the experiment this transition belongs to.
        state:         Current state dict.
        strategy:      Action/strategy dict.
        reward:        Reward dict.
        next_state:    Resulting state dict.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO transitions (experiment_id, state, strategy, reward, next_state) VALUES (?, ?, ?, ?, ?)",
            (experiment_id, json.dumps(state, sort_keys=True), json.dumps(strategy, sort_keys=True), json.dumps(reward, sort_keys=True), json.dumps(next_state, sort_keys=True)),
        )
        rows = conn.execute("SELECT * FROM transitions ORDER BY id DESC LIMIT 1").fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "record_transition"}]


@mcp.tool()
def record_episode_summary(
    period: str, initial_capital: float, final_nav: float, sharpe: float, max_drawdown: float
) -> list[dict]:
    """
    Record an episode summary.

    Args:
        period:         Period identifier (e.g., "2024Q1").
        initial_capital: Starting capital.
        final_nav:      Final NAV (net asset value).
        sharpe:         Sharpe ratio.
        max_drawdown:   Maximum drawdown.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO episode_summaries (period, initial_capital, final_nav, sharpe, max_drawdown) VALUES (?, ?, ?, ?, ?)",
            (period, initial_capital, final_nav, sharpe, max_drawdown),
        )
        rows = conn.execute("SELECT * FROM episode_summaries ORDER BY id DESC LIMIT 1").fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "record_episode_summary"}]


@mcp.tool()
def list_episode_summaries() -> list[dict]:
    """List all episode summaries."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM episode_summaries ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_episode_summaries"}]



@mcp.tool()
def get_similar_states(state_vector: dict, top_k: int = 5) -> list[dict]:
    """
    Find experiments with historically similar state parameters.

    Similarity is measured by counting overlapping key-value pairs between
    the provided state_vector and each experiment's params JSON field.

    Args:
        state_vector: Dict of state fields to match against experiment params.
        top_k:        Number of top matches to return.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
        conn.close()

        scored = []
        for row in rows:
            params = json.loads(row["params"]) if row["params"] else {}
            overlap = sum(1 for k, v in state_vector.items() if params.get(k) == v)
            if overlap > 0:
                scored.append((overlap, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
    except Exception as e:
        return [{"error": str(e), "tool": "get_similar_states"}]


@mcp.tool()
def get_transition_matrix(state_vector: dict) -> dict:
    """
    Aggregate transitions matching a state vector, grouped by strategy.

    Returns a dict mapping strategy JSON to {avg_reward, count} for strategy
    selection based on historical performance from similar states.

    Args:
        state_vector: Dict of state fields to match against transition state JSON.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM transitions").fetchall()
        conn.close()

        aggregated = {}
        for row in rows:
            t_state = json.loads(row["state"]) if row["state"] else {}
            overlap = sum(1 for k, v in state_vector.items() if t_state.get(k) == v)
            if overlap == 0:
                continue

            strategy_key = row["strategy"]
            reward_data = json.loads(row["reward"]) if row["reward"] else {}
            reward_val = reward_data.get("pnl", 0)

            if strategy_key not in aggregated:
                aggregated[strategy_key] = {"total_reward": 0.0, "count": 0}
            aggregated[strategy_key]["total_reward"] += reward_val
            aggregated[strategy_key]["count"] += 1

        return {
            k: {"avg_reward": v["total_reward"] / v["count"], "count": v["count"]}
            for k, v in aggregated.items()
        }
    except Exception as e:
        return {"error": str(e), "tool": "get_transition_matrix"}


@mcp.tool()
def record_experiment_step(
    experiment_id: int,
    step_index: int,
    step_type: str,
    hypothesis: dict,
    signals_summary: dict | None = None,
    simulation_result: dict | None = None,
    state_snapshot: dict | None = None,
) -> list[dict]:
    """
    Record a single step within an evolution loop iteration.

    Each iteration can have multiple steps (hypothesis generation, signal generation,
    simulation, state update). This provides fine-grained experiment tracking.

    Args:
        experiment_id:     ID of the parent experiment.
        step_index:        Step number within the iteration (0-based).
        step_type:         Step type: "hypothesis", "signals", "simulation", "state_update".
        hypothesis:        Strategy hypothesis dict (factors, weights, universe, etc.).
        signals_summary:   Optional summary of generated signals (count, date range, etc.).
        simulation_result: Optional simulation output (return_pct, trades, etc.).
        state_snapshot:    Optional evolution state snapshot at this step.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO experiment_steps (experiment_id, step_index, step_type, hypothesis, signals_summary, simulation_result, state_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                experiment_id,
                step_index,
                step_type,
                json.dumps(hypothesis, sort_keys=True),
                json.dumps(signals_summary, sort_keys=True) if signals_summary else None,
                json.dumps(simulation_result, sort_keys=True) if simulation_result else None,
                json.dumps(state_snapshot, sort_keys=True) if state_snapshot else None,
            ),
        )
        rows = conn.execute("SELECT * FROM experiment_steps ORDER BY id DESC LIMIT 1").fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "record_experiment_step"}]


@mcp.tool()
def list_experiment_steps(experiment_id: int) -> list[dict]:
    """
    List all steps for a given experiment, ordered by step_index.

    Args:
        experiment_id: ID of the experiment.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM experiment_steps WHERE experiment_id=? ORDER BY step_index ASC",
            (experiment_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_experiment_steps"}]


@mcp.tool()
def get_latest_step(experiment_id: int) -> list[dict]:
    """
    Get the most recent step for an experiment.

    Args:
        experiment_id: ID of the experiment.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM experiment_steps WHERE experiment_id=? ORDER BY step_index DESC LIMIT 1",
            (experiment_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_latest_step"}]


@mcp.tool()
def get_failures(experiment_id: int | None = None, limit: int = 20) -> list[dict]:
    """
    Retrieve experiments with negative returns (final_nav < 1.0).

    Args:
        experiment_id: Optional filter by specific experiment ID.
        limit:         Maximum number of failures to return.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM experiments WHERE CAST(json_extract(result, '$.final_nav') AS REAL) < 1.0"
        params: list = []
        if experiment_id is not None:
            query += " AND id = ?"
            params.append(experiment_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_failures"}]


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
    Auto-deduplicates by expression text.

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
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

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
        conditions = []
        params = []

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


# ============================================================
# Half-automatic feedback loop (子项目 ❻ Meta-Agent 探索)
# ============================================================
# 设计原则（路线图 §3❻ D2 半自动）：
#   - Meta-Agent 生成"候选"(candidate)，不自动入库为 active
#   - 入库决策权在人：通过 promote_factor / reject_factor 工具审批
#   - 候选可被推荐报告引用，推荐附置信度
# ============================================================


@mcp.tool()
def register_factor_candidate(
    name: str,
    expression: str,
    operators: list[str],
    data_fields: list[str],
    hypothesis: str,
    ic: float = 0.0,
    icir: float = 0.0,
    turnover: float = 0.0,
    sharpe: float = 0.0,
    max_drawdown: float = 0.0,
    universe: str = "",
    period: str = "",
    confidence: float = 0.5,
    rationale: str = "",
    source_experiment_id: int | None = None,
) -> list[dict]:
    """
    Register a factor as a CANDIDATE (sub-project ❻ half-automatic loop).

    Candidates are NOT active. They wait for human review.
    Use promote_factor(id) to approve, reject_factor(id) to reject.

    Args:
        name, expression, operators, data_fields, hypothesis: factor definition
        ic, icir, turnover, sharpe, max_drawdown: evaluation metrics
        universe, period: validation context
        confidence:    Meta-Agent self-assessed confidence (0.0-1.0)
        rationale:     Why the agent recommends this factor (Markdown OK)
        source_experiment_id: ID of the experiment that produced this candidate
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        existing = conn.execute(
            "SELECT id, status FROM factor_library WHERE expression = ?",
            (expression,),
        ).fetchone()
        if existing:
            conn.close()
            return [{
                "status": "duplicate",
                "id": existing["id"],
                "existing_status": existing["status"],
                "message": "Factor with same expression already exists",
            }]

        conn.execute(
            """INSERT INTO factor_library
            (name, expression, hypothesis, operators, data_fields, ic, icir, turnover,
             sharpe, max_drawdown, universe, period, walk_forward, status, source_experiment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)""",
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
                json.dumps({"confidence": confidence, "rationale": rationale}),
                source_experiment_id,
            ),
        )
        rows = conn.execute(
            "SELECT * FROM factor_library WHERE status = 'candidate' ORDER BY id DESC LIMIT 1"
        ).fetchall()
        conn.commit()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "register_factor_candidate"}]


@mcp.tool()
def list_candidates(limit: int = 50) -> list[dict]:
    """
    List all candidate factors awaiting human review (sub-project ❻).

    Args:
        limit: Max number of candidates to return (most recent first).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM factor_library
               WHERE status = 'candidate'
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_candidates"}]


@mcp.tool()
def promote_factor(factor_id: int, reviewer: str = "", notes: str = "") -> list[dict]:
    """
    Promote a candidate factor to ACTIVE status (human approval gate, sub-project ❻).

    This is the human-in-the-loop step. Only call after reviewing the candidate's
    metrics, hypothesis, and Meta-Agent rationale.

    Args:
        factor_id: ID of the candidate factor to promote.
        reviewer:  Name of the human reviewer (for audit trail).
        notes:     Reviewer notes (optional).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM factor_library WHERE id = ?", (factor_id,)
        ).fetchone()
        if not row:
            conn.close()
            return [{"error": f"factor_id {factor_id} not found"}]
        if row["status"] != "candidate":
            conn.close()
            return [{
                "error": f"factor_id {factor_id} is '{row['status']}', not 'candidate' — only candidates can be promoted",
            }]
        conn.execute(
            "UPDATE factor_library SET status = 'active' WHERE id = ?",
            (factor_id,),
        )
        rows = conn.execute("SELECT * FROM factor_library WHERE id = ?", (factor_id,)).fetchall()
        conn.commit()
        conn.close()
        # Annotate the returned row with reviewer info (not stored in DB schema
        # to avoid migration; audit trail lives in agent logs)
        result = [dict(r) for r in rows]
        if result and reviewer:
            result[0]["_promoted_by"] = reviewer
        if result and notes:
            result[0]["_promotion_notes"] = notes
        return result
    except Exception as e:
        return [{"error": str(e), "tool": "promote_factor"}]


@mcp.tool()
def reject_factor(factor_id: int, reason: str = "", reviewer: str = "") -> list[dict]:
    """
    Reject a candidate factor (human decision, sub-project ❻).

    Sets status to 'rejected' (distinct from 'deprecated' which is for formerly-active factors).

    Args:
        factor_id: ID of the candidate to reject.
        reason:    Reason for rejection.
        reviewer:  Name of the human reviewer.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status FROM factor_library WHERE id = ?", (factor_id,)
        ).fetchone()
        if not row:
            conn.close()
            return [{"error": f"factor_id {factor_id} not found"}]
        conn.execute(
            "UPDATE factor_library SET status = 'rejected' WHERE id = ?",
            (factor_id,),
        )
        rows = conn.execute("SELECT * FROM factor_library WHERE id = ?", (factor_id,)).fetchall()
        conn.commit()
        conn.close()
        result = [dict(r) for r in rows]
        if result and reviewer:
            result[0]["_rejected_by"] = reviewer
        if result and reason:
            result[0]["_rejection_reason"] = reason
        return result
    except Exception as e:
        return [{"error": str(e), "tool": "reject_factor"}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
