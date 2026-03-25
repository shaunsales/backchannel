"""
Account management routes:
  /accounts            — list all accounts
  /accounts/{id}       — account detail page
  /accounts/{id}/clear — clear synced data
  /accounts/wizard/*   — add-account wizard steps
"""
import json
import logging
from datetime import datetime
from fasthtml.common import *
from app.db import get_db
from app.components.layout import page, SERVICE_ICONS
from app.components.service_card import STATUS_DOT, STATUS_BADGE
from app.components.auth_forms import (
    notion_auth_form, telegram_auth_form, gmail_auth_form, _sync_buttons,
)
from app.components.account_wizard import (
    wizard_modal, wizard_step1, wizard_step2,
    wizard_step3_success, wizard_step3_failure,
    wizard_telegram_code, wizard_telegram_2fa, SERVICE_TYPES,
)
from app.components import alerts
from app.services import manager

log = logging.getLogger(__name__)

AUTH_FORMS = {
    "notion": notion_auth_form,
    "telegram": telegram_auth_form,
    "gmail": gmail_auth_form,
}

# In-memory state for multi-step Telegram auth in wizard
_wizard_auth_state = {}


def _humanize_time(ts_str: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        delta = datetime.utcnow() - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''} ago"
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    except (ValueError, TypeError):
        return ts_str


def _runs_table(runs):
    from app.components.sync_table import STATUS_COLORS
    rows = []
    for r in runs:
        badge_cls = STATUS_COLORS.get(r["status"], "badge-ghost")
        duration = f"{r['duration_sec']:.1f}s" if r["duration_sec"] else "—"
        time_display = _humanize_time(r["started_at"]) if r["started_at"] else "—"
        rows.append(Tr(
            Td(r["run_type"], cls="text-xs"),
            Td(Span(r["status"], cls=f"badge badge-sm {badge_cls}")),
            Td(str(r["items_fetched"] or 0)),
            Td(duration, cls="font-mono text-xs"),
            Td(time_display, cls="text-xs", title=r["started_at"] or ""),
        ))
    return Table(
        Thead(Tr(Th("Type"), Th("Status"), Th("Items"), Th("Duration"), Th("Time"))),
        Tbody(*rows),
        cls="table table-sm",
    )


