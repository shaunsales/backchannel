from datetime import datetime
from fasthtml.common import *
from app.db import get_db
from app.components.layout import page, SERVICE_ICONS
from app.components.sync_table import sync_history_table


def _stat_card(value, label, icon_svg):
    return Div(
        Div(
            Div(
                NotStr(icon_svg),
                cls="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0",
            ),
            Div(
                Span(str(value), cls="text-xl font-bold font-mono leading-tight"),
                Span(label, cls="text-[11px] opacity-40"),
                cls="flex flex-col",
            ),
            cls="flex items-center gap-3",
        ),
        cls="stat-card card bg-base-200/50 border border-base-content/5 p-4",
    )


def register(rt):

    @rt("/")
    def get():
        db = get_db()

        # Connected accounts only, sorted by last sync
        connected_accounts = db.execute(
            "SELECT * FROM services WHERE status = 'connected' "
            "ORDER BY last_sync_at DESC NULLS LAST, display_name"
        ).fetchall()

        item_counts = {
            r["service_id"]: r["cnt"]
            for r in db.execute(
                "SELECT service_id, COUNT(*) as cnt FROM items GROUP BY service_id"
            ).fetchall()
        }
        doc_counts = {
            r["service_id"]: r["cnt"]
            for r in db.execute(
                "SELECT service_id, COUNT(*) as cnt FROM documents WHERE hidden = 0 GROUP BY service_id"
            ).fetchall()
        }

        recent_runs = db.execute(
            "SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()

        total_items = db.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        total_docs = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE hidden = 0").fetchone()["cnt"]
        stored_count = total_items + total_docs

        connected_count = len(connected_accounts)

        last_run = db.execute(
            "SELECT started_at, items_fetched, items_new, items_updated FROM sync_runs WHERE status='success' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        last_sync_ago = _humanize_time(last_run["started_at"]) if last_run else "Never"

        stats = Div(
            _stat_card(
                f"{stored_count:,}", "Items Stored",
                '<svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/></svg>',
            ),
            _stat_card(
                f"{connected_count}", "Accounts Connected",
                '<svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>',
            ),
            _stat_card(
                last_sync_ago, "Last Sync",
                '<svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
            ),
            cls="grid grid-cols-3 gap-3 mb-6",
        )

        # Connected accounts as a compact table
        acct_rows = []
        for s in connected_accounts:
            d = dict(s)
            sid = d["id"]
            svc_type = d.get("service_type") or sid
            icon_svg = SERVICE_ICONS.get(svc_type, "")
            stored = item_counts.get(sid, 0) + doc_counts.get(sid, 0)
            last_sync = _humanize_time(d["last_sync_at"]) if d["last_sync_at"] else "Never"

            acct_rows.append(Tr(
                Td(
                    A(
                        Div(
                            NotStr(icon_svg.replace('opacity-60', 'opacity-80')),
                            cls="w-5 h-5 flex items-center justify-center shrink-0",
                        ),
                        Span(d["display_name"], cls="text-sm font-medium"),
                        href=f"/accounts/{sid}",
                        cls="flex items-center gap-2 hover:text-primary transition-colors",
                    ),
                ),
                Td(Span(svc_type.title(), cls="text-xs opacity-50")),
                Td(Span(f"{stored:,}", cls="text-sm font-mono"), cls="text-right"),
                Td(Span(last_sync, cls="text-xs opacity-60"), cls="text-right"),
                Td(
                    Button(
                        NotStr('<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'),
                        hx_post=f"/sync/{sid}",
                        hx_target=f"#dash-acct-{sid}",
                        hx_swap="outerHTML",
                        cls="btn btn-ghost btn-xs btn-circle",
                    ),
                    cls="text-right",
                    id=f"dash-acct-{sid}",
                ),
            ))

        section_accounts = Div(
            Div(
                H3("Connected Accounts", cls="text-sm font-semibold"),
                A("Manage", href="/accounts", cls="text-[11px] text-primary opacity-70 hover:opacity-100"),
                cls="flex items-center justify-between mb-3",
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Account"), Th("Type"), Th("Stored", cls="text-right"),
                        Th("Last Sync", cls="text-right"), Th("", cls="text-right w-10"),
                    )),
                    Tbody(*acct_rows),
                    cls="table table-sm",
                ),
                cls="card bg-base-200/50 border border-base-content/5 overflow-hidden",
            ) if acct_rows else
            Div(
                P("No connected accounts. ", A("Add one", href="/accounts", cls="link link-primary"), ".",
                  cls="text-sm opacity-50"),
                cls="card bg-base-200/50 border border-base-content/5 p-4",
            ),
            cls="mb-6",
        )

        section_activity = Div(
            Div(
                H3("Recent Activity", cls="text-sm font-semibold"),
                A("View all", href="/history", cls="text-[11px] text-primary opacity-70 hover:opacity-100"),
                cls="flex items-center justify-between mb-3",
            ),
            Div(
                sync_history_table(recent_runs),
                cls="card bg-base-200/50 border border-base-content/5 overflow-hidden",
            ),
        )

        return page(stats, section_accounts, section_activity, title="Dashboard")


def _humanize_time(ts_str: str) -> str:
    """Convert an ISO timestamp to a human-friendly relative time string."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        # Strip timezone if present for comparison with utcnow
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        delta = datetime.utcnow() - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''} ago"
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    except (ValueError, TypeError):
        return ts_str
