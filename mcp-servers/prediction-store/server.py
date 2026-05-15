"""
Prediction Store MCP Server — Stock prediction persistence and accuracy tracking
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8003
"""

import logging
import math
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import akshare as ak

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

        CREATE TABLE IF NOT EXISTS strategy_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            note_date   TEXT NOT NULL,
            note_type   TEXT NOT NULL DEFAULT 'post_analysis',
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_strategy_notes_date ON strategy_notes(note_date);

        CREATE TABLE IF NOT EXISTS factor_analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_date   TEXT NOT NULL,
            factor_name     TEXT NOT NULL,
            stock_code      TEXT,
            ic              REAL,
            rank_ic         REAL,
            icir            REAL,
            hit_rate        REAL,
            sample_size     INTEGER,
            period_days     INTEGER DEFAULT 1,
            mean_ic         REAL,
            std_ic          REAL,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_factor_analyses_date ON factor_analyses(analysis_date);
        CREATE INDEX IF NOT EXISTS idx_factor_analyses_factor ON factor_analyses(factor_name);
        CREATE INDEX IF NOT EXISTS idx_factor_analyses_stock ON factor_analyses(stock_code);
        """
    )
    conn.commit()
    conn.close()
    _seed_trading_calendar()


def _seed_trading_calendar():
    """Pre-populate 2024-2026 Chinese trading days."""
    holidays_2024 = {
        "20240101",
        "20240102",
        "20240103",  # New Year
        "20240210",
        "20240211",
        "20240212",
        "20240213",
        "20240214",
        "20240215",
        "20240216",
        "20240217",  # Spring Festival
        "20240404",
        "20240405",
        "20240406",  # Qingming
        "20240501",
        "20240502",
        "20240503",
        "20240504",
        "20240505",  # Labor Day
        "20240610",
        "20240611",
        "20240612",  # Dragon Boat
        "20240915",
        "20240916",
        "20240917",  # Mid-Autumn
        "20241001",
        "20241002",
        "20241003",
        "20241004",
        "20241005",
        "20241006",
        "20241007",  # National Day
    }
    holidays_2025 = {
        "20250101",
        "20250128",
        "20250129",
        "20250130",
        "20250131",
        "20250201",
        "20250202",
        "20250203",
        "20250204",  # Spring Festival
        "20250404",
        "20250405",
        "20250406",  # Qingming
        "20250501",
        "20250502",
        "20250503",
        "20250504",
        "20250505",  # Labor Day
        "20250531",
        "20250601",
        "20250602",  # Dragon Boat
        "20251001",
        "20251002",
        "20251003",
        "20251004",
        "20251005",
        "20251006",
        "20251007",  # National Day
    }
    holidays_2026 = {
        "20260101",
        "20260117",
        "20260118",
        "20260119",
        "20260120",
        "20260121",
        "20260122",
        "20260123",
        "20260124",
        "20260125",
        "20260126",
        "20260127",  # Spring Festival
        "20260403",
        "20260404",
        "20260405",  # Qingming
        "20260501",
        "20260502",
        "20260503",
        "20260504",
        "20260505",  # Labor Day
        "20260620",
        "20260621",
        "20260622",  # Dragon Boat
        "20261001",
        "20261002",
        "20261003",
        "20261004",
        "20261005",
        "20261006",
        "20261007",  # National Day
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
            return [
                {
                    "error": "action must be 'add', 'remove', or 'list'",
                    "tool": "manage_watchlist",
                    "params": {"action": action},
                }
            ]

        if not stock_codes:
            conn.close()
            return [
                {
                    "error": "stock_codes required for add/remove",
                    "tool": "manage_watchlist",
                    "params": {"action": action},
                }
            ]

        for code in stock_codes:
            if not _validate_stock_code(code):
                conn.close()
                return [
                    {
                        "error": f"Invalid stock code: {code} (must be 6 digits)",
                        "tool": "manage_watchlist",
                        "params": {"code": code},
                    }
                ]

        results = []
        if action == "add":
            existing = conn.execute(
                "SELECT COUNT(*) as cnt FROM watchlist WHERE is_active=1"
            ).fetchone()["cnt"]
            if existing + len(stock_codes) > 20:
                conn.close()
                return [
                    {
                        "error": f"Watchlist limit exceeded (max 20). Current: {existing}, Adding: {len(stock_codes)}",
                        "tool": "manage_watchlist",
                    }
                ]

            for code in stock_codes:
                cursor = conn.execute(
                    "SELECT id, is_active FROM watchlist WHERE stock_code=?",
                    (code,),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    if existing_row["is_active"] == 1:
                        results.append(
                            {
                                "stock_code": code,
                                "status": "already_exists",
                                "id": existing_row["id"],
                            }
                        )
                    else:
                        conn.execute(
                            "UPDATE watchlist SET is_active=1 WHERE stock_code=?",
                            (code,),
                        )
                        results.append(
                            {
                                "stock_code": code,
                                "status": "reactivated",
                                "id": existing_row["id"],
                            }
                        )
                else:
                    cursor = conn.execute(
                        "INSERT INTO watchlist (stock_code) VALUES (?)",
                        (code,),
                    )
                    results.append(
                        {"stock_code": code, "status": "added", "id": cursor.lastrowid}
                    )

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
        return [
            {"error": str(e), "tool": "manage_watchlist", "params": {"action": action}}
        ]


@mcp.tool()
def store_prediction(
    stock_code: str,
    signal_date: str,
    predicted_pct: float,
    confidence: float,
    features_summary: str = "",
    baseline: bool = False,
) -> list[dict]:
    """
    Store or update a prediction. Uses upsert on (stock_code, signal_date).

    Args:
        stock_code: 6-digit stock code.
        signal_date: YYYYMMDD.
        predicted_pct: Predicted % change, must be in [-30, 30].
        confidence: Confidence level 0-1.
        features_summary: JSON string of key technical indicators.
        baseline: Mark as cold-start baseline prediction (first 20 predictions).
    """
    try:
        if not _validate_stock_code(stock_code):
            return [
                {
                    "error": f"Invalid stock code: {stock_code} (must be 6 digits)",
                    "tool": "store_prediction",
                }
            ]

        if not _validate_date(signal_date):
            return [
                {
                    "error": f"Invalid signal_date: {signal_date} (must be YYYYMMDD)",
                    "tool": "store_prediction",
                }
            ]

        if not isinstance(predicted_pct, (int, float)) or abs(predicted_pct) > 30:
            return [
                {
                    "error": f"predicted_pct must be in [-30, 30], got {predicted_pct}",
                    "tool": "store_prediction",
                }
            ]

        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            return [
                {
                    "error": f"confidence must be in [0, 1], got {confidence}",
                    "tool": "store_prediction",
                }
            ]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        existing = conn.execute(
            "SELECT version FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()

        baseline_flag = 1 if baseline else 0

        if existing:
            new_version = existing["version"] + 1
            conn.execute(
                """
                UPDATE predictions
                SET predicted_pct=?, confidence=?, features_summary=?, version=?,
                    baseline=?, created_at=datetime('now')
                WHERE stock_code=? AND signal_date=?
                """,
                (
                    predicted_pct,
                    confidence,
                    features_summary,
                    new_version,
                    baseline_flag,
                    stock_code,
                    signal_date,
                ),
            )
        else:
            new_version = 1
            conn.execute(
                """
                INSERT INTO predictions (stock_code, signal_date, predicted_pct, confidence, features_summary, version, baseline)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stock_code,
                    signal_date,
                    predicted_pct,
                    confidence,
                    features_summary,
                    new_version,
                    baseline_flag,
                ),
            )

        conn.commit()
        row = conn.execute(
            "SELECT * FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()
        conn.close()
        return [dict(row)] if row else [{"status": "stored"}]

    except Exception as e:
        return [
            {
                "error": str(e),
                "tool": "store_prediction",
                "params": {"stock_code": stock_code, "signal_date": signal_date},
            }
        ]


@mcp.tool()
def get_predictions(
    stock_code: str = None,
    signal_date: str = None,
    verified: bool = None,
    limit: int = 30,
) -> list[dict]:
    """
    Query prediction records with optional filters.

    Args:
        stock_code: Filter by exact 6-digit stock code.
        signal_date: Filter by exact YYYYMMDD date.
        verified: If True, return only verified. If False, return only pending (unverified).
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
                return [
                    {
                        "error": f"Invalid stock code: {stock_code}",
                        "tool": "get_predictions",
                    }
                ]
            query += " AND stock_code=?"
            params.append(stock_code)

        if signal_date:
            if not _validate_date(signal_date):
                conn.close()
                return [
                    {
                        "error": f"Invalid signal_date: {signal_date}",
                        "tool": "get_predictions",
                    }
                ]
            query += " AND signal_date=?"
            params.append(signal_date)

        if verified is True:
            query += " AND verified_at IS NOT NULL"
        elif verified is False:
            query += " AND verified_at IS NULL"

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
            return [
                {"error": f"Invalid stock code: {stock_code}", "tool": "record_actual"}
            ]

        if not _validate_date(signal_date):
            return [
                {
                    "error": f"Invalid signal_date: {signal_date}",
                    "tool": "record_actual",
                }
            ]

        if not isinstance(actual_pct, (int, float)):
            return [
                {
                    "error": f"actual_pct must be numeric, got {actual_pct}",
                    "tool": "record_actual",
                }
            ]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM predictions WHERE stock_code=? AND signal_date=?",
            (stock_code, signal_date),
        ).fetchone()

        if not row:
            conn.close()
            return [
                {
                    "error": f"No prediction found for {stock_code} on {signal_date}",
                    "tool": "record_actual",
                }
            ]

        error = round(actual_pct - row["predicted_pct"], 4)
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
        return [
            {
                "error": str(e),
                "tool": "record_actual",
                "params": {"stock_code": stock_code, "signal_date": signal_date},
            }
        ]


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
            return [
                {
                    "error": f"Invalid signal_date: {signal_date}",
                    "tool": "batch_record_actual",
                }
            ]

        if not isinstance(actuals_list, list):
            return [
                {
                    "error": "actuals_list must be a list of dicts",
                    "tool": "batch_record_actual",
                }
            ]

        results = []
        for item in actuals_list:
            if not isinstance(item, dict):
                results.append(
                    {"error": f"Invalid item: {item}", "tool": "batch_record_actual"}
                )
                continue
            code = item.get("stock_code")
            actual = item.get("actual_pct")
            if not code or actual is None:
                results.append(
                    {
                        "error": f"Missing stock_code or actual_pct in {item}",
                        "tool": "batch_record_actual",
                    }
                )
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
            return [
                {
                    "error": "days must be between 1 and 365",
                    "tool": "get_accuracy_report",
                }
            ]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y%m%d")

        query = "SELECT * FROM predictions WHERE verified_at IS NOT NULL AND signal_date >= ?"
        params = [cutoff_str]

        if stock_code:
            if not _validate_stock_code(stock_code):
                conn.close()
                return [
                    {
                        "error": f"Invalid stock code: {stock_code}",
                        "tool": "get_accuracy_report",
                    }
                ]
            query += " AND stock_code=?"
            params.append(stock_code)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        if not rows:
            return [
                {"mae": 0.0, "hit_rate": 0.0, "bias": 0.0, "total": 0, "verified": 0}
            ]

        errors = [r["error"] for r in rows]
        predicted_pcts = [r["predicted_pct"] for r in rows]
        mae = sum(abs(e) for e in errors) / len(errors)
        bias = sum(errors) / len(errors)
        hit_rate = sum(
            1 for i in range(len(errors)) if (errors[i] > 0) == (predicted_pcts[i] > 0)
        ) / len(errors)

        total_query = "SELECT COUNT(*) as cnt FROM predictions WHERE signal_date >= ?"
        total_params = [cutoff_str]
        if stock_code:
            total_query += " AND stock_code=?"
            total_params.append(stock_code)

        return [
            {
                "mae": round(mae, 4),
                "hit_rate": round(hit_rate, 4),
                "bias": round(bias, 4),
                "total": len(rows),
                "verified": len(rows),
            }
        ]

    except Exception as e:
        return [{"error": str(e), "tool": "get_accuracy_report"}]


@mcp.tool()
def get_error_analysis(days: int = 30) -> list[dict]:
    """
    Analyze error patterns by stock, time period, and direction.

    Returns list of error pattern dicts:
    - by_stock: top 10 stocks by mean absolute error
    - by_direction: overestimation vs underestimation counts
    - by_magnitude: small (<1%), medium (1-3%), large (>3%) error distribution
    - by_confidence: MAE broken down by confidence level
    """
    try:
        if days < 1 or days > 365:
            return [
                {
                    "error": "days must be between 1 and 365",
                    "tool": "get_error_analysis",
                }
            ]

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
            return [
                {
                    "by_stock": [],
                    "by_direction": {"overestimate": 0, "underestimate": 0},
                    "by_magnitude": {"small": 0, "medium": 0, "large": 0},
                    "by_confidence": {
                        "high": {"count": 0, "mae": 0},
                        "medium": {"count": 0, "mae": 0},
                        "low": {"count": 0, "mae": 0},
                    },
                }
            ]

        by_stock = {}
        overestimate = 0
        underestimate = 0
        small = 0
        medium = 0
        large = 0
        conf_high = []
        conf_med = []
        conf_low = []

        for r in rows:
            code = r["stock_code"]
            err = r["error"]
            abs_err = abs(err)

            if code not in by_stock:
                by_stock[code] = {"stock_code": code, "errors": []}
            by_stock[code]["errors"].append(err)

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

            conf = r["confidence"]
            if conf >= 0.7:
                conf_high.append(abs_err)
            elif conf >= 0.4:
                conf_med.append(abs_err)
            else:
                conf_low.append(abs_err)

        by_stock_list = []
        for code in by_stock:
            errs = by_stock[code]["errors"]
            by_stock_list.append(
                {
                    "stock_code": code,
                    "mean_abs_error": round(sum(abs(e) for e in errs) / len(errs), 4),
                    "mean_error": round(sum(errs) / len(errs), 4),
                    "count": len(errs),
                }
            )
        by_stock_list.sort(key=lambda x: x["mean_abs_error"], reverse=True)
        by_stock_list = by_stock_list[:10]

        return [
            {
                "by_stock": by_stock_list,
                "by_direction": {
                    "overestimate": overestimate,
                    "underestimate": underestimate,
                },
                "by_magnitude": {"small": small, "medium": medium, "large": large},
                "by_confidence": {
                    "high": {
                        "count": len(conf_high),
                        "mae": round(sum(conf_high) / len(conf_high), 4),
                    }
                    if conf_high
                    else {"count": 0, "mae": 0},
                    "medium": {
                        "count": len(conf_med),
                        "mae": round(sum(conf_med) / len(conf_med), 4),
                    }
                    if conf_med
                    else {"count": 0, "mae": 0},
                    "low": {
                        "count": len(conf_low),
                        "mae": round(sum(conf_low) / len(conf_low), 4),
                    }
                    if conf_low
                    else {"count": 0, "mae": 0},
                },
            }
        ]

    except Exception as e:
        return [{"error": str(e), "tool": "get_error_analysis"}]


@mcp.tool()
def get_accuracy_trend(days: int = 30, bucket_days: int = 7) -> list[dict]:
    """
    Compute MAE trend over time, bucketed by period. Shows whether accuracy
    is improving, stable, or degrading.

    Args:
        days: Total lookback window (default 30, max 365).
        bucket_days: Size of each time bucket in days (default 7).
    """
    try:
        if days < 1 or days > 365:
            return [
                {
                    "error": "days must be between 1 and 365",
                    "tool": "get_accuracy_trend",
                }
            ]
        if bucket_days < 1:
            return [{"error": "bucket_days must be >= 1", "tool": "get_accuracy_trend"}]

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
            return [{"buckets": [], "trend": "no_data"}]

        buckets = {}
        for r in rows:
            sig_date = datetime.strptime(r["signal_date"], "%Y%m%d")
            days_ago = (datetime.now() - sig_date).days
            bucket_idx = days_ago // bucket_days
            if bucket_idx not in buckets:
                bucket_start = sig_date - timedelta(days=days_ago % bucket_days)
                bucket_end = bucket_start + timedelta(days=bucket_days - 1)
                buckets[bucket_idx] = {
                    "period_start": bucket_start.strftime("%Y%m%d"),
                    "period_end": bucket_end.strftime("%Y%m%d"),
                    "errors": [],
                    "predicted_pcts": [],
                }
            buckets[bucket_idx]["errors"].append(r["error"])
            buckets[bucket_idx]["predicted_pcts"].append(r["predicted_pct"])

        bucket_list = []
        for idx in sorted(buckets.keys()):
            b = buckets[idx]
            errs = b["errors"]
            preds = b["predicted_pcts"]
            mae = sum(abs(e) for e in errs) / len(errs)
            hit = sum(
                1 for i in range(len(errs)) if (errs[i] > 0) == (preds[i] > 0)
            ) / len(errs)
            bucket_list.append(
                {
                    "period_start": b["period_start"],
                    "period_end": b["period_end"],
                    "mae": round(mae, 4),
                    "hit_rate": round(hit, 4),
                    "count": len(errs),
                }
            )

        # Determine trend from last 2 buckets (most recent first)
        trend = "stable"
        if len(bucket_list) >= 2:
            recent_mae = bucket_list[0]["mae"]
            older_mae = bucket_list[1]["mae"]
            if recent_mae < older_mae * 0.8:
                trend = "improving"
            elif recent_mae > older_mae * 1.2:
                trend = "degrading"

        return [{"buckets": bucket_list, "trend": trend}]

    except Exception as e:
        return [{"error": str(e), "tool": "get_accuracy_trend"}]


def _sma(series: list[float], period: int) -> float:
    """Simple moving average of the last `period` values."""
    if len(series) < period:
        return float("nan")
    return sum(series[-period:]) / period


def _ema(series: list[float], period: int) -> float:
    """Exponential moving average over entire series."""
    if not series:
        return float("nan")
    k = 2 / (period + 1)
    ema_val = series[0]
    for price in series[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def _compute_indicators_from_ohlcv(records: list[dict]) -> dict:
    """Compute technical indicators from OHLCV records."""
    closes = []
    volumes = []
    for r in records:
        c = r.get("收盘")
        v = r.get("成交量")
        try:
            closes.append(float(c) if c is not None and c != "NaN" else None)
        except (ValueError, TypeError):
            closes.append(None)
        try:
            volumes.append(float(v) if v is not None and v != "NaN" else None)
        except (ValueError, TypeError):
            volumes.append(None)

    closes = [c for c in closes if c is not None]
    volumes = [v for v in volumes if v is not None]

    if len(closes) < 5:
        return {"error": f"Need at least 5 valid close prices, got {len(closes)}"}

    result = {
        "latest_close": closes[-1],
        "latest_date": records[-1].get("日期", ""),
        "data_points_used": len(closes),
    }

    # MA
    result["ma5"] = round(_sma(closes, 5), 4)
    result["ma10"] = round(_sma(closes, 10), 4) if len(closes) >= 10 else "NaN"
    result["ma20"] = round(_sma(closes, 20), 4) if len(closes) >= 20 else "NaN"

    # RSI(14) Wilder smoothing
    if len(closes) >= 15:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14
        for i in range(14, len(deltas)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        if avg_loss == 0:
            result["rsi14"] = 100.0
        else:
            rs = avg_gain / avg_loss
            result["rsi14"] = round(100 - 100 / (1 + rs), 2)
    else:
        result["rsi14"] = "NaN"

    # MACD (EMA12, EMA26, Signal 9)
    if len(closes) >= 26:
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        dif = ema12 - ema26
        # Compute DEA as EMA9 of DIF series
        dif_series = []
        ema12_s = closes[0]
        ema26_s = closes[0]
        for p in closes[1:]:
            ema12_s = p * (2 / 13) + ema12_s * (1 - 2 / 13)
            ema26_s = p * (2 / 27) + ema26_s * (1 - 2 / 27)
            dif_series.append(ema12_s - ema26_s)
        if len(dif_series) >= 9:
            dea = _ema(dif_series, 9)
        else:
            dea = float("nan")
        hist = 2 * (dif - dea)
        result["macd_dif"] = round(dif, 4)
        result["macd_dea"] = round(dea, 4) if not math.isnan(dea) else "NaN"
        result["macd_hist"] = round(hist, 4) if not math.isnan(hist) else "NaN"
    else:
        result["macd_dif"] = "NaN"
        result["macd_dea"] = "NaN"
        result["macd_hist"] = "NaN"

    # Bollinger Bands (MA20 ± 2σ)
    if len(closes) >= 20:
        bb_mid = _sma(closes, 20)
        std = math.sqrt(sum((c - bb_mid) ** 2 for c in closes[-20:]) / 20)
        result["boll_upper"] = round(bb_mid + 2 * std, 4)
        result["boll_middle"] = round(bb_mid, 4)
        result["boll_lower"] = round(bb_mid - 2 * std, 4)
    else:
        result["boll_upper"] = "NaN"
        result["boll_middle"] = "NaN"
        result["boll_lower"] = "NaN"

    # Volume Ratio
    if len(volumes) >= 5:
        vol_avg5 = (
            sum(volumes[-6:-1]) / 5
            if len(volumes) >= 6
            else sum(volumes[:-1]) / (len(volumes) - 1)
        )
        result["vol_ratio"] = (
            round(volumes[-1] / vol_avg5, 4) if vol_avg5 > 0 else "NaN"
        )
    else:
        result["vol_ratio"] = "NaN"

    return result


@mcp.tool()
def compute_indicators(ohlcv_data: list[dict]) -> list[dict]:
    """
    Compute technical indicators from OHLCV data. Returns MA, RSI, MACD,
    Bollinger Bands, and Volume Ratio.

    Args:
        ohlcv_data: List of OHLCV dicts from stock_zh_a_hist.
                    Requires keys: 日期, 收盘, 成交量.
                    Minimum 5 records for basic indicators, 26 for full set.
    """
    try:
        if not isinstance(ohlcv_data, list) or len(ohlcv_data) < 5:
            return [
                {
                    "error": "ohlcv_data must be a list with at least 5 records",
                    "tool": "compute_indicators",
                }
            ]
        result = _compute_indicators_from_ohlcv(ohlcv_data)
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "compute_indicators"}]


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
            return [
                {
                    "error": f"Invalid from_date: {from_date}",
                    "tool": "get_next_trading_day",
                }
            ]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT trade_date FROM trading_calendar WHERE trade_date > ? AND is_trading_day=1 ORDER BY trade_date ASC LIMIT 1",
            (from_date,),
        ).fetchone()
        conn.close()

        if row:
            return [{"next_trading_day": row["trade_date"], "from_date": from_date}]
        return [
            {
                "next_trading_day": None,
                "from_date": from_date,
                "error": "No trading day found",
            }
        ]

    except Exception as e:
        return [{"error": str(e), "tool": "get_next_trading_day"}]


def _get_signal_and_next_close(
    stock_code: str, signal_date: str, next_td: str
) -> tuple[float, float] | None:
    """Fetch signal_date close and next_trading_day close. Tries AKShare first, then Tencent fallback."""
    try:
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=signal_date,
            end_date=next_td,
            adjust="qfq",
        )
        if df is not None and not df.empty and len(df) >= 2:
            return float(df.iloc[0]["收盘"]), float(df.iloc[1]["收盘"])
    except Exception:
        pass

    # Tencent fallback
    try:
        if stock_code.startswith(("0", "3")):
            market = "sz"
        elif stock_code.startswith("6"):
            market = "sh"
        elif stock_code.startswith("8"):
            market = "bj"
        else:
            market = "sz"

        sd_fmt = f"{signal_date[:4]}-{signal_date[4:6]}-{signal_date[6:8]}"
        nt_fmt = f"{next_td[:4]}-{next_td[4:6]}-{next_td[6:8]}"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={market}{stock_code},day,{sd_fmt},{nt_fmt},10,qfq"
        import requests as _req

        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        text = resp.text
        if text.startswith("kline_dayqfq="):
            text = text[len("kline_dayqfq=") :]
        data = json.loads(text)
        key = f"{market}{stock_code}"
        qfqday = data.get("data", {}).get(key, {}).get("qfqday", [])

        # If we only got next_trading_day but not signal_date, fetch wider range
        if len(qfqday) < 2:
            # Fetch last 15 days from signal_date to ensure we cover both dates
            from datetime import timedelta as _td

            sd_dt = datetime.strptime(signal_date, "%Y%m%d")
            earlier = (sd_dt - _td(days=15)).strftime("%Y-%m-%d")
            later = (datetime.strptime(next_td, "%Y%m%d")).strftime("%Y-%m-%d")
            url2 = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={market}{stock_code},day,{earlier},{later},30,qfq"
            resp2 = _req.get(url2, timeout=10)
            text2 = resp2.text
            if text2.startswith("kline_dayqfq="):
                text2 = text2[len("kline_dayqfq=") :]
            data2 = json.loads(text2)
            qfqday_all = data2.get("data", {}).get(key, {}).get("qfqday", [])
            # Filter to only signal_date and next_td
            qfqday = [r for r in qfqday_all if r[0] in (sd_fmt, nt_fmt)]

        if len(qfqday) >= 2:
            return float(qfqday[0][2]), float(qfqday[1][2])
    except Exception:
        pass

    return None


@mcp.tool()
def auto_verify_predictions(signal_date: str = None) -> list[dict]:
    """
    Auto-verify unverified predictions by fetching actual prices from AKShare.
    Finds predictions where verified_at IS NULL, fetches OHLCV data,
    computes actual_pct, and records the actuals.

    Args:
        signal_date: YYYYMMDD. If provided, only verify predictions for this date.
                     If None, verify all unverified predictions.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM predictions WHERE verified_at IS NULL"
        params = []
        if signal_date:
            if not _validate_date(signal_date):
                conn.close()
                return [
                    {
                        "error": f"Invalid signal_date: {signal_date}",
                        "tool": "auto_verify_predictions",
                    }
                ]
            query += " AND signal_date=?"
            params.append(signal_date)
        rows = conn.execute(query, params).fetchall()
        conn.close()

        if not rows:
            return [{"status": "no_unverified_predictions", "count": 0}]

        results = []
        for r in rows:
            code = r["stock_code"]
            sig_date = r["signal_date"]

            # Get next trading day
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.row_factory = sqlite3.Row
            next_td_row = conn2.execute(
                "SELECT trade_date FROM trading_calendar WHERE trade_date > ? AND is_trading_day=1 ORDER BY trade_date ASC LIMIT 1",
                (sig_date,),
            ).fetchone()
            conn2.close()

            if not next_td_row:
                results.append(
                    {
                        "stock_code": code,
                        "signal_date": sig_date,
                        "status": "no_next_trading_day",
                    }
                )
                continue

            next_td = next_td_row["trade_date"]
            prices = _get_signal_and_next_close(code, sig_date, next_td)

            if prices is None:
                results.append(
                    {
                        "stock_code": code,
                        "signal_date": sig_date,
                        "status": "price_data_unavailable",
                        "next_trading_day": next_td,
                    }
                )
                continue

            signal_close, next_close = prices
            actual_pct = round((next_close - signal_close) / signal_close * 100, 4)
            record_actual(code, sig_date, actual_pct)
            results.append(
                {
                    "stock_code": code,
                    "signal_date": sig_date,
                    "next_trading_day": next_td,
                    "signal_close": signal_close,
                    "next_close": next_close,
                    "actual_pct": actual_pct,
                    "predicted_pct": r["predicted_pct"],
                    "error": round(actual_pct - r["predicted_pct"], 4),
                    "status": "verified",
                }
            )

        return results

    except Exception as e:
        return [{"error": str(e), "tool": "auto_verify_predictions"}]


@mcp.tool()
def manage_strategy_notes(
    action: str,
    note_date: str = None,
    content: str = None,
    note_type: str = "post_analysis",
    note_id: int = None,
    limit: int = 10,
) -> list[dict]:
    """
    Manage persistent strategy adjustment notes that survive between sessions.

    Args:
        action: One of "add", "list", "recent", "delete".
        note_date: YYYYMMDD. Required for "add". Optional filter for "list".
        content: Note text. Required for "add".
        note_type: "post_analysis", "pre_prediction", or "manual".
        note_id: Note ID. Required for "delete".
        limit: Max notes to return (default 10, max 50).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        if action == "add":
            if not note_date or not _validate_date(note_date):
                conn.close()
                return [
                    {
                        "error": "note_date (YYYYMMDD) required for add",
                        "tool": "manage_strategy_notes",
                    }
                ]
            if not content:
                conn.close()
                return [
                    {
                        "error": "content required for add",
                        "tool": "manage_strategy_notes",
                    }
                ]
            cursor = conn.execute(
                "INSERT INTO strategy_notes (note_date, note_type, content) VALUES (?, ?, ?)",
                (note_date, note_type, content),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM strategy_notes WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
            conn.close()
            return [dict(row)]

        elif action == "list":
            query = "SELECT * FROM strategy_notes WHERE 1=1"
            params = []
            if note_date:
                query += " AND note_date=?"
                params.append(note_date)
            if note_type:
                query += " AND note_type=?"
                params.append(note_type)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(min(limit, 50))
            rows = conn.execute(query, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]

        elif action == "recent":
            rows = conn.execute(
                "SELECT * FROM strategy_notes ORDER BY created_at DESC LIMIT ?",
                (min(limit, 50),),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

        elif action == "delete":
            if not note_id:
                conn.close()
                return [
                    {
                        "error": "note_id required for delete",
                        "tool": "manage_strategy_notes",
                    }
                ]
            cursor = conn.execute("DELETE FROM strategy_notes WHERE id=?", (note_id,))
            conn.commit()
            conn.close()
            if cursor.rowcount > 0:
                return [{"status": "deleted", "note_id": note_id}]
            return [
                {"error": f"Note {note_id} not found", "tool": "manage_strategy_notes"}
            ]

        else:
            conn.close()
            return [
                {
                    "error": f"Unknown action: {action}. Use add/list/recent/delete.",
                    "tool": "manage_strategy_notes",
                }
            ]

    except Exception as e:
        return [{"error": str(e), "tool": "manage_strategy_notes"}]


def _pearson_corr(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient between two equal-length series."""
    n = len(x)
    if n < 2 or n != len(y):
        return float("nan")
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    if var_x == 0 or var_y == 0:
        return float("nan")
    return cov / math.sqrt(var_x * var_y)


def _rank_series(values: list[float]) -> list[float]:
    """Convert values to ranks (average rank for ties)."""
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _rank_corr(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation (Pearson on ranks)."""
    if len(x) != len(y) or len(x) < 2:
        return float("nan")
    return _pearson_corr(_rank_series(x), _rank_series(y))


def _linear_slope(values: list[float]) -> float:
    """Simple linear regression slope of values vs index."""
    n = len(values)
    if n < 2:
        return float("nan")
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    cov = sum((i - mean_x) * (values[i] - mean_y) for i in range(n))
    var_x = sum((i - mean_x) ** 2 for i in range(n))
    if var_x == 0:
        return float("nan")
    return cov / var_x


def _compute_factors_from_ohlcv(records: list[dict]) -> dict:
    """Compute 17 alpha factors from OHLCV records."""
    closes = []
    volumes = []
    highs = []
    lows = []
    dates = []
    for r in records:
        c = r.get("收盘")
        v = r.get("成交量")
        h = r.get("最高")
        lo = r.get("最低")
        try:
            closes.append(float(c) if c is not None and c != "NaN" else None)
        except (ValueError, TypeError):
            closes.append(None)
        try:
            volumes.append(float(v) if v is not None and v != "NaN" else None)
        except (ValueError, TypeError):
            volumes.append(None)
        try:
            highs.append(float(h) if h is not None and h != "NaN" else None)
        except (ValueError, TypeError):
            highs.append(None)
        try:
            lows.append(float(lo) if lo is not None and lo != "NaN" else None)
        except (ValueError, TypeError):
            lows.append(None)
        dates.append(r.get("日期", ""))

    closes = [c for c in closes if c is not None]
    volumes = [v for v in volumes if v is not None]
    highs = [h for h in highs if h is not None]
    lows = [lo for lo in lows if lo is not None]

    if len(closes) < 5:
        return {"error": f"Need at least 5 valid close prices, got {len(closes)}"}

    result = {
        "latest_date": dates[-1] if dates else "",
        "data_points_used": len(closes),
    }
    nan = float("nan")

    # --- Momentum Factors ---
    if len(closes) >= 6:
        result["mom_5d"] = round(closes[-1] / closes[-6] - 1, 6)
        result["reversal_5d"] = round(-result["mom_5d"], 6)
    else:
        result["mom_5d"] = nan
        result["reversal_5d"] = nan

    result["mom_10d"] = (
        round(closes[-1] / closes[-11] - 1, 6) if len(closes) >= 11 else nan
    )
    result["mom_20d"] = (
        round(closes[-1] / closes[-21] - 1, 6) if len(closes) >= 21 else nan
    )

    # --- Volatility Factors ---
    if len(closes) >= 21:
        log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        vol_20d = _sma([(r**2) for r in log_rets[-20:]], 20)
        vol_5d = _sma([(r**2) for r in log_rets[-5:]], 5)
        result["realized_vol_20d"] = (
            round(math.sqrt(vol_20d), 6) if vol_20d > 0 else 0.0
        )
        result["vol_ratio_5_20"] = (
            round(math.sqrt(vol_5d) / math.sqrt(vol_20d), 6) if vol_20d > 0 else nan
        )
    else:
        result["realized_vol_20d"] = nan
        result["vol_ratio_5_20"] = nan

    # --- Volume Factors ---
    if len(volumes) >= 10:
        vol_avg_5 = _sma(volumes[-5:], 5)
        vol_avg_prev5 = _sma(volumes[-10:-5], 5)
        result["vol_change_5d"] = (
            round(vol_avg_5 / vol_avg_prev5 - 1, 6) if vol_avg_prev5 > 0 else nan
        )
    else:
        result["vol_change_5d"] = nan

    if len(volumes) >= 20:
        vol_avg_10 = _sma(volumes[-10:], 10)
        vol_avg_prev10 = _sma(volumes[-20:-10], 10)
        result["vol_change_10d"] = (
            round(vol_avg_10 / vol_avg_prev10 - 1, 6) if vol_avg_prev10 > 0 else nan
        )
    else:
        result["vol_change_10d"] = nan

    if len(closes) >= 10 and len(volumes) >= 10:
        result["vol_price_corr_10d"] = round(
            _pearson_corr(closes[-10:], volumes[-10:]), 6
        )
    else:
        result["vol_price_corr_10d"] = nan

    # --- Technical Factors ---
    sma5 = _sma(closes, 5)
    result["ma5_deviation"] = round((closes[-1] - sma5) / sma5, 6) if sma5 > 0 else nan

    sma10 = _sma(closes, 10)
    result["ma10_deviation"] = (
        round((closes[-1] - sma10) / sma10, 6)
        if len(closes) >= 10 and sma10 > 0
        else nan
    )

    sma20 = _sma(closes, 20)
    result["ma20_deviation"] = (
        round((closes[-1] - sma20) / sma20, 6)
        if len(closes) >= 20 and sma20 > 0
        else nan
    )

    # RSI(14) deviation from 50
    if len(closes) >= 15:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14
        for i in range(14, len(deltas)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        result["rsi14_deviation"] = round(rsi - 50, 4)
    else:
        result["rsi14_deviation"] = nan

    # Bollinger position
    if len(closes) >= 20:
        std = math.sqrt(sum((c - sma20) ** 2 for c in closes[-20:]) / 20)
        boll_upper = sma20 + 2 * std
        boll_lower = sma20 - 2 * std
        if boll_upper != boll_lower:
            result["boll_position"] = round(
                (closes[-1] - boll_lower) / (boll_upper - boll_lower), 6
            )
        else:
            result["boll_position"] = 0.5
    else:
        result["boll_position"] = nan

    # --- Price Position Factor ---
    if len(closes) >= 20:
        low_20 = min(closes[-20:])
        high_20 = max(closes[-20:])
        result["high_low_position_20d"] = (
            round((closes[-1] - low_20) / (high_20 - low_20), 6)
            if high_20 != low_20
            else 0.5
        )
    else:
        result["high_low_position_20d"] = nan

    # --- Volume-Price Extended Factors ---
    # OBV slope (10d)
    if len(closes) >= 11 and len(volumes) >= 11:
        obv = [0.0]
        for i in range(1, min(len(closes), len(volumes))):
            if closes[i] > closes[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        result["obv_slope_10d"] = round(_linear_slope(obv[-10:]), 4)
    else:
        result["obv_slope_10d"] = nan

    # VWAP deviation (5d)
    if len(closes) >= 5 and len(highs) >= 5 and len(lows) >= 5 and len(volumes) >= 5:
        tp_vol_sum = 0.0
        vol_sum = 0.0
        for i in range(-5, 0):
            typical = (highs[i] + lows[i] + closes[i]) / 3
            tp_vol_sum += typical * volumes[i]
            vol_sum += volumes[i]
        vwap = tp_vol_sum / vol_sum if vol_sum > 0 else nan
        result["vwap_deviation"] = (
            round((closes[-1] - vwap) / vwap, 6)
            if vwap > 0 and not math.isnan(vwap)
            else nan
        )
    else:
        result["vwap_deviation"] = nan

    # Count non-NaN factors
    result["factor_count"] = sum(
        1
        for k, v in result.items()
        if k not in ("latest_date", "data_points_used", "factor_count")
        and isinstance(v, (int, float))
        and not math.isnan(v)
    )

    return result


@mcp.tool()
def compute_factors(ohlcv_data: list[dict], stock_code: str = "") -> list[dict]:
    """
    Compute 17 classic A-share alpha factors from OHLCV data.

    Factor categories: momentum, volatility, volume, technical, price position.

    Args:
        ohlcv_data: List of OHLCV dicts from stock_zh_a_hist.
                    Requires keys: 日期, 收盘, 最高, 最低, 成交量.
                    Minimum 21 records for full factor set.
        stock_code: Optional 6-digit stock code for labeling output.
    """
    try:
        if not isinstance(ohlcv_data, list) or len(ohlcv_data) < 5:
            return [
                {
                    "error": "ohlcv_data must be a list with at least 5 records",
                    "tool": "compute_factors",
                }
            ]
        result = _compute_factors_from_ohlcv(ohlcv_data)
        result["stock_code"] = stock_code
        # Convert NaN to "NaN" string for JSON serialization
        for k, v in result.items():
            if isinstance(v, float) and math.isnan(v):
                result[k] = "NaN"
        return [result]
    except Exception as e:
        return [{"error": str(e), "tool": "compute_factors"}]


@mcp.tool()
def test_factor_effectiveness(
    stock_codes: list[str],
    factor_names: list[str] = None,
    days: int = 60,
    period: int = 1,
    end_date: str = None,
) -> list[dict]:
    """
    Test factor effectiveness across stocks using IC, Rank IC, ICIR, and hit rate.

    For each factor, computes cross-sectional correlation between factor values
    and forward returns across all provided stocks on each trading day,
    then aggregates into IC statistics.

    Args:
        stock_codes: List of 6-digit stock codes to test (min 10, max 50).
        factor_names: Optional list of factor names to test. Tests all if None.
        days: Lookback window in calendar days (default 60, min 30, max 365).
        period: Forward return period in trading days (default 1).
        end_date: End date YYYYMMDD (default: today).
    """
    try:
        import time

        if not isinstance(stock_codes, list) or len(stock_codes) < 10:
            return [
                {
                    "error": "Need at least 10 stock codes for cross-sectional IC test",
                    "tool": "test_factor_effectiveness",
                }
            ]
        if len(stock_codes) > 50:
            return [
                {
                    "error": "Maximum 50 stock codes allowed",
                    "tool": "test_factor_effectiveness",
                }
            ]
        for code in stock_codes:
            if not _validate_stock_code(code):
                return [
                    {
                        "error": f"Invalid stock code: {code}",
                        "tool": "test_factor_effectiveness",
                    }
                ]

        if days < 30 or days > 365:
            return [
                {
                    "error": "days must be between 30 and 365",
                    "tool": "test_factor_effectiveness",
                }
            ]

        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        elif not _validate_date(end_date):
            return [
                {
                    "error": f"Invalid end_date: {end_date}",
                    "tool": "test_factor_effectiveness",
                }
            ]

        end_dt = datetime.strptime(end_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=days)
        start_date = start_dt.strftime("%Y%m%d")

        # Extend fetch range to cover lookback + forward period + buffer
        fetch_start = (start_dt - timedelta(days=90)).strftime("%Y%m%d")

        # Get trading calendar for the test period
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        trading_days = conn.execute(
            "SELECT trade_date FROM trading_calendar WHERE is_trading_day=1 AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date",
            (start_date, end_date),
        ).fetchall()
        conn.close()

        if len(trading_days) < 5:
            return [
                {
                    "error": f"Only {len(trading_days)} trading days in range, need at least 5",
                    "tool": "test_factor_effectiveness",
                }
            ]

        trading_day_list = [r["trade_date"] for r in trading_days]

        # Fetch OHLCV for all stocks (with rate limiting)
        stock_data = {}
        failed = []
        for code in stock_codes:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=fetch_start,
                    end_date=end_date,
                    adjust="qfq",
                )
                if df is not None and not df.empty:
                    records = df.to_dict("records")
                    stock_data[code] = records
                else:
                    failed.append(code)
                time.sleep(0.3)
            except Exception:
                failed.append(code)
                time.sleep(0.3)

        if len(stock_data) < 10:
            return [
                {
                    "error": f"Only fetched data for {len(stock_data)} stocks (need 10+). Failed: {failed}",
                    "tool": "test_factor_effectiveness",
                }
            ]

        # All factor names
        ALL_FACTOR_NAMES = [
            "mom_5d",
            "mom_10d",
            "mom_20d",
            "reversal_5d",
            "realized_vol_20d",
            "vol_ratio_5_20",
            "vol_change_5d",
            "vol_change_10d",
            "vol_price_corr_10d",
            "ma5_deviation",
            "ma10_deviation",
            "ma20_deviation",
            "rsi14_deviation",
            "boll_position",
            "high_low_position_20d",
            "obv_slope_10d",
            "vwap_deviation",
        ]
        if factor_names is None:
            factor_names = ALL_FACTOR_NAMES
        else:
            factor_names = [f for f in factor_names if f in ALL_FACTOR_NAMES]
            if not factor_names:
                return [
                    {
                        "error": f"No valid factor names. Available: {ALL_FACTOR_NAMES}",
                        "tool": "test_factor_effectiveness",
                    }
                ]

        # For each trading day, compute cross-sectional IC
        ic_by_factor = {f: [] for f in factor_names}
        rank_ic_by_factor = {f: [] for f in factor_names}
        skipped_dates = 0

        for td in trading_day_list:
            # For each trading day, need: (factor_value, forward_return) per stock
            # We need to find the index of td in each stock's data,
            # compute factors using data up to td, and get forward return from td+1 to td+1+period

            cross_section = {f: {"factors": [], "returns": []} for f in factor_names}

            for code, records in stock_data.items():
                # Find the index of td in this stock's records
                td_idx = None
                for i, r in enumerate(records):
                    if str(r.get("日期", "")).replace("-", "") == td:
                        td_idx = i
                        break

                if td_idx is None:
                    continue

                # Need forward return: close[td+1+period-1] / close[td+1] - 1 (T+1)
                fwd_idx = td_idx + 1 + period - 1  # index of the forward close
                if fwd_idx >= len(records) or td_idx + 1 >= len(records):
                    continue

                try:
                    fwd_close = float(records[fwd_idx].get("收盘", 0))
                    t1_close = float(records[td_idx + 1].get("收盘", 0))
                except (ValueError, TypeError):
                    continue

                if t1_close == 0:
                    continue

                fwd_return = fwd_close / t1_close - 1

                # Compute factors using data up to td (point-in-time)
                slice_data = records[: td_idx + 1]
                if len(slice_data) < 21:
                    continue

                factors = _compute_factors_from_ohlcv(slice_data)
                if "error" in factors:
                    continue

                for f in factor_names:
                    val = factors.get(f)
                    if (
                        val is not None
                        and isinstance(val, (int, float))
                        and not math.isnan(val)
                    ):
                        cross_section[f]["factors"].append(val)
                        cross_section[f]["returns"].append(fwd_return)

            # Compute IC for each factor on this date
            valid_count = 0
            for f in factor_names:
                n = len(cross_section[f]["factors"])
                if n >= 10:
                    ic = _pearson_corr(
                        cross_section[f]["factors"], cross_section[f]["returns"]
                    )
                    ric = _rank_corr(
                        cross_section[f]["factors"], cross_section[f]["returns"]
                    )
                    if not math.isnan(ic):
                        ic_by_factor[f].append(ic)
                        rank_ic_by_factor[f].append(ric)
                        valid_count += 1

            if valid_count == 0:
                skipped_dates += 1

        # Aggregate results
        results = []
        analysis_date = end_date
        conn = sqlite3.connect(str(DB_PATH))

        for f in factor_names:
            ic_series = ic_by_factor[f]
            ric_series = rank_ic_by_factor[f]

            if not ic_series:
                results.append(
                    {
                        "factor_name": f,
                        "status": "insufficient_data",
                        "mean_ic": "NaN",
                        "mean_rank_ic": "NaN",
                        "icir": "NaN",
                        "hit_rate": "NaN",
                        "sample_dates": 0,
                    }
                )
                continue

            mean_ic = sum(ic_series) / len(ic_series)
            std_ic = (
                math.sqrt(sum((x - mean_ic) ** 2 for x in ic_series) / len(ic_series))
                if len(ic_series) > 1
                else 0.0
            )
            icir = mean_ic / std_ic if std_ic > 0 else 0.0
            hit_rate = sum(1 for x in ic_series if x > 0) / len(ic_series)
            mean_ric = sum(ric_series) / len(ric_series) if ric_series else "NaN"

            row_data = {
                "factor_name": f,
                "mean_ic": round(mean_ic, 6),
                "std_ic": round(std_ic, 6),
                "icir": round(icir, 4),
                "mean_rank_ic": round(mean_ric, 6)
                if isinstance(mean_ric, float)
                else mean_ric,
                "hit_rate": round(hit_rate, 4),
                "sample_dates": len(ic_series),
                "skipped_dates": skipped_dates,
                "period_days": period,
            }

            # Persist to factor_analyses
            conn.execute(
                """INSERT INTO factor_analyses
                (analysis_date, factor_name, ic, rank_ic, icir, hit_rate, sample_size, period_days, mean_ic, std_ic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_date,
                    f,
                    round(mean_ic, 6),
                    round(mean_ric, 6) if isinstance(mean_ric, float) else None,
                    round(icir, 4),
                    round(hit_rate, 4),
                    len(ic_series),
                    period,
                    round(mean_ic, 6),
                    round(std_ic, 6),
                ),
            )

            results.append(row_data)

        conn.commit()
        conn.close()

        results.insert(
            0,
            {
                "status": "completed",
                "stocks_tested": len(stock_data),
                "stocks_failed": failed,
                "trading_days_tested": len(trading_day_list),
                "skipped_dates": skipped_dates,
                "factors_tested": len(factor_names),
            },
        )

        return results

    except Exception as e:
        return [{"error": str(e), "tool": "test_factor_effectiveness"}]


@mcp.tool()
def get_factor_report(days: int = 30) -> list[dict]:
    """
    Summarize which factors have been effective recently.
    Returns factor performance ranked by ICIR with effectiveness assessment.

    Args:
        days: Lookback window (default 30, max 365).
    """
    try:
        if days < 1 or days > 365:
            return [
                {"error": "days must be between 1 and 365", "tool": "get_factor_report"}
            ]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y%m%d")

        rows = conn.execute(
            "SELECT * FROM factor_analyses WHERE stock_code IS NULL AND analysis_date >= ?",
            (cutoff_str,),
        ).fetchall()
        conn.close()

        if not rows:
            return [
                {
                    "status": "no_factor_data",
                    "hint": "Run test_factor_effectiveness first",
                }
            ]

        by_factor = {}
        for r in rows:
            fn = r["factor_name"]
            if fn not in by_factor:
                by_factor[fn] = {
                    "icir_vals": [],
                    "ic_vals": [],
                    "ric_vals": [],
                    "hit_vals": [],
                    "samples": [],
                }
            if r["icir"] is not None:
                by_factor[fn]["icir_vals"].append(r["icir"])
            if r["mean_ic"] is not None:
                by_factor[fn]["ic_vals"].append(r["mean_ic"])
            if r["rank_ic"] is not None:
                by_factor[fn]["ric_vals"].append(r["rank_ic"])
            if r["hit_rate"] is not None:
                by_factor[fn]["hit_vals"].append(r["hit_rate"])
            if r["sample_size"] is not None:
                by_factor[fn]["samples"].append(r["sample_size"])

        results = []
        for fn, data in by_factor.items():
            avg_icir = (
                sum(data["icir_vals"]) / len(data["icir_vals"])
                if data["icir_vals"]
                else 0
            )
            avg_ic = (
                sum(data["ic_vals"]) / len(data["ic_vals"]) if data["ic_vals"] else 0
            )
            avg_ric = (
                sum(data["ric_vals"]) / len(data["ric_vals"]) if data["ric_vals"] else 0
            )
            avg_hit = (
                sum(data["hit_vals"]) / len(data["hit_vals"]) if data["hit_vals"] else 0
            )
            total_samples = sum(data["samples"])

            abs_icir = abs(avg_icir)
            if abs_icir > 0.5:
                effectiveness = "strong"
            elif abs_icir > 0.3:
                effectiveness = "moderate"
            else:
                effectiveness = "weak"

            results.append(
                {
                    "factor_name": fn,
                    "mean_ic": round(avg_ic, 6),
                    "mean_rank_ic": round(avg_ric, 6),
                    "icir": round(avg_icir, 4),
                    "hit_rate": round(avg_hit, 4),
                    "effectiveness": effectiveness,
                    "test_count": len(data["icir_vals"]),
                    "total_sample_size": total_samples,
                }
            )

        results.sort(key=lambda x: abs(x["icir"]), reverse=True)
        return results

    except Exception as e:
        return [{"error": str(e), "tool": "get_factor_report"}]


@mcp.tool()
def get_top_factors(
    min_icir: float = 0.3, min_ic: float = 0.02, days: int = 60
) -> list[dict]:
    """
    Return factors passing effectiveness criteria, ready for use in predictions.

    Args:
        min_icir: Minimum absolute ICIR threshold (default 0.3).
        min_ic: Minimum absolute mean IC threshold (default 0.02).
        days: Lookback window (default 60).
    """
    try:
        report = get_factor_report(days=days)
        if not report or "error" in report[0]:
            return report

        top = [
            f
            for f in report
            if abs(f.get("mean_ic", 0)) >= min_ic and abs(f.get("icir", 0)) >= min_icir
        ]
        if not top:
            return [
                {
                    "status": "no_factors_pass_criteria",
                    "min_icir": min_icir,
                    "min_ic": min_ic,
                    "factors_checked": len(report),
                }
            ]

        return top

    except Exception as e:
        return [{"error": str(e), "tool": "get_top_factors"}]


mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8003)
