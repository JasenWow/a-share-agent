"""Event-driven backtest simulation engine."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from cost_model import (
    apply_buy_slippage,
    apply_sell_slippage,
    calculate_buy_cost,
    calculate_max_buy_shares,
    calculate_sell_cost,
    round_lot_size,
    should_exclude,
)
from models import BarData, Portfolio, Position, SessionConfig, Signal, TradeRecord

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "backtest.db"
PREDICTION_DB_PATH = Path(__file__).parent.parent / "prediction-store" / "predictions.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_trading_days(start_date: str, end_date: str) -> list[str]:
    """Get list of trading days from prediction-store calendar."""
    days: list[str] = []
    if PREDICTION_DB_PATH.exists():
        conn = sqlite3.connect(str(PREDICTION_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT trade_date FROM trading_calendar WHERE is_trading_day = 1 "
                "AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date",
                (start_date, end_date),
            ).fetchall()
            days = [r["trade_date"] for r in rows]
        finally:
            conn.close()
    return days


class BacktestEngine:
    """Event-driven backtest simulation engine."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.config = self._load_config()
        self.bar_data: dict[str, dict[str, BarData]] = {}  # stock_code -> {date -> BarData}
        self.benchmark_data: dict[str, float] = {}  # date -> close
        self.signals: dict[str, list[Signal]] = {}  # signal_date -> [Signal]
        self.portfolio = Portfolio(cash=self.config.initial_capital)
        self.trade_records: list[TradeRecord] = []
        self._trading_days: list[str] = []  # Cached trading day list
        self._day_index: int = 0  # Current position in trading_days
        self._prev_nav: float = self.config.initial_capital
        self._prev_bm_close: float = 0.0
        self._benchmark_cumulative: float = 1.0
        self._step_initialized: bool = False  # True after first step in this instance

    def _load_config(self) -> SessionConfig:
        conn = _get_conn()
        try:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (self.session_id,)).fetchone()
            if row is None:
                raise ValueError(f"Session {self.session_id} not found")
            import json

            d = dict(row)
            return SessionConfig(
                session_id=d["session_id"],
                name=d.get("name", ""),
                strategy=d.get("strategy", ""),
                status=d.get("status", "created"),
                initial_capital=d.get("initial_capital", 1000000.0),
                start_date=d.get("start_date", ""),
                end_date=d.get("end_date", ""),
                universe=json.loads(d.get("universe", "[]")),
                benchmark=d.get("benchmark", "sh000300"),
                commission_rate=d.get("cost_commission", 0.00025),
                stamp_duty_rate=d.get("cost_stamp_duty", 0.0005),
                slippage_rate=d.get("cost_slippage", 0.0005),
                exclude_st=bool(d.get("exclude_st", 1)),
            )
        finally:
            conn.close()

    def load_bar_data(self, stock_codes: list[str], data: dict[str, list[dict]]) -> dict[str, Any]:
        """Load OHLCV data into memory. data = {stock_code: [records from akshare]}."""
        loaded = 0
        failed: list[str] = []

        for code in stock_codes:
            records = data.get(code, [])
            if not records:
                failed.append(code)
                continue
            self.bar_data[code] = {}
            for r in records:
                try:
                    self.bar_data[code][r["日期"]] = BarData(
                        date=r["日期"],
                        open=float(r["开盘"]),
                        close=float(r["收盘"]),
                        high=float(r["最高"]),
                        low=float(r["最低"]),
                        volume=float(r["成交量"]),
                        name=str(r.get("名称", "")),
                    )
                except (KeyError, ValueError):
                    continue
            if self.bar_data[code]:
                loaded += 1
            else:
                failed.append(code)

        self._update_status("ready")
        return {"loaded": loaded, "failed": failed, "stocks_in_memory": len(self.bar_data)}

    def load_benchmark(self, data: list[dict]) -> None:
        """Load benchmark index data. data = [records from akshare index daily]."""
        for r in data:
            try:
                self.benchmark_data[r["日期"]] = float(r["收盘"])
            except (KeyError, ValueError):
                continue

    def register_signals(self, signals: list[Signal]) -> int:
        """Queue signals indexed by signal_date. Persists to DB for step mode."""
        conn = _get_conn()
        try:
            for sig in signals:
                self.signals.setdefault(sig.signal_date, []).append(sig)
                conn.execute(
                    "INSERT INTO pending_signals "
                    "(session_id, signal_date, stock_code, direction, target_weight, target_shares) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (self.session_id, sig.signal_date, sig.stock_code, sig.direction, sig.target_weight, sig.target_shares),
                )
            conn.commit()
        finally:
            conn.close()
        return len(signals)

    def _load_pending_signals(self) -> None:
        """Load unprocessed signals from DB into memory."""
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT signal_date, stock_code, direction, target_weight, target_shares "
                "FROM pending_signals WHERE session_id = ? AND processed = 0",
                (self.session_id,),
            ).fetchall()
            for r in rows:
                sig = Signal(
                    signal_date=r["signal_date"],
                    stock_code=r["stock_code"],
                    direction=r["direction"],
                    target_weight=r["target_weight"],
                    target_shares=r["target_shares"],
                )
                self.signals.setdefault(sig.signal_date, []).append(sig)
        finally:
            conn.close()

    def _mark_signals_processed(self, conn: sqlite3.Connection, signal_date: str) -> None:
        """Mark all signals for a given date as processed."""
        conn.execute(
            "UPDATE pending_signals SET processed = 1 WHERE session_id = ? AND signal_date = ?",
            (self.session_id, signal_date),
        )
        conn.commit()

    def _init_run(self) -> list[str] | dict:
        """Initialize for a run (batch or step). Returns trading_days list or error dict."""
        trading_days = get_trading_days(self.config.start_date, self.config.end_date)
        if not trading_days:
            self._update_status("failed", "No trading days in range")
            return {"error": "No trading days found", "tool": "run_session"}

        # Clear previous run data
        self._clear_session_data()
        self.portfolio = Portfolio(cash=self.config.initial_capital)
        self.trade_records = []
        self._trading_days = trading_days
        self._day_index = 0
        self._prev_nav = self.config.initial_capital
        self._prev_bm_close = self.benchmark_data.get(trading_days[0], 0.0)
        self._benchmark_cumulative = 1.0
        self._update_status("running")
        return trading_days

    def _restore_state(self) -> None:
        """Restore engine state from DB for resuming a step session."""
        conn = _get_conn()
        try:
            # Restore trading days
            self._trading_days = get_trading_days(self.config.start_date, self.config.end_date)

            # Find current position from last daily_nav
            last_nav = conn.execute(
                "SELECT trade_date FROM daily_nav WHERE session_id = ? ORDER BY trade_date DESC LIMIT 1",
                (self.session_id,),
            ).fetchone()

            if last_nav:
                current_date = last_nav["trade_date"]
                self._day_index = self._trading_days.index(current_date) + 1 if current_date in self._trading_days else 0

                # Restore portfolio from positions snapshot
                pos_rows = conn.execute(
                    "SELECT * FROM positions WHERE session_id = ? AND trade_date = ?",
                    (self.session_id, current_date),
                ).fetchall()
                for r in pos_rows:
                    pos = Position(
                        stock_code=r["stock_code"],
                        shares=r["shares"],
                        sellable_shares=r["shares"] if r["sellable"] else 0,
                        cost_basis=r["cost_basis"],
                        market_value=r["market_value"],
                    )
                    self.portfolio.positions[r["stock_code"]] = pos

                # Restore cash
                nav_row = conn.execute(
                    "SELECT cash FROM daily_nav WHERE session_id = ? AND trade_date = ?",
                    (self.session_id, current_date),
                ).fetchone()
                if nav_row:
                    self.portfolio.cash = nav_row["cash"]

                self._prev_nav = conn.execute(
                    "SELECT nav FROM daily_nav WHERE session_id = ? AND trade_date = ?",
                    (self.session_id, current_date),
                ).fetchone()["nav"]
            else:
                self._day_index = 0
                self._prev_nav = self.config.initial_capital

            # Restore benchmark state
            if self._day_index > 0:
                prev_date = self._trading_days[self._day_index - 1]
                nav_data = conn.execute(
                    "SELECT benchmark_value, benchmark_close FROM daily_nav WHERE session_id = ? AND trade_date = ?",
                    (self.session_id, prev_date),
                ).fetchone()
                if nav_data:
                    self._benchmark_cumulative = nav_data["benchmark_value"]
                    self._prev_bm_close = nav_data["benchmark_close"]
            else:
                self._prev_bm_close = self.benchmark_data.get(self._trading_days[0], 0.0) if self._trading_days else 0.0
                self._benchmark_cumulative = 1.0

            # Restore trade records count
            count = conn.execute("SELECT COUNT(*) as c FROM trades WHERE session_id = ?", (self.session_id,)).fetchone()["c"]
            self.trade_records = [TradeRecord("", "", "", 0, 0.0, 0.0)] * count  # Placeholder for count

        finally:
            conn.close()

        # Load pending signals from DB
        self._load_pending_signals()

    def _process_day(self, conn: sqlite3.Connection, i: int, trade_date: str) -> None:
        """Process a single trading day: execute signals, mark-to-market, write NAV/positions."""
        # Step 1: Mark positions from previous day as sellable (T+1 unlock)
        if i > 0:
            for pos in self.portfolio.positions.values():
                if not pos.sellable_shares:
                    pos.mark_sellable()

        # Step 2: Execute pending signals from previous trading day
        if i > 0:
            prev_date = self._trading_days[i - 1]
            pending = self.signals.get(prev_date, [])
            if pending:
                self._execute_signals(conn, pending, trade_date)
                self._mark_signals_processed(conn, prev_date)

        # Step 3: Mark-to-market with close prices
        positions_value = self._mark_to_market(trade_date)

        # Step 4: Calculate daily NAV
        total_value = self.portfolio.cash + positions_value
        daily_return = (total_value - self._prev_nav) / self._prev_nav if self._prev_nav > 0 else 0.0

        # Benchmark
        bm_close = self.benchmark_data.get(trade_date, self._prev_bm_close)
        bm_return = (bm_close / self._prev_bm_close - 1) if self._prev_bm_close > 0 else 0.0
        self._benchmark_cumulative *= (1 + bm_return)

        # Step 5: Write daily_nav
        conn.execute(
            "INSERT OR REPLACE INTO daily_nav "
            "(session_id, trade_date, nav, cash, positions_value, benchmark_value, "
            "benchmark_close, daily_return, benchmark_return, excess_return) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.session_id,
                trade_date,
                total_value,
                self.portfolio.cash,
                positions_value,
                self._benchmark_cumulative,
                bm_close,
                daily_return,
                bm_return,
                daily_return - bm_return,
            ),
        )

        # Step 6: Write position snapshots
        if self.portfolio.positions:
            conn.execute(
                "DELETE FROM positions WHERE session_id = ? AND trade_date = ?",
                (self.session_id, trade_date),
            )
            for stock_code, pos in self.portfolio.positions.items():
                weight = pos.market_value / total_value if total_value > 0 else 0.0
                conn.execute(
                    "INSERT INTO positions "
                    "(session_id, trade_date, stock_code, shares, cost_basis, "
                    "market_value, unrealized_pnl, unrealized_pnl_pct, weight, sellable) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.session_id,
                        trade_date,
                        stock_code,
                        pos.shares,
                        pos.cost_basis,
                        pos.market_value,
                        pos.unrealized_pnl,
                        pos.unrealized_pnl_pct,
                        weight,
                        int(pos.sellable_shares > 0),
                    ),
                )

        conn.commit()
        self._prev_nav = total_value
        self._prev_bm_close = bm_close

        # Update session progress
        conn.execute(
            "UPDATE sessions SET current_date = ?, updated_at = datetime('now') WHERE session_id = ?",
            (trade_date, self.session_id),
        )
        conn.commit()

    def run(self) -> dict[str, Any]:
        """Run the full backtest simulation."""
        try:
            trading_days = self._init_run()
            if isinstance(trading_days, dict):
                return trading_days

            conn = _get_conn()
            try:
                for i, trade_date in enumerate(trading_days):
                    self._process_day(conn, i, trade_date)
            finally:
                conn.close()

            # Finalize
            self.config.final_nav = self._prev_nav
            self.config.total_trades = len(self.trade_records)
            self._update_status("completed")

            return {
                "session_id": self.session_id,
                "status": "completed",
                "final_nav": round(self._prev_nav, 2),
                "total_return": round((self._prev_nav / self.config.initial_capital - 1), 6),
                "total_trades": len(self.trade_records),
                "trading_days": len(trading_days),
            }

        except Exception as e:
            logger.exception("Backtest run failed")
            self._update_status("failed", str(e))
            return {"error": str(e), "tool": "run_session"}

    def step(self) -> dict[str, Any]:
        """Advance the simulation by one trading day.

        On first call, initializes the session. On subsequent calls, processes
        the next trading day. The agent can submit signals between steps.
        """
        try:
            if not self._step_initialized:
                # First step in this engine instance
                if self.config.status == "running":
                    # Session was already started (e.g. server restart) — restore from DB
                    self._restore_state()
                    if not self._trading_days:
                        return {"error": "No trading days found", "tool": "step_session"}
                else:
                    # Fresh start
                    trading_days = self._init_run()
                    if isinstance(trading_days, dict):
                        return trading_days
                self._step_initialized = True

            if self._day_index >= len(self._trading_days):
                self.config.final_nav = self._prev_nav
                self._update_status("completed")
                return {
                    "session_id": self.session_id,
                    "status": "completed",
                    "message": "All trading days processed",
                    "final_nav": round(self._prev_nav, 2),
                }

            trade_date = self._trading_days[self._day_index]
            conn = _get_conn()
            try:
                self._process_day(conn, self._day_index, trade_date)
            finally:
                conn.close()

            self._day_index += 1

            # Build result with today's market data
            today_bars = {}
            for code in self.config.universe:
                bars = self.bar_data.get(code, {})
                bar = bars.get(trade_date)
                if bar:
                    today_bars[code] = {
                        "date": trade_date,
                        "open": bar.open,
                        "close": bar.close,
                        "high": bar.high,
                        "low": bar.low,
                        "volume": bar.volume,
                        "name": bar.name,
                    }

            positions_summary = [
                {
                    "stock_code": code,
                    "shares": pos.shares,
                    "sellable_shares": pos.sellable_shares,
                    "cost_basis": round(pos.cost_basis, 2),
                    "market_value": round(pos.market_value, 2),
                    "unrealized_pnl": round(pos.unrealized_pnl, 2),
                }
                for code, pos in self.portfolio.positions.items()
            ]

            return {
                "session_id": self.session_id,
                "status": "running",
                "trade_date": trade_date,
                "day_index": self._day_index,
                "total_days": len(self._trading_days),
                "remaining_days": len(self._trading_days) - self._day_index,
                "nav": round(self._prev_nav, 2),
                "cash": round(self.portfolio.cash, 2),
                "daily_return": round(
                    (self._prev_nav - (self._prev_nav / (1 + ((self._prev_nav / self.config.initial_capital - 1) / max(self._day_index, 1))))) / self._prev_nav,
                    6,
                )
                if self._prev_nav > 0 and self._day_index > 0
                else 0.0,
                "positions": positions_summary,
                "market_data": today_bars,
            }

        except Exception as e:
            logger.exception("Step failed")
            self._update_status("failed", str(e))
            return {"error": str(e), "tool": "step_session"}

    def get_today_bars(self) -> dict[str, Any]:
        """Get current day's bar data for the universe. Only valid during step mode."""
        if not self._trading_days or self._day_index == 0:
            return {"error": "No active trading day. Call step_session first."}

        # Return data for the last processed day
        last_idx = min(self._day_index, len(self._trading_days)) - 1
        trade_date = self._trading_days[last_idx]

        bars = {}
        for code in self.config.universe:
            bar = self.bar_data.get(code, {}).get(trade_date)
            if bar:
                bars[code] = {
                    "date": trade_date,
                    "open": bar.open,
                    "close": bar.close,
                    "high": bar.high,
                    "low": bar.low,
                    "volume": bar.volume,
                    "name": bar.name,
                }

        return {"trade_date": trade_date, "bars": bars}

    def _execute_signals(self, conn: sqlite3.Connection, signals: list[Signal], execution_date: str) -> None:
        """Execute queued signals at execution_date open price."""
        sells = [s for s in signals if s.direction == "sell"]
        buys = [s for s in signals if s.direction == "buy"]

        for sig in sells:
            self._execute_sell(conn, sig, execution_date)
        for sig in buys:
            self._execute_buy(conn, sig, execution_date)

    def _execute_buy(self, conn: sqlite3.Connection, signal: Signal, exec_date: str) -> None:
        """Execute a buy signal."""
        code = signal.stock_code
        bars = self.bar_data.get(code, {})
        bar = bars.get(exec_date)
        if bar is None or bar.is_suspended:
            return

        # Get previous close for limit check
        prev_close = self._get_prev_close(code, exec_date)
        excluded, reason = should_exclude(code, bar, self.config, prev_close)
        if excluded:
            return

        exec_price = apply_buy_slippage(bar.open, self.config.slippage_rate)

        # Determine target shares
        if signal.target_weight > 0:
            target_amount = self.portfolio.total_value * signal.target_weight
            target_shares = int(target_amount / exec_price)
        else:
            target_shares = signal.target_shares

        # Lot size rounding
        target_shares = round_lot_size(target_shares)

        # Cash constraint
        max_affordable = calculate_max_buy_shares(
            self.portfolio.cash, bar.open, self.config.commission_rate, self.config.slippage_rate
        )
        actual_shares = min(target_shares, max_affordable)
        if actual_shares < 100:
            return

        amount = actual_shares * exec_price
        commission, stamp_duty, slippage_cost, total_cost = calculate_buy_cost(
            amount, exec_price, actual_shares, self.config.commission_rate, self.config.slippage_rate
        )

        total_debit = amount + total_cost
        if total_debit > self.portfolio.cash:
            return

        # Execute
        self.portfolio.cash -= total_debit

        if code in self.portfolio.positions:
            pos = self.portfolio.positions[code]
            old_shares = pos.shares
            pos.add_shares(actual_shares, exec_price, exec_date)
            # New shares are not sellable, old sellable shares stay sellable
            pos.sellable_shares = min(pos.sellable_shares, old_shares)
        else:
            pos = Position(stock_code=code, shares=0, sellable_shares=0)
            pos.add_shares(actual_shares, exec_price, exec_date)
            self.portfolio.positions[code] = pos

        # Record trade
        trade = TradeRecord(
            trade_date=exec_date,
            stock_code=code,
            direction="buy",
            shares=actual_shares,
            price=exec_price,
            amount=amount,
            commission=commission,
            stamp_duty=0.0,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
            signal_date=signal.signal_date,
        )
        self.trade_records.append(trade)
        self._save_trade(conn, trade)

    def _execute_sell(self, conn: sqlite3.Connection, signal: Signal, exec_date: str) -> None:
        """Execute a sell signal."""
        code = signal.stock_code
        pos = self.portfolio.positions.get(code)
        if pos is None or pos.sellable_shares == 0:
            return

        bars = self.bar_data.get(code, {})
        bar = bars.get(exec_date)
        if bar is None or bar.is_suspended:
            return

        exec_price = apply_sell_slippage(bar.open, self.config.slippage_rate)

        # Shares to sell
        if signal.target_shares == 0:
            shares_to_sell = pos.sellable_shares
        else:
            shares_to_sell = min(signal.target_shares, pos.sellable_shares)

        shares_to_sell = round_lot_size(shares_to_sell)
        if shares_to_sell < 100:
            shares_to_sell = pos.sellable_shares  # Sell all if can't round to 100
        if shares_to_sell == 0:
            return

        amount = shares_to_sell * exec_price
        commission, stamp_duty, slippage_cost, total_cost = calculate_sell_cost(
            amount, self.config.commission_rate, self.config.stamp_duty_rate, self.config.slippage_rate
        )

        realized_pnl = (exec_price - pos.cost_basis) * shares_to_sell - total_cost
        net_proceeds = amount - total_cost

        # Execute
        self.portfolio.cash += net_proceeds
        pos.remove_shares(shares_to_sell)

        # Remove position if fully sold
        if pos.shares == 0:
            del self.portfolio.positions[code]

        # Record trade
        trade = TradeRecord(
            trade_date=exec_date,
            stock_code=code,
            direction="sell",
            shares=shares_to_sell,
            price=exec_price,
            amount=amount,
            commission=commission,
            stamp_duty=stamp_duty,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
            realized_pnl=realized_pnl,
            signal_date=signal.signal_date,
        )
        self.trade_records.append(trade)
        self._save_trade(conn, trade)

    def _mark_to_market(self, trade_date: str) -> float:
        """Update position market values with close prices. Returns total positions value."""
        total = 0.0
        for code, pos in self.portfolio.positions.items():
            bars = self.bar_data.get(code, {})
            bar = bars.get(trade_date)
            if bar and not bar.is_suspended:
                pos.current_price = bar.close
                pos.market_value = pos.shares * bar.close
            # If no bar data (delisted), keep last known value
            total += pos.market_value
        return total

    def _get_prev_close(self, stock_code: str, date: str) -> float:
        """Get previous day's close price for a stock."""
        bars = self.bar_data.get(stock_code, {})
        sorted_dates = sorted(bars.keys())
        try:
            idx = sorted_dates.index(date)
            if idx > 0:
                return bars[sorted_dates[idx - 1]].close
        except ValueError:
            pass
        return 0.0

    def _save_trade(self, conn: sqlite3.Connection, trade: TradeRecord) -> None:
        conn.execute(
            "INSERT INTO trades "
            "(session_id, trade_date, stock_code, direction, shares, price, amount, "
            "commission, stamp_duty, slippage_cost, total_cost, realized_pnl, signal_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.session_id,
                trade.trade_date,
                trade.stock_code,
                trade.direction,
                trade.shares,
                trade.price,
                trade.amount,
                trade.commission,
                trade.stamp_duty,
                trade.slippage_cost,
                trade.total_cost,
                trade.realized_pnl,
                trade.signal_date,
            ),
        )

    def _clear_session_data(self) -> None:
        """Clear previous run data for this session."""
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM daily_nav WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM trades WHERE session_id = ?", (self.session_id,))
            conn.execute("DELETE FROM positions WHERE session_id = ?", (self.session_id,))
            conn.commit()
        finally:
            conn.close()

    def _update_status(self, status: str, error_message: str = "") -> None:
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE sessions SET status = ?, error_message = ?, updated_at = datetime('now') "
                "WHERE session_id = ?",
                (status, error_message, self.session_id),
            )
            conn.commit()
        finally:
            conn.close()
