"""
Add Account wizard modal — 3-step flow:
  Step 1: Select service type + name
  Step 2: Enter credentials (service-specific)
  Step 3: Finalize (connection result + optional sync)
"""
from fasthtml.common import *
from app.components.layout import SERVICE_ICONS


# Service types available for adding
SERVICE_TYPES = {
    "notion":     {"name": "Notion",     "description": "Sync pages and databases", "auth_type": "api_key"},
    "gmail":      {"name": "Gmail",      "description": "Sync emails via IMAP", "auth_type": "app_password"},
    "telegram":   {"name": "Telegram",   "description": "Sync messages from chats", "auth_type": "phone_code"},
    "protonmail": {"name": "ProtonMail", "description": "Sync emails via IMAP bridge", "auth_type": "imap_login"},
    "whatsapp":   {"name": "WhatsApp",   "description": "Sync messages via bridge", "auth_type": "qr_link"},
}


def wizard_modal():
    """The outer modal shell — always present on the page, toggled open by JS."""
    return Div(
        Div(
            Div(
                Div(
                    H3("Add Account", cls="text-base font-semibold"),
                    Button(
                        NotStr('<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>'),
                        onclick="document.getElementById('wizard-modal').classList.add('hidden')",
                        cls="btn btn-ghost btn-sm btn-circle",
                    ),
                    cls="flex items-center justify-between mb-4",
                ),
                Div(id="wizard-content"),
                cls="bg-base-200 rounded-xl p-6 w-full max-w-lg shadow-xl border border-base-content/10",
            ),
            cls="flex items-center justify-center min-h-screen p-4",
        ),
        id="wizard-modal",
        cls="hidden fixed inset-0 z-50 bg-black/50",
    )


def wizard_step1():
    """Step 1: Pick a service type."""
    cards = []
    for svc_type, info in SERVICE_TYPES.items():
        icon_svg = SERVICE_ICONS.get(svc_type, "")
        cards.append(
            Button(
                Div(
                    NotStr(icon_svg.replace('opacity-60', 'opacity-80')),
                    cls="w-8 h-8 rounded-lg bg-base-300 flex items-center justify-center shrink-0",
                ),
                Div(
                    Span(info["name"], cls="text-sm font-semibold"),
                    Span(info["description"], cls="text-[11px] opacity-50"),
                    cls="flex flex-col text-left",
                ),
                hx_get=f"/accounts/wizard/step2?service_type={svc_type}",
                hx_target="#wizard-content",
                hx_swap="innerHTML",
                cls="flex items-center gap-3 p-3 rounded-lg border border-base-content/5 "
                    "hover:border-primary/30 hover:bg-base-300/50 transition-colors w-full cursor-pointer",
            )
        )

    return Div(
        _step_indicator(1),
        Div(
            P("Choose a service to connect:", cls="text-sm opacity-60 mb-3"),
            Div(*cards, cls="flex flex-col gap-2"),
        ),
    )


