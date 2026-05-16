"""Pure simulation engine — no DB, no I/O. Accepts data dicts, returns result dicts."""

from __future__ import annotations

import logging
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
from models import BarData, DayResult, Portfolio, Position, SessionConfig, Signal, TradeRecord

logger = logging.getLogger(__name__)


class BacktestSimulator:
    """Stateless-ish simulation engine. All state is in memory."""

    def __init__(self, config: SessionConfig):
        self.config = config
        self.portfolio = Portfolio(cash=config.initial_capital)
        self.bar_data: dict[str, dict[str, BarData]] = {}  # code -> {date -> BarData}
        self.benchmark_data: dict[str, float] = {}  # date -> close
        self.signals: dict[str, list[Signal]] = {}  # signal_date -> [Signal]
        self.trade_records: list[TradeRecord] = []
        self._prev_nav: float = config.initial_capital
        self._prev_bm_close: float = 0.0
        self._benchmark_cumulative: float = 1.0

    def load_bar_data(self, data: dict[str, list[dict]]) -> dict[str, Any]:
        """Load OHLCV data. data = {stock_code: [records with 日期/开盘/收盘/最高/最低/成交量/名称]}."""
        loaded = 0
        failed: list[str] = []
        for code, records in data.items():
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
        return {"loaded": loaded, "failed": failed, "stocks_in_memory": len(self.bar_data)}

    def load_benchmark(self, data: list[dict]) -> None:
        """Load benchmark index. data = [{日期, 收盘}]."""
        for r in data:
            try:
                self.benchmark_data[r["日期"]] = float(r["收盘"])
            except (KeyError, ValueError):
                continue

    def add_signals(self, signals: list[dict]) -> None:
        """Add signals from list of dicts: [{signal_date, stock_code, direction, target_weight, target_shares}]."""
        for s in signals:
            sig = Signal(
                signal_date=s["signal_date"],
                stock_code=s["stock_code"],
                direction=s["direction"],
                target_weight=s.get("target_weight", 0.0),
                target_shares=s.get("target_shares", 0),
            )
            self.signals.setdefault(sig.signal_date, []).append(sig)

    def run(self, trading_days: list[str]) -> dict[str, Any]:
        """Run full batch backtest. Returns summary dict with all day results."""
        if not trading_days:
            return {"error": "No trading days"}

        self.portfolio = Portfolio(cash=self.config.initial_capital)
        self.trade_records = []
        self._prev_nav = self.config.initial_capital
        self._prev_bm_close = self.benchmark_data.get(trading_days[0], 0.0)
        self._benchmark_cumulative = 1.0

        daily_results: list[dict] = []
        all_trades: list[dict] = []
        all_positions: list[dict] = []

        for i, trade_date in enumerate(trading_days):
            day = self._process_day(i, trade_date)
            daily_results.append({
                "trade_date": day.trade_date,
                "nav": day.nav,
                "cash": day.cash,
                "positions_value": day.positions_value,
                "daily_return": day.daily_return,
                "benchmark_return": day.benchmark_return,
                "excess_return": day.excess_return,
                "benchmark_value": day.benchmark_value,
                "benchmark_close": day.benchmark_close,
            })
            for t in day.trades:
                all_trades.append({
                    "trade_date": t.trade_date,
                    "stock_code": t.stock_code,
                    "direction": t.direction,
                    "shares": t.shares,
                    "price": t.price,
                    "amount": t.amount,
                    "commission": t.commission,
                    "stamp_duty": t.stamp_duty,
                    "slippage_cost": t.slippage_cost,
                    "total_cost": t.total_cost,
                    "realized_pnl": t.realized_pnl,
                    "signal_date": t.signal_date,
                })
            all_positions.extend(day.position_snapshots)

        return {
            "status": "completed",
            "final_nav": round(self._prev_nav, 2),
            "total_return": round((self._prev_nav / self.config.initial_capital - 1), 6),
            "total_trades": len(all_trades),
            "trading_days": len(trading_days),
            "daily_nav": daily_results,
            "trades": all_trades,
            "positions": all_positions,
        }

    def _process_day(self, i: int, trade_date: str) -> DayResult:
        """Process a single trading day."""
        if i > 0:
            for pos in self.portfolio.positions.values():
                if not pos.sellable_shares:
                    pos.mark_sellable()

        if i > 0:
            prev_date = None
            # Find the previous trading day that has signals
            for d in sorted(self.signals.keys()):
                if d < trade_date:
                    prev_date = d
            if prev_date:
                pending = self.signals.get(prev_date, [])
                if pending:
                    self._execute_signals(pending, trade_date)
                    del self.signals[prev_date]

        positions_value = self._mark_to_market(trade_date)
        total_value = self.portfolio.cash + positions_value
        daily_return = (total_value - self._prev_nav) / self._prev_nav if self._prev_nav > 0 else 0.0

        bm_close = self.benchmark_data.get(trade_date, self._prev_bm_close)
        bm_return = (bm_close / self._prev_bm_close - 1) if self._prev_bm_close > 0 else 0.0
        self._benchmark_cumulative *= (1 + bm_return)

        day_trades = list(self.trade_records)  # snapshot current trades
        self.trade_records = []

        position_snapshots = []
        for stock_code, pos in self.portfolio.positions.items():
            weight = pos.market_value / total_value if total_value > 0 else 0.0
            position_snapshots.append({
                "trade_date": trade_date,
                "stock_code": stock_code,
                "shares": pos.shares,
                "cost_basis": pos.cost_basis,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                "weight": weight,
                "sellable": int(pos.sellable_shares > 0),
            })

        self._prev_nav = total_value
        self._prev_bm_close = bm_close

        return DayResult(
            trade_date=trade_date,
            nav=total_value,
            cash=self.portfolio.cash,
            positions_value=positions_value,
            daily_return=daily_return,
            benchmark_return=bm_return,
            excess_return=daily_return - bm_return,
            benchmark_value=self._benchmark_cumulative,
            benchmark_close=bm_close,
            trades=day_trades,
            position_snapshots=position_snapshots,
        )

    def _execute_signals(self, signals: list[Signal], execution_date: str) -> None:
        sells = [s for s in signals if s.direction == "sell"]
        buys = [s for s in signals if s.direction == "buy"]
        for sig in sells:
            self._execute_sell(sig, execution_date)
        for sig in buys:
            self._execute_buy(sig, execution_date)

    def _execute_buy(self, signal: Signal, exec_date: str) -> None:
        code = signal.stock_code
        bars = self.bar_data.get(code, {})
        bar = bars.get(exec_date)
        if bar is None or bar.is_suspended:
            return

        prev_close = self._get_prev_close(code, exec_date)
        excluded, _ = should_exclude(code, bar, self.config, prev_close)
        if excluded:
            return

        exec_price = apply_buy_slippage(bar.open, self.config.slippage_rate)

        if signal.target_weight > 0:
            target_amount = self.portfolio.total_value * signal.target_weight
            target_shares = int(target_amount / exec_price)
        else:
            target_shares = signal.target_shares

        target_shares = round_lot_size(target_shares)
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

        self.portfolio.cash -= total_debit

        if code in self.portfolio.positions:
            pos = self.portfolio.positions[code]
            old_shares = pos.shares
            pos.add_shares(actual_shares, exec_price, exec_date)
            pos.sellable_shares = min(pos.sellable_shares, old_shares)
        else:
            pos = Position(stock_code=code, shares=0, sellable_shares=0)
            pos.add_shares(actual_shares, exec_price, exec_date)
            self.portfolio.positions[code] = pos

        self.trade_records.append(TradeRecord(
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
        ))

    def _execute_sell(self, signal: Signal, exec_date: str) -> None:
        code = signal.stock_code
        pos = self.portfolio.positions.get(code)
        if pos is None or pos.sellable_shares == 0:
            return

        bars = self.bar_data.get(code, {})
        bar = bars.get(exec_date)
        if bar is None or bar.is_suspended:
            return

        exec_price = apply_sell_slippage(bar.open, self.config.slippage_rate)

        if signal.target_shares == 0:
            shares_to_sell = pos.sellable_shares
        else:
            shares_to_sell = min(signal.target_shares, pos.sellable_shares)

        shares_to_sell = round_lot_size(shares_to_sell)
        if shares_to_sell < 100:
            shares_to_sell = pos.sellable_shares
        if shares_to_sell == 0:
            return

        amount = shares_to_sell * exec_price
        commission, stamp_duty, slippage_cost, total_cost = calculate_sell_cost(
            amount, self.config.commission_rate, self.config.stamp_duty_rate, self.config.slippage_rate
        )

        realized_pnl = (exec_price - pos.cost_basis) * shares_to_sell - total_cost
        net_proceeds = amount - total_cost

        self.portfolio.cash += net_proceeds
        pos.remove_shares(shares_to_sell)

        if pos.shares == 0:
            del self.portfolio.positions[code]

        self.trade_records.append(TradeRecord(
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
        ))

    def _mark_to_market(self, trade_date: str) -> float:
        total = 0.0
        for code, pos in self.portfolio.positions.items():
            bars = self.bar_data.get(code, {})
            bar = bars.get(trade_date)
            if bar and not bar.is_suspended:
                pos.current_price = bar.close
                pos.market_value = pos.shares * bar.close
            total += pos.market_value
        return total

    def _get_prev_close(self, stock_code: str, date: str) -> float:
        bars = self.bar_data.get(stock_code, {})
        sorted_dates = sorted(bars.keys())
        try:
            idx = sorted_dates.index(date)
            if idx > 0:
                return bars[sorted_dates[idx - 1]].close
        except ValueError:
            pass
        return 0.0
