from fasthtml.common import *
from app.db import get_db
from app.components.layout import page, SERVICE_ICONS


def register(rt):

    @rt("/messages")
    def get(q: str = "", service: str = "", conversation: str = ""):
        db = get_db()

        # Build query with filters
        params = []
        conditions = []

        if service:
            conditions.append("i.service_id = ?")
            params.append(service)
        if conversation:
            conditions.append("i.conversation = ?")
            params.append(conversation)

        if q:
            cond_sql = (" AND " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT i.id, i.service_id, i.item_type, i.source_id, i.conversation,
                       i.sender, i.sender_is_me, i.subject, i.body_plain,
                       i.source_ts, i.metadata,
                       snippet(items_fts, 1, '<mark>', '</mark>', '...', 50) as snippet
                FROM items_fts
                JOIN items i ON i.id = items_fts.rowid
                WHERE items_fts MATCH ? {cond_sql}
                ORDER BY rank
                LIMIT 100
            """, [q] + params).fetchall()
            total_row = db.execute(f"""
                SELECT COUNT(*) as cnt FROM items_fts
                JOIN items i ON i.id = items_fts.rowid
                WHERE items_fts MATCH ? {cond_sql}
            """, [q] + params).fetchone()
        else:
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            rows = db.execute(f"""
                SELECT id, service_id, item_type, source_id, conversation,
                       sender, sender_is_me, subject, body_plain,
                       source_ts, metadata
                FROM items i {where}
                ORDER BY source_ts DESC
                LIMIT 100
            """, params).fetchall()
            total_row = db.execute(f"""
                SELECT COUNT(*) as cnt FROM items i {where}
            """, params).fetchone()

        total = total_row["cnt"]

        # Get service counts for filter pills
        svc_counts = db.execute("""
            SELECT service_id, COUNT(*) as cnt FROM items GROUP BY service_id ORDER BY cnt DESC
        """).fetchall()

        # Get conversation list for the selected service
        conv_rows = []
        if service:
            conv_rows = db.execute("""
                SELECT conversation, COUNT(*) as cnt FROM items
                WHERE service_id = ? AND conversation != ''
                GROUP BY conversation ORDER BY cnt DESC LIMIT 50
            """, (service,)).fetchall()

        # --- Build UI ---

        # Service filter pills
        all_active = "btn-primary" if not service else "btn-ghost"
        pills = [
            A("All", href=_filter_url(q=q), cls=f"btn btn-xs {all_active}"),
        ]
        for sc in svc_counts:
            sid = sc["service_id"]
            active = "btn-primary" if service == sid else "btn-ghost"
            icon = NotStr(SERVICE_ICONS.get(sid, ""))
            pills.append(
                A(icon, Span(f"{sid.title()} ({sc['cnt']:,})"),
                  href=_filter_url(q=q, service=sid),
                  cls=f"btn btn-xs {active} gap-1"),
            )

        filter_bar = Div(*pills, cls="flex flex-wrap gap-1.5 mb-3")

        # Conversation filter (when a service is selected)
        conv_bar = None
        if conv_rows:
            conv_pills = [
                A("All threads", href=_filter_url(q=q, service=service),
                  cls=f"btn btn-xs {'btn-secondary' if not conversation else 'btn-ghost'}"),
            ]
            for cr in conv_rows[:20]:
                active = "btn-secondary" if conversation == cr["conversation"] else "btn-ghost"
                label = cr["conversation"][:30] + ("..." if len(cr["conversation"]) > 30 else "")
                conv_pills.append(
                    A(f"{label} ({cr['cnt']})",
                      href=_filter_url(q=q, service=service, conversation=cr["conversation"]),
                      cls=f"btn btn-xs {active}"),
                )
            conv_bar = Div(*conv_pills, cls="flex flex-wrap gap-1.5 mb-3")

        # Search bar
        search_bar = Div(
            Form(
                Div(
                    Input(
                        type="search", name="q", value=q,
                        placeholder="Search messages...",
                        cls="input input-bordered input-sm w-full max-w-xs font-mono text-xs",
                    ),
                    Input(type="hidden", name="service", value=service) if service else None,
                    Input(type="hidden", name="conversation", value=conversation) if conversation else None,
                    Button("Search", type="submit", cls="btn btn-primary btn-sm"),
                    A("Clear", href="/messages", cls="btn btn-ghost btn-sm") if (q or service or conversation) else None,
                    cls="flex gap-2 items-center",
                ),
                method="get", action="/messages",
            ),
            cls="mb-4",
        )

        # Empty state
        if not rows:
            empty = Div(
                NotStr('<svg class="w-10 h-10 opacity-15 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"/></svg>'),
                P("No messages yet" if not q else f'No results for "{q}"', cls="text-xs opacity-40"),
                P("Connect a messaging service and sync to pull messages", cls="text-[11px] opacity-25") if not q else None,
                cls="flex flex-col items-center py-12",
            )
            return page(
                _page_header(total, service, conversation),
                search_bar, filter_bar,
                conv_bar if conv_bar else None,
                empty, title="Messages",
            )

        # Message cards
        msg_cards = []
        for r in rows:
            is_me = r["sender_is_me"]
            sender = r["sender"] or "Unknown"
            body = r.get("snippet") if q else _truncate(r["body_plain"], 200)
            conv = r["conversation"] or ""
            sid = r["service_id"]

            # Build "From → To" label
            from_name = "You" if is_me else sender
            to_name = conv if conv else ("You" if not is_me else "")
            direction = Div(
                Span(from_name, cls=f"text-xs font-medium {'text-primary' if is_me else ''}"),
                Span("→", cls="opacity-40 text-[10px] mx-0.5"),
                Span(to_name, cls=f"text-xs font-medium {'text-primary' if not is_me and to_name == 'You' else 'opacity-60'}"),
                cls="flex items-center gap-0.5",
            ) if to_name else Span(from_name, cls=f"text-xs font-medium {'text-primary' if is_me else ''}")

            svc_icon = NotStr(SERVICE_ICONS.get(sid, ""))
            human_ts = _humanize_ts(r["source_ts"])

            msg_cards.append(
                Div(
                    A(
                        Div(
                            Div(svc_icon, direction, cls="flex items-center gap-1.5"),
                            Span(human_ts, cls="text-[11px] opacity-40 shrink-0"),
                            cls="flex items-center justify-between gap-2",
                        ),
                        P(NotStr(body) if q else body,
                          cls="text-xs opacity-50 line-clamp-3 mt-1.5 leading-relaxed"),
                        href=f"/messages/{r['id']}",
                        cls="block flex-1",
                    ),
                    cls="msg-card group card bg-base-200/50 border border-base-content/5 p-3 "
                        "hover:bg-base-300/50 hover:border-base-content/10 transition-all",
                )
            )

        msg_list = Div(*msg_cards, cls="flex flex-col gap-2")

        showing = f"Showing {len(rows):,}" + (f" of {total:,}" if total > len(rows) else "")

        return page(
            _page_header(total, service, conversation),
            search_bar,
            filter_bar,
            conv_bar if conv_bar else None,
            Div(Span(showing, cls="text-[11px] opacity-30"), cls="mb-3"),
            msg_list,
            title="Messages",
        )

    @rt("/messages/{msg_id}")
    def get(msg_id: int):
        db = get_db()
        msg = db.execute("SELECT * FROM items WHERE id = ?", (msg_id,)).fetchone()
        if msg is None:
            return page(P("Message not found", cls="text-sm opacity-50"), title="Not Found")

        is_me = msg["sender_is_me"]
        sender = msg["sender"] or "Unknown"
        conv = msg["conversation"] or ""
        sid = msg["service_id"]
        ts = msg["source_ts"][:19] if msg["source_ts"] else ""

        # Get adjacent messages in same conversation for context
        context_msgs = []
        if conv:
            context_msgs = db.execute("""
                SELECT id, sender, sender_is_me, body_plain, source_ts
                FROM items
                WHERE service_id = ? AND conversation = ?
                AND source_ts BETWEEN datetime(?, '-1 hour') AND datetime(?, '+1 hour')
                ORDER BY source_ts ASC
                LIMIT 50
            """, (sid, conv, msg["source_ts"] or "", msg["source_ts"] or "")).fetchall()

        svc_icon = NotStr(SERVICE_ICONS.get(sid, ""))

        header_bar = Div(
            Div(
                A("← Messages", href="/messages", cls="text-xs opacity-50 hover:opacity-100"),
                Div(
                    svc_icon,
                    Span(conv or f"Message #{msg_id}", cls="text-lg font-semibold"),
                    cls="flex items-center gap-2 mt-1",
                ),
                Div(
                    Span(sid.title(), cls="text-[10px] font-mono bg-base-300 px-1.5 py-0.5 rounded"),
                    Span(f"From: {'You' if is_me else sender}", cls="text-[11px] opacity-40"),
                    Span(f"Date: {ts}", cls="text-[11px] opacity-40 font-mono"),
                    cls="flex items-center gap-3 mt-1",
                ),
            ),
            cls="mb-6",
        )

        # Show conversation thread if available
        if context_msgs and len(context_msgs) > 1:
            thread_items = []
            for cm in context_msgs:
                cm_is_me = cm["sender_is_me"]
                cm_sender = cm["sender"] or "Unknown"
                cm_ts = cm["source_ts"][:16] if cm["source_ts"] else ""
                is_current = cm["id"] == msg_id

                thread_items.append(
                    Div(
                        Div(
                            Span("You" if cm_is_me else cm_sender,
                                 cls=f"text-xs font-medium {'text-primary' if cm_is_me else 'opacity-60'}"),
                            Span(cm_ts, cls="text-[10px] font-mono opacity-30"),
                            cls="flex items-center gap-2 mb-1",
                        ),
                        P(cm["body_plain"][:500], cls="text-xs opacity-70 leading-relaxed whitespace-pre-wrap"),
                        cls=f"p-3 rounded-lg {'bg-primary/10 border border-primary/20' if is_current else 'bg-base-200/30'}",
                    )
                )

            content = Div(
                Span(f"Thread context ({len(context_msgs)} messages)", cls="text-[11px] opacity-40 mb-2 block"),
                Div(*thread_items, cls="flex flex-col gap-2"),
                cls="card bg-base-200/50 border border-base-content/5 p-4",
            )
        else:
            content = Div(
                P(msg["body_plain"], cls="text-sm opacity-80 leading-relaxed whitespace-pre-wrap p-5"),
                cls="card bg-base-200/50 border border-base-content/5",
            )

        return page(header_bar, content, title=conv or f"Message #{msg_id}")


def _page_header(total, service, conversation):
    parts = [f"{total:,} messages"]
    if service:
        parts.append(f"in {service.title()}")
    if conversation:
        parts.append(f"· {conversation[:40]}")
    return Div(
        H3("Messages", cls="text-sm font-semibold"),
        Span(" ".join(parts), cls="text-[11px] opacity-40"),
        cls="flex items-center justify-between mb-4",
    )


def _filter_url(q="", service="", conversation=""):
    params = []
    if q:
        params.append(f"q={q}")
    if service:
        params.append(f"service={service}")
    if conversation:
        from urllib.parse import quote
        params.append(f"conversation={quote(conversation)}")
    return "/messages" + ("?" + "&".join(params) if params else "")


def _humanize_ts(ts_str):
    """Format ISO timestamp as '13:05 Jun 12, 2024'."""
    if not ts_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M %b %d, %Y")
    except Exception:
        return ts_str[:16] if ts_str else ""


def _truncate(text, length=200):
    if not text:
        return ""
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "..."
