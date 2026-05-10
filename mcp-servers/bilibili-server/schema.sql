-- Followed UP hosts
CREATE TABLE IF NOT EXISTS up_hosts (
    mid             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    keywords        TEXT DEFAULT '',
    added_at        TEXT NOT NULL,
    last_fetched_at TEXT,
    notes           TEXT DEFAULT ''
);

-- Credential metadata (singleton row)
CREATE TABLE IF NOT EXISTS credential_meta (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    login_status    TEXT DEFAULT 'not_logged_in',
    updated_at      TEXT NOT NULL
);

-- Ensure the singleton row exists
INSERT OR IGNORE INTO credential_meta (id, login_status, updated_at)
VALUES (1, 'not_logged_in', datetime('now'));
