import asyncio
import logging
from fasthtml.common import *
from app.components.layout import page
from app.components import alerts
from app.components.auth_forms import (
    notion_auth_form, telegram_auth_form, telegram_code_form, telegram_2fa_form,
)
from app.services import manager
from app.pullers.telegram import _get_client, _run_async

log = logging.getLogger(__name__)

AUTH_FORMS = {
    "notion": notion_auth_form,
    "telegram": telegram_auth_form,
}

# Temporary state for Telegram multi-step auth
_tg_auth_state = {}


def register(rt):

    @rt("/auth/{service_id}")
    def get(service_id: str):
        svc = manager.status(service_id)
        if svc is None:
            return page(alerts.error(f"Unknown service: {service_id}"), title="Error")

        form_fn = AUTH_FORMS.get(service_id)
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

    @rt("/auth/notion/connect")
    def post(token: str):
        try:
            manager.connect("notion", {"token": token})
            ok, msg = manager.test("notion")
            if not ok:
                manager.disconnect("notion")
                return Div(
                    alerts.error(f"Connection failed: {msg}"),
                    notion_auth_form(manager.status("notion")),
                    id="notion-auth-area",
                )
            svc = manager.status("notion")
            return notion_auth_form(svc)
        except Exception as e:
            manager.disconnect("notion")
            return Div(
                alerts.error(str(e)),
                notion_auth_form(manager.status("notion")),
                id="notion-auth-area",
            )

    @rt("/auth/notion/test")
    def post():
        try:
            ok, msg = manager.test("notion")
            if ok:
                return alerts.success("Connection successful")
            return alerts.error(f"Test failed: {msg}")
        except Exception as e:
            return alerts.error(str(e))

    @rt("/auth/notion/disconnect")
    def post():
        manager.disconnect("notion")
        svc = manager.status("notion")
        return notion_auth_form(svc)

    @rt("/auth/{service_id}/disconnect")
    def post(service_id: str):
        try:
            manager.disconnect(service_id)
            return alerts.success(f"Disconnected {service_id}")
        except Exception as e:
            return alerts.error(str(e))

    # ── Telegram Auth ────────────────────────────────────────────

    @rt("/auth/telegram/phone")
    def post(phone: str):
        from telethon.errors import FloodWaitError
        phone = phone.strip()
        if not phone:
            return Div(alerts.error("Phone number is required"), telegram_auth_form(manager.status("telegram")), id="telegram-auth-area")

        try:
            async def _send_code():
                client = _get_client()
                await client.connect()
                result = await client.send_code_request(phone)
                return client, result

            client, result = _run_async(_send_code())
            _tg_auth_state["phone"] = phone
            _tg_auth_state["phone_code_hash"] = result.phone_code_hash
            log.info("Telegram: code sent to %s", phone)
            return telegram_code_form(phone)

        except FloodWaitError as e:
            return Div(alerts.error(f"Rate limited by Telegram. Please wait {e.seconds}s and try again."),
                       telegram_auth_form(manager.status("telegram")), id="telegram-auth-area")
        except Exception as e:
            log.error("Telegram phone auth failed: %s", e)
            return Div(alerts.error(f"Failed to send code: {e}"),
                       telegram_auth_form(manager.status("telegram")), id="telegram-auth-area")

    @rt("/auth/telegram/code")
    def post(phone: str, code: str):
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
        code = code.strip()
        phone_code_hash = _tg_auth_state.get("phone_code_hash")

        if not phone_code_hash:
            return Div(alerts.error("Session expired. Please start over."),
                       telegram_auth_form(manager.status("telegram")), id="telegram-auth-area")

        try:
            async def _verify_code():
                client = _get_client()
                await client.connect()
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                me = await client.get_me()
                await client.disconnect()
                return me

            me = _run_async(_verify_code())
            # Success — save credentials and mark connected
            manager.connect("telegram", {"phone": phone, "user_id": me.id, "username": me.username or ""})
            _tg_auth_state.clear()
            log.info("Telegram: authenticated as %s (id=%d)", me.username or phone, me.id)
            return telegram_auth_form(manager.status("telegram"))

        except SessionPasswordNeededError:
            log.info("Telegram: 2FA required for %s", phone)
            return telegram_2fa_form(phone)

        except PhoneCodeInvalidError:
            return Div(alerts.error("Invalid code. Please try again."),
                       telegram_code_form(phone), id="telegram-auth-area")

        except Exception as e:
            log.error("Telegram code verification failed: %s", e)
            return Div(alerts.error(f"Verification failed: {e}"),
                       telegram_code_form(phone), id="telegram-auth-area")

    @rt("/auth/telegram/password")
    def post(phone: str, password: str):
        try:
            async def _verify_2fa():
                client = _get_client()
                await client.connect()
                await client.sign_in(password=password)
                me = await client.get_me()
                await client.disconnect()
                return me

            me = _run_async(_verify_2fa())
            manager.connect("telegram", {"phone": phone, "user_id": me.id, "username": me.username or ""})
            _tg_auth_state.clear()
            log.info("Telegram: 2FA complete, authenticated as %s", me.username or phone)
            return telegram_auth_form(manager.status("telegram"))

        except Exception as e:
            log.error("Telegram 2FA failed: %s", e)
            return Div(alerts.error(f"2FA failed: {e}"),
                       telegram_2fa_form(phone), id="telegram-auth-area")

    @rt("/auth/telegram/disconnect")
    def post():
        import os
        from app.config import TELEGRAM_SESSION_PATH
        manager.disconnect("telegram")
        # Remove session file so next auth starts fresh
        for ext in ("", ".session"):
            path = TELEGRAM_SESSION_PATH + ext
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        return telegram_auth_form(manager.status("telegram"))
