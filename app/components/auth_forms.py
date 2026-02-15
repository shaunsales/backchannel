from fasthtml.common import *


def telegram_auth_form(service: dict):
    """Multi-step auth form for Telegram (phone → code → 2FA)."""
    import json
    creds = json.loads(service.get("credentials", "{}") or "{}")
    is_connected = service["status"] == "connected"
    phone = creds.get("phone", "")

    if is_connected:
        return Div(
            Div(
                Div(
                    Span(cls="w-2 h-2 rounded-full bg-success inline-block"),
                    Span("Connected", cls="text-sm font-medium"),
                    cls="flex items-center gap-2",
                ),
                P(f"Phone: {phone}", cls="text-xs font-mono opacity-50 mt-1") if phone else None,
                cls="mb-4",
            ),
            Div(
                Button(
                    Span("Preview Sync", cls="sync-label"),
                    Span("Scanning...", cls="loading loading-spinner loading-xs htmx-indicator"),
                    hx_post="/sync/telegram/preview",
                    hx_target="#telegram-auth-result",
                    hx_swap="innerHTML",
                    hx_indicator="closest button",
                    hx_disabled_elt="this",
                    cls="btn btn-outline btn-sm",
                ),
                Button(
                    Span("Sync Now", cls="sync-label"),
                    Span("Syncing...", cls="loading loading-spinner loading-xs htmx-indicator"),
                    hx_post="/sync/telegram",
                    hx_target="#telegram-auth-result",
                    hx_swap="innerHTML",
                    hx_indicator="closest button",
                    hx_disabled_elt="this",
                    cls="btn btn-primary btn-sm",
                ),
                Button(
                    "Disconnect",
                    hx_post="/auth/telegram/disconnect",
                    hx_target="#telegram-auth-area",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm text-error border border-error/20",
                ),
                cls="flex gap-2",
            ),
            Div(id="telegram-auth-result", cls="mt-3"),
            id="telegram-auth-area",
        )

    return Div(
        Form(
            Div(
                Label("API ID", fr="tg-api-id", cls="label text-xs font-semibold"),
                Input(
                    type="text",
                    name="api_id",
                    id="tg-api-id",
                    placeholder="12345678",
                    cls="input input-bordered input-sm w-full font-mono",
                    required=True,
                ),
                cls="mb-3",
            ),
            Div(
                Label("API Hash", fr="tg-api-hash", cls="label text-xs font-semibold"),
                Input(
                    type="password",
                    name="api_hash",
                    id="tg-api-hash",
                    placeholder="abcdef0123456789...",
                    cls="input input-bordered input-sm w-full font-mono",
                    required=True,
                ),
                cls="mb-3",
            ),
            Div(
                Label("Phone Number", fr="tg-phone", cls="label text-xs font-semibold"),
                Input(
                    type="tel",
                    name="phone",
                    id="tg-phone",
                    placeholder="+1234567890",
                    cls="input input-bordered input-sm w-full font-mono",
                    required=True,
                ),
                P(
                    "Get API ID and Hash from ",
                    A("my.telegram.org/apps", href="https://my.telegram.org/apps", target="_blank",
                      cls="link link-primary"),
                    ".",
                    cls="text-[11px] opacity-40 mt-1",
                ),
                cls="mb-4",
            ),
            Button("Send Code", type="submit", cls="btn btn-primary btn-sm"),
            hx_post="/auth/telegram/phone",
            hx_target="#telegram-auth-area",
            hx_swap="innerHTML",
        ),
        Div(id="telegram-auth-result", cls="mt-3"),
        id="telegram-auth-area",
    )


def telegram_code_form(phone: str):
    """Verification code input (step 2 of Telegram auth)."""
    return Div(
        P(f"Code sent to {phone}", cls="text-sm opacity-70 mb-3"),
        Form(
            Input(type="hidden", name="phone", value=phone),
            Div(
                Label("Verification Code", fr="tg-code", cls="label text-xs font-semibold"),
                Input(
                    type="text",
                    name="code",
                    id="tg-code",
                    placeholder="12345",
                    cls="input input-bordered input-sm w-full font-mono tracking-widest",
                    required=True,
                    autofocus=True,
                ),
                cls="mb-4",
            ),
            Button("Verify", type="submit", cls="btn btn-primary btn-sm"),
            hx_post="/auth/telegram/code",
            hx_target="#telegram-auth-area",
            hx_swap="innerHTML",
        ),
        id="telegram-auth-area",
    )


def telegram_2fa_form(phone: str):
    """2FA password input (step 3 of Telegram auth, if enabled)."""
    return Div(
        P("Two-factor authentication is enabled. Enter your password.", cls="text-sm opacity-70 mb-3"),
        Form(
            Input(type="hidden", name="phone", value=phone),
            Div(
                Label("2FA Password", fr="tg-password", cls="label text-xs font-semibold"),
                Input(
                    type="password",
                    name="password",
                    id="tg-password",
                    cls="input input-bordered input-sm w-full",
                    required=True,
                    autofocus=True,
                ),
                cls="mb-4",
            ),
            Button("Submit", type="submit", cls="btn btn-primary btn-sm"),
            hx_post="/auth/telegram/password",
            hx_target="#telegram-auth-area",
            hx_swap="innerHTML",
        ),
        id="telegram-auth-area",
    )


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
                    Span("Sync Now", cls="sync-label"),
                    Span("Syncing...", cls="loading loading-spinner loading-xs htmx-indicator"),
                    hx_post=f"/sync/notion",
                    hx_target="#notion-auth-result",
                    hx_swap="innerHTML",
                    hx_indicator="closest button",
                    hx_disabled_elt="this",
                    cls="btn btn-primary btn-sm",
                ),
                Button(
                    "Test Connection",
                    hx_post="/auth/notion/test",
                    hx_target="#notion-auth-result",
                    hx_swap="innerHTML",
                    hx_disabled_elt="this",
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
