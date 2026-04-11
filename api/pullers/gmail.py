import json
import logging
import imaplib
import email
import email.message
import email.utils
import email.header
from datetime import datetime, timezone

from imapclient import IMAPClient

from api.pullers import imap_uid_sync as ius
from api.pullers.base import BasePuller, PullResult
from api.content import process_content

log = logging.getLogger(__name__)

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993

DEFAULT_SYNC_DAYS = 365
ALL_MAIL = "[Gmail]/All Mail"


def _imap_connect(email_addr: str, app_password: str) -> imaplib.IMAP4_SSL:
    """Connect and authenticate to Gmail via IMAP with App Password."""
    conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
    conn.login(email_addr, app_password)
    return conn


def _decode_header(raw: str) -> str:
    """Decode RFC 2047 encoded header value."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _parse_email_address(raw: str) -> str:
    """Extract display-friendly name from 'Name <email>' format."""
    decoded = _decode_header(raw)
    name, addr = email.utils.parseaddr(decoded)
    return name if name else addr


def _get_body(msg: email.message.Message) -> tuple[str, str]:
    """Extract plain text and HTML body from an email message.
    Returns (body_plain, body_html).
    """
    plain = ""
    html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain" and not plain:
                plain = text
            elif content_type == "text/html" and not html:
                html = text
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html = text
                else:
                    plain = text
        except Exception:
            pass

    return plain, html


def _get_attachments(msg: email.message.Message) -> list[dict]:
    """Extract attachment metadata (no binary content) from an email message."""
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in disposition or "inline" in disposition:
            filename = part.get_filename()
            if filename:
                attachments.append({
                    "filename": _decode_header(filename),
                    "content_type": part.get_content_type(),
                    "size": len(part.get_payload(decode=True) or b""),
                })
    return attachments


def _parse_date(msg: email.message.Message) -> str | None:
    """Parse the Date header into an ISO timestamp."""
    date_raw = msg.get("Date", "")
    if not date_raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except Exception:
        return None


def _gmail_fetch_uid_batch_imapclient(
    client: IMAPClient,
    uids: list[int],
    my_email: str,
    normalize_fn,
) -> list[dict]:
    if not uids:
        return []
    client.select_folder(ALL_MAIL, readonly=True)
    resp = client.fetch(uids, ["RFC822", "X-GM-THRID"])
    items: list[dict] = []
    for uid, data in resp.items():
        try:
            raw = data.get(b"RFC822")
            if not raw:
                continue
            thr = data.get(b"X-GM-THRID")
            if thr is None:
                gmail_thread_id = None
            elif isinstance(thr, bytes):
                gmail_thread_id = thr.decode("ascii", errors="replace").strip()
            else:
                gmail_thread_id = str(thr).strip()
            msg = email.message_from_bytes(raw)
            item = normalize_fn(msg, my_email, gmail_thread_id or None)
            if item:
                items.append(item)
        except Exception as e:
            log.warning("Gmail IMAP: failed to process UID %s: %s", uid, e)
    return items


class GmailPuller(BasePuller):

    def _connect(self) -> imaplib.IMAP4_SSL:
        email_addr = self.credentials.get("email", "")
        app_password = self.credentials.get("app_password", "")
        if not email_addr or not app_password:
            raise ValueError("Gmail email and App Password not configured. Please connect via the dashboard.")
        return _imap_connect(email_addr, app_password)

    def test_connection(self) -> bool:
        conn = self._connect()
        try:
            status, data = conn.select("INBOX", readonly=True)
            if status != "OK":
                raise ValueError(f"Failed to select INBOX: {status}")
            count = int(data[0])
            log.info("Gmail IMAP connected: %s (%d messages in INBOX)",
                     self.credentials.get("email", ""), count)
            return True
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def get_stats(self) -> dict:
        """Get mailbox statistics: folder list with counts, total, date range."""
        conn = self._connect()
        try:
            # List all folders
            status, folder_data = conn.list()
            if status != "OK":
                raise ValueError(f"Failed to list folders: {status}")

            folders = []
            for entry in folder_data:
                # Parse: (\\flags) "/" "folder name"
                if isinstance(entry, bytes):
                    entry = entry.decode("utf-8", errors="replace")
                parts = entry.rsplit('"', 2)
                if len(parts) >= 2:
                    folder_name = parts[-1].strip().strip('"')
                else:
                    folder_name = entry.split()[-1].strip('"')

                # Try to get message count
                try:
                    st, dt = conn.select(folder_name, readonly=True)
                    if st == "OK":
                        count = int(dt[0])
                        if count > 0:
                            folders.append({"name": folder_name, "count": count})
                except Exception:
                    pass

            # Get All Mail stats
            total = 0
            oldest_date = None
            newest_date = None

            st, dt = conn.select("[Gmail]/All Mail", readonly=True)
            if st == "OK":
                total = int(dt[0])

                if total > 0:
                    # Get oldest message date
                    try:
                        st2, dt2 = conn.fetch("1", "(BODY.PEEK[HEADER.FIELDS (DATE)])")
                        if st2 == "OK" and dt2 and dt2[0]:
                            raw = dt2[0][1] if isinstance(dt2[0], tuple) else dt2[0]
                            if isinstance(raw, bytes):
                                raw = raw.decode("utf-8", errors="replace")
                            date_line = raw.replace("Date:", "").strip()
                            try:
                                parsed = email.utils.parsedate_to_datetime(date_line)
                                oldest_date = parsed.isoformat()
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Get newest message date
                    try:
                        st2, dt2 = conn.fetch(str(total), "(BODY.PEEK[HEADER.FIELDS (DATE)])")
                        if st2 == "OK" and dt2 and dt2[0]:
                            raw = dt2[0][1] if isinstance(dt2[0], tuple) else dt2[0]
                            if isinstance(raw, bytes):
                                raw = raw.decode("utf-8", errors="replace")
                            date_line = raw.replace("Date:", "").strip()
                            try:
                                parsed = email.utils.parsedate_to_datetime(date_line)
                                newest_date = parsed.isoformat()
                            except Exception:
                                pass
                    except Exception:
                        pass

            return {
                "email": self.credentials.get("email", ""),
                "total_messages": total,
                "oldest_date": oldest_date,
                "newest_date": newest_date,
                "folders": sorted(folders, key=lambda f: f["count"], reverse=True),
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def pull(self, cursor: str | None = None, since: str | None = None, *, fresh_start: bool = False) -> PullResult:
        """UID-based batch pull (IMAPClient) with shared cursor format (v4).

        Oldest mail first (lowest UID in each search window). ``fresh_start`` is set
        by the service manager when this account has no stored items yet, widening
        the initial lookback (capped at ~20 years in ``imap_uid_sync``).

        Returns ``complete=False`` when more batches remain; the manager commits
        ``new_cursor`` after each batch.
        """
        my_email = self.credentials.get("email", "").lower()
        batch_size = ius.imap_batch_size(self.config)
        max_total = ius.max_messages_cap(self.config)

        state = ius.parse_single_mailbox_cursor(
            cursor,
            config=self.config,
            fresh_start=fresh_start,
            default_days_when_not_fresh=DEFAULT_SYNC_DAYS,
        )
        if since:
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            state = ius.new_single_mailbox_backfill_state(cutoff=cutoff, uidvalidity=None)

        if not state.get("imap_since") and state.get("since_iso"):
            try:
                dt = datetime.fromisoformat(str(state["since_iso"]).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                state["imap_since"] = ius.imap_since_from_datetime(dt)
            except ValueError:
                state["imap_since"] = ius.imap_since_from_datetime(datetime.now(timezone.utc))

        email_addr = self.credentials.get("email", "")
        app_password = self.credentials.get("app_password", "")
        client = ius.gmail_imap_client(email_addr, app_password)
        try:
            validity = ius.folder_uidvalidity(client, ALL_MAIL)
            if validity is not None:
                stored = state.get("uidvalidity")
                if stored is not None and int(stored) != validity:
                    log.warning(
                        "Gmail IMAP: UIDVALIDITY changed (%s → %s); resetting UID cursor",
                        stored,
                        validity,
                    )
                    state["last_uid"] = 0
                state["uidvalidity"] = validity

            imap_since = state.get("imap_since") or ius.imap_since_from_datetime(
                datetime.fromisoformat(str(state["since_iso"]).replace("Z", "+00:00"))
            )
            last_uid = int(state.get("last_uid") or 0)
            fetched_total = int(state.get("fetched_total") or 0)
            phase = state.get("phase") or "backfill"

            if max_total is not None and fetched_total >= max_total:
                log.info("Gmail IMAP: reached max_messages cap (%s), finishing sync run", max_total)
                now = datetime.now(timezone.utc)
                live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
                return PullResult(
                    items=[],
                    new_cursor=ius.dump_cursor(live),
                    items_new=0,
                    complete=True,
                )

            uids = ius.uid_search_uids_ascending(client, ALL_MAIL, imap_since, last_uid)
            if not uids:
                if phase == "backfill":
                    now = datetime.now(timezone.utc)
                    live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
                    log.info("Gmail IMAP: backfill complete for SINCE %s → switching to live cursor", imap_since)
                    return PullResult(
                        items=[],
                        new_cursor=ius.dump_cursor(live),
                        items_new=0,
                        complete=True,
                    )
                now = datetime.now(timezone.utc)
                live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
                log.info("Gmail IMAP: live batch empty (since %s)", imap_since)
                return PullResult(
                    items=[],
                    new_cursor=ius.dump_cursor(live),
                    items_new=0,
                    complete=True,
                )

            remaining_cap = None
            if max_total is not None:
                remaining_cap = max_total - fetched_total
                if remaining_cap <= 0:
                    now = datetime.now(timezone.utc)
                    live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
                    return PullResult(items=[], new_cursor=ius.dump_cursor(live), items_new=0, complete=True)

            take = min(batch_size, len(uids))
            if remaining_cap is not None:
                take = min(take, remaining_cap)
            batch_uids = uids[:take]

            log.info(
                "Gmail IMAP: %s phase batch uid %s..%s (%d/%d in window, fetched_total=%d, oldest-first)",
                phase,
                batch_uids[0],
                batch_uids[-1],
                take,
                len(uids),
                fetched_total,
            )

            items = _gmail_fetch_uid_batch_imapclient(client, batch_uids, my_email, self.normalize)
            new_last_uid = max(batch_uids)
            fetched_total += len(batch_uids)

            more_in_window = len(uids) > take
            hit_cap = max_total is not None and fetched_total >= max_total

            if hit_cap and more_in_window:
                state["phase"] = phase
                state["imap_since"] = imap_since
                state.setdefault("since_iso", datetime.now(timezone.utc).isoformat())
                state["last_uid"] = new_last_uid
                state["uidvalidity"] = validity
                state["fetched_total"] = fetched_total
                log.info(
                    "Gmail IMAP: max_messages cap reached (%s); saving cursor for next sync",
                    max_total,
                )
                return PullResult(
                    items=items,
                    new_cursor=ius.dump_cursor(state),
                    items_new=len(items),
                    complete=True,
                )

            if more_in_window and not hit_cap:
                state["phase"] = phase
                state["imap_since"] = imap_since
                state.setdefault("since_iso", datetime.now(timezone.utc).isoformat())
                state["last_uid"] = new_last_uid
                state["uidvalidity"] = validity
                state["fetched_total"] = fetched_total
                return PullResult(
                    items=items,
                    new_cursor=ius.dump_cursor(state),
                    items_new=len(items),
                    complete=False,
                )

            if phase == "backfill" and not more_in_window:
                now = datetime.now(timezone.utc)
                live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
                log.info(
                    "Gmail IMAP: backfill finished (%d msgs this batch, %d UIDs counted); live cursor set",
                    len(items),
                    fetched_total,
                )
                return PullResult(
                    items=items,
                    new_cursor=ius.dump_cursor(live),
                    items_new=len(items),
                    complete=True,
                )

            now = datetime.now(timezone.utc)
            live = ius.new_single_mailbox_live_state(when=now, uidvalidity=validity)
            log.info("Gmail IMAP: live window drained (%d items this batch)", len(items))
            return PullResult(
                items=items,
                new_cursor=ius.dump_cursor(live),
                items_new=len(items),
                complete=True,
            )
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def normalize(self, raw_item, my_email: str = "", gmail_thread_id: str | None = None) -> dict | None:
        msg = raw_item

        subject = _decode_header(msg.get("Subject", ""))
        from_raw = msg.get("From", "")
        to_raw = msg.get("To", "")
        cc_raw = msg.get("Cc", "")
        message_id = msg.get("Message-ID", "")

        sender = _parse_email_address(from_raw)
        _, sender_addr = email.utils.parseaddr(_decode_header(from_raw))
        sender_is_me = 1 if sender_addr.lower() == my_email else 0

        # Parse recipients
        recipients = []
        for field in [to_raw, cc_raw]:
            if not field:
                continue
            decoded = _decode_header(field)
            for addr_str in decoded.split(","):
                addr_str = addr_str.strip()
                if addr_str:
                    recipients.append(_parse_email_address(addr_str))

        # Parse date
        source_ts = _parse_date(msg)

        # Decode raw body parts
        body_plain, body_html = _get_body(msg)

        # Skip empty messages
        if not body_plain and not body_html and not subject:
            return None

        # Content pipeline: convert to markdown with filtering and truncation
        body_markdown = process_content(body_plain=body_plain, body_html=body_html)

        # Attachments metadata only (no binary content)
        attachments = _get_attachments(msg)

        # Conversation display name: strip Re:/Fwd: prefixes from subject
        conv = subject
        for prefix in ("Re: ", "RE: ", "Fwd: ", "FWD: ", "Fw: "):
            while conv.startswith(prefix):
                conv = conv[len(prefix):]

        # Thread ID for global grouping
        thread_id = f"gmail:{gmail_thread_id}" if gmail_thread_id else None

        # Use Message-ID as unique source_id
        source_id = message_id.strip("<>") if message_id else f"gmail_{hash(msg.as_bytes())}"

        metadata = {
            "message_id": message_id,
            "gmail_thread_id": gmail_thread_id,
            "in_reply_to": msg.get("In-Reply-To", ""),
            "references": msg.get("References", ""),
        }

        return {
            "item_type": "email",
            "source_id": f"gmail_{source_id}",
            "thread_id": thread_id,
            "conversation": conv or "No Subject",
            "sender": sender,
            "sender_is_me": sender_is_me,
            "recipients": json.dumps(recipients),
            "subject": subject,
            "body_plain": body_markdown,
            "body_html": body_html,
            "attachments": json.dumps(attachments),
            "labels": "[]",
            "metadata": json.dumps(metadata),
            "source_ts": source_ts,
        }
