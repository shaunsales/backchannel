from fasthtml.common import *


STATUS_COLORS = {
    "success":  "badge-success",
    "running":  "badge-info",
    "failed":   "badge-error",
}

STATUS_DOT = {
    "success": "bg-success",
    "running": "bg-info",
    "failed":  "bg-error",
}


def sync_history_table(rows):
    if not rows:
        return Div(
            Div(
                NotStr('<svg class="w-8 h-8 opacity-20 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'),
                P("No sync runs yet", cls="text-xs opacity-40"),
                P("Connect a service and run your first sync", cls="text-[11px] opacity-25"),
                cls="flex flex-col items-center py-10",
            ),
        )

    header = Tr(
        Th("Service", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        Th("Type", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        Th("Status", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        Th("Items", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        Th("Duration", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
        Th("Time", cls="text-[11px] uppercase tracking-wider opacity-40 font-semibold"),
    )

    body_rows = []
    for r in rows:
        dot_cls = STATUS_DOT.get(r["status"], "bg-base-content/20")
        duration = f"{r['duration_sec']:.1f}s" if r["duration_sec"] else "—"
        body_rows.append(Tr(
            Td(Span(r["service_id"], cls="capitalize"), cls="text-sm font-medium"),
            Td(Span(r["run_type"], cls="text-xs opacity-60")),
            Td(Div(
                Span(cls=f"w-1.5 h-1.5 rounded-full {dot_cls} inline-block"),
                Span(r["status"], cls="text-xs"),
                cls="flex items-center gap-1.5",
            )),
            Td(Span(str(r["items_fetched"] or 0), cls="text-xs font-mono")),
            Td(Span(duration, cls="font-mono text-xs opacity-60")),
            Td(Span(r["started_at"] or "—", cls="text-xs opacity-50")),
        ))

    return Div(
        Table(
            Thead(header),
            Tbody(*body_rows),
            cls="table table-sm table-zebra",
        ),
        cls="overflow-x-auto",
    )
