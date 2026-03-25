from fasthtml.common import *


def _sync_buttons(sid: str, result_id: str, area_id: str, show_preview: bool = False):
    """Reusable Sync Now button with live SSE log output, plus Disconnect."""
    buttons = []

    buttons.append(Button(
        "Sync Now",
        onclick=f"startSyncStream('{sid}', '{result_id}')",
        id=f"{sid}-sync-btn",
        cls="btn btn-primary btn-sm",
    ))

    buttons.append(Button(
        "Disconnect",
        hx_post=f"/auth/{sid}/disconnect",
        hx_target=f"#{area_id}",
        hx_swap="innerHTML",
        cls="btn btn-ghost btn-sm text-error border border-error/20",
    ))

    sync_js = Script("""
    function startSyncStream(sid, resultId) {
        var btn = document.getElementById(sid + '-sync-btn');
        var el = document.getElementById(resultId);
        if (!el || !btn) return;
        btn.disabled = true;
        btn.innerHTML = '<span class="loading loading-spinner loading-xs"></span> Syncing…';
        el.innerHTML = '<div class="flex items-center gap-2 text-xs opacity-60"><span class="loading loading-spinner loading-xs"></span><span id="' + sid + '-status">Starting sync…</span></div>';
        var statusEl = document.getElementById(sid + '-status');
        var lastMsg = '';
        var es = new EventSource('/sync/' + sid + '/stream');
        es.onmessage = function(e) {
            var d = JSON.parse(e.data);
            if (d.type === 'log' && statusEl) {
                // Show only short summary lines, skip verbose data
                var m = d.msg || '';
                if (m.length < 120 && !m.startsWith('{') && !m.startsWith('cursor=')) {
                    lastMsg = m;
                    statusEl.textContent = m;
                }
            } else if (d.type === 'done') {
                es.close();
                btn.disabled = false;
                btn.innerHTML = 'Sync Now';
                var isOk = d.status === 'success';
                var cls = isOk ? 'text-success' : 'text-error';
                var icon = isOk ? '✓' : '✗';
                el.innerHTML = '<div class="flex items-center gap-2 mt-1"><span class="' + cls + ' text-sm font-medium">' + icon + ' ' + d.msg + '</span><button onclick="this.parentElement.remove()" class="btn btn-ghost btn-xs btn-circle opacity-40 hover:opacity-100">✕</button></div>';
                // Auto-refresh sync history table if present
                var hist = document.querySelector('[data-sync-history]');
                if (hist) { htmx.trigger(hist, 'refresh'); }
            }
        };
        es.onerror = function() {
            es.close();
            btn.disabled = false;
            btn.innerHTML = 'Sync Now';
            el.innerHTML = '<div class="flex items-center gap-2 mt-1"><span class="text-error text-sm">✗ Connection lost</span><button onclick="this.parentElement.remove()" class="btn btn-ghost btn-xs btn-circle opacity-40 hover:opacity-100">✕</button></div>';
        };
    }
    """)

    return Div(
        Div(*buttons, cls="flex gap-2"),
        sync_js,
    )


def telegram_auth_form(service: dict):
    """Multi-step auth form for Telegram (phone → code → 2FA)."""
    import json
    sid = service["id"]
    creds = json.loads(service.get("credentials", "{}") or "{}")
    is_connected = service["status"] == "connected"
    phone = creds.get("phone", "")
    area_id = f"{sid}-auth-area"
    result_id = f"{sid}-auth-result"

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
            _sync_buttons(sid, result_id, area_id, show_preview=True),
            Div(id=result_id, cls="mt-3"),
            id=area_id,
        )

    return Div(
        Form(
            Input(type="hidden", name="service_id", value=sid),
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
            hx_post=f"/auth/{sid}/phone",
            hx_target=f"#{area_id}",
            hx_swap="innerHTML",
        ),
        Div(id=result_id, cls="mt-3"),
        id=area_id,
    )


