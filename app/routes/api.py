import json
from fasthtml.common import *
from app.db import get_db


def register(rt):

    # ── Documents ────────────────────────────────────────────────

    @rt("/api/documents")
    def get(q: str = "", limit: int = 50, offset: int = 0,
            include_hidden: str = "", service: str = ""):
        db = get_db()
        params = []
        conditions = []

        if not include_hidden:
            conditions.append("d.hidden = 0")

        if service:
            conditions.append("d.service_id = ?")
            params.append(service)

        if q:
            # FTS search
            conditions_sql = (" AND " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT d.id, d.service_id, d.source_id, d.title, d.body_markdown,
                       d.content_hash, d.version, d.hidden, d.metadata,
                       d.source_ts, d.fetched_at
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ? {conditions_sql}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """, [q] + params + [limit, offset]).fetchall()

            count_rows = db.execute(f"""
                SELECT COUNT(*) as cnt
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ? {conditions_sql}
            """, [q] + params).fetchone()
        else:
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT id, service_id, source_id, title, body_markdown,
                       content_hash, version, hidden, metadata,
                       source_ts, fetched_at
                FROM documents d {where}
                ORDER BY source_ts DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()

            count_rows = db.execute(f"""
                SELECT COUNT(*) as cnt FROM documents d {where}
            """, params).fetchone()

        total = count_rows["cnt"]
        docs = [_doc_to_dict(r) for r in rows]

        return JSONResponse({
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": docs,
        })

    @rt("/api/documents/{doc_id}")
    def get(doc_id: int):
        db = get_db()
        doc = db.execute("""
            SELECT id, service_id, source_id, title, body_markdown,
                   content_hash, version, hidden, metadata,
                   source_ts, fetched_at
            FROM documents WHERE id = ?
        """, (doc_id,)).fetchone()

        if doc is None:
            return JSONResponse({"error": "Document not found"}, status_code=404)

        versions = db.execute("""
            SELECT version, content_hash, source_ts, created_at
            FROM document_versions WHERE document_id = ?
            ORDER BY version DESC
        """, (doc_id,)).fetchall()

        result = _doc_to_dict(doc)
        result["versions"] = [
            {"version": v["version"], "content_hash": v["content_hash"],
             "source_ts": v["source_ts"], "created_at": v["created_at"]}
            for v in versions
        ]

        return JSONResponse(result)

    @rt("/api/documents/{doc_id}/markdown")
    def get(doc_id: int):
        db = get_db()
        doc = db.execute(
            "SELECT title, body_markdown FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if doc is None:
            return Response("Document not found", status_code=404, media_type="text/plain")

        content = f"# {doc['title']}\n\n{doc['body_markdown']}"
        return Response(content, media_type="text/markdown")

    # ── Items ────────────────────────────────────────────────────

    @rt("/api/items")
    def get(q: str = "", limit: int = 50, offset: int = 0,
            service: str = "", item_type: str = "", sender_is_me: str = ""):
        db = get_db()
        params = []
        conditions = []

        if service:
            conditions.append("i.service_id = ?")
            params.append(service)
        if item_type:
            conditions.append("i.item_type = ?")
            params.append(item_type)
        if sender_is_me == "1":
            conditions.append("i.sender_is_me = 1")
        elif sender_is_me == "0":
            conditions.append("i.sender_is_me = 0")

        if q:
            conditions_sql = (" AND " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT i.id, i.service_id, i.item_type, i.source_id,
                       i.conversation, i.sender, i.sender_is_me, i.recipients,
                       i.subject, i.body_plain, i.body_html, i.attachments,
                       i.labels, i.metadata, i.source_ts, i.fetched_at
                FROM items_fts
                JOIN items i ON i.id = items_fts.rowid
                WHERE items_fts MATCH ? {conditions_sql}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """, [q] + params + [limit, offset]).fetchall()

            count_rows = db.execute(f"""
                SELECT COUNT(*) as cnt
                FROM items_fts
                JOIN items i ON i.id = items_fts.rowid
                WHERE items_fts MATCH ? {conditions_sql}
            """, [q] + params).fetchone()
        else:
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT id, service_id, item_type, source_id,
                       conversation, sender, sender_is_me, recipients,
                       subject, body_plain, body_html, attachments,
                       labels, metadata, source_ts, fetched_at
                FROM items i {where}
                ORDER BY source_ts DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()

            count_rows = db.execute(f"""
                SELECT COUNT(*) as cnt FROM items i {where}
            """, params).fetchone()

        total = count_rows["cnt"]
        items = [_item_to_dict(r) for r in rows]

        return JSONResponse({
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        })

    @rt("/api/items/{item_id}")
    def get(item_id: int):
        db = get_db()
        item = db.execute("""
            SELECT id, service_id, item_type, source_id,
                   conversation, sender, sender_is_me, recipients,
                   subject, body_plain, body_html, attachments,
                   labels, metadata, source_ts, fetched_at
            FROM items WHERE id = ?
        """, (item_id,)).fetchone()

        if item is None:
            return JSONResponse({"error": "Item not found"}, status_code=404)

        return JSONResponse(_item_to_dict(item))

    # ── Unified Search ───────────────────────────────────────────

    @rt("/api/search")
    def get(q: str = "", limit: int = 20):
        if not q:
            return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)

        db = get_db()

        doc_rows = db.execute("""
            SELECT d.id, d.title, d.service_id, d.source_ts, d.hidden,
                   snippet(documents_fts, 1, '', '', '...', 40) as snippet
            FROM documents_fts
            JOIN documents d ON d.id = documents_fts.rowid
            WHERE documents_fts MATCH ? AND d.hidden = 0
            ORDER BY rank
            LIMIT ?
        """, (q, limit)).fetchall()

        item_rows = db.execute("""
            SELECT i.id, i.service_id, i.item_type, i.subject, i.sender,
                   i.conversation, i.source_ts,
                   snippet(items_fts, 1, '', '', '...', 40) as snippet
            FROM items_fts
            JOIN items i ON i.id = items_fts.rowid
            WHERE items_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (q, limit)).fetchall()

        return JSONResponse({
            "query": q,
            "documents": [
                {"id": r["id"], "type": "document", "title": r["title"],
                 "service_id": r["service_id"], "source_ts": r["source_ts"],
                 "snippet": r["snippet"]}
                for r in doc_rows
            ],
            "items": [
                {"id": r["id"], "type": r["item_type"], "subject": r["subject"],
                 "service_id": r["service_id"], "sender": r["sender"],
                 "conversation": r["conversation"], "source_ts": r["source_ts"],
                 "snippet": r["snippet"]}
                for r in item_rows
            ],
        })

    # ── Stats ────────────────────────────────────────────────────

    @rt("/api/stats")
    def get():
        db = get_db()
        doc_count = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0").fetchone()["cnt"]
        doc_hidden = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 1").fetchone()["cnt"]
        item_count = db.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        services = db.execute("""
            SELECT id, display_name, status, last_sync_at
            FROM services WHERE enabled = 1
        """).fetchall()

        return JSONResponse({
            "documents": {"total": doc_count, "hidden": doc_hidden},
            "items": {"total": item_count},
            "services": [
                {"id": s["id"], "name": s["display_name"],
                 "status": s["status"], "last_sync_at": s["last_sync_at"]}
                for s in services
            ],
        })


# ── Helpers ──────────────────────────────────────────────────────

def _doc_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "service_id": row["service_id"],
        "source_id": row["source_id"],
        "title": row["title"],
        "body_markdown": row["body_markdown"],
        "content_hash": row["content_hash"],
        "version": row["version"],
        "hidden": bool(row["hidden"]),
        "metadata": _safe_json(row["metadata"]),
        "source_ts": row["source_ts"],
        "fetched_at": row["fetched_at"],
    }


def _item_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "service_id": row["service_id"],
        "item_type": row["item_type"],
        "source_id": row["source_id"],
        "conversation": row["conversation"],
        "sender": row["sender"],
        "sender_is_me": bool(row["sender_is_me"]),
        "recipients": _safe_json(row["recipients"]),
        "subject": row["subject"],
        "body_plain": row["body_plain"],
        "body_html": row["body_html"],
        "attachments": _safe_json(row["attachments"]),
        "labels": _safe_json(row["labels"]),
        "metadata": _safe_json(row["metadata"]),
        "source_ts": row["source_ts"],
        "fetched_at": row["fetched_at"],
    }


def _safe_json(val):
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val
