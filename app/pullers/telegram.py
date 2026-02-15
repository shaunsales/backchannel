"""
Telegram puller — syncs messages from all dialogs via Telethon.

Auth flow is multi-step (phone → code → optional 2FA password) and
handled separately in routes/auth.py. This puller assumes a valid
session file already exists.
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import (
    User, Chat, Channel, ChannelForbidden, ChatForbidden,
    MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage,
)

from app.pullers.base import BasePuller, PullResult
from app.config import TELEGRAM_SESSION_PATH

log = logging.getLogger(__name__)

DEFAULT_SYNC_DAYS = 365
MAX_MESSAGES_PER_DIALOG = 200
PREVIEW_SAMPLE_MESSAGES = 5  # messages to peek at per dialog during preview


def _run_async(coro):
    """Run an async coroutine from sync code, safe even inside an existing event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        # Cancel any remaining Telethon background tasks before closing
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()


def _get_client(api_id: int = 0, api_hash: str = "", session_path: str | None = None) -> TelegramClient:
    """Create a Telethon client instance. Reads credentials from args or DB."""
    path = session_path or TELEGRAM_SESSION_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not api_id or not api_hash:
        # Try loading from DB
        import json
        from app.db import get_db
        db = get_db()
        row = db.execute("SELECT credentials FROM services WHERE id = 'telegram'").fetchone()
        if row:
            creds = json.loads(row["credentials"] or "{}")
            api_id = int(creds.get("api_id", 0))
            api_hash = creds.get("api_hash", "")
    if not api_id or not api_hash:
        raise ValueError("Telegram API ID and Hash not configured. Please connect via the dashboard.")
    return TelegramClient(path, api_id, api_hash)


def _entity_name(entity) -> str:
    """Extract a display name from a Telethon entity."""
    if isinstance(entity, User):
        parts = [entity.first_name or "", entity.last_name or ""]
        return " ".join(p for p in parts if p) or f"User#{entity.id}"
    if isinstance(entity, (Chat, Channel)):
        return entity.title or f"Chat#{entity.id}"
    return str(getattr(entity, "id", "unknown"))


def _media_summary(media) -> str | None:
    """Return a short description of message media."""
    if media is None:
        return None
    if isinstance(media, MessageMediaPhoto):
        return "[Photo]"
    if isinstance(media, MessageMediaDocument):
        doc = media.document
        if doc:
            for attr in doc.attributes:
                name = getattr(attr, "file_name", None)
                if name:
                    return f"[File: {name}]"
            mime = getattr(doc, "mime_type", "")
            if "audio" in mime:
                return "[Audio]"
            if "video" in mime:
                return "[Video]"
            if "sticker" in mime or "webp" in mime:
                return "[Sticker]"
            return "[Document]"
        return "[Document]"
    if isinstance(media, MessageMediaWebPage):
        wp = media.webpage
        if wp and hasattr(wp, "url"):
            return f"[Link: {wp.url}]"
        return "[Link]"
    return f"[Media: {type(media).__name__}]"


def _dialog_type(entity) -> str:
    """Return a human-readable type for a dialog entity."""
    if isinstance(entity, User):
        return "bot" if entity.bot else "private"
    if isinstance(entity, Channel):
        return "channel" if entity.broadcast else "group"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, (ChannelForbidden, ChatForbidden)):
        return "forbidden"
    return "unknown"


def _should_skip_dialog(dialog, entity, since_dt) -> str | None:
    """Return a skip reason string, or None if dialog should be synced."""
    # Skip forbidden/deleted chats
    if isinstance(entity, (ChannelForbidden, ChatForbidden)):
        return "forbidden/deleted"

    # Skip archived dialogs
    if dialog.archived:
        return "archived"

    # Skip bots
    if isinstance(entity, User) and entity.bot:
        return "bot"

    # Skip broadcast channels (keep supergroups)
    if isinstance(entity, Channel) and entity.broadcast:
        return "channel"

    # Skip inactive dialogs (no messages within cutoff)
    if dialog.date:
        last_msg_dt = dialog.date
        if last_msg_dt.tzinfo is None:
            last_msg_dt = last_msg_dt.replace(tzinfo=timezone.utc)
        if last_msg_dt < since_dt:
            return f"inactive since {last_msg_dt.strftime('%Y-%m-%d')}"

    return None


