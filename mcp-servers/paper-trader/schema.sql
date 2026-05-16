-- Paper Trader backtest database schema

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    strategy        TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'created',
    initial_capital REAL NOT NULL DEFAULT 1000000.0,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    universe        TEXT NOT NULL DEFAULT '[]',
    benchmark       TEXT NOT NULL DEFAULT 'sh000300',
    cost_commission  REAL NOT NULL DEFAULT 0.00025,
    cost_stamp_duty  REAL NOT NULL DEFAULT 0.0005,
    cost_slippage    REAL NOT NULL DEFAULT 0.0005,
    exclude_st      INTEGER NOT NULL DEFAULT 1,
    current_date    TEXT,
    final_nav       REAL,
    total_trades    INTEGER DEFAULT 0,
    error_message   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_nav (
    session_id      TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    nav             REAL NOT NULL,
    cash            REAL NOT NULL,
    positions_value REAL NOT NULL,
    benchmark_value REAL NOT NULL,
    benchmark_close REAL NOT NULL,
    daily_return    REAL NOT NULL,
    benchmark_return REAL NOT NULL,
    excess_return   REAL NOT NULL,
    PRIMARY KEY (session_id, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_nav_session ON daily_nav(session_id);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    stock_code      TEXT NOT NULL,
    direction       TEXT NOT NULL,
    shares          INTEGER NOT NULL,
    price           REAL NOT NULL,
    amount          REAL NOT NULL,
    commission      REAL NOT NULL DEFAULT 0.0,
    stamp_duty      REAL NOT NULL DEFAULT 0.0,
    slippage_cost   REAL NOT NULL DEFAULT 0.0,
    total_cost      REAL NOT NULL DEFAULT 0.0,
    realized_pnl    REAL,
    signal_date     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id);
CREATE INDEX IF NOT EXISTS idx_trades_stock ON trades(session_id, stock_code);

CREATE TABLE IF NOT EXISTS positions (
    session_id      TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    stock_code      TEXT NOT NULL,
    shares          INTEGER NOT NULL,
    cost_basis      REAL NOT NULL,
    market_value    REAL NOT NULL,
    unrealized_pnl  REAL NOT NULL,
    unrealized_pnl_pct REAL NOT NULL,
    weight          REAL NOT NULL,
    sellable        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, trade_date, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_positions_session ON positions(session_id);
CREATE INDEX IF NOT EXISTS idx_positions_date ON positions(session_id, trade_date);

CREATE TABLE IF NOT EXISTS trading_calendar (
    trade_date      TEXT PRIMARY KEY,
    is_trading_day  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    signal_date     TEXT NOT NULL,
    stock_code      TEXT NOT NULL,
    direction       TEXT NOT NULL,
    target_weight   REAL NOT NULL DEFAULT 0.0,
    target_shares   INTEGER NOT NULL DEFAULT 0,
    processed       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pending_signals_session ON pending_signals(session_id);
CREATE INDEX IF NOT EXISTS idx_pending_signals_date ON pending_signals(session_id, signal_date);
