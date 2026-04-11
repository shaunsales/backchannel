"""Assemble retrieval context for external LLMs (e.g. OpenClaw / Claude).

No in-process LLM calls — hybrid search + capped markdown payload only.
"""
from __future__ import annotations

import re
from datetime import datetime

from api import embeddings


def _normalize_since(since: str | None) -> str | None:
    if not since or not since.strip():
        return None
    raw = since.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return raw


def _load_item(db, item_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, service_id, item_type, source_id, thread_id, conversation, "
        "sender, sender_is_me, subject, body_plain, body_html, source_ts "
        "FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def _load_document(db, doc_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, service_id, title, body_markdown, source_ts "
        "FROM documents WHERE id = ? AND hidden = 0",
        (doc_id,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def _passes_filters(
    hit: dict,
    row: dict | None,
    *,
    service_id: str | None,
    conversation_substring: str | None,
    thread_id: str | None,
    since_iso: str | None,
) -> bool:
    if service_id and hit.get("service_id") != service_id:
        return False
    ts = hit.get("source_ts") or (row or {}).get("source_ts")
    if since_iso and ts:
        if ts < since_iso:
            return False
    if hit["source_type"] != "item":
        if conversation_substring or thread_id:
            return False
        return True
    if not row:
        return False
    if thread_id and (row.get("thread_id") or "") != thread_id:
        return False
    if conversation_substring:
        conv = (row.get("conversation") or "") + " " + (row.get("subject") or "")
        if conversation_substring.lower() not in conv.lower():
            return False
    return True


def _truncate(s: str, max_chars: int) -> tuple[str, bool]:
    if not s:
        return "", False
    if len(s) <= max_chars:
        return s, False
    return s[: max_chars - 20] + "\n\n…(truncated)", True


def _strip_md_section_breaks(s: str) -> str:
    """Avoid accidental horizontal rules when pasting bodies."""
    return re.sub(r"(?m)^---\s*$", "— — —", s)


def build_retrieval_context(
    db,
    q: str,
    *,
    mode: str = "hybrid",
    limit: int = 15,
    max_context_chars: int = 48000,
    per_source_max_chars: int = 12000,
    service_id: str | None = None,
    conversation_substring: str | None = None,
    thread_id: str | None = None,
    since: str | None = None,
) -> dict:
    q = (q or "").strip()
    if not q:
        raise ValueError("q is required")

    since_iso = _normalize_since(since)
    conv_sub = (conversation_substring or "").strip() or None
    tid = (thread_id or "").strip() or None
    svc = (service_id or "").strip() or None

    fetch_n = min(100, max(limit * 5, limit, 20))

    if mode == "semantic":
        raw_hits = embeddings.search_semantic(db, q, limit=fetch_n)
    elif mode == "keyword":
        raw_hits = embeddings.search_keyword(db, q, limit=fetch_n)
    else:
        raw_hits = embeddings.search_hybrid(db, q, limit=fetch_n)

    citations: list[dict] = []
    sections: list[str] = []
    used = 0
    rank = 0

    header = (
        f"# Retrieved context\n\n"
        f"**Query:** {q}\n\n"
        f"**Mode:** {mode}"
        + (f" · **service_id:** `{svc}`" if svc else "")
        + (f" · **since:** `{since_iso}`" if since_iso else "")
        + "\n\n"
        "---\n\n"
    )

    budget = max_context_chars - len(header) - 500
    truncated_bundle = False

    for hit in raw_hits:
        if used >= budget or rank >= limit:
            break

        st = hit["source_type"]
        sid = int(hit["source_id"])
        row = _load_item(db, sid) if st == "item" else _load_document(db, sid)
        if not row:
            continue
        if not _passes_filters(
            hit, row, service_id=svc, conversation_substring=conv_sub,
            thread_id=tid, since_iso=since_iso,
        ):
            continue

        rank += 1
        title = hit.get("title") or row.get("subject") or row.get("title") or "(untitled)"
        svc_id = row.get("service_id", "")
        ts = row.get("source_ts") or ""

        if st == "item":
            body = row.get("body_plain") or ""
            meta_lines = [
                f"- **Type:** item (internal id `{sid}`)",
                f"- **Service:** `{svc_id}`",
                f"- **When:** {ts}",
            ]
            if row.get("sender"):
                meta_lines.append(f"- **From:** {row['sender']}")
            if row.get("conversation"):
                meta_lines.append(f"- **Conversation:** {row['conversation']}")
            if row.get("thread_id"):
                meta_lines.append(f"- **Thread id:** `{row['thread_id']}`")
            if row.get("source_id"):
                meta_lines.append(f"- **External source_id:** `{row['source_id']}`")
            body_label = "body_plain"
        else:
            body = row.get("body_markdown") or ""
            meta_lines = [
                f"- **Type:** document (internal id `{sid}`)",
                f"- **Service:** `{svc_id}`",
                f"- **When:** {ts}",
            ]
            body_label = "body_markdown"

        body, body_trunc = _truncate(body, per_source_max_chars)
        body = _strip_md_section_breaks(body)

        block = f"## [{rank}] {title}\n\n" + "\n".join(meta_lines) + f"\n\n**{body_label}:**\n\n"
        if st == "document":
            block += "```markdown\n" + body + "\n```\n\n"
        else:
            block += "```text\n" + body + "\n```\n\n"
        block += "---\n\n"

        if used + len(block) > budget:
            truncated_bundle = True
            break

        sections.append(block)
        used += len(block)

        citations.append({
            "rank": rank,
            "source_type": st,
            "internal_id": sid,
            "service_id": svc_id,
            "title": title,
            "source_ts": ts,
            "score": hit.get("score"),
            "body_truncated": body_trunc,
        })

    context_markdown = header + "".join(sections)
    if truncated_bundle:
        context_markdown += (
            "\n*(Additional content omitted: `max_context_chars` budget exhausted.)*\n"
        )

    return {
        "query": q,
        "mode": mode,
        "hits_included": rank,
        "context_markdown": context_markdown,
        "context_char_count": len(context_markdown),
        "citations": citations,
        "truncated": truncated_bundle or (used >= budget and rank < limit),
    }
