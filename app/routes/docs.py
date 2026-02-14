from fasthtml.common import *
from app.db import get_db
from app.components.layout import page


def register(rt):

    @rt("/docs")
    def get(q: str = ""):
        db = get_db()

        if q:
            rows = db.execute("""
                SELECT d.id, d.title, d.version, d.source_ts, d.fetched_at,
                       d.service_id, d.hidden, d.body_markdown,
                       snippet(documents_fts, 1, '<mark>', '</mark>', '...', 40) as snippet
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ?
                ORDER BY d.hidden ASC, rank
                LIMIT 50
            """, (q,)).fetchall()
        else:
            rows = db.execute("""
                SELECT id, title, version, source_ts, fetched_at,
                       service_id, hidden, body_markdown
                FROM documents ORDER BY hidden ASC, source_ts DESC
            """).fetchall()

        total = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0").fetchone()["cnt"]
        hidden_count = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 1").fetchone()["cnt"]

        search_bar = Div(
            Form(
                Div(
                    Input(
                        type="search", name="q", value=q,
                        placeholder="Search documents...",
                        cls="input input-bordered input-sm w-full max-w-xs font-mono text-xs",
                    ),
                    Button("Search", type="submit", cls="btn btn-primary btn-sm"),
                    A("Clear", href="/docs", cls="btn btn-ghost btn-sm") if q else None,
                    cls="flex gap-2 items-center",
                ),
                method="get", action="/docs",
            ),
            cls="mb-6",
        )

        if not rows:
            empty = Div(
                NotStr('<svg class="w-10 h-10 opacity-15 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>'),
                P("No documents yet" if not q else f'No results for "{q}"', cls="text-xs opacity-40"),
                P("Connect Notion and run a sync to pull pages", cls="text-[11px] opacity-25") if not q else None,
                cls="flex flex-col items-center py-12",
            )
            return page(
                Div(
                    H3("Documents", cls="text-sm font-semibold"),
                    Span(f"{total} pages" + (f" · {hidden_count} hidden" if hidden_count else ""),
                         cls="text-[11px] opacity-40"),
                    cls="flex items-center justify-between mb-4",
                ),
                search_bar, empty, title="Documents",
            )

        doc_cards = []
        for r in rows:
            is_hidden = r["hidden"]
            preview = _plain_preview(r["body_markdown"], 150)
            hide_action = "unhide" if is_hidden else "hide"
            hide_label = "Unhide" if is_hidden else "Hide"

            doc_cards.append(
                Div(
                    A(
                        Div(
                            Span(r["title"], cls="text-sm font-semibold line-clamp-1"),
                            Span(r["source_ts"][:10] if r["source_ts"] else "",
                                 cls="text-[10px] font-mono opacity-30"),
                            cls="flex items-center justify-between gap-2",
                        ),
                        P(preview, cls="text-xs opacity-50 line-clamp-4 mt-2 leading-relaxed") if preview else
                            P("Empty page", cls="text-xs opacity-20 italic mt-2"),
                        href=f"/docs/{r['id']}",
                        cls="block flex-1",
                    ),
                    Div(
                        Span(f"v{r['version']}", cls="text-[10px] font-mono opacity-30 bg-base-300 px-1.5 py-0.5 rounded"),
                        Button(hide_label,
                               hx_post=f"/docs/{r['id']}/{hide_action}",
                               hx_target="closest .doc-card",
                               hx_swap="outerHTML",
                               cls="btn btn-ghost btn-xs opacity-0 group-hover:opacity-60 text-[10px] min-h-0 h-5 px-2"),
                        cls="flex items-center justify-between mt-3 pt-2 border-t border-base-content/5",
                    ),
                    cls=f"doc-card group card bg-base-200/50 border border-base-content/5 p-4 "
                        f"hover:bg-base-300/50 hover:border-base-content/10 transition-all "
                        f"flex flex-col {'opacity-30' if is_hidden else ''}",
                )
            )

        doc_grid = Div(
            *doc_cards,
            cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3",
        )

        return page(
            Div(
                H3("Documents", cls="text-sm font-semibold"),
                Span(f"{total} pages" + (f" · {hidden_count} hidden" if hidden_count else ""),
                     cls="text-[11px] opacity-40"),
                cls="flex items-center justify-between mb-4",
            ),
            search_bar,
            doc_grid,
            title="Documents",
        )

    @rt("/docs/{doc_id}/hide")
    def post(doc_id: int):
        db = get_db()
        db.execute("UPDATE documents SET hidden = 1 WHERE id = ?", (doc_id,))
        db.commit()
        doc = db.execute("SELECT id, title, version, source_ts, hidden, body_markdown FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return ""
        return _doc_card(doc)

    @rt("/docs/{doc_id}/unhide")
    def post(doc_id: int):
        db = get_db()
        db.execute("UPDATE documents SET hidden = 0 WHERE id = ?", (doc_id,))
        db.commit()
        doc = db.execute("SELECT id, title, version, source_ts, hidden, body_markdown FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return ""
        return _doc_card(doc)

    @rt("/docs/{doc_id}")
    def get(doc_id: int):
        db = get_db()
        doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return page(P("Document not found", cls="text-sm opacity-50"), title="Not Found")

        version_count = db.execute(
            "SELECT COUNT(*) as cnt FROM document_versions WHERE document_id = ?", (doc_id,)
        ).fetchone()["cnt"]

        is_hidden = doc["hidden"] if "hidden" in doc.keys() else False
        hide_action = "unhide" if is_hidden else "hide"
        hide_label = "Unhide" if is_hidden else "Hide"

        header_bar = Div(
            Div(
                A("← Documents", href="/docs", cls="text-xs opacity-50 hover:opacity-100"),
                Div(
                    H2(doc["title"], cls="text-lg font-semibold mt-1"),
                    Span("hidden", cls="badge badge-sm badge-ghost opacity-50") if is_hidden else None,
                    cls="flex items-center gap-2",
                ),
                Div(
                    Span(f"v{doc['version']}", cls="text-[10px] font-mono bg-base-300 px-1.5 py-0.5 rounded"),
                    Span(f"Edited: {doc['source_ts'][:16] if doc['source_ts'] else '—'}", cls="text-[11px] opacity-40 font-mono"),
                    Span(f"Synced: {doc['fetched_at'][:16] if doc['fetched_at'] else '—'}", cls="text-[11px] opacity-40 font-mono"),
                    A(f"{version_count} prior version{'s' if version_count != 1 else ''}",
                      href=f"/docs/{doc_id}/history", cls="text-[11px] text-primary opacity-70 hover:opacity-100") if version_count > 0 else None,
                    A(hide_label, href=f"/docs/{doc_id}/{hide_action}", cls="text-[11px] opacity-40 hover:opacity-70",
                      hx_post=f"/docs/{doc_id}/{hide_action}", hx_swap="none",
                      **{"hx-on::after-request": "window.location.reload()"}),
                    cls="flex items-center gap-3 mt-1",
                ),
            ),
            cls="mb-6",
        )

        # Render markdown as HTML using a simple conversion
        rendered = _md_to_html(doc["body_markdown"])

        content = Div(
            Div(
                NotStr(rendered),
                cls="prose prose-sm prose-invert max-w-none p-5",
            ),
            cls="card bg-base-200/50 border border-base-content/5",
        )

        return page(header_bar, content, title=doc["title"])

    @rt("/docs/{doc_id}/history")
    def get(doc_id: int):
        db = get_db()
        doc = db.execute("SELECT id, title, version FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return page(P("Document not found", cls="text-sm opacity-50"), title="Not Found")

        versions = db.execute("""
            SELECT version, content_hash, source_ts, created_at
            FROM document_versions WHERE document_id = ? ORDER BY version DESC
        """, (doc_id,)).fetchall()

        header_bar = Div(
            A(f"← {doc['title']}", href=f"/docs/{doc_id}", cls="text-xs opacity-50 hover:opacity-100"),
            H2(f"Version History", cls="text-lg font-semibold mt-1"),
            Span(f"Current: v{doc['version']}  ·  {len(versions)} prior version{'s' if len(versions) != 1 else ''}",
                 cls="text-[11px] opacity-40"),
            cls="mb-6",
        )

        if not versions:
            return page(
                header_bar,
                P("No prior versions — this document has only been synced once.", cls="text-sm opacity-50"),
                title=f"History — {doc['title']}",
            )

        rows = []
        for v in versions:
            rows.append(
                A(
                    Div(
                        Div(
                            Span(f"Version {v['version']}", cls="text-sm font-medium"),
                            Span(v["source_ts"][:16] if v["source_ts"] else "—", cls="text-[11px] opacity-40 font-mono"),
                            cls="flex items-center justify-between",
                        ),
                        Div(
                            Span(f"Hash: {v['content_hash'][:12]}...", cls="text-[10px] font-mono opacity-30"),
                            Span(f"Saved: {v['created_at'][:16]}", cls="text-[10px] font-mono opacity-30"),
                            cls="flex gap-4 mt-0.5",
                        ),
                        cls="px-4 py-3 hover:bg-base-300/50 transition-colors border-b border-base-content/5",
                    ),
                    href=f"/docs/{doc_id}/version/{v['version']}",
                )
            )

        version_list = Div(*rows, cls="card bg-base-200/50 border border-base-content/5 overflow-hidden")
        return page(header_bar, version_list, title=f"History — {doc['title']}")

    @rt("/docs/{doc_id}/version/{version}")
    def get(doc_id: int, version: int):
        db = get_db()
        doc = db.execute("SELECT id, title FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return page(P("Document not found", cls="text-sm opacity-50"), title="Not Found")

        ver = db.execute("""
            SELECT * FROM document_versions
            WHERE document_id = ? AND version = ?
        """, (doc_id, version)).fetchone()
        if ver is None:
            return page(P("Version not found", cls="text-sm opacity-50"), title="Not Found")

        header_bar = Div(
            A(f"← History", href=f"/docs/{doc_id}/history", cls="text-xs opacity-50 hover:opacity-100"),
            H2(f"{doc['title']} — v{version}", cls="text-lg font-semibold mt-1"),
            Div(
                Span(f"Saved: {ver['created_at'][:16]}", cls="text-[11px] opacity-40 font-mono"),
                Span(f"Hash: {ver['content_hash'][:12]}...", cls="text-[10px] font-mono opacity-30"),
                cls="flex items-center gap-3 mt-1",
            ),
            cls="mb-6",
        )

        rendered = _md_to_html(ver["body_markdown"])
        content = Div(
            Div(
                NotStr(rendered),
                cls="prose prose-sm prose-invert max-w-none p-5",
            ),
            cls="card bg-base-200/50 border border-base-content/5",
        )

        return page(header_bar, content, title=f"{doc['title']} v{version}")


def _md_to_html(md_text: str) -> str:
    """Simple markdown to HTML. Handles headers, bold, italic, code, lists, links, images, hr."""
    import re, html as html_mod

    lines = md_text.split("\n")
    out = []
    in_code = False
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                lang = stripped[3:].strip()
                out.append(f'<pre class="bg-base-300 rounded-lg p-3 text-xs overflow-x-auto"><code class="language-{lang}">')
                in_code = True
            continue

        if in_code:
            out.append(html_mod.escape(line))
            continue

        # Close open lists if not a list item
        if in_ul and not stripped.startswith("- ") and not stripped.startswith("* "):
            out.append("</ul>")
            in_ul = False
        if in_ol and not re.match(r"^\d+\.\s", stripped):
            out.append("</ol>")
            in_ol = False

        # Empty line
        if not stripped:
            out.append("")
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            text = _inline_md(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            continue

        # HR
        if stripped in ("---", "***", "___"):
            out.append("<hr>")
            continue

        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            text = _inline_md(stripped[2:])
            # Checkbox
            if text.startswith("[x] "):
                out.append(f'<li><input type="checkbox" checked disabled> {text[4:]}</li>')
            elif text.startswith("[ ] "):
                out.append(f'<li><input type="checkbox" disabled> {text[4:]}</li>')
            else:
                out.append(f"<li>{text}</li>")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m:
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            text = _inline_md(m.group(1))
            out.append(f"<li>{text}</li>")
            continue

        # Blockquote
        if stripped.startswith("> "):
            text = _inline_md(stripped[2:])
            out.append(f"<blockquote>{text}</blockquote>")
            continue

        # Image
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            alt, src = m.group(1), m.group(2)
            out.append(f'<img src="{html_mod.escape(src)}" alt="{html_mod.escape(alt)}" class="rounded-lg max-w-full">')
            continue

        # Default: paragraph
        out.append(f"<p>{_inline_md(stripped)}</p>")

    if in_ul:
        out.append("</ul>")
    if in_ol:
        out.append("</ol>")
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out)


def _inline_md(text: str) -> str:
    """Convert inline markdown: bold, italic, code, links, strikethrough."""
    import re, html as html_mod

    # Inline code (do first to avoid processing inside code)
    text = re.sub(r'`([^`]+)`', r'<code class="bg-base-300 px-1 rounded text-xs">\1</code>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Strikethrough
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="link link-primary" target="_blank">\1</a>', text)

    return text


def _plain_preview(md_text: str, max_chars: int = 150) -> str:
    """Strip markdown formatting and return a plain text preview."""
    import re
    text = md_text.strip()
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove headings markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    # Remove subpage references
    text = re.sub(r'\*\*\[Subpage: [^\]]+\]\*\*', '', text)
    # Remove list markers
    text = re.sub(r'^[\s]*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove checkboxes
    text = re.sub(r'\[[ x]\]\s*', '', text)
    # Collapse whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + '...'
    return text


def _doc_card(doc) -> 'Div':
    """Render a single document as a grid card (used by list and hide/unhide routes)."""
    is_hidden = doc["hidden"]
    preview = _plain_preview(doc["body_markdown"], 150)
    hide_action = "unhide" if is_hidden else "hide"
    hide_label = "Unhide" if is_hidden else "Hide"

    return Div(
        A(
            Div(
                Span(doc["title"], cls="text-sm font-semibold line-clamp-1"),
                Span(doc["source_ts"][:10] if doc["source_ts"] else "",
                     cls="text-[10px] font-mono opacity-30"),
                cls="flex items-center justify-between gap-2",
            ),
            P(preview, cls="text-xs opacity-50 line-clamp-4 mt-2 leading-relaxed") if preview else
                P("Empty page", cls="text-xs opacity-20 italic mt-2"),
            href=f"/docs/{doc['id']}",
            cls="block flex-1",
        ),
        Div(
            Span(f"v{doc['version']}", cls="text-[10px] font-mono opacity-30 bg-base-300 px-1.5 py-0.5 rounded"),
            Button(hide_label,
                   hx_post=f"/docs/{doc['id']}/{hide_action}",
                   hx_target="closest .doc-card",
                   hx_swap="outerHTML",
                   cls="btn btn-ghost btn-xs opacity-0 group-hover:opacity-60 text-[10px] min-h-0 h-5 px-2"),
            cls="flex items-center justify-between mt-3 pt-2 border-t border-base-content/5",
        ),
        cls=f"doc-card group card bg-base-200/50 border border-base-content/5 p-4 "
            f"hover:bg-base-300/50 hover:border-base-content/10 transition-all "
            f"flex flex-col {'opacity-30' if is_hidden else ''}",
    )
