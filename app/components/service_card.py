from fasthtml.common import *


STATUS_COLORS = {
    "connected":    "badge-success",
    "disconnected": "badge-ghost",
    "auth_required": "badge-warning",
    "error":        "badge-error",
    "syncing":      "badge-info",
}


def service_card(service):
    sid = service["id"]
    name = service["display_name"]
    status = service["status"]
    last_sync = service["last_sync_at"] or "Never"
    badge_cls = STATUS_COLORS.get(status, "badge-ghost")

    if status == "connected":
        action = Button(
            "Sync Now",
            hx_post=f"/sync/{sid}",
            hx_target=f"#card-{sid}",
            hx_swap="outerHTML",
            cls="btn btn-primary btn-xs",
        )
    else:
        action = A(
            "Connect",
            href=f"/services/{sid}",
            cls="btn btn-outline btn-xs",
        )

    return Div(
        Div(
            Div(
                Span(name, cls="card-title text-sm font-semibold"),
                Span(status, cls=f"badge badge-sm {badge_cls}"),
                cls="flex items-center justify-between",
            ),
            Div(
                Div(
                    Span("Last sync", cls="text-xs opacity-50"),
                    Span(last_sync, cls="text-xs font-mono"),
                    cls="flex justify-between",
                ),
                Div(
                    Span("Items", cls="text-xs opacity-50"),
                    Span(str(service.get("item_count", 0)), cls="text-xs font-mono"),
                    cls="flex justify-between",
                ),
                cls="mt-3 space-y-1",
            ),
            Div(action, cls="mt-3"),
            cls="card-body p-4",
        ),
        id=f"card-{sid}",
        hx_get=f"/services/{sid}/card",
        hx_trigger="every 30s",
        hx_swap="outerHTML",
        cls="card bg-base-200 shadow-sm",
    )
