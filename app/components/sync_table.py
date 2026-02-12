from fasthtml.common import *


STATUS_COLORS = {
    "success":  "badge-success",
    "running":  "badge-info",
    "failed":   "badge-error",
}


def sync_history_table(rows):
    if not rows:
        return Div(
            P("No sync runs yet.", cls="text-sm opacity-50 text-center py-8"),
            cls="overflow-x-auto",
        )

    header = Tr(
        Th("Service"),
        Th("Type"),
        Th("Status"),
        Th("Items"),
        Th("Duration"),
        Th("Time"),
    )

    body_rows = []
    for r in rows:
        badge_cls = STATUS_COLORS.get(r["status"], "badge-ghost")
        duration = f"{r['duration_sec']:.1f}s" if r["duration_sec"] else "—"
        body_rows.append(Tr(
            Td(r["service_id"], cls="font-medium"),
            Td(r["run_type"]),
            Td(Span(r["status"], cls=f"badge badge-sm {badge_cls}")),
            Td(str(r["items_fetched"] or 0)),
            Td(duration, cls="font-mono text-xs"),
            Td(r["started_at"] or "—", cls="text-xs"),
        ))

    return Div(
        Table(
            Thead(header),
            Tbody(*body_rows),
            cls="table table-sm",
        ),
        cls="overflow-x-auto",
    )
