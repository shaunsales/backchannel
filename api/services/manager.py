import json
import hashlib
import logging
from datetime import datetime, timezone
from api.db import get_db

log = logging.getLogger(__name__)


PULLER_REGISTRY = {}  # keyed by service_type (e.g. "gmail", "telegram")


def register_puller(service_type: str, puller_cls):
    PULLER_REGISTRY[service_type] = puller_cls


def get_puller(service_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown service: {service_id}")

    svc_type = row["service_type"] or service_id
    puller_cls = PULLER_REGISTRY.get(svc_type)
    if puller_cls is None:
        raise ValueError(f"No puller registered for type: {svc_type}")

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


AUTH_TYPES = {
    "notion": "api_key",
    "telegram": "phone_code",
    "gmail": "app_password",
    "protonmail": "imap_login",
    "whatsapp": "qr_link",
}


def add_service_instance(service_type: str, display_name: str) -> str:
    """Create a new service instance of the given type. Returns the new service ID."""
    db = get_db()

    # Determine auth_type from known mapping, fallback to existing row
    auth_type = AUTH_TYPES.get(service_type)
    if not auth_type:
        existing = db.execute(
            "SELECT auth_type FROM services WHERE service_type = ? LIMIT 1", (service_type,)
        ).fetchone()
        if existing is None:
            raise ValueError(f"Unknown service type: {service_type}")
        auth_type = existing["auth_type"]

    # Generate next ID: count existing instances of this type
    count = db.execute(
        "SELECT COUNT(*) as cnt FROM services WHERE service_type = ?", (service_type,)
    ).fetchone()["cnt"]
    new_id = f"{service_type}-{count + 1}" if count > 0 else service_type

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO services (id, service_type, display_name, auth_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (new_id, service_type, display_name, auth_type, now, now),
    )
    db.commit()
    log.info("Added service instance: %s (%s) as %s", display_name, service_type, new_id)
    return new_id


def remove_service_instance(service_id: str):
    """Remove a service instance and all its data. Cannot remove the base instance."""
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown service: {service_id}")
    # Prevent removing the base service instance (id == service_type)
    if service_id == row["service_type"]:
        raise ValueError(f"Cannot remove the base {service_id} service. Disconnect it instead.")
    # Delete related data
    db.execute("DELETE FROM items WHERE service_id = ?", (service_id,))
    db.execute("DELETE FROM document_versions WHERE document_id IN (SELECT id FROM documents WHERE service_id = ?)", (service_id,))
    db.execute("DELETE FROM documents WHERE service_id = ?", (service_id,))
    db.execute("DELETE FROM sync_runs WHERE service_id = ?", (service_id,))
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    log.info("Removed service instance: %s", service_id)


def rename_service(service_id: str, display_name: str):
    """Rename a service instance."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE services SET display_name = ?, updated_at = ? WHERE id = ?",
        (display_name, now, service_id),
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


def clear_data(service_id: str):
    """Delete all synced data for a service (items, docs, runs) but keep credentials."""
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown service: {service_id}")
    db.execute("DELETE FROM items WHERE service_id = ?", (service_id,))
    db.execute("DELETE FROM document_versions WHERE document_id IN (SELECT id FROM documents WHERE service_id = ?)", (service_id,))
    db.execute("DELETE FROM documents WHERE service_id = ?", (service_id,))
    db.execute("DELETE FROM sync_runs WHERE service_id = ?", (service_id,))
    now = datetime.now(timezone.utc).isoformat()
    db.execute("UPDATE services SET sync_cursor = NULL, last_sync_at = NULL, updated_at = ? WHERE id = ?", (now, service_id))
    db.commit()
    log.info("Cleared all data for service: %s", service_id)


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

    log.info("Starting sync for %s (run_id=%d, cursor=%s)", service_id, run_id, cursor_before or "none")

    try:
        puller = get_puller(service_id)
        result = puller.pull(cursor=cursor_before)

        for item in result.items:
            item["service_id"] = service_id
            item["sync_run_id"] = run_id
            item.setdefault("thread_id", None)
            db.execute("""
                INSERT INTO items (service_id, item_type, source_id, thread_id, conversation,
                    sender, sender_is_me, recipients, subject, body_plain, body_html,
                    attachments, labels, metadata, source_ts, sync_run_id)
                VALUES (:service_id, :item_type, :source_id, :thread_id, :conversation,
                    :sender, :sender_is_me, :recipients, :subject, :body_plain, :body_html,
                    :attachments, :labels, :metadata, :source_ts, :sync_run_id)
                ON CONFLICT(service_id, source_id) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    body_plain=excluded.body_plain, body_html=excluded.body_html,
                    subject=excluded.subject, labels=excluded.labels,
                    metadata=excluded.metadata, source_ts=excluded.source_ts
            """, item)

        if result.documents:
            log.info("Processing %d documents...", len(result.documents))

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
                log.info("Updated: %s (v%d → v%d)", doc["title"], existing["version"], existing["version"] + 1)
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

        # Deletion detection: remove docs no longer present in source
        docs_deleted = 0
        if result.all_source_ids:
            existing_docs = db.execute(
                "SELECT id, source_id, title FROM documents WHERE service_id = ?",
                (service_id,),
            ).fetchall()
            for ed in existing_docs:
                if ed["source_id"] not in result.all_source_ids:
                    log.info("Removing deleted doc: %s (source_id=%s)", ed["title"], ed["source_id"][:12])
                    db.execute("DELETE FROM document_versions WHERE document_id = ?", (ed["id"],))
                    db.execute("DELETE FROM documents WHERE id = ?", (ed["id"],))
                    docs_deleted += 1
            if docs_deleted:
                log.info("Removed %d documents no longer in source", docs_deleted)

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

        log.info("Sync complete for %s: %d fetched, %d new, %d updated, %d deleted (%.1fs)",
                 service_id, total_fetched, total_new, total_updated, docs_deleted, duration)

        return {"run_id": run_id, "status": "success", "items": len(result.items), "docs_deleted": docs_deleted}

    except Exception as e:
        log.error("Sync failed for %s: %s", service_id, e)
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE sync_runs SET status='failed', completed_at=?, error_message=? WHERE id=?",
            (now, str(e), run_id),
        )
        db.commit()
        raise
