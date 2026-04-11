"""
Shared UID + SINCE incremental IMAP helpers for IMAP-based email pullers.

Oldest-first: UID lists are sorted ascending (lowest UID first), which usually
matches oldest mail in a stable mailbox. Batched pulls commit cursors in the
service manager between ``PullResult(complete=False)`` iterations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from imapclient import IMAPClient

log = logging.getLogger(__name__)

# Hard cap on how far back initial / fresh import will look (configurable below that).
MAX_SYNC_LOOKBACK_DAYS = 20 * 365

DEFAULT_IMAP_BATCH_SIZE = 100
DEFAULT_MAX_MESSAGES_TOTAL = 500_000

# Unified cursor version for single-mailbox and per-folder IMAP entries.
IMAP_UID_CURSOR_VERSION = 4


def imap_since_from_datetime(dt: datetime) -> str:
    """IMAP SINCE date string (DD-Mon-YYYY) in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d-%b-%Y")


def effective_backfill_cutoff(
    config: dict,
    *,
    fresh_start: bool,
    default_days_when_not_fresh: int,
) -> datetime:
    """
    ``fresh_start`` (no items in DB yet): use sync_days from config, capped to
    MAX_SYNC_LOOKBACK_DAYS (~20 years). When not fresh, default_days_when_not_fresh
    applies if sync_days is omitted.
    """
    if fresh_start:
        raw = int(config.get("sync_days", MAX_SYNC_LOOKBACK_DAYS))
        days = min(max(raw, 1), MAX_SYNC_LOOKBACK_DAYS)
    else:
        raw = int(config.get("sync_days", default_days_when_not_fresh))
        days = max(raw, 1)
    return datetime.now(timezone.utc) - timedelta(days=days)


def imap_batch_size(config: dict) -> int:
    b = int(config.get("imap_batch_size", DEFAULT_IMAP_BATCH_SIZE))
    return max(1, min(b, 500))


def max_messages_cap(config: dict, *, default_when_missing: int = DEFAULT_MAX_MESSAGES_TOTAL) -> int | None:
    """Total message *slots* (UIDs processed) cap for a long backfill; 0 = unlimited."""
    if "max_messages" in config:
        v = int(config["max_messages"])
        if v == 0:
            return None
        return max(v, 1)
    return default_when_missing


def folder_uidvalidity(client: IMAPClient, folder: str) -> int | None:
    try:
        st = client.folder_status(folder, [b"UIDVALIDITY"])
        raw_v = st.get(b"UIDVALIDITY")
        return int(raw_v) if raw_v is not None else None
    except Exception:
        return None


def uid_search_uids_ascending(
    client: IMAPClient,
    folder: str,
    imap_since_str: str,
    last_uid: int,
) -> list[int]:
    """
    Return UIDs matching SINCE (and UID strictly after last_uid when last_uid > 0),
    sorted ascending (oldest / lowest UID first).
    """
    client.select_folder(folder, readonly=True)
    if last_uid <= 0:
        crit = f"SINCE {imap_since_str}"
    else:
        crit = f"(SINCE {imap_since_str}) (UID {last_uid + 1}:*)"
    uids = client.search(crit)
    out = sorted({int(u) for u in uids if u is not None})
    return out


def gmail_imap_client(email: str, app_password: str) -> IMAPClient:
    c = IMAPClient("imap.gmail.com", ssl=True)
    c.login(email, app_password)
    return c


def new_single_mailbox_backfill_state(
    *,
    cutoff: datetime,
    uidvalidity: int | None,
) -> dict:
    imap_since = imap_since_from_datetime(cutoff)
    return {
        "v": IMAP_UID_CURSOR_VERSION,
        "phase": "backfill",
        "since_iso": cutoff.astimezone(timezone.utc).isoformat(),
        "imap_since": imap_since,
        "last_uid": 0,
        "uidvalidity": uidvalidity,
        "fetched_total": 0,
    }


def new_single_mailbox_live_state(
    *,
    when: datetime,
    uidvalidity: int | None,
) -> dict:
    imap_since = imap_since_from_datetime(when)
    return {
        "v": IMAP_UID_CURSOR_VERSION,
        "phase": "live",
        "since_iso": when.astimezone(timezone.utc).isoformat(),
        "imap_since": imap_since,
        "last_uid": 0,
        "uidvalidity": uidvalidity,
        "fetched_total": 0,
    }


def folder_slice_backfill(cutoff: datetime, uidvalidity: int | None) -> dict:
    """Per-folder progress (nested under multi-folder cursor) — no ``v`` key."""
    st = new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=uidvalidity)
    st.pop("v", None)
    return st


def folder_slice_live(when: datetime, uidvalidity: int | None) -> dict:
    st = new_single_mailbox_live_state(when=when, uidvalidity=uidvalidity)
    st.pop("v", None)
    return st


def parse_single_mailbox_cursor(
    raw: str | None,
    *,
    config: dict,
    fresh_start: bool,
    default_days_when_not_fresh: int,
) -> dict:
    """Parse v4 JSON, migrate v3 Gmail cursor, or legacy ISO → live."""
    import json

    if not raw or not str(raw).strip():
        cutoff = effective_backfill_cutoff(
            config, fresh_start=fresh_start, default_days_when_not_fresh=default_days_when_not_fresh
        )
        return new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=None)

    s = str(raw).strip()
    if s.startswith("{"):
        try:
            d = json.loads(s)
        except json.JSONDecodeError:
            cutoff = effective_backfill_cutoff(
                config, fresh_start=fresh_start, default_days_when_not_fresh=default_days_when_not_fresh
            )
            return new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=None)
        if isinstance(d, dict):
            if d.get("v") in (IMAP_UID_CURSOR_VERSION, 3) and "phase" in d:
                if d.get("v") == 3:
                    d = dict(d)
                    d["v"] = IMAP_UID_CURSOR_VERSION
                return d
        cutoff = effective_backfill_cutoff(
            config, fresh_start=fresh_start, default_days_when_not_fresh=default_days_when_not_fresh
        )
        return new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=None)

    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        cutoff = effective_backfill_cutoff(
            config, fresh_start=fresh_start, default_days_when_not_fresh=default_days_when_not_fresh
        )
        return new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=None)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return new_single_mailbox_live_state(when=dt, uidvalidity=None)


def dump_cursor(state: dict) -> str:
    import json

    return json.dumps(state, separators=(",", ":"))
