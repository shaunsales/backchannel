import sqlite3
import threading
from pathlib import Path
from app.config import DATABASE_PATH

_local = threading.local()


def get_db():
    conn = getattr(_local, "connection", None)
    if conn is None:
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.connection = conn
    return conn


def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.executescript(SEED_SQL)
    db.commit()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS services (
    id            TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'disconnected',
    auth_type     TEXT NOT NULL,
    credentials   TEXT DEFAULT '{}',
    config        TEXT DEFAULT '{}',
    enabled       INTEGER NOT NULL DEFAULT 1,
    last_sync_at  TEXT,
    sync_cursor   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id     TEXT NOT NULL REFERENCES services(id),
    run_type       TEXT NOT NULL DEFAULT 'manual',
    status         TEXT NOT NULL DEFAULT 'running',
    started_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT,
    items_fetched  INTEGER DEFAULT 0,
    items_new      INTEGER DEFAULT 0,
    items_updated  INTEGER DEFAULT 0,
    cursor_before  TEXT,
    cursor_after   TEXT,
    error_message  TEXT,
    duration_sec   REAL
);

CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id   TEXT NOT NULL REFERENCES services(id),
    item_type    TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    conversation TEXT,
    sender       TEXT,
    sender_is_me INTEGER DEFAULT 0,
    recipients   TEXT DEFAULT '[]',
    subject      TEXT,
    body_plain   TEXT,
    body_html    TEXT,
    attachments  TEXT DEFAULT '[]',
    labels       TEXT DEFAULT '[]',
    metadata     TEXT DEFAULT '{}',
    source_ts    TEXT,
    fetched_at   TEXT NOT NULL DEFAULT (datetime('now')),
    sync_run_id  INTEGER REFERENCES sync_runs(id),
    UNIQUE(service_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_items_service    ON items(service_id);
CREATE INDEX IF NOT EXISTS idx_items_source_ts  ON items(source_ts DESC);
CREATE INDEX IF NOT EXISTS idx_items_type       ON items(item_type);
CREATE INDEX IF NOT EXISTS idx_items_me_ts      ON items(sender_is_me, source_ts DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    subject, body_plain, sender, conversation,
    content='items',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, subject, body_plain, sender, conversation)
    VALUES (new.id, new.subject, new.body_plain, new.sender, new.conversation);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, subject, body_plain, sender, conversation)
    VALUES ('delete', old.id, old.subject, old.body_plain, old.sender, old.conversation);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, subject, body_plain, sender, conversation)
    VALUES ('delete', old.id, old.subject, old.body_plain, old.sender, old.conversation);
    INSERT INTO items_fts(rowid, subject, body_plain, sender, conversation)
    VALUES (new.id, new.subject, new.body_plain, new.sender, new.conversation);
END;
"""

SEED_SQL = """
INSERT OR IGNORE INTO services (id, display_name, auth_type) VALUES
    ('notion',     'Notion',     'api_key'),
    ('gmail',      'Gmail',      'oauth2'),
    ('telegram',   'Telegram',   'phone_code'),
    ('protonmail', 'ProtonMail', 'imap_login'),
    ('whatsapp',   'WhatsApp',   'qr_link');
"""