def register(rt):

    # ── Accounts list ─────────────────────────────────────────────

    @rt("/accounts")
    def get():
        db = get_db()
        # Only connected accounts, most recently synced first
        services = db.execute(
            "SELECT * FROM services WHERE status = 'connected' "
            "ORDER BY last_sync_at DESC NULLS LAST, display_name"
        ).fetchall()

        rows = []
        for svc in services:
            s = dict(svc)
            sid = s["id"]
            svc_type = s.get("service_type") or sid
            icon_svg = SERVICE_ICONS.get(svc_type, "")

            item_count = db.execute(
                "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (sid,)
            ).fetchone()["cnt"]
            doc_count = db.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (sid,)
            ).fetchone()["cnt"]
            stored = item_count + doc_count
            last_sync = _humanize_time(s["last_sync_at"]) if s["last_sync_at"] else "Never"

            rows.append(
                A(
                    Div(
                        Div(
                            Div(
                                NotStr(icon_svg.replace('opacity-60', 'opacity-80')),
                                cls="w-8 h-8 rounded-lg bg-base-300 flex items-center justify-center shrink-0",
                            ),
                            Div(
                                Span(s["display_name"], cls="text-sm font-semibold leading-tight"),
                                Span(svc_type.title(), cls="text-[11px] opacity-40"),
                                cls="flex flex-col",
                            ),
                            cls="flex items-center gap-3 flex-1",
                        ),
                        Div(
                            Div(
                                Span("Stored", cls="text-[10px] opacity-40"),
                                Span(f"{stored:,}", cls="text-sm font-mono font-semibold"),
                                cls="flex flex-col items-end",
                            ),
                            Div(
                                Span("Last sync", cls="text-[10px] opacity-40"),
                                Span(last_sync, cls="text-[11px] opacity-60"),
                                cls="flex flex-col items-end",
                            ),
                            cls="flex gap-6",
                        ),
                        cls="flex items-center justify-between p-4",
                    ),
                    href=f"/accounts/{sid}",
                    cls="card bg-base-200/50 border border-base-content/5 hover:border-base-content/10 "
                        "transition-colors block",
                )
            )

        add_btn = Button(
            NotStr('<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>'),
            "Add Account",
            onclick="document.getElementById('wizard-modal').classList.remove('hidden'); "
                    "htmx.ajax('GET', '/accounts/wizard/step1', '#wizard-content');",
            cls="btn btn-primary btn-sm gap-1.5",
        )

        return page(
            Div(
                H2("Accounts", cls="text-lg font-semibold"),
                add_btn,
                cls="flex items-center justify-between mb-4",
            ),
            Div(*rows, cls="flex flex-col gap-2") if rows else
            Div(
                P("No connected accounts yet. Add one to get started.", cls="text-sm opacity-50 mb-3"),
            ),
            wizard_modal(),
            title="Accounts",
        )

    # ── Account detail ────────────────────────────────────────────

    @rt("/accounts/{service_id}")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return page(alerts.error(f"Unknown account: {service_id}"), title="Error")

        s = dict(service)
        sid = s["id"]
        svc_type = s.get("service_type") or sid
        status = s["status"]
        icon_svg = SERVICE_ICONS.get(svc_type, "")
        dot_cls = STATUS_DOT.get(status, "bg-base-content/20")
        _, status_label = STATUS_BADGE.get(status, ("badge-ghost", status))

        item_count = db.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (sid,)
        ).fetchone()["cnt"]
        doc_count = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (sid,)
        ).fetchone()["cnt"]
        stored = item_count + doc_count
        last_sync = _humanize_time(s["last_sync_at"]) if s["last_sync_at"] else "Never"

        recent_runs = db.execute(
            "SELECT * FROM sync_runs WHERE service_id = ? ORDER BY started_at DESC LIMIT 10",
            (sid,),
        ).fetchall()

        # Connection card with auth form
        form_fn = AUTH_FORMS.get(svc_type)
        if form_fn:
            connection_card = Div(
                Div(
                    H3("Connection", cls="text-sm font-semibold mb-3"),
                    form_fn(s),
                    cls="card-body p-5",
                ),
                cls="card bg-base-200/50 border border-base-content/5 mb-4",
            )
        else:
            area_id = f"{sid}-auth-area"
            result_id = f"{sid}-auth-result"
            connection_card = Div(
                Div(
                    H3("Connection", cls="text-sm font-semibold mb-2"),
                    Div(
                        Span("Status: ", cls="opacity-50"),
                        Span(status_label, cls="font-medium"),
                        cls="text-sm mb-1",
                    ),
                    Div(
                        Span("Auth type: ", cls="opacity-50"),
                        Span(s["auth_type"], cls="font-mono text-xs"),
                        cls="text-sm mb-3",
                    ),
                    A("Configure", href=f"/auth/{sid}",
                      cls="btn btn-outline btn-sm") if status == "disconnected" else
                    Button("Disconnect", hx_post=f"/auth/{sid}/disconnect",
                           hx_target="#account-detail", hx_swap="outerHTML",
                           cls="btn btn-outline btn-error btn-sm"),
                    cls="card-body p-5",
                ),
                cls="card bg-base-200/50 border border-base-content/5 mb-4",
            )

        # Stats row
        stats_row = Div(
            Div(
                Span("Stored", cls="text-[11px] opacity-40"),
                Span(f"{stored:,}", cls="text-lg font-mono font-semibold"),
                cls="flex flex-col",
            ),
            Div(
                Span("Last sync", cls="text-[11px] opacity-40"),
                Span(last_sync, cls="text-xs opacity-70"),
                cls="flex flex-col",
            ),
            cls="flex gap-8 mb-4",
        )

        # Danger zone: clear data + remove
        is_extra = sid != svc_type
        danger_items = []
        if status == "connected" and stored > 0:
            danger_items.append(
                Button(
                    "Clear Synced Data",
                    hx_post=f"/accounts/{sid}/clear",
                    hx_target="#account-detail",
                    hx_swap="outerHTML",
                    hx_confirm=f"Delete all {stored:,} synced items for {s['display_name']}? This cannot be undone.",
                    cls="btn btn-ghost btn-sm text-warning border border-warning/20",
                )
            )
        if is_extra:
            danger_items.append(
                Button(
                    "Remove Account",
                    hx_post=f"/accounts/{sid}/remove",
                    hx_target="#account-detail",
                    hx_swap="innerHTML",
                    hx_confirm=f"Remove {s['display_name']} and all its data? This cannot be undone.",
                    cls="btn btn-ghost btn-sm text-error border border-error/20",
                )
            )

        danger_zone = Div(
            Div(cls="border-t border-base-content/5 my-4"),
            Div(*danger_items, cls="flex gap-2"),
        ) if danger_items else None

        # Editable name
        name_display = Div(
            H2(
                s["display_name"],
                cls="text-lg font-semibold leading-tight cursor-pointer hover:text-primary transition-colors",
                title="Click to rename",
                hx_get=f"/accounts/{sid}/rename-form",
                hx_target=f"#name-{sid}",
                hx_swap="innerHTML",
            ),
            Div(
                Span(cls=f"w-2 h-2 rounded-full {dot_cls} inline-block"),
                Span(status_label, cls="text-sm opacity-60"),
                cls="flex items-center gap-2",
            ),
            cls="flex flex-col",
            id=f"name-{sid}",
        )

        detail = Div(
            # Header
            Div(
                Div(
                    NotStr(icon_svg.replace('opacity-60', 'opacity-80')),
                    cls="w-10 h-10 rounded-lg bg-base-300 flex items-center justify-center shrink-0",
                ),
                name_display,
                cls="flex items-center gap-3 mb-5",
            ),

            stats_row,
            connection_card,

            Div(
                H3("Sync History", cls="text-sm font-semibold mb-3"),
                _runs_table(recent_runs) if recent_runs else
                P("No sync runs yet.", cls="text-sm opacity-50"),
                hx_get=f"/accounts/{sid}/history",
                hx_trigger="refresh",
                hx_swap="innerHTML",
                cls="mb-4",
                **{"data-sync-history": "true"},
            ),

            danger_zone,
            id="account-detail",
        )

        return page(detail, title=s["display_name"])

    # ── Rename account ────────────────────────────────────────────

    @rt("/accounts/{service_id}/rename-form")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return alerts.error("Unknown account")
        return Div(
            Form(
                Input(
                    type="text", name="display_name",
                    value=service["display_name"],
                    cls="input input-bordered input-sm text-lg font-semibold w-full",
                    autofocus=True,
                ),
                Div(
                    Button("Save", type="submit", cls="btn btn-primary btn-sm min-h-0 h-8"),
                    Button(
                        "Cancel", type="button",
                        hx_get=f"/accounts/{service_id}/name-display",
                        hx_target=f"#name-{service_id}",
                        hx_swap="innerHTML",
                        cls="btn btn-ghost btn-sm min-h-0 h-8",
                    ),
                    cls="flex items-center gap-2 mt-2",
                ),
                hx_post=f"/accounts/{service_id}/rename",
                hx_target=f"#name-{service_id}",
                hx_swap="innerHTML",
            ),
        )

    @rt("/accounts/{service_id}/name-display")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return Span("Unknown", cls="text-error")
        s = dict(service)
        status = s["status"]
        dot_cls = STATUS_DOT.get(status, "bg-base-content/20")
        _, status_label = STATUS_BADGE.get(status, ("badge-ghost", status))
        return Div(
            H2(
                s["display_name"],
                cls="text-lg font-semibold leading-tight cursor-pointer hover:text-primary transition-colors",
                title="Click to rename",
                hx_get=f"/accounts/{service_id}/rename-form",
                hx_target=f"#name-{service_id}",
                hx_swap="innerHTML",
            ),
            Div(
                Span(cls=f"w-2 h-2 rounded-full {dot_cls} inline-block"),
                Span(status_label, cls="text-sm opacity-60"),
                cls="flex items-center gap-2",
            ),
        )

    @rt("/accounts/{service_id}/rename")
    def post(service_id: str, display_name: str):
        display_name = display_name.strip()
        if not display_name:
            return alerts.error("Name cannot be empty.")
        try:
            manager.rename_service(service_id, display_name)
        except Exception as e:
            return alerts.error(str(e))
        # Return updated name display
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        s = dict(service)
        status = s["status"]
        dot_cls = STATUS_DOT.get(status, "bg-base-content/20")
        _, status_label = STATUS_BADGE.get(status, ("badge-ghost", status))
        return Div(
            H2(
                s["display_name"],
                cls="text-lg font-semibold leading-tight cursor-pointer hover:text-primary transition-colors",
                title="Click to rename",
                hx_get=f"/accounts/{service_id}/rename-form",
                hx_target=f"#name-{service_id}",
                hx_swap="innerHTML",
            ),
            Div(
                Span(cls=f"w-2 h-2 rounded-full {dot_cls} inline-block"),
                Span(status_label, cls="text-sm opacity-60"),
                cls="flex items-center gap-2",
            ),
        )

    # ── Sync history refresh ──────────────────────────────────────

    @rt("/accounts/{service_id}/history")
    def get(service_id: str):
        db = get_db()
        recent_runs = db.execute(
            "SELECT * FROM sync_runs WHERE service_id = ? ORDER BY started_at DESC LIMIT 10",
            (service_id,),
        ).fetchall()
        return Div(
            H3("Sync History", cls="text-sm font-semibold mb-3"),
            _runs_table(recent_runs) if recent_runs else
            P("No sync runs yet.", cls="text-sm opacity-50"),
        )

    # ── Clear data ────────────────────────────────────────────────

    @rt("/accounts/{service_id}/clear")
    def post(service_id: str):
        try:
            manager.clear_data(service_id)
            return RedirectResponse(f"/accounts/{service_id}", status_code=303)
        except Exception as e:
            return alerts.error(str(e))

    # ── Remove account ────────────────────────────────────────────

    @rt("/accounts/{service_id}/remove")
    def post(service_id: str):
        try:
            manager.remove_service_instance(service_id)
            return Div(
                alerts.success(f"Removed {service_id}"),
                Script("setTimeout(function(){ window.location='/accounts'; }, 500);"),
            )
        except Exception as e:
            return alerts.error(str(e))

    # ── Wizard steps ──────────────────────────────────────────────

    @rt("/accounts/wizard/step1")
    def get():
        return wizard_step1()

    @rt("/accounts/wizard/step2")
    def get(service_type: str, display_name: str = ""):
        return wizard_step2(service_type, display_name)

    @rt("/accounts/wizard/connect")
    def post(service_type: str, display_name: str, token: str = "",
             email: str = "", app_password: str = "",
             api_id: str = "", api_hash: str = "", phone: str = ""):
        """Step 2 submit: create account + connect + test."""
        display_name = display_name.strip()
        if not display_name:
            return wizard_step3_failure(service_type, display_name, "Account name is required.")

        try:
            new_id = manager.add_service_instance(service_type, display_name)
        except Exception as e:
            return wizard_step3_failure(service_type, display_name, str(e))

        # Build credentials and connect based on type
        if service_type == "notion":
            credentials = {"token": token.strip()}
            if not credentials["token"]:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, "Integration token is required.")
            try:
                manager.connect(new_id, credentials)
                ok, msg = manager.test(new_id)
                if not ok:
                    manager.disconnect(new_id)
                    manager.remove_service_instance(new_id)
                    return wizard_step3_failure(service_type, display_name, msg)
                return wizard_step3_success(new_id, display_name)
            except Exception as e:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, str(e))

        elif service_type == "gmail":
            credentials = {"email": email.strip(), "app_password": app_password.strip()}
            if not credentials["email"] or not credentials["app_password"]:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, "Email and App Password are required.")
            try:
                manager.connect(new_id, credentials)
                ok, msg = manager.test(new_id)
                if not ok:
                    manager.disconnect(new_id)
                    manager.remove_service_instance(new_id)
                    return wizard_step3_failure(service_type, display_name, msg)
                return wizard_step3_success(new_id, display_name)
            except Exception as e:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, str(e))

        elif service_type == "telegram":
            api_id_s = api_id.strip()
            api_hash_s = api_hash.strip()
            phone_s = phone.strip()
            if not api_id_s or not api_hash_s or not phone_s:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, "API ID, API Hash, and Phone are all required.")
            try:
                api_id_int = int(api_id_s)
            except ValueError:
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, "API ID must be a number.")

            # Save credentials early (needed for _get_client)
            manager.connect(new_id, {
                "api_id": api_id_int,
                "api_hash": api_hash_s,
                "phone": phone_s,
            })

            # Send code
            try:
                from app.pullers.telegram import _get_client, _run_async
                import asyncio

                async def _send_code():
                    client = _get_client(api_id=api_id_int, api_hash=api_hash_s, service_id=new_id)
                    await client.connect()
                    result = await client.send_code_request(phone_s)
                    return client, result

                client, result = _run_async(_send_code())
                _wizard_auth_state[new_id] = {
                    "phone": phone_s,
                    "api_id": api_id_int,
                    "api_hash": api_hash_s,
                    "phone_code_hash": result.phone_code_hash,
                    "display_name": display_name,
                }
                log.info("Wizard: Telegram code sent for %s to %s", new_id, phone_s)
                return wizard_telegram_code(new_id, phone_s)

            except Exception as e:
                log.error("Wizard: Telegram send code failed for %s: %s", new_id, e)
                manager.disconnect(new_id)
                manager.remove_service_instance(new_id)
                return wizard_step3_failure(service_type, display_name, str(e))
        else:
            manager.remove_service_instance(new_id)
            return wizard_step3_failure(service_type, display_name, f"{service_type} setup is not yet available.")

    @rt("/accounts/wizard/telegram-code")
    def post(service_id: str, code: str):
        """Handle Telegram verification code in wizard."""
        state = _wizard_auth_state.get(service_id, {})
        if not state:
            return wizard_step3_failure("telegram", "", "Session expired. Please start over.")

        phone = state["phone"]
        api_id = state["api_id"]
        api_hash = state["api_hash"]
        phone_code_hash = state["phone_code_hash"]
        display_name = state.get("display_name", "Telegram")

        try:
            from app.pullers.telegram import _get_client, _run_async
            from telethon.errors import SessionPasswordNeededError

            async def _sign_in():
                client = _get_client(api_id=api_id, api_hash=api_hash, service_id=service_id)
                await client.connect()
                await client.sign_in(phone, code.strip(), phone_code_hash=phone_code_hash)
                me = await client.get_me()
                await client.disconnect()
                return me

            try:
                me = _run_async(_sign_in())
            except SessionPasswordNeededError:
                return wizard_telegram_2fa(service_id, phone)

            # Success — update credentials with me info
            manager.connect(service_id, {
                "api_id": api_id,
                "api_hash": api_hash,
                "phone": phone,
                "user_id": me.id,
                "username": me.username or "",
            })
            _wizard_auth_state.pop(service_id, None)
            log.info("Wizard: Telegram authenticated %s as %s", service_id, me.username or phone)
            return wizard_step3_success(service_id, display_name)

        except Exception as e:
            log.error("Wizard: Telegram code verify failed for %s: %s", service_id, e)
            return Div(
                alerts.error(f"Verification failed: {e}"),
                wizard_telegram_code(service_id, phone),
            )

    @rt("/accounts/wizard/telegram-2fa")
    def post(service_id: str, password: str):
        """Handle Telegram 2FA password in wizard."""
        state = _wizard_auth_state.get(service_id, {})
        if not state:
            return wizard_step3_failure("telegram", "", "Session expired. Please start over.")

        phone = state["phone"]
        api_id = state["api_id"]
        api_hash = state["api_hash"]
        display_name = state.get("display_name", "Telegram")

        try:
            from app.pullers.telegram import _get_client, _run_async

            async def _sign_in_2fa():
                client = _get_client(api_id=api_id, api_hash=api_hash, service_id=service_id)
                await client.connect()
                await client.sign_in(password=password.strip())
                me = await client.get_me()
                await client.disconnect()
                return me

            me = _run_async(_sign_in_2fa())
            manager.connect(service_id, {
                "api_id": api_id,
                "api_hash": api_hash,
                "phone": phone,
                "user_id": me.id,
                "username": me.username or "",
            })
            _wizard_auth_state.pop(service_id, None)
            log.info("Wizard: Telegram 2FA complete for %s as %s", service_id, me.username or phone)
            return wizard_step3_success(service_id, display_name)

        except Exception as e:
            log.error("Wizard: Telegram 2FA failed for %s: %s", service_id, e)
            return Div(
                alerts.error(f"2FA failed: {e}"),
                wizard_telegram_2fa(service_id, phone),
            )
