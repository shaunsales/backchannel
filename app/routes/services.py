from fasthtml.common import *
from app.db import get_db
from app.components.layout import page
from app.components.service_card import service_card
from app.components.auth_forms import notion_auth_form
from app.components import alerts


AUTH_FORMS = {
    "notion": notion_auth_form,
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
            "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ?", (service_id,)
        ).fetchone()["cnt"]
        s["item_count"] = item_count

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

        stats_row = Div(
            Div(
                Span("Items", cls="text-[11px] opacity-40"),
                Span(f"{item_count:,}", cls="text-lg font-mono font-semibold"),
                cls="flex flex-col",
            ),
            Div(
                Span("Documents", cls="text-[11px] opacity-40"),
                Span(f"{doc_count:,}", cls="text-lg font-mono font-semibold"),
                cls="flex flex-col",
            ) if doc_count > 0 else None,
            Div(
                Span("Last sync", cls="text-[11px] opacity-40"),
                Span(last_sync[:16] if last_sync != "Never" else "Never", cls="text-xs font-mono opacity-70"),
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
        s["item_count"] = db.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (service_id,)
        ).fetchone()["cnt"]
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
