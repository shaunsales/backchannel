import asyncio
import logging
from fasthtml.common import *
from app.components.layout import page
from app.components import alerts
from app.components.auth_forms import (
    notion_auth_form, telegram_auth_form, telegram_code_form, telegram_2fa_form,
    gmail_auth_form,
)
from app.services import manager
from app.pullers.telegram import _get_client, _run_async

log = logging.getLogger(__name__)

# Auth form functions keyed by service_type
AUTH_FORMS = {
    "notion": notion_auth_form,
    "telegram": telegram_auth_form,
    "gmail": gmail_auth_form,
}

# Per-service_id auth state for multi-step flows (e.g. Telegram)
_auth_state = {}


def _get_service_type(service_id: str) -> str | None:
    """Look up service_type for a given service_id."""
    from app.db import get_db
    row = get_db().execute(
        "SELECT service_type FROM services WHERE id = ?", (service_id,)
    ).fetchone()
    return row["service_type"] if row else None


def register(rt):

    @rt("/auth/{service_id}")
    def get(service_id: str):
        svc = manager.status(service_id)
        if svc is None:
            return page(alerts.error(f"Unknown service: {service_id}"), title="Error")

        svc_type = svc.get("service_type") or service_id
        form_fn = AUTH_FORMS.get(svc_type)
        if form_fn:
            form = form_fn(svc)
        else:
            form = Div(
                P(f"Auth flow for {svc['display_name']} ({svc['auth_type']}) is not yet implemented.",
                  cls="text-sm opacity-70"),
                P("This will be built in a later phase.", cls="text-sm opacity-50 mt-2"),
            )

        return page(
            H2(f"Connect {svc['display_name']}", cls="text-lg font-semibold mb-4"),
            Div(
                Div(form, cls="card-body p-5"),
                cls="card bg-base-200/50 border border-base-content/5",
            ),
            title=f"Connect {svc['display_name']}",
        )

    # ── Generic auth routes (dispatched by service_type) ─────────

    @rt("/auth/{service_id}/connect")
    def post(service_id: str, token: str = "", email: str = "", app_password: str = "", **kwargs):
        """Generic connect — handles API key (Notion) and IMAP (Gmail) services."""
        svc_type = _get_service_type(service_id)
        area_id = f"{service_id}-auth-area"
        form_fn = AUTH_FORMS.get(svc_type)

        # Build credentials based on service type
        if svc_type == "gmail":
            credentials = {"email": email.strip(), "app_password": app_password.strip()}
        else:
            credentials = {"token": token}

        try:
            manager.connect(service_id, credentials)
            ok, msg = manager.test(service_id)
            if not ok:
                manager.disconnect(service_id)
                svc = manager.status(service_id)
                return Div(alerts.error(f"Connection failed: {msg}"),
                           form_fn(svc) if form_fn else None, id=area_id)
            svc = manager.status(service_id)
            return form_fn(svc) if form_fn else alerts.success("Connected")
        except Exception as e:
            manager.disconnect(service_id)
            svc = manager.status(service_id)
            return Div(alerts.error(str(e)),
                       form_fn(svc) if form_fn else None, id=area_id)

    @rt("/auth/{service_id}/test")
    def post(service_id: str):
        try:
            ok, msg = manager.test(service_id)
            if ok:
                return alerts.success("Connection successful")
            return alerts.error(f"Test failed: {msg}")
        except Exception as e:
            return alerts.error(str(e))

    @rt("/auth/{service_id}/disconnect")
    def post(service_id: str):
        svc_type = _get_service_type(service_id)
        try:
            # Service-type specific cleanup
            if svc_type == "telegram":
                import os
                from pathlib import Path
                from app.config import TELEGRAM_SESSION_PATH
                sessions_dir = Path(TELEGRAM_SESSION_PATH).parent
                for ext in ("", ".session"):
                    path = str(sessions_dir / service_id) + ext
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass

            manager.disconnect(service_id)
            svc = manager.status(service_id)
            form_fn = AUTH_FORMS.get(svc_type)
            if form_fn:
                return form_fn(svc)
            return alerts.success(f"Disconnected {service_id}")
        except Exception as e:
            return alerts.error(str(e))

    # ── Telegram-specific multi-step auth ────────────────────────

    @rt("/auth/{service_id}/phone")
    def post(service_id: str, phone: str, api_id: str = "", api_hash: str = ""):
        from telethon.errors import FloodWaitError
        svc_type = _get_service_type(service_id)
        if svc_type != "telegram":
            return alerts.error(f"Phone auth not supported for {svc_type}")

        area_id = f"{service_id}-auth-area"
        phone = phone.strip()
        api_id = api_id.strip()
        api_hash = api_hash.strip()
        if not phone or not api_id or not api_hash:
            return Div(alerts.error("API ID, API Hash, and Phone number are all required."),
                       telegram_auth_form(manager.status(service_id)), id=area_id)

        try:
            api_id_int = int(api_id)
        except ValueError:
            return Div(alerts.error("API ID must be a number."),
                       telegram_auth_form(manager.status(service_id)), id=area_id)

        try:
            async def _send_code():
                client = _get_client(api_id=api_id_int, api_hash=api_hash, service_id=service_id)
                await client.connect()
                result = await client.send_code_request(phone)
                return client, result

            client, result = _run_async(_send_code())
            _auth_state[service_id] = {
                "phone": phone,
                "api_id": api_id_int,
                "api_hash": api_hash,
                "phone_code_hash": result.phone_code_hash,
            }
            log.info("Telegram [%s]: code sent to %s", service_id, phone)
            return telegram_code_form(phone, service_id=service_id)

        except FloodWaitError as e:
            return Div(alerts.error(f"Rate limited by Telegram. Please wait {e.seconds}s and try again."),
                       telegram_auth_form(manager.status(service_id)), id=area_id)
        except Exception as e:
            log.error("Telegram [%s] phone auth failed: %s", service_id, e)
            return Div(alerts.error(f"Failed to send code: {e}"),
                       telegram_auth_form(manager.status(service_id)), id=area_id)

    @rt("/auth/{service_id}/code")
    def post(service_id: str, phone: str, code: str):
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
        svc_type = _get_service_type(service_id)
        if svc_type != "telegram":
            return alerts.error(f"Code auth not supported for {svc_type}")

        area_id = f"{service_id}-auth-area"
        code = code.strip()
        state = _auth_state.get(service_id, {})
        phone_code_hash = state.get("phone_code_hash")
        api_id = state.get("api_id", 0)
        api_hash = state.get("api_hash", "")

        if not phone_code_hash:
            return Div(alerts.error("Session expired. Please start over."),
                       telegram_auth_form(manager.status(service_id)), id=area_id)

        try:
            async def _verify_code():
                client = _get_client(api_id=api_id, api_hash=api_hash, service_id=service_id)
                await client.connect()
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                me = await client.get_me()
                await client.disconnect()
                return me

            me = _run_async(_verify_code())
            manager.connect(service_id, {
                "phone": phone, "api_id": api_id, "api_hash": api_hash,
                "user_id": me.id, "username": me.username or "",
            })
            _auth_state.pop(service_id, None)
            log.info("Telegram [%s]: authenticated as %s (id=%d)", service_id, me.username or phone, me.id)
            return telegram_auth_form(manager.status(service_id))

        except SessionPasswordNeededError:
            log.info("Telegram [%s]: 2FA required for %s", service_id, phone)
            return telegram_2fa_form(phone, service_id=service_id)

        except PhoneCodeInvalidError:
            return Div(alerts.error("Invalid code. Please try again."),
                       telegram_code_form(phone, service_id=service_id), id=area_id)

        except Exception as e:
            log.error("Telegram [%s] code verification failed: %s", service_id, e)
            return Div(alerts.error(f"Verification failed: {e}"),
                       telegram_code_form(phone, service_id=service_id), id=area_id)

    @rt("/auth/{service_id}/password")
    def post(service_id: str, phone: str, password: str):
        svc_type = _get_service_type(service_id)
        if svc_type != "telegram":
            return alerts.error(f"Password auth not supported for {svc_type}")

        area_id = f"{service_id}-auth-area"
        state = _auth_state.get(service_id, {})
        api_id = state.get("api_id", 0)
        api_hash = state.get("api_hash", "")
        try:
            async def _verify_2fa():
                client = _get_client(api_id=api_id, api_hash=api_hash, service_id=service_id)
                await client.connect()
                await client.sign_in(password=password)
                me = await client.get_me()
                await client.disconnect()
                return me

            me = _run_async(_verify_2fa())
            manager.connect(service_id, {
                "phone": phone, "api_id": api_id, "api_hash": api_hash,
                "user_id": me.id, "username": me.username or "",
            })
            _auth_state.pop(service_id, None)
            log.info("Telegram [%s]: 2FA complete, authenticated as %s", service_id, me.username or phone)
            return telegram_auth_form(manager.status(service_id))

        except Exception as e:
            log.error("Telegram [%s] 2FA failed: %s", service_id, e)
            return Div(alerts.error(f"2FA failed: {e}"),
                       telegram_2fa_form(phone, service_id=service_id), id=area_id)