def wizard_step2(service_type: str, display_name: str = ""):
    """Step 2: Enter credentials — service-specific fields."""
    info = SERVICE_TYPES.get(service_type, {})
    svc_name = info.get("name", service_type.title())

    # Account name field (common to all)
    name_field = Div(
        Label("Account Name", cls="label text-xs font-semibold"),
        Input(
            type="text", name="display_name", value=display_name,
            placeholder=f"{svc_name} (Personal)",
            cls="input input-bordered input-sm w-full",
            required=True,
        ),
        cls="mb-3",
    )

    # Service-specific credential fields
    if service_type == "notion":
        cred_fields = Div(
            Label("Integration Token", cls="label text-xs font-semibold"),
            Div(
                Input(
                    type="password", name="token",
                    placeholder="ntn_...",
                    cls="input input-bordered input-sm w-full font-mono text-xs",
                    required=True,
                ),
                P(
                    "Create one at ",
                    A("notion.so/my-integrations", href="https://www.notion.so/my-integrations",
                      target="_blank", cls="link link-primary"),
                    cls="text-[11px] opacity-40 mt-1",
                ),
            ),
            cls="mb-3",
        )
    elif service_type == "gmail":
        cred_fields = Div(
            Div(
                Label("Gmail Address", cls="label text-xs font-semibold"),
                Input(
                    type="email", name="email",
                    placeholder="you@gmail.com",
                    cls="input input-bordered input-sm w-full",
                    required=True,
                ),
                cls="mb-3",
            ),
            Div(
                Label("App Password", cls="label text-xs font-semibold"),
                Input(
                    type="password", name="app_password",
                    placeholder="xxxx xxxx xxxx xxxx",
                    cls="input input-bordered input-sm w-full font-mono text-xs",
                    required=True,
                ),
                P(
                    "Generate at ",
                    A("myaccount.google.com/apppasswords",
                      href="https://myaccount.google.com/apppasswords",
                      target="_blank", cls="link link-primary"),
                    cls="text-[11px] opacity-40 mt-1",
                ),
                cls="mb-3",
            ),
        )
    elif service_type == "telegram":
        cred_fields = Div(
            Div(
                Label("API ID", cls="label text-xs font-semibold"),
                Input(
                    type="text", name="api_id",
                    placeholder="12345678",
                    cls="input input-bordered input-sm w-full font-mono text-xs",
                    required=True,
                ),
                cls="mb-3",
            ),
            Div(
                Label("API Hash", cls="label text-xs font-semibold"),
                Input(
                    type="password", name="api_hash",
                    placeholder="abc123...",
                    cls="input input-bordered input-sm w-full font-mono text-xs",
                    required=True,
                ),
                P(
                    "Get from ",
                    A("my.telegram.org", href="https://my.telegram.org",
                      target="_blank", cls="link link-primary"),
                    cls="text-[11px] opacity-40 mt-1",
                ),
                cls="mb-3",
            ),
            Div(
                Label("Phone Number", cls="label text-xs font-semibold"),
                Input(
                    type="tel", name="phone",
                    placeholder="+1234567890",
                    cls="input input-bordered input-sm w-full",
                    required=True,
                ),
                cls="mb-3",
            ),
        )
    else:
        cred_fields = Div(
            P(f"{svc_name} setup is not yet available.", cls="text-sm opacity-50"),
            cls="mb-3",
        )

    return Div(
        _step_indicator(2),
        Form(
            Input(type="hidden", name="service_type", value=service_type),
            name_field,
            cred_fields,
            Div(
                Button(
                    "Back",
                    hx_get="/accounts/wizard/step1",
                    hx_target="#wizard-content",
                    hx_swap="innerHTML",
                    type="button",
                    cls="btn btn-ghost btn-sm",
                ),
                Button(
                    Span("Connect", cls="sync-label"),
                    Span("Connecting...", cls="loading loading-spinner loading-xs htmx-indicator"),
                    type="submit",
                    cls="btn btn-primary btn-sm",
                ),
                cls="flex justify-between mt-4",
            ),
            hx_post="/accounts/wizard/connect",
            hx_target="#wizard-content",
            hx_swap="innerHTML",
            hx_indicator="find .btn-primary",
            hx_disabled_elt="find .btn-primary",
        ),
    )


def wizard_step3_success(service_id: str, display_name: str):
    """Step 3: Connection successful — offer sync or skip."""
    return Div(
        _step_indicator(3),
        Div(
            Div(
                NotStr('<svg class="w-10 h-10 text-success" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'),
                cls="flex justify-center mb-3",
            ),
            P(f"{display_name} connected successfully!", cls="text-sm text-center font-medium mb-4"),
            Div(id="wizard-sync-result", cls="mb-3"),
            Div(
                Button(
                    "Sync Now",
                    onclick=f"wizardSync('{service_id}')",
                    id="wizard-sync-btn",
                    cls="btn btn-primary btn-sm",
                ),
                A(
                    "Skip for Later",
                    href=f"/accounts/{service_id}",
                    cls="btn btn-ghost btn-sm",
                ),
                cls="flex justify-center gap-3",
            ),
            Script("""
            function wizardSync(sid) {
                var btn = document.getElementById('wizard-sync-btn');
                var el = document.getElementById('wizard-sync-result');
                if (!btn || !el) return;
                btn.disabled = true;
                btn.innerHTML = '<span class="loading loading-spinner loading-xs"></span> Syncing…';
                el.innerHTML = '<div class="bg-base-300/50 rounded-lg p-3 font-mono text-xs max-h-32 overflow-y-auto border border-base-content/5" id="wizard-log"></div>';
                var logEl = document.getElementById('wizard-log');
                var es = new EventSource('/sync/' + sid + '/stream');
                es.onmessage = function(e) {
                    var d = JSON.parse(e.data);
                    if (d.type === 'log') {
                        var line = document.createElement('div');
                        line.className = 'py-0.5 opacity-70';
                        line.textContent = d.msg;
                        logEl.appendChild(line);
                        logEl.scrollTop = logEl.scrollHeight;
                    } else if (d.type === 'done') {
                        es.close();
                        btn.disabled = false;
                        btn.innerHTML = 'Done';
                        btn.onclick = function(){ window.location='/accounts/' + sid; };
                        btn.className = 'btn btn-success btn-sm';
                        var cls = d.status === 'success' ? 'alert-success' : 'alert-error';
                        var alert = '<div role="alert" class="alert ' + cls + ' text-sm mt-2"><span>' + d.msg + '</span></div>';
                        el.innerHTML = alert + el.innerHTML;
                    }
                };
                es.onerror = function() { es.close(); btn.disabled = false; btn.innerHTML = 'Sync Now'; };
            }
            """),
        ),
    )


