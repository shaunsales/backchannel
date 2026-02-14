import json
import hashlib
from datetime import datetime, timezone
from app.db import get_db


PULLER_REGISTRY = {}


def register_puller(service_id: str, puller_cls):
    PULLER_REGISTRY[service_id] = puller_cls


def get_puller(service_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown service: {service_id}")

    puller_cls = PULLER_REGISTRY.get(service_id)
    if puller_cls is None:
        raise ValueError(f"No puller registered for: {service_id}")

    credentials = json.loads(row["credentials"] or "{}")
    config = json.loads(row["config"] or "{}")
    return puller_cls(service_id=service_id, credentials=credentials, config=config)


def connect(service_id: str, credentials: dict):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE services SET credentials = ?, status = 'connected', updated_at = ? WHERE id = ?",
        (json.dumps(credentials), now, service_id),
    )
    db.commit()


def disconnect(service_id: str):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE services SET credentials = '{}', status = 'disconnected', sync_cursor = NULL, updated_at = ? WHERE id = ?",
        (now, service_id),
    )
    db.commit()


def test(service_id: str) -> tuple[bool, str]:
    try:
        puller = get_puller(service_id)
        ok = puller.test_connection()
        return (ok, "Connection successful" if ok else "Connection test returned False")
    except Exception as e:
        return (False, str(e))


def status(service_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return dict(row) if row else None


def run_sync(service_id: str, run_type: str = "manual") -> dict:
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if service is None:
        raise ValueError(f"Unknown service: {service_id}")
    if service["status"] != "connected":
        raise ValueError(f"Service {service_id} is not connected (status: {service['status']})")

    cursor_before = service["sync_cursor"]

    run_id = db.execute(
        "INSERT INTO sync_runs (service_id, run_type, cursor_before) VALUES (?, ?, ?)",
        (service_id, run_type, cursor_before),
    ).lastrowid
    db.commit()

    try:
        puller = get_puller(service_id)
        result = puller.pull(cursor=cursor_before)

        for item in result.items:
            item["service_id"] = service_id
            item["sync_run_id"] = run_id
            db.execute("""
                INSERT INTO items (service_id, item_type, source_id, conversation,
                    sender, sender_is_me, recipients, subject, body_plain, body_html,
                    attachments, labels, metadata, source_ts, sync_run_id)
                VALUES (:service_id, :item_type, :source_id, :conversation,
                    :sender, :sender_is_me, :recipients, :subject, :body_plain, :body_html,
                    :attachments, :labels, :metadata, :source_ts, :sync_run_id)
                ON CONFLICT(service_id, source_id) DO UPDATE SET
                    body_plain=excluded.body_plain, body_html=excluded.body_html,
                    subject=excluded.subject, labels=excluded.labels,
                    metadata=excluded.metadata, source_ts=excluded.source_ts
            """, item)

        docs_new = 0
        docs_updated = 0
        for doc in result.documents:
            content_hash = hashlib.sha256(doc["body_markdown"].encode()).hexdigest()
            existing = db.execute(
                "SELECT id, content_hash, version FROM documents WHERE service_id = ? AND source_id = ?",
                (service_id, doc["source_id"]),
            ).fetchone()

            if existing is None:
                db.execute("""
                    INSERT INTO documents (service_id, source_id, title, body_markdown,
                        content_hash, version, metadata, source_ts, sync_run_id)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (service_id, doc["source_id"], doc["title"], doc["body_markdown"],
                      content_hash, doc.get("metadata", "{}"), doc.get("source_ts"), run_id))
                docs_new += 1
            elif existing["content_hash"] != content_hash:
                new_version = existing["version"] + 1
                db.execute("""
                    INSERT INTO document_versions (document_id, version, body_markdown, content_hash, source_ts)
                    VALUES (?, ?, ?, ?, ?)
                """, (existing["id"], existing["version"],
                      db.execute("SELECT body_markdown FROM documents WHERE id = ?", (existing["id"],)).fetchone()["body_markdown"],
                      existing["content_hash"], doc.get("source_ts")))
                db.execute("""
                    UPDATE documents SET title=?, body_markdown=?, content_hash=?,
                        version=?, metadata=?, source_ts=?, fetched_at=datetime('now'), sync_run_id=?
                    WHERE id=?
                """, (doc["title"], doc["body_markdown"], content_hash,
                      new_version, doc.get("metadata", "{}"), doc.get("source_ts"), run_id, existing["id"]))
                docs_updated += 1

        now = datetime.utcnow().isoformat()
        started = db.execute(
            "SELECT started_at FROM sync_runs WHERE id = ?", (run_id,)
        ).fetchone()["started_at"]

        duration = (datetime.fromisoformat(now) - datetime.fromisoformat(started)).total_seconds()

        total_fetched = len(result.items) + len(result.documents)
        total_new = result.items_new + docs_new
        total_updated = result.items_updated + docs_updated

        db.execute("""
            UPDATE sync_runs SET status='success', completed_at=?, items_fetched=?,
                items_new=?, items_updated=?, cursor_after=?, duration_sec=?
            WHERE id=?
        """, (now, total_fetched, total_new, total_updated,
              result.new_cursor, duration, run_id))

        db.execute(
            "UPDATE services SET last_sync_at=?, sync_cursor=?, updated_at=? WHERE id=?",
            (now, result.new_cursor or cursor_before, now, service_id),
        )
        db.commit()

        return {"run_id": run_id, "status": "success", "items": len(result.items)}

    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE sync_runs SET status='failed', completed_at=?, error_message=? WHERE id=?",
            (now, str(e), run_id),
        )
        db.commit()
        raise
