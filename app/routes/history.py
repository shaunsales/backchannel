from fasthtml.common import *
from app.db import get_db
from app.components.layout import page


STATUS_DOT = {
    "success": "bg-success",
    "running": "bg-info",
    "failed": "bg-error",
}


def register(rt):

    @rt("/history")
    def get(service: str = "", status: str = "", pg: int = 1):
        db = get_db()
        per_page = 25
        offset = (pg - 1) * per_page

        conditions = []
        params = []
        if service:
            conditions.append("service_id = ?")
            params.append(service)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        total = db.execute(
            f"SELECT COUNT(*) as cnt FROM sync_runs {where}", params
        ).fetchone()["cnt"]

        rows = db.execute(f"""
            SELECT * FROM sync_runs {where}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()

        services = db.execute(
            "SELECT DISTINCT service_id FROM sync_runs ORDER BY service_id"
        ).fetchall()

        total_pages = max(1, (total + per_page - 1) // per_page)

        # Filter bar
        svc_options = [
            Option("All services", value="", selected=not service),
        ] + [
            Option(r["service_id"].capitalize(), value=r["service_id"],
                   selected=r["service_id"] == service)
            for r in services
        ]
        status_options = [
            Option("All statuses", value="", selected=not status),
            Option("Success", value="success", selected=status == "success"),
            Option("Running", value="running", selected=status == "running"),
            Option("Failed", value="failed", selected=status == "failed"),
        ]

        filters = Form(
            Select(*svc_options, name="service",
                   cls="select select-sm select-bordered font-mono text-xs",
                   onchange="this.form.submit()"),
            Select(*status_options, name="status",
                   cls="select select-sm select-bordered font-mono text-xs",
                   onchange="this.form.submit()"),
            method="get", action="/history",
            cls="flex gap-2 mb-4",
        )

        # Table
        if not rows:
            empty = Div(
                NotStr('<svg class="w-8 h-8 opacity-15 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'),
                P("No sync runs found", cls="text-xs opacity-40"),
                cls="flex flex-col items-center py-10",
            )
            return page(
                Div(
                    H3("Sync History", cls="text-sm font-semibold"),
                    Span(f"{total} runs", cls="text-[11px] opacity-40"),
                    cls="flex items-center justify-between mb-4",
                ),
                filters, empty, title="Sync History",
            )

        header = Tr(
            Th("ID", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold w-12"),
            Th("Service", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Type", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Status", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Fetched", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("New", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Updated", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Duration", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Started", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
            Th("Error", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        )

        body_rows = []
        for r in rows:
            dot_cls = STATUS_DOT.get(r["status"], "bg-base-content/20")
            duration = f"{r['duration_sec']:.1f}s" if r["duration_sec"] else "—"
            error_msg = r["error_message"] or ""
            if len(error_msg) > 40:
                error_msg = error_msg[:40] + "..."

            body_rows.append(Tr(
                Td(Span(str(r["id"]), cls="text-xs font-mono opacity-40")),
                Td(Span(r["service_id"].capitalize(), cls="text-sm font-medium")),
                Td(Span(r["run_type"], cls="text-xs opacity-60")),
                Td(Div(
                    Span(cls=f"w-1.5 h-1.5 rounded-full {dot_cls} inline-block"),
                    Span(r["status"], cls="text-xs"),
                    cls="flex items-center gap-1.5",
                )),
                Td(Span(str(r["items_fetched"] or 0), cls="text-xs font-mono")),
                Td(Span(str(r["items_new"] or 0), cls="text-xs font-mono")),
                Td(Span(str(r["items_updated"] or 0), cls="text-xs font-mono")),
                Td(Span(duration, cls="font-mono text-xs opacity-60")),
                Td(Span(r["started_at"][:16] if r["started_at"] else "—",
                        cls="text-xs opacity-50 font-mono")),
                Td(Span(error_msg, cls="text-xs text-error opacity-70") if error_msg else
                   Span("—", cls="text-xs opacity-20")),
            ))

        table = Div(
            Table(
                Thead(header),
                Tbody(*body_rows),
                cls="table table-sm table-zebra",
            ),
            cls="card bg-base-200/50 border border-base-content/5 overflow-x-auto",
        )

        # Pagination
        pagination_items = []
        if pg > 1:
            pagination_items.append(
                A("← Prev", href=_history_url(service, status, pg - 1),
                  cls="btn btn-ghost btn-xs")
            )
        pagination_items.append(
            Span(f"Page {pg} of {total_pages}", cls="text-xs opacity-40 px-2")
        )
        if pg < total_pages:
            pagination_items.append(
                A("Next →", href=_history_url(service, status, pg + 1),
                  cls="btn btn-ghost btn-xs")
            )

        pagination = Div(
            *pagination_items,
            cls="flex items-center justify-center gap-2 mt-4",
        ) if total_pages > 1 else None

        return page(
            Div(
                H3("Sync History", cls="text-sm font-semibold"),
                Span(f"{total} runs", cls="text-[11px] opacity-40"),
                cls="flex items-center justify-between mb-4",
            ),
            filters,
            table,
            pagination,
            title="Sync History",
        )


def _history_url(service, status, pg):
    params = []
    if service:
        params.append(f"service={service}")
    if status:
        params.append(f"status={status}")
    if pg > 1:
        params.append(f"pg={pg}")
    qs = "&".join(params)
    return f"/history{'?' + qs if qs else ''}"
