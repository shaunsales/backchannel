import sqlite3
import threading
from pathlib import Path
from api.config import DATABASE_PATH

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

    # Migration: add service_type column if missing (for existing DBs)
    cols = [r[1] for r in db.execute("PRAGMA table_info(services)").fetchall()]
    if "service_type" not in cols:
        db.execute("ALTER TABLE services ADD COLUMN service_type TEXT NOT NULL DEFAULT ''")
        db.execute("UPDATE services SET service_type = id WHERE service_type = ''")
        db.execute("CREATE INDEX IF NOT EXISTS idx_services_type ON services(service_type)")
    # Ensure index exists even for fresh DBs (not just migrations)
    db.execute("CREATE INDEX IF NOT EXISTS idx_services_type ON services(service_type)")
    db.commit()

    # Seed (now safe — service_type column guaranteed to exist)
    db.executescript(SEED_SQL)

    # Backfill any rows with empty service_type
    db.execute("UPDATE services SET service_type = id WHERE service_type = ''")

    # Mark any stale "running" sync runs as failed (from prior crash/restart)
    db.execute(
        "UPDATE sync_runs SET status='failed', error_message='Server restarted', "
        "completed_at=datetime('now') WHERE status='running'"
    )
    db.commit()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS services (
    id            TEXT PRIMARY KEY,
    service_type  TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id    TEXT NOT NULL REFERENCES services(id),
    source_id     TEXT NOT NULL,
    title         TEXT NOT NULL,
    body_markdown TEXT NOT NULL DEFAULT '',
    content_hash  TEXT NOT NULL DEFAULT '',
    version       INTEGER NOT NULL DEFAULT 1,
    hidden        INTEGER NOT NULL DEFAULT 0,
    metadata      TEXT DEFAULT '{}',
    source_ts     TEXT,
    fetched_at    TEXT NOT NULL DEFAULT (datetime('now')),
    sync_run_id   INTEGER REFERENCES sync_runs(id),
    UNIQUE(service_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_docs_service ON documents(service_id);
CREATE INDEX IF NOT EXISTS idx_docs_source_ts ON documents(source_ts DESC);

CREATE TABLE IF NOT EXISTS document_versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   INTEGER NOT NULL REFERENCES documents(id),
    version       INTEGER NOT NULL,
    body_markdown TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    source_ts     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_docver_doc ON document_versions(document_id, version DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, body_markdown,
    content='documents',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, body_markdown)
    VALUES (new.id, new.title, new.body_markdown);
END;

CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, body_markdown)
    VALUES ('delete', old.id, old.title, old.body_markdown);
END;

CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, body_markdown)
    VALUES ('delete', old.id, old.title, old.body_markdown);
    INSERT INTO documents_fts(rowid, title, body_markdown)
    VALUES (new.id, new.title, new.body_markdown);
END;

"""

SEED_SQL = """
INSERT OR IGNORE INTO services (id, service_type, display_name, auth_type) VALUES
    ('notion',     'notion',     'Notion',     'api_key'),
    ('gmail',      'gmail',      'Gmail',      'app_password'),
    ('telegram',   'telegram',   'Telegram',   'phone_code'),
    ('protonmail', 'protonmail', 'ProtonMail', 'imap_login'),
    ('whatsapp',   'whatsapp',   'WhatsApp',   'qr_link');
"""
