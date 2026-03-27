import json
import logging
import imaplib
import email
import email.message
import email.utils
import email.header
from datetime import datetime, timezone, timedelta

from api.pullers.base import BasePuller, PullResult
from api.content import process_content

log = logging.getLogger(__name__)

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993

DEFAULT_SYNC_DAYS = 365
DEFAULT_MAX_MESSAGES = 100


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

    def pull(self, cursor: str | None = None, since: str | None = None) -> PullResult:
        my_email = self.credentials.get("email", "").lower()
        max_messages = self.config.get("max_messages", DEFAULT_MAX_MESSAGES)
        conn = self._connect()

        try:
            conn.select("[Gmail]/All Mail", readonly=True)

            # Determine date cutoff
            if since:
                cutoff = datetime.fromisoformat(since)
            elif cursor:
                cutoff = datetime.fromisoformat(cursor)
            else:
                days = self.config.get("sync_days", DEFAULT_SYNC_DAYS)
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # IMAP date search (format: DD-Mon-YYYY)
            imap_date = cutoff.strftime("%d-%b-%Y")
            log.info("Gmail IMAP sync starting (since=%s, max=%d)", imap_date, max_messages)

            status, data = conn.search(None, f'(SINCE {imap_date})')
            if status != "OK":
                raise ValueError(f"IMAP search failed: {status}")

            msg_nums = data[0].split()
            log.info("Gmail IMAP: %d messages since %s", len(msg_nums), imap_date)

            # Cap to configured max (take most recent)
            if len(msg_nums) > max_messages:
                log.info("Gmail IMAP: capping to %d most recent messages", max_messages)
                msg_nums = msg_nums[-max_messages:]

            items = []
            for i, num in enumerate(msg_nums):
                try:
                    # Fetch RFC822 body + Gmail thread ID via X-GM-THRID extension
                    status, msg_data = conn.fetch(num, "(X-GM-THRID RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue

                    # Parse X-GM-THRID from the response
                    gmail_thread_id = None
                    raw_email = None
                    for part in msg_data:
                        if isinstance(part, tuple):
                            header = part[0]
                            if isinstance(header, bytes):
                                header = header.decode("utf-8", errors="replace")
                            # Extract X-GM-THRID value from IMAP response
                            if "X-GM-THRID" in header:
                                import re
                                thrid_match = re.search(r'X-GM-THRID\s+(\d+)', header)
                                if thrid_match:
                                    gmail_thread_id = thrid_match.group(1)
                            raw_email = part[1]

                    if raw_email is None:
                        continue

                    msg = email.message_from_bytes(raw_email)
                    item = self.normalize(msg, my_email, gmail_thread_id)
                    if item:
                        items.append(item)

                    if (i + 1) % 50 == 0:
                        log.info("Gmail IMAP: processed %d/%d messages", i + 1, len(msg_nums))
                except Exception as e:
                    log.warning("Gmail IMAP: failed to process message %s: %s", num, e)

            # Cursor: ISO timestamp of now (next sync will use SINCE this date)
            new_cursor = datetime.now(timezone.utc).isoformat()

            log.info("Gmail IMAP sync complete: %d items from %d messages",
                     len(items), len(msg_nums))

            return PullResult(
                items=items,
                new_cursor=new_cursor,
                items_new=len(items),
            )
        finally:
            try:
                conn.logout()
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
