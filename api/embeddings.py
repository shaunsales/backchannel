"""Vector embedding and semantic search for Backchannel.

Uses sentence-transformers for local embeddings and sqlite-vec for
database-native KNN search via vec0 virtual tables.
"""
import logging

import numpy as np
from sqlite_vec import serialize_float32

from api.config import EMBEDDING_MODEL

log = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        log.info("Embedding model loaded")
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Generate normalized embeddings for a list of texts."""
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True)


def _serialize(vec: np.ndarray) -> bytes:
    """Convert a numpy vector to the blob format sqlite-vec expects."""
    return serialize_float32(vec.tolist())


# ── Chunking ────────────────────────────────────────────────────────────────

CHUNK_MAX_CHARS = 1000
CHUNK_MIN_CHARS = 50


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Split text into chunks at paragraph boundaries."""
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < CHUNK_MIN_CHARS:
            merged[-1] = f"{merged[-1]}\n\n{c}"
        else:
            merged.append(c)

    return merged


# ── Index / Remove ──────────────────────────────────────────────────────────

def _replace_chunks(db, source_type: str, source_id: int, texts: list[str]):
    """Embed texts and upsert chunks + vec_chunks for a single source."""
    if not texts:
        return

    old_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM chunks WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        ).fetchall()
    ]
    for cid in old_ids:
        db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (cid,))
    db.execute(
        "DELETE FROM chunks WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )

    vectors = embed(texts)
    for i, (text, vec) in enumerate(zip(texts, vectors)):
        chunk_id = db.execute(
            "INSERT INTO chunks (source_type, source_id, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            (source_type, source_id, i, text),
        ).lastrowid
        db.execute(
            "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
            (chunk_id, _serialize(vec)),
        )


def index_item(db, item_id: int):
    """Embed a single item (message/email). Usually one chunk."""
    row = db.execute(
        "SELECT id, subject, body_plain FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return
    parts = [p for p in [row["subject"], row["body_plain"]] if p and p.strip()]
    text = "\n\n".join(parts)
    if not text.strip():
        return
    _replace_chunks(db, "item", row["id"], [text])


def index_document(db, doc_id: int):
    """Embed a document, chunking long markdown bodies."""
    row = db.execute(
        "SELECT id, title, body_markdown FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    if not row:
        return
    title = row["title"] or ""
    body = row["body_markdown"] or ""
    text = f"# {title}\n\n{body}" if title else body
    if not text.strip():
        return
    _replace_chunks(db, "document", row["id"], chunk_text(text))


def remove_for_source(db, source_type: str, source_id: int):
    """Remove all chunks and vectors for a single source row."""
    old_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM chunks WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        ).fetchall()
    ]
    for cid in old_ids:
        db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (cid,))
    db.execute(
        "DELETE FROM chunks WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )


def remove_for_service(db, service_id: str):
    """Remove all chunks and vectors belonging to a service."""
    chunk_ids = [
        r["id"]
        for r in db.execute(
            "SELECT c.id FROM chunks c "
            "JOIN items i ON c.source_type = 'item' AND c.source_id = i.id "
            "WHERE i.service_id = ? "
            "UNION ALL "
            "SELECT c.id FROM chunks c "
            "JOIN documents d ON c.source_type = 'document' AND c.source_id = d.id "
            "WHERE d.service_id = ?",
            (service_id, service_id),
        ).fetchall()
    ]
    for cid in chunk_ids:
        db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (cid,))
        db.execute("DELETE FROM chunks WHERE id = ?", (cid,))


# ── Sync hook ───────────────────────────────────────────────────────────────

def index_new_for_service(db, service_id: str) -> int:
    """Index any un-embedded items/documents for a service. Returns count."""
    count = 0

    items = db.execute(
        "SELECT id FROM items WHERE service_id = ? "
        "AND id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'item')",
        (service_id,),
    ).fetchall()
    for row in items:
        index_item(db, row["id"])
        count += 1

    docs = db.execute(
        "SELECT id FROM documents WHERE service_id = ? AND hidden = 0 "
        "AND id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'document')",
        (service_id,),
    ).fetchall()
    for row in docs:
        index_document(db, row["id"])
        count += 1

    if count:
        db.commit()
        log.info("Indexed %d new items/documents for %s", count, service_id)
    return count


# ── Backfill ────────────────────────────────────────────────────────────────