def telegram_code_form(phone: str, service_id: str = "telegram"):
    """Verification code input (step 2 of Telegram auth)."""
    area_id = f"{service_id}-auth-area"
    return Div(
        P(f"Code sent to {phone}", cls="text-sm opacity-70 mb-3"),
        Form(
            Input(type="hidden", name="phone", value=phone),
            Input(type="hidden", name="service_id", value=service_id),
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
            hx_post=f"/auth/{service_id}/code",
            hx_target=f"#{area_id}",
            hx_swap="innerHTML",
        ),
        id=area_id,
    )


def telegram_2fa_form(phone: str, service_id: str = "telegram"):
    """2FA password input (step 3 of Telegram auth, if enabled)."""
    area_id = f"{service_id}-auth-area"
    return Div(
        P("Two-factor authentication is enabled. Enter your password.", cls="text-sm opacity-70 mb-3"),
        Form(
            Input(type="hidden", name="phone", value=phone),
            Input(type="hidden", name="service_id", value=service_id),
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
            hx_post=f"/auth/{service_id}/password",
            hx_target=f"#{area_id}",
            hx_swap="innerHTML",
        ),
        id=area_id,
    )


def notion_auth_form(service: dict):
    """API key input form for Notion integration."""
    import json
    sid = service["id"]
    creds = json.loads(service.get("credentials", "{}") or "{}")
    current_token = creds.get("token", "")
    is_connected = service["status"] == "connected"
    masked = f"{current_token[:8]}...{current_token[-4:]}" if len(current_token) > 12 else ""
    area_id = f"{sid}-auth-area"
    result_id = f"{sid}-auth-result"

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
            _sync_buttons(sid, result_id, area_id),
            Div(id=result_id, cls="mt-3"),
            id=area_id,
        )

    return Div(
        Form(
            Input(type="hidden", name="service_id", value=sid),
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
            hx_post=f"/auth/{sid}/connect",
            hx_target=f"#{area_id}",
            hx_swap="innerHTML",
        ),
        Div(id=result_id, cls="mt-3"),
        id=area_id,
    )


def gmail_auth_form(service: dict):
    """IMAP auth form for Gmail — email + App Password."""
    import json
    sid = service["id"]
    creds = json.loads(service.get("credentials", "{}") or "{}")
    is_connected = service["status"] == "connected"
    area_id = f"{sid}-auth-area"
    result_id = f"{sid}-auth-result"

    if is_connected:
        email_addr = creds.get("email", "")
        return Div(
            Div(
                Div(
                    Span(cls="w-2 h-2 rounded-full bg-success inline-block"),
                    Span("Connected", cls="text-sm font-medium"),
                    cls="flex items-center gap-2",
                ),
                P(f"Account: {email_addr}", cls="text-xs font-mono opacity-50 mt-1") if email_addr else None,
                cls="mb-4",
            ),
            _sync_buttons(sid, result_id, area_id),
            Div(id=result_id, cls="mt-3"),
            id=area_id,
        )

    return Div(
        Form(
            Input(type="hidden", name="service_id", value=sid),
            Div(
                Label("Gmail Address", cls="label text-xs font-semibold"),
                Input(
                    type="email",
                    name="email",
                    placeholder="you@gmail.com",
                    value=creds.get("email", ""),
                    cls="input input-bordered input-sm w-full font-mono",
                    required=True,
                ),
                cls="mb-3",
            ),
            Div(
                Label("App Password", cls="label text-xs font-semibold"),
                Input(
                    type="password",
                    name="app_password",
                    placeholder="xxxx xxxx xxxx xxxx",
                    cls="input input-bordered input-sm w-full font-mono tracking-widest",
                    required=True,
                ),
                P(
                    "Enable 2-Step Verification, then generate at ",
                    A("myaccount.google.com/apppasswords",
                      href="https://myaccount.google.com/apppasswords",
                      target="_blank", cls="link link-primary"),
                    ".",
                    cls="text-[11px] opacity-40 mt-1",
                ),
                cls="mb-4",
            ),
            Button("Save & Test", type="submit", cls="btn btn-primary btn-sm"),
            hx_post=f"/auth/{sid}/connect",
            hx_target=f"#{area_id}",
            hx_swap="innerHTML",
        ),
        Div(id=result_id, cls="mt-3"),
        id=area_id,
    )
