"""
Prediction Store MCP Server — Stock prediction persistence and accuracy tracking
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8003
"""

import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "predictions.db"

mcp = FastMCP(
    name="prediction-store",
    instructions="Stock prediction storage, accuracy tracking, and error analysis",
)


def _init_db():
    """Initialize SQLite database with schema."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            stock_code      TEXT NOT NULL,
            signal_date     TEXT NOT NULL,
            predicted_pct   REAL NOT NULL,
            confidence      REAL NOT NULL,
            features_summary TEXT,
            actual_pct      REAL,
            error           REAL,
            version         INTEGER DEFAULT 1,
            baseline        INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            verified_at     TEXT,
            PRIMARY KEY (stock_code, signal_date)
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code  TEXT NOT NULL UNIQUE,
            stock_name  TEXT,
            added_at    TEXT DEFAULT (datetime('now')),
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS trading_calendar (
            trade_date      TEXT PRIMARY KEY,
            is_trading_day  INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_predictions_stock ON predictions(stock_code);
        CREATE INDEX IF NOT EXISTS idx_predictions_signal ON predictions(signal_date);
        CREATE INDEX IF NOT EXISTS idx_predictions_verified ON predictions(verified_at);
        """
    )
    conn.commit()
    conn.close()
    _seed_trading_calendar()


def _seed_trading_calendar():
    """Pre-populate 2024-2026 Chinese trading days."""
    holidays_2024 = {
        "20240101", "20240102", "20240103",  # New Year
        "20240210", "20240211", "20240212", "20240213", "20240214", "20240215", "20240216", "20240217",  # Spring Festival
        "20240404", "20240405", "20240406",  # Qingming
        "20240501", "20240502", "20240503", "20240504", "20240505",  # Labor Day
        "20240610", "20240611", "20240612",  # Dragon Boat
        "20240915", "20240916", "20240917",  # Mid-Autumn
        "20241001", "20241002", "20241003", "20241004", "20241005", "20241006", "20241007",  # National Day
    }
    holidays_2025 = {
        "20250101", "20250128", "20250129", "20250130", "20250131", "20250201", "20250202", "20250203", "20250204",  # Spring Festival
        "20250404", "20250405", "20250406",  # Qingming
        "20250501", "20250502", "20250503", "20250504", "20250505",  # Labor Day
        "20250531", "20250601", "20250602",  # Dragon Boat
        "20251001", "20251002", "20251003", "20251004", "20251005", "20251006", "20251007",  # National Day
    }
    holidays_2026 = {
        "20260101", "20260117", "20260118", "20260119", "20260120", "20260121", "20260122", "20260123", "20260124", "20260125", "20260126", "20260127",  # Spring Festival
        "20260403", "20260404", "20260405",  # Qingming
        "20260501", "20260502", "20260503", "20260504", "20260505",  # Labor Day
        "20260620", "20260621", "20260622",  # Dragon Boat
        "20261001", "20261002", "20261003", "20261004", "20261005", "20261006", "20261007",  # National Day
    }

    all_holidays = holidays_2024 | holidays_2025 | holidays_2026

    conn = sqlite3.connect(str(DB_PATH))
    for date_str in all_holidays:
        conn.execute(
            "INSERT OR IGNORE INTO trading_calendar (trade_date, is_trading_day) VALUES (?, 0)",
            (date_str,),
        )

    start_2024 = datetime(2024, 1, 1)
    end_2026 = datetime(2026, 12, 31)
    current = start_2024
    while current <= end_2026:
        date_str = current.strftime("%Y%m%d")
        is_weekend = current.weekday() >= 5
        is_holiday = date_str in all_holidays
        is_trading = not is_weekend and not is_holiday
        if is_trading:
            conn.execute(
                "INSERT OR IGNORE INTO trading_calendar (trade_date, is_trading_day) VALUES (?, 1)",
                (date_str,),
            )
        current += timedelta(days=1)

    conn.commit()
    conn.close()


_init_db()


def _validate_stock_code(code: str) -> bool:
    """Validate 6-digit stock code."""
    return bool(re.fullmatch(r"^\d{6}$", code))


def _validate_date(date_str: str) -> bool:
    """Validate YYYYMMDD date format."""
    if not re.fullmatch(r"^\d{8}$", date_str):
        return False
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False


