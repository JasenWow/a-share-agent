"""
Paper Trader MCP Server — Event-driven backtest simulation engine.
Run: uvicorn mcp-servers.paper-trader.server:mcp_app --port 8004
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.routing import Mount

from engine import BacktestEngine, DB_PATH
from models import Signal
from performance import compute_performance

logger = logging.getLogger(__name__)

_engines: dict[str, BacktestEngine] = {}

mcp = FastMCP(
    name="paper-trader",
    instructions="Backtest simulation engine — event-driven A-share strategy backtesting with T+1, "
    "price limits, transaction costs, and performance metrics. Version 0.1.0",
)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _init_db() -> None:
    """Initialize SQLite database with schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


_init_db()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# === Session Management ===


@mcp.tool()
def create_session(
    start_date: str,
    end_date: str,
    name: str = "",
    strategy: str = "",
    initial_capital: float = 1000000.0,
    universe: list[str] | None = None,
    benchmark: str = "sh000300",
    commission_rate: float = 0.00025,
    stamp_duty_rate: float = 0.0005,
    slippage_rate: float = 0.0005,
    exclude_st: bool = True,
) -> list[dict]:
    """
    Create a new backtest session with configuration.

    Args:
        start_date:       Backtest start date (YYYYMMDD).
        end_date:         Backtest end date (YYYYMMDD).
        name:             Session name for reference.
        strategy:         Strategy description.
        initial_capital:  Starting cash in RMB (default 1,000,000).
        universe:         List of 6-digit stock codes. If empty, load_bar_data will define it.
        benchmark:        Benchmark index code (default sh000300 for CSI 300).
        commission_rate:  Commission rate per side (default 0.00025 = 0.025%).
        stamp_duty_rate:  Stamp duty rate for sells (default 0.0005 = 0.05%).
        slippage_rate:    One-way slippage rate (default 0.0005 = 0.05%).
        exclude_st:       Whether to exclude ST stocks (default True).
    """
    try:
        session_id = uuid.uuid4().hex[:12]
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions "
                "(session_id, name, strategy, status, initial_capital, start_date, end_date, "
                "universe, benchmark, cost_commission, cost_stamp_duty, cost_slippage, exclude_st) "
                "VALUES (?, ?, ?, 'created', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    name,
                    strategy,
                    initial_capital,
                    start_date,
                    end_date,
                    json.dumps(universe or []),
                    benchmark,
                    commission_rate,
                    stamp_duty_rate,
                    slippage_rate,
                    int(exclude_st),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return [
            {
                "session_id": session_id,
                "status": "created",
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "universe": universe or [],
                "benchmark": benchmark,
            }
        ]
    except Exception as e:
        return [{"error": str(e), "tool": "create_session"}]


@mcp.tool()
def list_sessions(status: str = "", limit: int = 20) -> list[dict]:
    """
    List backtest sessions, optionally filtered by status.

    Args:
        status: Filter by status (created/ready/running/completed/failed). Empty = all.
        limit:  Maximum number of sessions to return (default 20).
    """
    try:
        conn = _get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT session_id, name, strategy, status, initial_capital, start_date, end_date, "
                    "final_nav, total_trades, created_at, updated_at "
                    "FROM sessions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT session_id, name, strategy, status, initial_capital, start_date, end_date, "
                    "final_nav, total_trades, created_at, updated_at "
                    "FROM sessions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "list_sessions"}]


