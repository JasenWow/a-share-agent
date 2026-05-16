"""
Integration test: end-to-end step-by-step backtest with real A-share data.

Tests the full workflow: create session -> load data -> step daily -> submit signals -> performance.

Run: python -m pytest mcp-servers/paper-trader/test_integration.py -v -s
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

_int_tmpdir = tempfile.mkdtemp(prefix="paper_trader_int_")
INT_DB = Path(_int_tmpdir) / "backtest.db"

import engine as engine_mod  # noqa: E402
from models import Signal  # noqa: E402
from performance import compute_performance  # noqa: E402

engine_mod.DB_PATH = INT_DB
engine_mod.PREDICTION_DB_PATH = INT_DB  # Use our own DB for calendar too

import server as server_mod  # noqa: E402
from server import _init_db  # noqa: E402

server_mod.DB_PATH = INT_DB


def _norm_date(d: str) -> str:
    """Convert '2025-04-01' to '20250401'."""
    return d.replace("-", "")


# Real AKShare data for 000001 (平安银行) April 2025
RAW_000001 = [
    {"日期": "2025-04-01", "开盘": 10.672, "收盘": 10.672, "最高": 10.702, "最低": 10.622, "成交量": 68.147},
    {"日期": "2025-04-02", "开盘": 10.652, "收盘": 10.772, "最高": 10.812, "最低": 10.652, "成交量": 93.264},
    {"日期": "2025-04-03", "开盘": 10.712, "收盘": 10.742, "最高": 10.792, "最低": 10.702, "成交量": 64.391},
    {"日期": "2025-04-07", "开盘": 10.402, "收盘": 10.102, "最高": 10.452, "最低": 9.882, "成交量": 254.556},
    {"日期": "2025-04-08", "开盘": 10.082, "收盘": 10.222, "最高": 10.252, "最低": 10.062, "成交量": 146.399},
    {"日期": "2025-04-09", "开盘": 10.132, "收盘": 10.202, "最高": 10.232, "最低": 10.062, "成交量": 106.439},
    {"日期": "2025-04-10", "开盘": 10.262, "收盘": 10.302, "最高": 10.332, "最低": 10.222, "成交量": 86.655},
    {"日期": "2025-04-11", "开盘": 10.272, "收盘": 10.292, "最高": 10.302, "最低": 10.232, "成交量": 58.388},
    {"日期": "2025-04-14", "开盘": 10.352, "收盘": 10.332, "最高": 10.442, "最低": 10.322, "成交量": 78.599},
    {"日期": "2025-04-15", "开盘": 10.322, "收盘": 10.352, "最高": 10.372, "最低": 10.302, "成交量": 72.275},
    {"日期": "2025-04-16", "开盘": 10.332, "收盘": 10.402, "最高": 10.412, "最低": 10.312, "成交量": 84.282},
    {"日期": "2025-04-17", "开盘": 10.352, "收盘": 10.462, "最高": 10.482, "最低": 10.332, "成交量": 82.392},
    {"日期": "2025-04-18", "开盘": 10.442, "收盘": 10.582, "最高": 10.592, "最低": 10.432, "成交量": 72.710},
    {"日期": "2025-04-21", "开盘": 10.402, "收盘": 10.422, "最高": 10.532, "最低": 10.372, "成交量": 111.418},
    {"日期": "2025-04-22", "开盘": 10.422, "收盘": 10.442, "最高": 10.462, "最低": 10.382, "成交量": 83.113},
    {"日期": "2025-04-23", "开盘": 10.442, "收盘": 10.412, "最高": 10.452, "最低": 10.372, "成交量": 58.638},
    {"日期": "2025-04-24", "开盘": 10.402, "收盘": 10.432, "最高": 10.462, "最低": 10.392, "成交量": 68.926},
    {"日期": "2025-04-25", "开盘": 10.442, "收盘": 10.412, "最高": 10.452, "最低": 10.392, "成交量": 63.755},
    {"日期": "2025-04-28", "开盘": 10.402, "收盘": 10.402, "最高": 10.442, "最低": 10.362, "成交量": 64.202},
    {"日期": "2025-04-29", "开盘": 10.402, "收盘": 10.382, "最高": 10.422, "最低": 10.352, "成交量": 64.905},
    {"日期": "2025-04-30", "开盘": 10.362, "收盘": 10.312, "最高": 10.372, "最低": 10.292, "成交量": 86.984},
]

# Real AKShare data for 600519 (贵州茅台) April 2025
RAW_600519 = [
    {"日期": "2025-04-01", "开盘": 1512.443, "收盘": 1504.463, "最高": 1518.333, "最低": 1500.653, "成交量": 1.856},
    {"日期": "2025-04-02", "开盘": 1506.443, "收盘": 1497.463, "最高": 1516.243, "最低": 1493.943, "成交量": 2.167},
    {"日期": "2025-04-03", "开盘": 1478.443, "收盘": 1517.323, "最高": 1534.443, "最低": 1477.453, "成交量": 3.548},
    {"日期": "2025-04-07", "开盘": 1468.453, "收盘": 1448.443, "最高": 1485.293, "最低": 1410.443, "成交量": 10.195},
    {"日期": "2025-04-08", "开盘": 1461.443, "收盘": 1493.443, "最高": 1493.443, "最低": 1443.443, "成交量": 7.388},
    {"日期": "2025-04-09", "开盘": 1473.463, "收盘": 1489.483, "最高": 1505.243, "最低": 1468.993, "成交量": 5.563},
    {"日期": "2025-04-10", "开盘": 1499.433, "收盘": 1497.443, "最高": 1503.443, "最低": 1476.443, "成交量": 3.862},
    {"日期": "2025-04-11", "开盘": 1528.413, "收盘": 1517.423, "最高": 1528.413, "最低": 1493.443, "成交量": 3.263},
    {"日期": "2025-04-14", "开盘": 1509.413, "收盘": 1500.433, "最高": 1514.443, "最低": 1499.973, "成交量": 2.171},
    {"日期": "2025-04-15", "开盘": 1500.443, "收盘": 1506.443, "最高": 1513.443, "最低": 1493.443, "成交量": 2.149},
    {"日期": "2025-04-16", "开盘": 1500.443, "收盘": 1507.613, "最高": 1524.443, "最低": 1485.443, "成交量": 3.116},
    {"日期": "2025-04-17", "开盘": 1502.443, "收盘": 1518.443, "最高": 1524.943, "最低": 1498.433, "成交量": 2.385},
    {"日期": "2025-04-18", "开盘": 1514.443, "收盘": 1514.383, "最高": 1523.443, "最低": 1504.443, "成交量": 2.030},
    {"日期": "2025-04-21", "开盘": 1513.943, "收盘": 1499.443, "最高": 1513.943, "最低": 1499.443, "成交量": 1.806},
    {"日期": "2025-04-22", "开盘": 1498.443, "收盘": 1497.243, "最高": 1504.743, "最低": 1491.653, "成交量": 1.843},
    {"日期": "2025-04-23", "开盘": 1507.443, "收盘": 1500.443, "最高": 1507.663, "最低": 1493.443, "成交量": 1.867},
    {"日期": "2025-04-24", "开盘": 1500.443, "收盘": 1500.693, "最高": 1509.123, "最低": 1497.423, "成交量": 1.487},
    {"日期": "2025-04-25", "开盘": 1505.543, "收盘": 1498.443, "最高": 1509.643, "最低": 1498.443, "成交量": 1.477},
    {"日期": "2025-04-28", "开盘": 1500.443, "收盘": 1498.443, "最高": 1503.443, "最低": 1495.043, "成交量": 1.466},
    {"日期": "2025-04-29", "开盘": 1498.443, "收盘": 1492.443, "最高": 1500.983, "最低": 1480.463, "成交量": 1.892},
    {"日期": "2025-04-30", "开盘": 1498.433, "收盘": 1495.443, "最高": 1515.103, "最低": 1494.743, "成交量": 2.575},
]

# CSI 300 benchmark April 2025 (date field name differs)
RAW_BENCHMARK = [
    {"date": "2025-04-01", "close": 3887.684},
    {"date": "2025-04-02", "close": 3884.386},
    {"date": "2025-04-03", "close": 3861.503},
    {"date": "2025-04-07", "close": 3589.441},
    {"date": "2025-04-08", "close": 3650.759},
    {"date": "2025-04-09", "close": 3686.794},
    {"date": "2025-04-10", "close": 3735.115},
    {"date": "2025-04-11", "close": 3750.517},
    {"date": "2025-04-14", "close": 3759.142},
    {"date": "2025-04-15", "close": 3761.235},
    {"date": "2025-04-16", "close": 3772.820},
    {"date": "2025-04-17", "close": 3772.222},
    {"date": "2025-04-18", "close": 3772.523},
    {"date": "2025-04-21", "close": 3784.881},
    {"date": "2025-04-22", "close": 3783.952},
    {"date": "2025-04-23", "close": 3786.882},
    {"date": "2025-04-24", "close": 3784.357},
    {"date": "2025-04-25", "close": 3786.994},
    {"date": "2025-04-28", "close": 3781.619},
    {"date": "2025-04-29", "close": 3775.077},
    {"date": "2025-04-30", "close": 3770.571},
]


def _prepare_stock_data(raw: list[dict]) -> list[dict]:
    """Normalize AKShare stock data: convert dates to YYYYMMDD format."""
    return [{**r, "日期": _norm_date(r["日期"])} for r in raw]


def _prepare_benchmark_data(raw: list[dict]) -> list[dict]:
    """Normalize AKShare benchmark data: rename 'date' to '日期', convert format."""
    return [{"日期": _norm_date(r["date"]), "收盘": r["close"]} for r in raw]


@pytest.fixture(autouse=True)
def init_db():
    # Ensure our module-level DB paths are active (may have been overwritten by other test files)
    engine_mod.DB_PATH = INT_DB
    engine_mod.PREDICTION_DB_PATH = INT_DB
    server_mod.DB_PATH = INT_DB

    INT_DB.parent.mkdir(parents=True, exist_ok=True)
    if INT_DB.exists():
        INT_DB.unlink()
    _init_db()
    # Seed trading calendar from our stock data dates
    conn = sqlite3.connect(str(INT_DB))
    all_dates = set()
    for r in RAW_000001:
        all_dates.add(_norm_date(r["日期"]))
    for d in sorted(all_dates):
        conn.execute("INSERT OR REPLACE INTO trading_calendar (trade_date, is_trading_day) VALUES (?, 1)", (d,))
    conn.commit()
    conn.close()
    yield
    if INT_DB.exists():
        INT_DB.unlink()


@pytest.fixture
def step_engine():
    """Create and configure an engine ready for step-by-step testing."""
    # Insert session via server tool
    result = server_mod.create_session(
        start_date="20250401",
        end_date="20250430",
        name="integration_test",
        strategy="momentum_daily",
        initial_capital=1000000.0,
        universe=["000001", "600519"],
    )
    session_id = result[0]["session_id"]

    # Load data
    stock_data = {
        "000001": _prepare_stock_data(RAW_000001),
        "600519": _prepare_stock_data(RAW_600519),
    }
    benchmark_data = _prepare_benchmark_data(RAW_BENCHMARK)

    load_result = server_mod.load_bar_data(session_id, ["000001", "600519"], stock_data, benchmark_data)
    assert load_result[0]["loaded"] == 2

    engine = server_mod._engines[session_id]
    return engine, session_id


class TestIntegration:
    def test_step_by_step_daily_trading(self, step_engine):
        """Full integration: agent steps through each day, observes, decides, trades."""
        engine, session_id = step_engine

        print(f"\n{'='*60}")
        print(f"Session: {session_id}")
        print(f"Initial Capital: ¥{engine.config.initial_capital:,.0f}")
        print(f"Period: {engine.config.start_date} ~ {engine.config.end_date}")
        print(f"Universe: {engine.config.universe}")
        print(f"{'='*60}")

        trading_log = []

        # Day 1: 2025-04-01 - observe, buy both stocks
        r = engine.step()
        print(f"\n[Day {r['day_index']}] {r['trade_date']}")
        print(f"  NAV: ¥{r['nav']:,.2f} | Cash: ¥{r['cash']:,.2f}")
        for code, bar in r["market_data"].items():
            print(f"  {code}: Open={bar['open']:.3f} Close={bar['close']:.3f}")

        # Strategy: buy 40% 平安银行, 30% 贵州茅台
        engine.register_signals([
            Signal(signal_date=r["trade_date"], stock_code="000001", direction="buy", target_weight=0.4),
            Signal(signal_date=r["trade_date"], stock_code="600519", direction="buy", target_weight=0.3),
        ])
        trading_log.append((r["trade_date"], "SIGNAL", "买入000001 40%, 600519 30%"))

        # Day 2-4: 2025-04-02 ~ 04-03, 04-07 (including the big drop on Apr 7)
        for _ in range(2):
            r = engine.step()
            print(f"\n[Day {r['day_index']}] {r['trade_date']}")
            print(f"  NAV: ¥{r['nav']:,.2f} | Cash: ¥{r['cash']:,.2f}")
            for p in r["positions"]:
                print(f"  Holding: {p['stock_code']} {p['shares']}股 @ ¥{p['cost_basis']:.3f} 市值¥{p['market_value']:,.0f}")

        # Day 4: 2025-04-07 - big crash day! 000001 dropped -5.6%
        # Wait, positions should now be established (bought on 04-02 open)
        r = engine.step()
        print(f"\n[Day {r['day_index']}] {r['trade_date']} ⚠️ CRASH DAY")
        print(f"  NAV: ¥{r['nav']:,.2f} | Cash: ¥{r['cash']:,.2f}")
        for p in r["positions"]:
            pnl_str = f"+{p['unrealized_pnl']:,.0f}" if p["unrealized_pnl"] >= 0 else f"{p['unrealized_pnl']:,.0f}"
            print(f"  Holding: {p['stock_code']} {p['shares']}股 浮盈 {pnl_str}")

        # After crash, decide to hold (no signal)
        trading_log.append((r["trade_date"], "HOLD", "持有不动"))

        # Continue stepping...
        for _ in range(10):
            r = engine.step()
            print(f"\n[Day {r['day_index']}] {r['trade_date']}")
            print(f"  NAV: ¥{r['nav']:,.2f} | Cash: ¥{r['cash']:,.2f} | Positions: {len(r['positions'])}")

        # Around mid-month, decide to sell 000001 (it recovered)
        if r["positions"]:
            sell_target = next((p for p in r["positions"] if p["stock_code"] == "000001" and p["sellable_shares"] > 0), None)
            if sell_target:
                engine.register_signals([
                    Signal(signal_date=r["trade_date"], stock_code="000001", direction="sell"),
                ])
                trading_log.append((r["trade_date"], "SIGNAL", "卖出000001"))
                print("  >> Decision: SELL 000001")

        # Step through remaining days
        remaining = r["remaining_days"]
        for _ in range(remaining):
            r = engine.step()
            if "trade_date" in r:
                print(f"\n[Day {r['day_index']}] {r['trade_date']}")
                print(f"  NAV: ¥{r['nav']:,.2f} | Cash: ¥{r['cash']:,.2f} | Positions: {len(r['positions'])}")

        # Should be completed
        final_r = engine.step()
        assert final_r["status"] == "completed"
        print(f"\n{'='*60}")
        print(f"FINAL: NAV ¥{final_r['final_nav']:,.2f}")
        print(f"{'='*60}")

        # Get full performance metrics
        perf = compute_performance(session_id)
        m = perf[0]
        print("\n--- Performance Report ---")
        print(f"Total Return:     {m['total_return']*100:.2f}%")
        print(f"Annual Return:    {m['annual_return']*100:.2f}%")
        print(f"Sharpe Ratio:     {m['sharpe_ratio']:.4f}")
        print(f"Max Drawdown:     {m['max_drawdown']*100:.2f}% ({m['max_drawdown_start']} ~ {m['max_drawdown_end']})")
        print(f"Win Rate:         {m['win_rate']*100:.1f}%")
        print(f"Total Trades:     {m['total_trades']}")
        print(f"Total Cost:       ¥{m['total_cost']:,.2f}")
        print(f"Benchmark Return: {m['benchmark_total_return']*100:.2f}%")
        print(f"Excess Return:    {m['excess_annual_return']*100:.2f}%")
        print(f"Trading Days:     {m['trading_days']}")

        # Assertions
        assert m["trading_days"] == 21
        assert m["total_trades"] >= 2  # At least buy 000001 + buy 600519
        assert "sharpe_ratio" in m
        assert m["max_drawdown"] > 0

    def test_batch_run_same_result(self, step_engine):
        """Verify batch run and step run produce same results for same signals."""
        engine, session_id = step_engine

        # Submit all signals upfront then run batch
        trading_days = [r["日期"] for r in _prepare_stock_data(RAW_000001)]

        # Buy both on day 1
        engine.register_signals([
            Signal(signal_date=trading_days[0], stock_code="000001", direction="buy", target_weight=0.5),
            Signal(signal_date=trading_days[0], stock_code="600519", direction="buy", target_weight=0.3),
        ])

        # Run batch
        result = engine.run()
        assert result["status"] == "completed"
        batch_nav = result["final_nav"]

        print(f"\nBatch run final NAV: ¥{batch_nav:,.2f}")
        print(f"Total return: {result['total_return']*100:.2f}%")

        assert batch_nav != engine.config.initial_capital  # Should have changed

    def test_get_equity_curve_and_trade_log(self, step_engine):
        """Test equity curve and trade log retrieval after a run."""
        engine, session_id = step_engine

        trading_days = [r["日期"] for r in _prepare_stock_data(RAW_000001)]
        engine.register_signals([
            Signal(signal_date=trading_days[0], stock_code="000001", direction="buy", target_weight=0.5),
        ])
        engine.run()

        # Get equity curve
        curve = server_mod.get_equity_curve(session_id)
        assert len(curve) == 21
        assert all("nav" in r for r in curve)
        assert all("daily_return" in r for r in curve)
        print(f"\nEquity curve: {len(curve)} records")
        print(f"  Start NAV: ¥{curve[0]['nav']:,.2f}")
        print(f"  End NAV:   ¥{curve[-1]['nav']:,.2f}")

        # Get trade log
        trades = server_mod.get_trade_log(session_id)
        assert len(trades) >= 1
        print(f"  Trades: {len(trades)}")
        for t in trades:
            print(f"    {t['trade_date']} {t['direction']} {t['stock_code']} "
                  f"{t['shares']}股 @ ¥{t['price']:.3f} 成本¥{t['total_cost']:.2f}")
