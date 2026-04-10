"""FastAPI REST API server for Backchannel."""
import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.db import get_db, init_db
from api.services import manager
from api.config import DATABASE_PATH

log = logging.getLogger(__name__)

app = FastAPI(title="Backchannel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _humanize_time(ts_str: str | None) -> str:
    if not ts_str:
        return "Never"
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        delta = datetime.utcnow() - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return f"{days // 30}mo ago"
    except (ValueError, TypeError):
        return ts_str


@app.on_event("startup")
def startup():
    init_db()
    # Register pullers
    from api.pullers.notion import NotionPuller
    from api.pullers.telegram import TelegramPuller
    from api.pullers.gmail import GmailPuller
    manager.register_puller("notion", NotionPuller)
    manager.register_puller("telegram", TelegramPuller)
    manager.register_puller("gmail", GmailPuller)
    # Install log broadcasting
    from api.logstream import install
    install()


# ── Dashboard ──────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard():
    db = get_db()
    services = db.execute(
        "SELECT * FROM services WHERE status = 'connected' ORDER BY last_sync_at DESC NULLS LAST"
    ).fetchall()

    total_items = db.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
    total_docs = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0").fetchone()["cnt"]

    accounts = []
    for s in services:
        d = dict(s)
        sid = d["id"]
        items = db.execute("SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (sid,)).fetchone()["cnt"]
        docs = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (sid,)).fetchone()["cnt"]
        accounts.append({
            "id": sid,
            "display_name": d["display_name"],
            "service_type": d.get("service_type") or sid,
            "stored": items + docs,
            "last_sync": _humanize_time(d["last_sync_at"]),
        })

    runs = db.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 10").fetchall()
    recent_runs = []
    for r in runs:
        rd = dict(r)
        recent_runs.append({
            "id": rd["id"],
            "service_id": rd["service_id"],
            "run_type": rd["run_type"],
            "status": rd["status"],
            "items_fetched": rd["items_fetched"] or 0,
            "duration": f"{rd['duration_sec']:.1f}s" if rd["duration_sec"] else "—",
            "time": _humanize_time(rd["started_at"]),
        })

    last_sync_at = db.execute(
        "SELECT last_sync_at FROM services WHERE last_sync_at IS NOT NULL ORDER BY last_sync_at DESC LIMIT 1"
    ).fetchone()

    return {
        "total_stored": total_items + total_docs,
        "connected_count": len(accounts),
        "last_sync_ago": _humanize_time(last_sync_at["last_sync_at"]) if last_sync_at else "Never",
        "accounts": accounts,
        "recent_runs": recent_runs,
    }


# ── Services ───────────────────────────────────────────────────────────────

@app.get("/api/services")
def list_services():
    db = get_db()
    services = db.execute(
        "SELECT * FROM services WHERE status = 'connected' ORDER BY last_sync_at DESC NULLS LAST, display_name"
    ).fetchall()
    result = []
    for s in services:
        d = dict(s)
        sid = d["id"]
        items = db.execute("SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (sid,)).fetchone()["cnt"]
        docs = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (sid,)).fetchone()["cnt"]
        result.append({
            "id": sid,
            "display_name": d["display_name"],
            "service_type": d.get("service_type") or sid,
            "status": d["status"],
            "stored": items + docs,
            "last_sync": _humanize_time(d["last_sync_at"]),
        })
    return result


@app.get("/api/services/{service_id}")
def get_service(service_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Service not found")
    d = dict(row)
    sid = d["id"]
    items = db.execute("SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (sid,)).fetchone()["cnt"]
    docs = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (sid,)).fetchone()["cnt"]
    creds = json.loads(d.get("credentials", "{}") or "{}")
    token = creds.get("token", "")

    runs = db.execute(
        "SELECT * FROM sync_runs WHERE service_id = ? ORDER BY started_at DESC LIMIT 10", (sid,)
    ).fetchall()
    recent_runs = []
    for r in runs:
        rd = dict(r)
        recent_runs.append({
            "id": rd["id"],
            "run_type": rd["run_type"],
            "status": rd["status"],
            "items_fetched": rd["items_fetched"] or 0,
            "duration": f"{rd['duration_sec']:.1f}s" if rd["duration_sec"] else "—",
            "time": _humanize_time(rd["started_at"]),
        })

    return {
        "id": sid,
        "display_name": d["display_name"],
        "service_type": d.get("service_type") or sid,
        "status": d["status"],
        "stored": items + docs,
        "last_sync": _humanize_time(d["last_sync_at"]),
        "phone": creds.get("phone", ""),
        "email": creds.get("email", ""),
        "token_preview": (token[:8] + "…" + token[-4:]) if token and len(token) > 12 else "",
        "recent_runs": recent_runs,
    }


class CreateService(BaseModel):
    service_type: str
    display_name: str


@app.post("/api/services")
def create_service(body: CreateService):
    try:
        sid = manager.add_service_instance(body.service_type, body.display_name)
        return {"id": sid}
    except ValueError as e:
        raise HTTPException(400, str(e))


class RenameService(BaseModel):
    display_name: str


@app.patch("/api/services/{service_id}")
def rename_service(service_id: str, body: RenameService):
    manager.rename_service(service_id, body.display_name)
    return {"ok": True}


@app.delete("/api/services/{service_id}")
def delete_service(service_id: str):
    try:
        manager.remove_service_instance(service_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


class ConnectBody(BaseModel):
    credentials: dict


@app.post("/api/services/{service_id}/connect")
def connect_service(service_id: str, body: ConnectBody):
    manager.connect(service_id, body.credentials)
    return {"ok": True}


@app.post("/api/services/{service_id}/disconnect")
def disconnect_service(service_id: str):
    manager.disconnect(service_id)
    return {"ok": True}


@app.post("/api/services/{service_id}/test")
def test_service(service_id: str):
    ok, msg = manager.test(service_id)
    return {"ok": ok, "message": msg}


@app.post("/api/services/{service_id}/sync")
def sync_service(service_id: str):
    try:
        result = manager.run_sync(service_id, run_type="manual")
        db = get_db()
        run = db.execute(
            "SELECT items_fetched, items_new, items_updated, duration_sec FROM sync_runs WHERE id = ?",
            (result["run_id"],)
        ).fetchone()
        return {
            "run_id": result["run_id"],
            "status": "success",
            "items_fetched": run["items_fetched"] if run else 0,
            "items_new": run["items_new"] if run else 0,
            "items_updated": run["items_updated"] if run else 0,
            "duration": f"{run['duration_sec']:.1f}s" if run and run["duration_sec"] else "",
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/services/{service_id}/stats")
def get_service_stats(service_id: str):
    """Get remote service statistics (e.g. Gmail folder counts, date range)."""
    try:
        puller = manager.get_puller(service_id)
        if not hasattr(puller, "get_stats"):
            raise HTTPException(400, f"Stats not supported for this service type")
        stats = puller.get_stats()
        return stats
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/services/{service_id}/clear")
def clear_service_data(service_id: str):
    try:
        manager.clear_data(service_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Documents ──────────────────────────────────────────────────────────────

@app.get("/api/documents")
def list_documents(q: str = ""):
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT id, service_id, title, body_markdown, hidden, fetched_at FROM documents "
            "WHERE hidden = 0 AND (title LIKE ? OR body_markdown LIKE ?) ORDER BY fetched_at DESC LIMIT 200",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, service_id, title, body_markdown, hidden, fetched_at FROM documents "
            "WHERE hidden = 0 ORDER BY fetched_at DESC LIMIT 200"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        body = d.get("body_markdown") or ""
        result.append({
            "id": d["id"],
            "title": d["title"] or "Untitled",
            "service_id": d["service_id"],
            "preview": body[:200] + "…" if len(body) > 200 else body,
            "time": _humanize_time(d["fetched_at"]),
        })
    return result


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    d = dict(row)
    return {
        "id": d["id"],
        "title": d["title"],
        "body": d["body_markdown"],
        "service_id": d["service_id"],
        "source_id": d["source_id"],
        "version": d["version"],
        "time": _humanize_time(d["fetched_at"]),
    }


# ── Messages ──────────────────────────────────────────────────────────────

@app.get("/api/conversations")
def list_conversations(q: str = "", limit: int = 50):
    """Return conversations (threads) with latest message preview.
    Groups by thread_id when available, falls back to conversation+service_id.
    """
    db = get_db()
    if q:
        rows = db.execute(
            """SELECT COALESCE(thread_id, conversation || ':' || service_id) as group_key,
                      conversation, service_id, thread_id,
                      MAX(source_ts) as last_ts,
                      COUNT(*) as msg_count
               FROM items
               WHERE id IN (
                   SELECT i.id FROM items i JOIN items_fts f ON i.id = f.rowid
                   WHERE items_fts MATCH ?
               )
               GROUP BY group_key
               ORDER BY last_ts DESC LIMIT ?""",
            (q, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT COALESCE(thread_id, conversation || ':' || service_id) as group_key,
                      conversation, service_id, thread_id,
                      MAX(source_ts) as last_ts,
                      COUNT(*) as msg_count
               FROM items
               GROUP BY group_key
               ORDER BY last_ts DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        conv = d["conversation"] or "Unknown"
        group_key = d["group_key"]
        # Get latest message in this conversation group
        if d["thread_id"]:
            latest = db.execute(
                "SELECT sender, body_plain FROM items WHERE thread_id = ? ORDER BY source_ts DESC LIMIT 1",
                (d["thread_id"],),
            ).fetchone()
        else:
            latest = db.execute(
                "SELECT sender, body_plain FROM items WHERE conversation = ? AND service_id = ? ORDER BY source_ts DESC LIMIT 1",
                (d["conversation"], d["service_id"]),
            ).fetchone()
        preview = ""
        sender = ""
        if latest:
            sender = latest["sender"] or ""
            preview = (latest["body_plain"] or "")[:150]
        result.append({
            "conversation": conv,
            "thread_id": d["thread_id"],
            "service_id": d["service_id"],
            "msg_count": d["msg_count"],
            "last_sender": sender,
            "preview": preview,
            "time": _humanize_time(d["last_ts"]),
        })
    return result


@app.get("/api/conversations/{conv_name:path}")
def get_conversation(conv_name: str, service: str = "", thread_id: str = "", limit: int = 100):
    """Return all messages in a conversation thread."""
    db = get_db()
    if thread_id:
        rows = db.execute(
            "SELECT * FROM items WHERE thread_id = ? ORDER BY source_ts ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
    elif service:
        rows = db.execute(
            "SELECT * FROM items WHERE conversation = ? AND service_id = ? ORDER BY source_ts ASC LIMIT ?",
            (conv_name, service, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM items WHERE conversation = ? ORDER BY source_ts ASC LIMIT ?",
            (conv_name, limit),
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        result.append({
            "id": d["id"],
            "service_id": d["service_id"],
            "sender": d["sender"],
            "conversation": d["conversation"],
            "thread_id": d.get("thread_id"),
            "body": d["body_plain"] or "",
            "source_ts": d["source_ts"],
            "time": _humanize_time(d["source_ts"]),
        })
    return result


@app.get("/api/messages")
def list_messages(q: str = "", service: str = "", limit: int = 100):
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT i.* FROM items i JOIN items_fts f ON i.id = f.rowid "
            "WHERE items_fts MATCH ? ORDER BY rank LIMIT ?",
            (q, limit),
        ).fetchall()
    elif service:
        rows = db.execute(
            "SELECT * FROM items WHERE service_id LIKE ? ORDER BY source_ts DESC LIMIT ?",
            (f"{service}%", limit),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM items ORDER BY source_ts DESC LIMIT ?", (limit,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        result.append({
            "id": d["id"],
            "service_id": d["service_id"],
            "sender": d["sender"],
            "recipients": d["recipients"],
            "conversation": d["conversation"],
            "body": (d["body_plain"] or "")[:300],
            "source_ts": d["source_ts"],
            "time": _humanize_time(d["source_ts"]),
        })
    return result


# ── Sync History ──────────────────────────────────────────────────────────

@app.get("/api/history")
def get_history(limit: int = 50):
    db = get_db()
    rows = db.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        result.append({
            "id": d["id"],
            "service_id": d["service_id"],
            "run_type": d["run_type"],
            "status": d["status"],
            "items_fetched": d["items_fetched"] or 0,
            "items_new": d["items_new"] or 0,
            "items_updated": d["items_updated"] or 0,
            "duration": f"{d['duration_sec']:.1f}s" if d["duration_sec"] else "—",
            "time": _humanize_time(d["started_at"]),
            "error": d.get("error_message"),
        })
    return result


# ── Search ─────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(q: str = "", mode: str = "hybrid", limit: int = 20):
    """Unified search across items and documents.

    mode: semantic | keyword | hybrid (default)
    """
    if not q:
        raise HTTPException(400, "Query parameter 'q' is required")

    from api import embeddings

    if mode == "semantic":
        results = embeddings.search_semantic(get_db(), q, limit=limit)
    elif mode == "keyword":
        results = embeddings.search_keyword(get_db(), q, limit=limit)
    else:
        results = embeddings.search_hybrid(get_db(), q, limit=limit)

    for r in results:
        r["time"] = _humanize_time(r.get("source_ts"))

    return {"results": results, "mode": mode, "total": len(results)}


# ── Embeddings ─────────────────────────────────────────────────────────────

@app.post("/api/embeddings/backfill")
def run_backfill():
    """Index all un-embedded items and documents."""
    from api import embeddings
    stats = embeddings.backfill(get_db())
    return stats


@app.get("/api/embeddings/stats")
def embedding_stats():
    """Return embedding index statistics."""
    db = get_db()
    try:
        total_chunks = db.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()["cnt"]
        item_chunks = db.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE source_type = 'item'"
        ).fetchone()["cnt"]
        doc_chunks = db.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE source_type = 'document'"
        ).fetchone()["cnt"]
        total_items = db.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        total_docs = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0"
        ).fetchone()["cnt"]
        unindexed_items = db.execute(
            "SELECT COUNT(*) as cnt FROM items "
            "WHERE id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'item')"
        ).fetchone()["cnt"]
        unindexed_docs = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0 "
            "AND id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'document')"
        ).fetchone()["cnt"]
    except Exception:
        return {"error": "Vector tables not available"}

    return {
        "total_chunks": total_chunks,
        "item_chunks": item_chunks,
        "doc_chunks": doc_chunks,
        "total_items": total_items,
        "total_docs": total_docs,
        "unindexed_items": unindexed_items,
        "unindexed_docs": unindexed_docs,
        "coverage_pct": round(
            (1 - (unindexed_items + unindexed_docs) / max(total_items + total_docs, 1)) * 100, 1
        ),
    }


# ── Logs ──────────────────────────────────────────────────────────────────

@app.get("/api/logs")
def get_logs():
    """Return the current in-memory log buffer."""
    from api.logstream import get_buffer
    return get_buffer()


@app.get("/api/logs/stream")
async def stream_logs():
    """SSE endpoint for real-time log streaming."""
    import asyncio
    from starlette.responses import StreamingResponse
    from api.logstream import subscribe, unsubscribe

    queue: asyncio.Queue[dict] = asyncio.Queue()

    def on_log(entry: dict):
        try:
            queue.put_nowait(entry)
        except asyncio.QueueFull:
            pass

    subscribe(on_log)

    async def event_generator():
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return
        finally:
            unsubscribe(on_log)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