def backfill(db) -> dict:
    """Index all un-embedded items and documents across all services."""
    stats = {"items": 0, "documents": 0, "chunks": 0}

    items = db.execute(
        "SELECT id FROM items "
        "WHERE id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'item')"
    ).fetchall()
    log.info("Backfilling %d items...", len(items))
    for row in items:
        index_item(db, row["id"])
        stats["items"] += 1
        if stats["items"] % 100 == 0:
            db.commit()
            log.info("  ...%d items embedded", stats["items"])

    docs = db.execute(
        "SELECT id FROM documents WHERE hidden = 0 "
        "AND id NOT IN (SELECT source_id FROM chunks WHERE source_type = 'document')"
    ).fetchall()
    log.info("Backfilling %d documents...", len(docs))
    for row in docs:
        index_document(db, row["id"])
        stats["documents"] += 1

    db.commit()
    stats["chunks"] = db.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()["cnt"]
    log.info("Backfill complete: %s", stats)
    return stats


# ── Search ──────────────────────────────────────────────────────────────────

def search_semantic(db, query: str, limit: int = 20) -> list[dict]:
    """KNN search via sqlite-vec's vec0 MATCH operator."""
    query_vec = embed([query])[0]

    vec_rows = db.execute(
        "SELECT rowid, distance FROM vec_chunks "
        "WHERE embedding MATCH ? AND k = ?",
        (_serialize(query_vec), limit),
    ).fetchall()

    results = []
    for vr in vec_rows:
        chunk = db.execute(
            "SELECT id, source_type, source_id, content FROM chunks WHERE id = ?",
            (vr["rowid"],),
        ).fetchone()
        if not chunk:
            continue
        result = {
            "chunk_id": chunk["id"],
            "source_type": chunk["source_type"],
            "source_id": chunk["source_id"],
            "preview": chunk["content"][:300],
            "distance": vr["distance"],
            "score": max(0.0, 1.0 - vr["distance"]),
        }
        _enrich(db, result)
        results.append(result)
    return results


def search_keyword(db, query: str, limit: int = 20) -> list[dict]:
    """FTS5 search across items and documents."""
    results = []

    item_rows = db.execute(
        "SELECT i.id, rank FROM items i JOIN items_fts f ON i.id = f.rowid "
        "WHERE items_fts MATCH ? ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    for r in item_rows:
        row = db.execute(
            "SELECT id, service_id, sender, conversation, subject, body_plain, source_ts "
            "FROM items WHERE id = ?", (r["id"],)
        ).fetchone()
        if not row:
            continue
        preview = row["subject"] or (row["body_plain"] or "")[:300]
        results.append({
            "source_type": "item",
            "source_id": row["id"],
            "preview": preview,
            "score": -r["rank"],
            "title": row["subject"] or row["conversation"] or "",
            "service_id": row["service_id"],
            "source_ts": row["source_ts"],
        })

    doc_rows = db.execute(
        "SELECT d.id, rank FROM documents d JOIN documents_fts f ON d.id = f.rowid "
        "WHERE documents_fts MATCH ? AND d.hidden = 0 ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    for r in doc_rows:
        row = db.execute(
            "SELECT id, service_id, title, body_markdown, source_ts "
            "FROM documents WHERE id = ?", (r["id"],)
        ).fetchone()
        if not row:
            continue
        results.append({
            "source_type": "document",
            "source_id": row["id"],
            "preview": (row["body_markdown"] or "")[:300],
            "score": -r["rank"],
            "title": row["title"] or "",
            "service_id": row["service_id"],
            "source_ts": row["source_ts"],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def search_hybrid(db, query: str, limit: int = 20, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion of semantic + keyword results."""
    semantic = search_semantic(db, query, limit=limit * 2)
    keyword = search_keyword(db, query, limit=limit * 2)

    scores: dict[str, float] = {}
    entries: dict[str, dict] = {}

    for rank, r in enumerate(semantic):
        key = f"{r['source_type']}:{r['source_id']}"
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key not in entries:
            entries[key] = r

    for rank, r in enumerate(keyword):
        key = f"{r['source_type']}:{r['source_id']}"
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key not in entries:
            entries[key] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    results = []
    for key, score in ranked:
        entry = entries[key]
        entry["score"] = score
        if "title" not in entry:
            _enrich(db, entry)
        results.append(entry)

    return results


def _enrich(db, result: dict):
    """Add title, service_id, source_ts from the source row."""
    if result["source_type"] == "item":
        row = db.execute(
            "SELECT service_id, sender, conversation, subject, source_ts "
            "FROM items WHERE id = ?", (result["source_id"],)
        ).fetchone()
        if row:
            result["title"] = row["subject"] or row["conversation"] or row["sender"] or ""
            result["service_id"] = row["service_id"]
            result["source_ts"] = row["source_ts"]
    elif result["source_type"] == "document":
        row = db.execute(
            "SELECT service_id, title, source_ts FROM documents WHERE id = ?",
            (result["source_id"],)
        ).fetchone()
        if row:
            result["title"] = row["title"] or ""
            result["service_id"] = row["service_id"]
            result["source_ts"] = row["source_ts"]