@mcp.tool()
def get_session_status(session_id: str) -> list[dict]:
    """
    Get current session state including date, portfolio summary, and open positions.

    Args:
        session_id: Session ID returned by create_session.
    """
    try:
        conn = _get_conn()
        try:
            session = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not session:
                return [{"error": "Session not found", "session_id": session_id}]

            # Get latest positions
            latest_date = conn.execute(
                "SELECT MAX(trade_date) as d FROM positions WHERE session_id = ?", (session_id,)
            ).fetchone()["d"]

            positions = []
            if latest_date:
                pos_rows = conn.execute(
                    "SELECT * FROM positions WHERE session_id = ? AND trade_date = ?",
                    (session_id, latest_date),
                ).fetchall()
                positions = [dict(r) for r in pos_rows]

            # Get latest NAV
            latest_nav = conn.execute(
                "SELECT * FROM daily_nav WHERE session_id = ? ORDER BY trade_date DESC LIMIT 1",
                (session_id,),
            ).fetchone()

            result = dict(session)
            result["positions"] = positions
            result["latest_nav"] = dict(latest_nav) if latest_nav else None
        finally:
            conn.close()

        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "get_session_status"}]


# === Data Loading ===


@mcp.tool()
def load_bar_data(
    session_id: str,
    stock_codes: list[str],
    data: dict[str, list[dict]],
    benchmark_data: list[dict] | None = None,
) -> list[dict]:
    """
    Load OHLCV data for stocks and benchmark into session memory.

    Args:
        session_id:    Session ID.
        stock_codes:   List of 6-digit stock codes.
        data:          Dict mapping stock_code -> list of OHLCV records from akshare.
                       Each record must have keys: 日期, 开盘, 收盘, 最高, 最低, 成交量.
        benchmark_data: Benchmark index OHLCV records from akshare (optional).
    """
    try:
        engine = BacktestEngine(session_id)
        result = engine.load_bar_data(stock_codes, data)
        if benchmark_data:
            engine.load_benchmark(benchmark_data)
        _engines[session_id] = engine  # Cache for step mode
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "load_bar_data"}]


# === Signal Submission ===


@mcp.tool()
def submit_signal(
    session_id: str,
    signal_date: str,
    stock_code: str,
    direction: str,
    target_weight: float = 0.0,
    target_shares: int = 0,
) -> list[dict]:
    """
    Submit a buy/sell signal for a stock on a specific date.
    Signals execute at T+1 open price during run_session.

    Args:
        session_id:   Session ID.
        signal_date:  Date the signal is generated (YYYYMMDD). Trade executes on next trading day.
        stock_code:   6-digit stock code.
        direction:    "buy" or "sell".
        target_weight: Target portfolio weight for buy signals (0.0 to 1.0). Takes precedence over target_shares.
        target_shares: Target number of shares for buy when target_weight=0. For sell, 0 means sell all sellable.
    """
    try:
        signal = Signal(
            signal_date=signal_date,
            stock_code=stock_code,
            direction=direction,
            target_weight=target_weight,
            target_shares=target_shares,
        )
        engine = _engines.get(session_id, BacktestEngine(session_id))
        engine.register_signals([signal])
        _engines[session_id] = engine
        return [{"session_id": session_id, "signal_date": signal_date, "stock_code": stock_code, "direction": direction, "status": "queued"}]
    except Exception as e:
        return [{"error": str(e), "tool": "submit_signal"}]


@mcp.tool()
def submit_signals_batch(session_id: str, signals: list[dict]) -> list[dict]:
    """
    Submit multiple signals at once.

    Args:
        session_id: Session ID.
        signals:    List of signal dicts. Each must have: signal_date, stock_code, direction.
                    Optional: target_weight (float), target_shares (int).
    """
    try:
        sig_objects = []
        for s in signals:
            sig_objects.append(
                Signal(
                    signal_date=s["signal_date"],
                    stock_code=s["stock_code"],
                    direction=s["direction"],
                    target_weight=s.get("target_weight", 0.0),
                    target_shares=s.get("target_shares", 0),
                )
            )
        engine = _engines.get(session_id, BacktestEngine(session_id))
        count = engine.register_signals(sig_objects)
        _engines[session_id] = engine
        return [{"session_id": session_id, "signals_registered": count, "status": "queued"}]
    except Exception as e:
        return [{"error": str(e), "tool": "submit_signals_batch"}]


# === Step-by-Step Execution ===


