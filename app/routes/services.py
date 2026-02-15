from datetime import datetime
from fasthtml.common import *
from app.db import get_db
from app.components.layout import page
from app.components.service_card import service_card
from app.components.auth_forms import notion_auth_form, telegram_auth_form
from app.components import alerts


AUTH_FORMS = {
    "notion": notion_auth_form,
    "telegram": telegram_auth_form,
}


def register(rt):

    @rt("/services/{service_id}")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return page(alerts.error(f"Unknown service: {service_id}"), title="Error")

        s = dict(service)
        item_count = db.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (service_id,)
        ).fetchone()["cnt"]
        doc_count = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (service_id,)
        ).fetchone()["cnt"]
        s["item_count"] = item_count + doc_count
        s["last_sync_ago"] = _humanize_time(s["last_sync_at"]) if s["last_sync_at"] else "Never"

        recent_runs = db.execute(
            "SELECT * FROM sync_runs WHERE service_id = ? ORDER BY started_at DESC LIMIT 5",
            (service_id,),
        ).fetchall()

        status_text = s["status"]
        last_sync = s["last_sync_at"] or "Never"

        # Use service-specific auth form if available
        form_fn = AUTH_FORMS.get(service_id)
        if form_fn:
            connection_card = Div(
                Div(
                    H3("Connection", cls="text-sm font-semibold mb-3"),
                    form_fn(s),
                    cls="card-body p-5",
                ),
                cls="card bg-base-200/50 border border-base-content/5 mb-4",
            )
        else:
            connection_card = Div(
                Div(
                    H3("Connection", cls="text-sm font-semibold mb-2"),
                    Div(
                        Span("Status: ", cls="opacity-50"),
                        Span(status_text, cls="font-medium"),
                        cls="text-sm mb-1",
                    ),
                    Div(
                        Span("Auth type: ", cls="opacity-50"),
                        Span(s["auth_type"], cls="font-mono text-xs"),
                        cls="text-sm mb-3",
                    ),
                    A("Configure", href=f"/auth/{service_id}",
                      cls="btn btn-outline btn-sm") if status_text == "disconnected" else
                    Button("Disconnect", hx_post=f"/auth/{service_id}/disconnect",
                           hx_target="#service-detail", hx_swap="outerHTML",
                           cls="btn btn-outline btn-error btn-sm"),
                    cls="card-body p-5",
                ),
                cls="card bg-base-200/50 border border-base-content/5 mb-4",
            )

        stored = item_count + doc_count
        last_sync_display = s["last_sync_ago"]

        stats_row = Div(
            Div(
                Span("Stored", cls="text-[11px] opacity-40"),
                Span(f"{stored:,}", cls="text-lg font-mono font-semibold"),
                cls="flex flex-col",
            ),
            Div(
                Span("Last sync", cls="text-[11px] opacity-40"),
                Span(last_sync_display, cls="text-xs opacity-70"),
                cls="flex flex-col",
            ),
            cls="flex gap-8 mb-4",
        )

        detail = Div(
            H2(s["display_name"], cls="text-lg font-semibold mb-4"),
            stats_row,
            connection_card,

            Div(
                H3("Recent Runs", cls="text-sm font-semibold mb-3"),
                _runs_table(recent_runs) if recent_runs else
                P("No sync runs yet.", cls="text-sm opacity-50"),
                cls="mb-4",
            ),

            id="service-detail",
        )

        return page(detail, title=s["display_name"])

    @rt("/services/{service_id}/card")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return Div("Unknown service", cls="text-error text-sm")
        s = dict(service)
        items = db.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (service_id,)
        ).fetchone()["cnt"]
        docs = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (service_id,)
        ).fetchone()["cnt"]
        s["item_count"] = items + docs
        s["last_sync_ago"] = _humanize_time(s["last_sync_at"]) if s["last_sync_at"] else "Never"
        return service_card(s)


def _runs_table(runs):
    from app.components.sync_table import STATUS_COLORS
    rows = []
    for r in runs:
        badge_cls = STATUS_COLORS.get(r["status"], "badge-ghost")
        duration = f"{r['duration_sec']:.1f}s" if r["duration_sec"] else "—"
        rows.append(Tr(
            Td(r["run_type"], cls="text-xs"),
            Td(Span(r["status"], cls=f"badge badge-sm {badge_cls}")),
            Td(str(r["items_fetched"] or 0)),
            Td(duration, cls="font-mono text-xs"),
            Td(r["started_at"] or "—", cls="text-xs"),
        ))
    return Table(
        Thead(Tr(Th("Type"), Th("Status"), Th("Items"), Th("Duration"), Th("Time"))),
        Tbody(*rows),
        cls="table table-sm",
    )


def _humanize_time(ts_str: str) -> str:
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
