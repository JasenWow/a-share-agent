"""
Prediction Store MCP Server — Stock prediction persistence and accuracy tracking
Run: uvicorn server:mcp_app --host 0.0.0.0 --port 8003
"""

import logging
import math
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
                (predicted_pct, confidence, features_summary, new_version, baseline_flag, stock_code, signal_date),
            )
        else:
            new_version = 1
            conn.execute(
                """
                INSERT INTO predictions (stock_code, signal_date, predicted_pct, confidence, features_summary, version, baseline)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (stock_code, signal_date, predicted_pct, confidence, features_summary, new_version, baseline_flag),
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
                return [{"error": f"Invalid stock code: {stock_code}", "tool": "get_predictions"}]
            query += " AND stock_code=?"
            params.append(stock_code)

        if signal_date:
            if not _validate_date(signal_date):
                conn.close()
                return [{"error": f"Invalid signal_date: {signal_date}", "tool": "get_predictions"}]
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
    - by_stock: top 10 stocks by mean absolute error
    - by_direction: overestimation vs underestimation counts
    - by_magnitude: small (<1%), medium (1-3%), large (>3%) error distribution
    - by_confidence: MAE broken down by confidence level
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
                "by_confidence": {"high": {"count": 0, "mae": 0}, "medium": {"count": 0, "mae": 0}, "low": {"count": 0, "mae": 0}},
            }]

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
            by_stock_list.append({
                "stock_code": code,
                "mean_abs_error": round(sum(abs(e) for e in errs) / len(errs), 4),
                "mean_error": round(sum(errs) / len(errs), 4),
                "count": len(errs),
            })
        by_stock_list.sort(key=lambda x: x["mean_abs_error"], reverse=True)
        by_stock_list = by_stock_list[:10]

        return [{
            "by_stock": by_stock_list,
            "by_direction": {"overestimate": overestimate, "underestimate": underestimate},
            "by_magnitude": {"small": small, "medium": medium, "large": large},
            "by_confidence": {
                "high": {"count": len(conf_high), "mae": round(sum(conf_high) / len(conf_high), 4)} if conf_high else {"count": 0, "mae": 0},
                "medium": {"count": len(conf_med), "mae": round(sum(conf_med) / len(conf_med), 4)} if conf_med else {"count": 0, "mae": 0},
                "low": {"count": len(conf_low), "mae": round(sum(conf_low) / len(conf_low), 4)} if conf_low else {"count": 0, "mae": 0},
            },
        }]

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
            return [{"error": "days must be between 1 and 365", "tool": "get_accuracy_trend"}]
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
            hit = sum(1 for i in range(len(errs)) if (errs[i] > 0) == (preds[i] > 0)) / len(errs)
            bucket_list.append({
                "period_start": b["period_start"],
                "period_end": b["period_end"],
                "mae": round(mae, 4),
                "hit_rate": round(hit, 4),
                "count": len(errs),
            })

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
        vol_avg5 = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else sum(volumes[:-1]) / (len(volumes) - 1)
        result["vol_ratio"] = round(volumes[-1] / vol_avg5, 4) if vol_avg5 > 0 else "NaN"
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
            return [{"error": "ohlcv_data must be a list with at least 5 records", "tool": "compute_indicators"}]
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


def _get_signal_and_next_close(stock_code: str, signal_date: str, next_td: str) -> tuple[float, float] | None:
    """Fetch signal_date close and next_trading_day close via AKShare."""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date=signal_date, end_date=next_td, adjust="qfq")
        if df is None or df.empty or len(df) < 2:
            return None
        signal_close = float(df.iloc[0]["收盘"])
        next_close = float(df.iloc[1]["收盘"])
        return signal_close, next_close
    except Exception:
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
                return [{"error": f"Invalid signal_date: {signal_date}", "tool": "auto_verify_predictions"}]
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
            next_td_row = conn2.execute(
                "SELECT trade_date FROM trading_calendar WHERE trade_date > ? AND is_trading_day=1 ORDER BY trade_date ASC LIMIT 1",
                (sig_date,),
            ).fetchone()
            conn2.close()

            if not next_td_row:
                results.append({"stock_code": code, "signal_date": sig_date, "status": "no_next_trading_day"})
                continue

            next_td = next_td_row["trade_date"]
            prices = _get_signal_and_next_close(code, sig_date, next_td)

            if prices is None:
                results.append({"stock_code": code, "signal_date": sig_date, "status": "price_data_unavailable", "next_trading_day": next_td})
                continue

            signal_close, next_close = prices
            actual_pct = round((next_close - signal_close) / signal_close * 100, 4)
            record_actual(code, sig_date, actual_pct)
            results.append({
                "stock_code": code,
                "signal_date": sig_date,
                "next_trading_day": next_td,
                "signal_close": signal_close,
                "next_close": next_close,
                "actual_pct": actual_pct,
                "predicted_pct": r["predicted_pct"],
                "error": round(actual_pct - r["predicted_pct"], 4),
                "status": "verified",
            })

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
                return [{"error": "note_date (YYYYMMDD) required for add", "tool": "manage_strategy_notes"}]
            if not content:
                conn.close()
                return [{"error": "content required for add", "tool": "manage_strategy_notes"}]
            cursor = conn.execute(
                "INSERT INTO strategy_notes (note_date, note_type, content) VALUES (?, ?, ?)",
                (note_date, note_type, content),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM strategy_notes WHERE id=?", (cursor.lastrowid,)).fetchone()
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
                return [{"error": "note_id required for delete", "tool": "manage_strategy_notes"}]
            cursor = conn.execute("DELETE FROM strategy_notes WHERE id=?", (note_id,))
            conn.commit()
            conn.close()
            if cursor.rowcount > 0:
                return [{"status": "deleted", "note_id": note_id}]
            return [{"error": f"Note {note_id} not found", "tool": "manage_strategy_notes"}]

        else:
            conn.close()
            return [{"error": f"Unknown action: {action}. Use add/list/recent/delete.", "tool": "manage_strategy_notes"}]

    except Exception as e:
        return [{"error": str(e), "tool": "manage_strategy_notes"}]


mcp_app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="0.0.0.0", port=8003)