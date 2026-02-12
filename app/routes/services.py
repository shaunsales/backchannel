from fasthtml.common import *
from app.db import get_db
from app.components.layout import page
from app.components.service_card import service_card
from app.components import alerts


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
        s["item_count"] = item_count

        recent_runs = db.execute(
            "SELECT * FROM sync_runs WHERE service_id = ? ORDER BY started_at DESC LIMIT 5",
            (service_id,),
        ).fetchall()

        status_text = s["status"]
        last_sync = s["last_sync_at"] or "Never"

        detail = Div(
            H2(s["display_name"], cls="text-2xl font-bold mb-6"),

            Div(
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
                    cls="card-body p-4",
                ),
                cls="card bg-base-200 shadow-sm mb-4",
            ),

            Div(
                Div(
                    H3("Sync", cls="text-sm font-semibold mb-2"),
                    Div(
                        Span("Last sync: ", cls="opacity-50"),
                        Span(last_sync, cls="font-mono text-xs"),
                        cls="text-sm mb-1",
                    ),
                    Div(
                        Span("Items: ", cls="opacity-50"),
                        Span(str(item_count), cls="font-mono text-xs"),
                        cls="text-sm mb-3",
                    ),
                    Button("Sync Now", hx_post=f"/sync/{service_id}",
                           hx_target="#sync-result", hx_swap="innerHTML",
                           cls="btn btn-primary btn-sm",
                           disabled=status_text != "connected"),
                    Div(id="sync-result", cls="mt-3"),
                    cls="card-body p-4",
                ),
                cls="card bg-base-200 shadow-sm mb-4",
            ),

            Div(
                H3("Recent Runs", cls="text-sm font-semibold mb-2"),
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