@mcp.tool()
def step_session(session_id: str) -> list[dict]:
    """
    Advance the simulation by ONE trading day.
    First call initializes the session, subsequent calls process the next day.
    Between steps, the agent can submit signals using submit_signal/submit_signals_batch.
    Returns today's market data, current portfolio, and NAV.

    Args:
        session_id: Session ID to step.
    """
    try:
        engine = _engines.get(session_id)
        if engine is None:
            return [{"error": "No engine found. Call load_bar_data first to initialize.", "tool": "step_session"}]
        result = engine.step()
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "step_session"}]


@mcp.tool()
def get_today_market(session_id: str) -> list[dict]:
    """
    Get current trading day's OHLCV data for the session universe.
    Only meaningful during step mode after step_session has been called.

    Args:
        session_id: Session ID.
    """
    try:
        engine = _engines.get(session_id)
        if engine is None:
            return [{"error": "No engine found. Call load_bar_data first.", "tool": "get_today_market"}]
        result = engine.get_today_bars()
        if "error" in result:
            return [result]
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "get_today_market"}]


# === Execution ===


@mcp.tool()
def run_session(session_id: str) -> list[dict]:
    """
    Run the full backtest simulation from start_date to end_date.
    Processes all submitted signals day-by-day with T+1 execution.

    Args:
        session_id: Session ID to run.
    """
    try:
        engine = BacktestEngine(session_id)
        result = engine.run()
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "run_session"}]


# === Results Retrieval ===


@mcp.tool()
def get_equity_curve(session_id: str, start_date: str = "", end_date: str = "") -> list[dict]:
    """
    Get NAV time series for strategy and benchmark.

    Args:
        session_id: Session ID.
        start_date: Optional start date filter (YYYYMMDD).
        end_date:   Optional end date filter (YYYYMMDD).
    """
    try:
        conn = _get_conn()
        try:
            query = "SELECT trade_date, nav, cash, positions_value, benchmark_value, benchmark_close, "
            query += "daily_return, benchmark_return, excess_return "
            query += "FROM daily_nav WHERE session_id = ?"
            params: list = [session_id]
            if start_date:
                query += " AND trade_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND trade_date <= ?"
                params.append(end_date)
            query += " ORDER BY trade_date"
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_equity_curve"}]


@mcp.tool()
def get_trade_log(
    session_id: str,
    stock_code: str = "",
    direction: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 500,
) -> list[dict]:
    """
    Get all executed trades with costs.

    Args:
        session_id:  Session ID.
        stock_code:  Optional filter by 6-digit stock code.
        direction:   Optional filter by "buy" or "sell".
        start_date:  Optional start date filter (YYYYMMDD).
        end_date:    Optional end date filter (YYYYMMDD).
        limit:       Maximum trades to return (default 500).
    """
    try:
        conn = _get_conn()
        try:
            query = "SELECT * FROM trades WHERE session_id = ?"
            params: list = [session_id]
            if stock_code:
                query += " AND stock_code = ?"
                params.append(stock_code)
            if direction:
                query += " AND direction = ?"
                params.append(direction)
            if start_date:
                query += " AND trade_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND trade_date <= ?"
                params.append(end_date)
            query += " ORDER BY trade_date, id LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_trade_log"}]


@mcp.tool()
def get_positions_snapshot(session_id: str, trade_date: str) -> list[dict]:
    """
    Get end-of-day position snapshot for a specific date.

    Args:
        session_id: Session ID.
        trade_date: Date to get snapshot for (YYYYMMDD).
    """
    try:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM positions WHERE session_id = ? AND trade_date = ? ORDER BY weight DESC",
                (session_id, trade_date),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e), "tool": "get_positions_snapshot"}]


@mcp.tool()
def get_performance(session_id: str) -> list[dict]:
    """
    Compute full performance metrics for a completed session.
    Includes Sharpe, Sortino, MaxDD, Calmar, win rate, turnover, benchmark comparison.

    Args:
        session_id: Session ID.
    """
    try:
        return compute_performance(session_id)
    except Exception as e:
        return [{"error": str(e), "tool": "get_performance"}]