@mcp.tool()
def manage_watchlist(action: str, stock_codes: list[str] = None) -> list[dict]:
    """
    Manage stock watchlist. Actions: add, remove, list.

    Args:
        action: One of "add", "remove", "list".
        stock_codes: List of 6-digit stock codes. Required for add/remove.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        if action == "list":
            rows = conn.execute(
                "SELECT * FROM watchlist WHERE is_active=1 ORDER BY added_at DESC"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

        if action not in ("add", "remove"):
            conn.close()
            return [{"error": "action must be 'add', 'remove', or 'list'", "tool": "manage_watchlist", "params": {"action": action}}]

        if not stock_codes:
            conn.close()
            return [{"error": "stock_codes required for add/remove", "tool": "manage_watchlist", "params": {"action": action}}]

        for code in stock_codes:
            if not _validate_stock_code(code):
                conn.close()
                return [{"error": f"Invalid stock code: {code} (must be 6 digits)", "tool": "manage_watchlist", "params": {"code": code}}]

        results = []
        if action == "add":
            existing = conn.execute(
                "SELECT COUNT(*) as cnt FROM watchlist WHERE is_active=1"
            ).fetchone()["cnt"]
            if existing + len(stock_codes) > 20:
                conn.close()
                return [{"error": f"Watchlist limit exceeded (max 20). Current: {existing}, Adding: {len(stock_codes)}", "tool": "manage_watchlist"}]

            for code in stock_codes:
                cursor = conn.execute(
                    "SELECT id, is_active FROM watchlist WHERE stock_code=?",
                    (code,),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    if existing_row["is_active"] == 1:
                        results.append({"stock_code": code, "status": "already_exists", "id": existing_row["id"]})
                    else:
                        conn.execute("UPDATE watchlist SET is_active=1 WHERE stock_code=?", (code,))
                        results.append({"stock_code": code, "status": "reactivated", "id": existing_row["id"]})
                else:
                    cursor = conn.execute(
                        "INSERT INTO watchlist (stock_code) VALUES (?)",
                        (code,),
                    )
                    results.append({"stock_code": code, "status": "added", "id": cursor.lastrowid})

        elif action == "remove":
            for code in stock_codes:
                cursor = conn.execute(
                    "UPDATE watchlist SET is_active=0 WHERE stock_code=? AND is_active=1",
                    (code,),
                )
                if cursor.rowcount > 0:
                    results.append({"stock_code": code, "status": "removed"})
                else:
                    results.append({"stock_code": code, "status": "not_found"})

        conn.commit()
        conn.close()
        return results

    except Exception as e:
        return [{"error": str(e), "tool": "manage_watchlist", "params": {"action": action}}]


@mcp.tool()
def store_prediction(
    stock_code: str,
    signal_date: str,
    predicted_pct: float,
    confidence: float,
    features_summary: str = "",
) -> list[dict]:
    """
    Store or update a prediction. Uses upsert on (stock_code, signal_date).

    Args:
        stock_code: 6-digit stock code.
        signal_date: YYYYMMDD.
        predicted_pct: Predicted % change, must be in [-30, 30].
        confidence: Confidence level 0-1.
        features_summary: JSON string of key technical indicators.
    """
    try:
        if not _validate_stock_code(stock_code):
            return [{"error": f"Invalid stock code: {stock_code} (must be 6 digits)", "tool": "store_prediction"}]

        if not _validate_date(signal_date):
            return [{"error": f"Invalid signal_date: {signal_date} (must be YYYYMMDD)", "tool": "store_prediction"}]

        if not isinstance(predicted_pct, (int, float)) or abs(predicted_pct) > 30:
            return [{"error": f"predicted_pct must be in [-30, 30], got {predicted_pct}", "tool": "store_prediction"}]

        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            return [{"error": f"confidence must be in [0, 1], got {confidence}", "tool": "store_prediction"}]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        existing = conn.execute(
            "SELECT version FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()

        if existing:
            new_version = existing["version"] + 1
            conn.execute(
                """
                UPDATE predictions
                SET predicted_pct=?, confidence=?, features_summary=?, version=?,
                    created_at=datetime('now')
                WHERE stock_code=? AND signal_date=?
                """,
                (predicted_pct, confidence, features_summary, new_version, stock_code, signal_date),
            )
        else:
            new_version = 1
            conn.execute(
                """
                INSERT INTO predictions (stock_code, signal_date, predicted_pct, confidence, features_summary, version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (stock_code, signal_date, predicted_pct, confidence, features_summary, new_version),
            )

        conn.commit()
        row = conn.execute(
            "SELECT * FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()
        conn.close()
        return [dict(row)] if row else [{"status": "stored"}]

    except Exception as e:
        return [{"error": str(e), "tool": "store_prediction", "params": {"stock_code": stock_code, "signal_date": signal_date}}]


@mcp.tool()
def get_predictions(
    stock_code: str = None,
    signal_date: str = None,
    limit: int = 30,
) -> list[dict]:
    """
    Query prediction records with optional filters.

    Args:
        stock_code: Filter by exact 6-digit stock code.
        signal_date: Filter by exact YYYYMMDD date.
        limit: Maximum results (default 30, max 500).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM predictions WHERE 1=1"
        params = []

        if stock_code:
            if not _validate_stock_code(stock_code):
                conn.close()
                return [{"error": f"Invalid stock code: {stock_code}", "tool": "get_predictions"}]
            query += " AND stock_code=?"
            params.append(stock_code)

        if signal_date:
            if not _validate_date(signal_date):
                conn.close()
                return [{"error": f"Invalid signal_date: {signal_date}", "tool": "get_predictions"}]
            query += " AND signal_date=?"
            params.append(signal_date)

        limit = min(limit, 500)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    except Exception as e:
        return [{"error": str(e), "tool": "get_predictions"}]


@mcp.tool()
def record_actual(
    stock_code: str,
    signal_date: str,
    actual_pct: float,
) -> list[dict]:
    """
    Record actual observed % change for a prediction. Auto-computes error.

    Args:
        stock_code: 6-digit stock code.
        signal_date: YYYYMMDD (the signal date, not the trade date).
        actual_pct: Actual % change from signal date to next trading day.
    """
    try:
        if not _validate_stock_code(stock_code):
            return [{"error": f"Invalid stock code: {stock_code}", "tool": "record_actual"}]

        if not _validate_date(signal_date):
            return [{"error": f"Invalid signal_date: {signal_date}", "tool": "record_actual"}]

        if not isinstance(actual_pct, (int, float)):
            return [{"error": f"actual_pct must be numeric, got {actual_pct}", "tool": "record_actual"}]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()

        if not row:
            conn.close()
            return [{"error": f"No prediction found for {stock_code} on {signal_date}", "tool": "record_actual"}]

        error = actual_pct - row["predicted_pct"]
        conn.execute(
            """
            UPDATE predictions
            SET actual_pct=?, error=?, verified_at=datetime('now')
            WHERE stock_code=? AND signal_date=?
            """,
            (actual_pct, error, stock_code, signal_date),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()
        conn.close()
        return [dict(updated)] if updated else []

    except Exception as e:
        return [{"error": str(e), "tool": "record_actual", "params": {"stock_code": stock_code, "signal_date": signal_date}}]


@mcp.tool()
def batch_record_actual(
    signal_date: str,
    actuals_list: list[dict],
) -> list[dict]:
    """
    Batch record actuals for multiple stocks.

    Args:
        signal_date: YYYYMMDD.
        actuals_list: [{"stock_code": "000001", "actual_pct": 1.5}, ...].
    """
    try:
        if not _validate_date(signal_date):
            return [{"error": f"Invalid signal_date: {signal_date}", "tool": "batch_record_actual"}]

        if not isinstance(actuals_list, list):
            return [{"error": "actuals_list must be a list of dicts", "tool": "batch_record_actual"}]

        results = []
        for item in actuals_list:
            if not isinstance(item, dict):
                results.append({"error": f"Invalid item: {item}", "tool": "batch_record_actual"})
                continue
            code = item.get("stock_code")
            actual = item.get("actual_pct")
            if not code or actual is None:
                results.append({"error": f"Missing stock_code or actual_pct in {item}", "tool": "batch_record_actual"})
                continue
            result = record_actual(code, signal_date, actual)
            results.extend(result)

        return results

    except Exception as e:
        return [{"error": str(e), "tool": "batch_record_actual"}]


@mcp.tool()
def get_accuracy_report(
    stock_code: str = None,
    days: int = 30,
) -> list[dict]:
    """
    Compute accuracy metrics over the specified window.

    Args:
        stock_code: Optional filter (if None, all stocks).
        days: Lookback window (default 30, max 365).
    """
    try:
        if days < 1 or days > 365:
            return [{"error": "days must be between 1 and 365", "tool": "get_accuracy_report"}]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y%m%d")

        query = "SELECT * FROM predictions WHERE verified_at IS NOT NULL AND signal_date >= ?"
        params = [cutoff_str]

        if stock_code:
            if not _validate_stock_code(stock_code):
                conn.close()
                return [{"error": f"Invalid stock code: {stock_code}", "tool": "get_accuracy_report"}]
            query += " AND stock_code=?"
            params.append(stock_code)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        if not rows:
            return [{"mae": 0.0, "hit_rate": 0.0, "bias": 0.0, "total": 0, "verified": 0}]

        errors = [r["error"] for r in rows]
        predicted_pcts = [r["predicted_pct"] for r in rows]
        mae = sum(abs(e) for e in errors) / len(errors)
        bias = sum(errors) / len(errors)
        hit_rate = sum(1 for i in range(len(errors)) if (errors[i] > 0) == (predicted_pcts[i] > 0)) / len(errors)

        total_query = "SELECT COUNT(*) as cnt FROM predictions WHERE signal_date >= ?"
        total_params = [cutoff_str]
        if stock_code:
            total_query += " AND stock_code=?"
            total_params.append(stock_code)

        return [{
            "mae": round(mae, 4),
            "hit_rate": round(hit_rate, 4),
            "bias": round(bias, 4),
            "total": len(rows),
            "verified": len(rows),
        }]

    except Exception as e:
        return [{"error": str(e), "tool": "get_accuracy_report"}]


@mcp.tool()
def get_error_analysis(days: int = 30) -> list[dict]:
    """
    Analyze error patterns by stock, time period, and direction.

    Returns list of error pattern dicts:
    - by_stock: top 10 stocks by |error|
    - by_direction: overestimation vs underestimation counts
    - by_magnitude: small (<1%), medium (1-3%), large (>3%) error distribution
    """
    try:
        if days < 1 or days > 365:
            return [{"error": "days must be between 1 and 365", "tool": "get_error_analysis"}]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y%m%d")

        rows = conn.execute(
            "SELECT * FROM predictions WHERE verified_at IS NOT NULL AND signal_date >= ?",
            (cutoff_str,),
        ).fetchall()
        conn.close()

        if not rows:
            return [{
                "by_stock": [],
                "by_direction": {"overestimate": 0, "underestimate": 0},
                "by_magnitude": {"small": 0, "medium": 0, "large": 0},
            }]

        by_stock = {}
        overestimate = 0
        underestimate = 0
        small = 0
        medium = 0
        large = 0

        for r in rows:
            code = r["stock_code"]
            err = r["error"]
            abs_err = abs(err)

            if code not in by_stock or abs_err > by_stock[code]["abs_error"]:
                by_stock[code] = {"stock_code": code, "abs_error": abs_err, "error": err}

            if err > 0:
                overestimate += 1
            else:
                underestimate += 1

            if abs_err < 1:
                small += 1
            elif abs_err <= 3:
                medium += 1
            else:
                large += 1

        by_stock_list = sorted(by_stock.values(), key=lambda x: x["abs_error"], reverse=True)[:10]
        for item in by_stock_list:
            del item["abs_error"]

        return [{
            "by_stock": by_stock_list,
            "by_direction": {"overestimate": overestimate, "underestimate": underestimate},
            "by_magnitude": {"small": small, "medium": medium, "large": large},
        }]

    except Exception as e:
        return [{"error": str(e), "tool": "get_error_analysis"}]


@mcp.tool()
def get_next_trading_day(from_date: str = None) -> list[dict]:
    """
    Get next trading day after from_date. Uses built-in Chinese trading calendar.

    Args:
        from_date: YYYYMMDD (default: today).
    """
    try:
        if from_date is None:
            from_date = datetime.now().strftime("%Y%m%d")
        elif not _validate_date(from_date):
            return [{"error": f"Invalid from_date: {from_date}", "tool": "get_next_trading_day"}]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT trade_date FROM trading_calendar WHERE trade_date > ? AND is_trading_day=1 ORDER BY trade_date ASC LIMIT 1",
            (from_date,),
        ).fetchone()
        conn.close()

        if row:
            return [{"next_trading_day": row["trade_date"], "from_date": from_date}]
        return [{"next_trading_day": None, "from_date": from_date, "error": "No trading day found"}]

    except Exception as e:
        return [{"error": str(e), "tool": "get_next_trading_day"}]


mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8003)