def wizard_step3_failure(service_type: str, display_name: str, error: str):
    """Step 3: Connection failed — offer retry."""
    return Div(
        _step_indicator(3),
        Div(
            Div(
                NotStr('<svg class="w-10 h-10 text-error" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/></svg>'),
                cls="flex justify-center mb-3",
            ),
            P("Connection failed", cls="text-sm text-center font-medium text-error mb-2"),
            P(error, cls="text-xs text-center opacity-60 mb-4 font-mono"),
            Div(
                Button(
                    "Try Again",
                    hx_get=f"/accounts/wizard/step2?service_type={service_type}&display_name={display_name}",
                    hx_target="#wizard-content",
                    hx_swap="innerHTML",
                    cls="btn btn-primary btn-sm",
                ),
                Button(
                    "Cancel",
                    onclick="document.getElementById('wizard-modal').classList.add('hidden')",
                    cls="btn btn-ghost btn-sm",
                ),
                cls="flex justify-center gap-3",
            ),
        ),
    )


def wizard_telegram_code(service_id: str, phone: str):
    """Intermediate step for Telegram: enter verification code."""
    return Div(
        _step_indicator(2),
        P(f"A code was sent to {phone}", cls="text-sm opacity-60 mb-3"),
        Form(
            Input(type="hidden", name="service_id", value=service_id),
            Div(
                Label("Verification Code", cls="label text-xs font-semibold"),
                Input(
                    type="text", name="code",
                    placeholder="12345",
                    cls="input input-bordered input-sm w-full font-mono text-center tracking-widest",
                    required=True, autofocus=True,
                ),
                cls="mb-3",
            ),
            Div(id="wizard-code-error"),
            Button(
                Span("Verify", cls="sync-label"),
                Span("Verifying...", cls="loading loading-spinner loading-xs htmx-indicator"),
                type="submit",
                cls="btn btn-primary btn-sm w-full",
            ),
            hx_post="/accounts/wizard/telegram-code",
            hx_target="#wizard-content",
            hx_swap="innerHTML",
            hx_indicator="find .btn-primary",
            hx_disabled_elt="find .btn-primary",
        ),
    )


def wizard_telegram_2fa(service_id: str, phone: str):
    """Intermediate step for Telegram: 2FA password."""
    return Div(
        _step_indicator(2),
        P("Two-factor authentication required", cls="text-sm opacity-60 mb-3"),
        Form(
            Input(type="hidden", name="service_id", value=service_id),
            Div(
                Label("2FA Password", cls="label text-xs font-semibold"),
                Input(
                    type="password", name="password",
                    placeholder="Your 2FA password",
                    cls="input input-bordered input-sm w-full",
                    required=True, autofocus=True,
                ),
                cls="mb-3",
            ),
            Button(
                Span("Verify", cls="sync-label"),
                Span("Verifying...", cls="loading loading-spinner loading-xs htmx-indicator"),
                type="submit",
                cls="btn btn-primary btn-sm w-full",
            ),
            hx_post="/accounts/wizard/telegram-2fa",
            hx_target="#wizard-content",
            hx_swap="innerHTML",
            hx_indicator="find .btn-primary",
            hx_disabled_elt="find .btn-primary",
        ),
    )


def _step_indicator(current: int):
    """Visual step indicator: 1=Select, 2=Connect, 3=Finalize."""
    steps = ["Select", "Connect", "Finalize"]
    items = []
    for i, label in enumerate(steps, 1):
        if i < current:
            cls = "text-primary opacity-80"
            dot = "bg-primary"
        elif i == current:
            cls = "text-primary font-semibold"
            dot = "bg-primary"
        else:
            cls = "opacity-30"
            dot = "bg-base-content/30"
        items.append(Div(
            Span(cls=f"w-2 h-2 rounded-full {dot} inline-block"),
            Span(label, cls="text-[11px]"),
            cls=f"flex items-center gap-1.5 {cls}",
        ))
        if i < len(steps):
            items.append(Div(cls="w-6 h-px bg-base-content/10"))

    return Div(*items, cls="flex items-center justify-center gap-2 mb-5")