# === Persistence ===


@mcp.tool()
def save_results(session_id: str) -> list[dict]:
    """
    Save backtest results summary to internal-store's backtest_results table.

    Args:
        session_id: Session ID to save.
    """
    try:
        # Get session info
        conn = _get_conn()
        try:
            session = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        finally:
            conn.close()

        if not session:
            return [{"error": "Session not found", "session_id": session_id}]

        # Compute performance
        perf = compute_performance(session_id)
        if not perf or "error" in perf[0]:
            return perf

        metrics = perf[0]

        # Write to internal-store's backtest_results table
        internal_db = Path(__file__).parent.parent / "internal-store" / "data" / "cache" / "meta.db"
        if internal_db.exists():
            iconn = sqlite3.connect(str(internal_db))
            try:
                iconn.execute(
                    "INSERT INTO backtest_results (name, strategy, start_date, end_date, sharpe, max_drawdown, annual_return) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        session["name"] or session_id,
                        session["strategy"],
                        session["start_date"],
                        session["end_date"],
                        metrics.get("sharpe_ratio"),
                        metrics.get("max_drawdown"),
                        metrics.get("annual_return"),
                    ),
                )
                iconn.commit()
            finally:
                iconn.close()
            return [{"status": "saved", "session_id": session_id, "sharpe": metrics.get("sharpe_ratio"), "annual_return": metrics.get("annual_return")}]
        else:
            return [{"status": "saved_local_only", "session_id": session_id, "note": "internal-store DB not found, results kept in paper-trader DB only"}]
    except Exception as e:
        return [{"error": str(e), "tool": "save_results"}]


# --- ASGI App ---
mcp_app = mcp.streamable_http_app()

# --- REST API + Static Files for Web UI ---
rest_app = FastAPI(title="Backtest Dashboard API")

WEB_DIR = Path(__file__).parent / "web"


@rest_app.get("/api/sessions")
def api_list_sessions():
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT session_id, name, strategy, status, initial_capital, start_date, end_date, "
            "final_nav, total_trades, created_at FROM sessions ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@rest_app.get("/api/sessions/{session_id}/status")
def api_session_status(session_id: str):
    return get_session_status(session_id)


@rest_app.get("/api/sessions/{session_id}/equity")
def api_equity_curve(session_id: str):
    return get_equity_curve(session_id)


@rest_app.get("/api/sessions/{session_id}/performance")
def api_performance(session_id: str):
    result = compute_performance(session_id)
    return result[0] if result else {}


@rest_app.get("/api/sessions/{session_id}/trades")
def api_trades(session_id: str, direction: str = "", stock_code: str = "", limit: int = 500):
    return get_trade_log(session_id, stock_code=stock_code, direction=direction, limit=limit)


@rest_app.get("/api/sessions/{session_id}/positions/latest")
def api_positions_latest(session_id: str):
    conn = _get_conn()
    try:
        last_date = conn.execute(
            "SELECT MAX(trade_date) as d FROM positions WHERE session_id = ?", (session_id,)
        ).fetchone()["d"]
        if not last_date:
            return []
        rows = conn.execute(
            "SELECT * FROM positions WHERE session_id = ? AND trade_date = ? ORDER BY weight DESC",
            (session_id, last_date),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Mount static files and SPA fallback
if WEB_DIR.exists():
    rest_app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="static")

    @rest_app.get("/")
    async def serve_index():
        return FileResponse(str(WEB_DIR / "index.html"))

    @rest_app.get("/index.html")
    async def serve_index_html():
        return FileResponse(str(WEB_DIR / "index.html"))


# Compose MCP + REST into a single ASGI app
combined_app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_app),
        Mount("/", app=rest_app),
    ]
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(combined_app, host="0.0.0.0", port=8004)
