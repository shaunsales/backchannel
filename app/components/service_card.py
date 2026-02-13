from fasthtml.common import *
from app.components.layout import SERVICE_ICONS


STATUS_BADGE = {
    "connected":     ("badge-success", "Connected"),
    "disconnected":  ("badge-ghost",   "Not connected"),
    "auth_required": ("badge-warning", "Auth required"),
    "error":         ("badge-error",   "Error"),
    "syncing":       ("badge-info",    "Syncing..."),
}

STATUS_DOT = {
    "connected":     "bg-success",
    "disconnected":  "bg-base-content/20",
    "auth_required": "bg-warning",
    "error":         "bg-error",
    "syncing":       "bg-info",
}


def service_card(service):
    sid = service["id"]
    name = service["display_name"]
    status = service["status"]
    last_sync = service["last_sync_at"] or "Never"
    item_count = service.get("item_count", 0)
    dot_cls = STATUS_DOT.get(status, "bg-base-content/20")
    _, status_label = STATUS_BADGE.get(status, ("badge-ghost", status))
    icon_svg = SERVICE_ICONS.get(sid, "")

    if status == "connected":
        action = Button(
            NotStr('<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'),
            Span("Sync"),
            hx_post=f"/sync/{sid}",
            hx_target=f"#card-{sid}",
            hx_swap="outerHTML",
            cls="btn btn-primary btn-xs gap-1 h-7 min-h-0",
        )
    else:
        action = A(
            "Connect",
            href=f"/services/{sid}",
            cls="btn btn-ghost btn-xs h-7 min-h-0 border border-base-content/10",
        )

    return Div(
        Div(
            Div(
                Div(
                    NotStr(icon_svg.replace('opacity-60', 'opacity-80')),
                    cls="w-8 h-8 rounded-lg bg-base-300 flex items-center justify-center shrink-0",
                ),
                Div(
                    Span(name, cls="text-sm font-semibold leading-tight"),
                    Div(
                        Span(cls=f"w-1.5 h-1.5 rounded-full {dot_cls} inline-block"),
                        Span(status_label, cls="text-[11px] opacity-50"),
                        cls="flex items-center gap-1.5",
                    ),
                    cls="flex flex-col",
                ),
                cls="flex items-center gap-3",
            ),
            Div(cls="border-b border-base-content/5 my-3"),
            Div(
                Div(
                    Span("Items", cls="text-[11px] opacity-40"),
                    Span(f"{item_count:,}", cls="text-sm font-mono font-semibold"),
                    cls="flex flex-col",
                ),
                Div(
                    Span("Last sync", cls="text-[11px] opacity-40"),
                    Span(last_sync, cls="text-[11px] font-mono opacity-70"),
                    cls="flex flex-col",
                ),
                cls="flex gap-6 mb-3",
            ),
            Div(action),
            cls="card-body p-4",
        ),
        id=f"card-{sid}",
        hx_get=f"/services/{sid}/card",
        hx_trigger="every 30s",
        hx_swap="outerHTML",
        cls="card bg-base-200/50 border border-base-content/5 hover:border-base-content/10 transition-colors",
    )