class TelegramPuller(BasePuller):

    def _client(self):
        return _get_client(
            api_id=int(self.credentials.get("api_id", 0)),
            api_hash=self.credentials.get("api_hash", ""),
        )

    def test_connection(self) -> bool:
        async def _test():
            client = self._client()
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise ValueError("Session expired or not authorized. Please re-authenticate.")
                me = await client.get_me()
                log.info("Telegram connected as: %s (id=%d)", _entity_name(me), me.id)
                return True
            finally:
                await client.disconnect()

        return _run_async(_test())

    def preview_sync(self) -> list[dict]:
        """Dry-run: list dialogs that would be synced with current filters."""
        return _run_async(self._preview_async())

    async def _preview_async(self) -> list[dict]:
        client = self._client()
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session expired. Please re-authenticate.")

            me = await client.get_me()
            my_id = me.id
            since_dt = datetime.now(timezone.utc) - timedelta(days=DEFAULT_SYNC_DAYS)
            results = []
            dialog_num = 0

            log.info("Preview: scanning dialogs (cutoff=%s)...", since_dt.strftime("%Y-%m-%d"))

            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                dialog_name = _entity_name(entity)
                skip_reason = _should_skip_dialog(dialog, entity, since_dt)

                if skip_reason:
                    log.info("  Skip: %s (%s)", dialog_name, skip_reason)
                    results.append({"name": dialog_name, "type": _dialog_type(entity),
                                    "status": "skip", "reason": skip_reason, "messages": 0})
                    continue

                # Check if I ever replied (peek at a small sample)
                i_replied = False
                sample_count = 0
                async for msg in client.iter_messages(dialog.id, limit=PREVIEW_SAMPLE_MESSAGES * 10):
                    if msg.sender_id == my_id:
                        i_replied = True
                        break
                    sample_count += 1

                if not i_replied:
                    log.info("  Skip: %s (never replied)", dialog_name)
                    results.append({"name": dialog_name, "type": _dialog_type(entity),
                                    "status": "skip", "reason": "never replied", "messages": 0})
                    continue

                # Count messages in window (capped for speed)
                msg_count = 0
                async for msg in client.iter_messages(
                    dialog.id, offset_date=since_dt, limit=MAX_MESSAGES_PER_DIALOG
                ):
                    if msg.date.replace(tzinfo=timezone.utc) < since_dt:
                        break
                    msg_count += 1

                dialog_num += 1
                last_active = dialog.date.strftime("%Y-%m-%d") if dialog.date else "?"
                log.info("  [%d] %s: ~%d messages (last: %s)",
                         dialog_num, dialog_name, msg_count, last_active)
                results.append({"name": dialog_name, "type": _dialog_type(entity),
                                "status": "sync", "reason": "", "messages": msg_count,
                                "last_active": last_active})

            to_sync = [r for r in results if r["status"] == "sync"]
            total_msgs = sum(r["messages"] for r in to_sync)
            log.info("Preview complete: %d dialogs to sync, ~%d messages total, %d skipped",
                     len(to_sync), total_msgs, len(results) - len(to_sync))
            return results
        finally:
            await client.disconnect()

    def pull(self, cursor: str | None = None, since: str | None = None) -> PullResult:
        return _run_async(self._pull_async(cursor, since))

    async def _pull_async(self, cursor: str | None, since: str | None) -> PullResult:
        client = self._client()
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Session expired. Please re-authenticate.")

            me = await client.get_me()
            my_id = me.id

            # Determine time window
            if since:
                since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            else:
                days = self.config.get("sync_days", DEFAULT_SYNC_DAYS)
                since_dt = datetime.now(timezone.utc) - timedelta(days=days)

            # Parse cursor: JSON dict of {dialog_id: last_message_id}
            cursor_map = {}
            if cursor:
                try:
                    cursor_map = json.loads(cursor)
                except (json.JSONDecodeError, TypeError):
                    pass

            items = []
            new_cursor_map = dict(cursor_map)
            total_dialogs = 0
            skipped = 0
            total_messages = 0

            log.info("Starting Telegram sync (since=%s, cursor_dialogs=%d)",
                     since_dt.strftime("%Y-%m-%d"), len(cursor_map))

            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                dialog_id = str(dialog.id)
                dialog_name = _entity_name(entity)

                # Apply filters
                skip_reason = _should_skip_dialog(dialog, entity, since_dt)
                if skip_reason:
                    log.info("Skipped: %s (%s)", dialog_name, skip_reason)
                    skipped += 1
                    continue

                # For new dialogs (no cursor), check that I replied at least once
                if dialog_id not in cursor_map:
                    i_replied = False
                    async for msg in client.iter_messages(dialog.id, limit=50):
                        if msg.sender_id == my_id:
                            i_replied = True
                            break
                    if not i_replied:
                        log.info("Skipped: %s (never replied)", dialog_name)
                        skipped += 1
                        continue

                total_dialogs += 1
                min_id = int(cursor_map.get(dialog_id, 0))
                max_id_seen = min_id
                msg_count = 0

                log.info("[%d] Fetching: %s (min_id=%d)", total_dialogs, dialog_name, min_id)

                async for message in client.iter_messages(
                    dialog.id,
                    min_id=min_id,
                    offset_date=since_dt if not min_id else None,
                    limit=MAX_MESSAGES_PER_DIALOG,
                ):
                    if message.date.replace(tzinfo=timezone.utc) < since_dt:
                        break

                    item = self.normalize(message, my_id, dialog_name)
                    if item:
                        items.append(item)
                        msg_count += 1
                        total_messages += 1

                    if message.id > max_id_seen:
                        max_id_seen = message.id

                if max_id_seen > min_id:
                    new_cursor_map[dialog_id] = max_id_seen

                if msg_count > 0:
                    log.info("[%d] %s: %d messages", total_dialogs, dialog_name, msg_count)

            log.info("Telegram sync complete: %d dialogs, %d messages, %d skipped",
                     total_dialogs, total_messages, skipped)

            return PullResult(
                items=items,
                new_cursor=json.dumps(new_cursor_map),
                items_new=total_messages,
            )
        finally:
            await client.disconnect()

    def normalize(self, raw_item, my_id: int = 0, dialog_name: str = "") -> dict | None:
        message = raw_item
        if not message.text and not message.media:
            return None

        sender_id = message.sender_id or 0
        sender_name = ""
        if message.sender:
            sender_name = _entity_name(message.sender)

        body = message.text or ""
        media_desc = _media_summary(message.media)
        if media_desc:
            body = f"{media_desc}\n{body}" if body else media_desc

        if not body.strip():
            return None

        msg_dt = message.date
        if msg_dt and msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=timezone.utc)

        metadata = {
            "message_id": message.id,
            "chat_id": message.chat_id,
            "reply_to": message.reply_to_msg_id if message.reply_to else None,
            "forward": bool(message.forward),
            "views": message.views,
            "media_type": type(message.media).__name__ if message.media else None,
        }

        return {
            "item_type": "message",
            "source_id": f"tg_{message.chat_id}_{message.id}",
            "conversation": dialog_name,
            "sender": sender_name,
            "sender_is_me": 1 if sender_id == my_id else 0,
            "recipients": "[]",
            "subject": "",
            "body_plain": body,
            "body_html": "",
            "attachments": "[]",
            "labels": "[]",
            "metadata": json.dumps(metadata),
            "source_ts": msg_dt.isoformat() if msg_dt else None,
        }
