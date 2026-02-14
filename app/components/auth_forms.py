from fasthtml.common import *


def notion_auth_form(service: dict):
    """API key input form for Notion integration."""
    import json
    creds = json.loads(service.get("credentials", "{}") or "{}")
    current_token = creds.get("token", "")
    is_connected = service["status"] == "connected"
    masked = f"{current_token[:8]}...{current_token[-4:]}" if len(current_token) > 12 else ""

    if is_connected:
        return Div(
            Div(
                Div(
                    Span(cls="w-2 h-2 rounded-full bg-success inline-block"),
                    Span("Connected", cls="text-sm font-medium"),
                    cls="flex items-center gap-2",
                ),
                P(f"Token: {masked}", cls="text-xs font-mono opacity-50 mt-1") if masked else None,
                cls="mb-4",
            ),
            Div(
                Button(
                    "Sync Now",
                    hx_post=f"/sync/notion",
                    hx_target="#notion-auth-result",
                    hx_swap="innerHTML",
                    cls="btn btn-primary btn-sm",
                ),
                Button(
                    "Test Connection",
                    hx_post="/auth/notion/test",
                    hx_target="#notion-auth-result",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm border border-base-content/10",
                ),
                Button(
                    "Disconnect",
                    hx_post="/auth/notion/disconnect",
                    hx_target="#notion-auth-area",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm text-error border border-error/20",
                ),
                cls="flex gap-2",
            ),
            Div(id="notion-auth-result", cls="mt-3"),
            id="notion-auth-area",
        )

    return Div(
        Form(
            Div(
                Label("Notion Integration Token", fr="notion-token", cls="label text-xs font-semibold"),
                Div(
                    Input(
                        type="password",
                        name="token",
                        id="notion-token",
                        placeholder="ntn_...",
                        value=current_token,
                        cls="input input-bordered input-sm w-full font-mono",
                        required=True,
                    ),
                    cls="mb-1",
                ),
                P(
                    "Create an integration at ",
                    A("notion.so/my-integrations", href="https://www.notion.so/my-integrations",
                      target="_blank", cls="link link-primary"),
                    " and share pages with it.",
                    cls="text-[11px] opacity-40",
                ),
                cls="mb-4",
            ),
            Div(
                Button("Save & Test", type="submit", cls="btn btn-primary btn-sm"),
                cls="flex gap-2",
            ),
            hx_post="/auth/notion/connect",
            hx_target="#notion-auth-area",
            hx_swap="innerHTML",
        ),
        Div(id="notion-auth-result", cls="mt-3"),
        id="notion-auth-area",
    )
