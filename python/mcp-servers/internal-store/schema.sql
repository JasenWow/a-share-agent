-- Cache tracking table
CREATE TABLE IF NOT EXISTS cache_entries (
    source      TEXT NOT NULL,       -- 'akshare' | 'tushare'
    tool_name   TEXT NOT NULL,       -- MCP tool name
    params_hash TEXT NOT NULL,       -- SHA256 of params JSON
    file_path   TEXT NOT NULL,       -- Relative path
    fetched_at  TEXT NOT NULL,       -- ISO timestamp
    expires_at  TEXT NOT NULL,       -- Expiry time
    row_count   INTEGER DEFAULT 0,
    PRIMARY KEY (source, tool_name, params_hash)
);

-- Backtest results index
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

-- Portfolio state
CREATE TABLE IF NOT EXISTS portfolio_state (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    holdings    TEXT NOT NULL,       -- JSON: [{ts_code, weight, shares}]
    cash        REAL DEFAULT 0,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- Experiment runs for strategy optimization
CREATE TABLE IF NOT EXISTS experiments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    strategy    TEXT NOT NULL,       -- JSON
    params      TEXT NOT NULL,       -- JSON
    result      TEXT NOT NULL,       -- JSON: {final_nav, sharpe, max_drawdown}
    created_at  TEXT DEFAULT (datetime('now'))
);

-- State transitions for RL-based strategies
CREATE TABLE IF NOT EXISTS transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id   INTEGER NOT NULL,
    state           TEXT NOT NULL,   -- JSON: current state
    strategy        TEXT NOT NULL,   -- JSON: action taken
    reward          TEXT NOT NULL,   -- JSON: reward received
    next_state      TEXT NOT NULL,   -- JSON: resulting state
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Episode summary for simulation runs
CREATE TABLE IF NOT EXISTS episode_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    period          TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    final_nav       REAL NOT NULL,
    sharpe          REAL NOT NULL,
    max_drawdown    REAL NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);
