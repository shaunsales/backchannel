"""
In-memory log broadcast for the real-time log panel.

A custom logging.Handler captures log records and pushes them to all
connected SSE clients via an asyncio-compatible deque.
"""
import logging
import time
import json
from collections import deque
from threading import Lock

MAX_BUFFER = 200  # keep last N log lines in memory

_buffer: deque[dict] = deque(maxlen=MAX_BUFFER)
_lock = Lock()
_subscribers: list = []  # list of callback functions
_installed = False


class BroadcastHandler(logging.Handler):
    """Logging handler that captures records for the log panel."""

    def emit(self, record):
        entry = {
            "ts": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "msg": self.format(record),
        }
        with _lock:
            _buffer.append(entry)
            for cb in _subscribers:
                try:
                    cb(entry)
                except Exception:
                    pass


def get_buffer() -> list[dict]:
    """Return a copy of the current log buffer."""
    with _lock:
        return list(_buffer)


def subscribe(callback):
    """Register a callback that receives each new log entry dict."""
    with _lock:
        _subscribers.append(callback)


def unsubscribe(callback):
    """Remove a previously registered callback."""
    with _lock:
        try:
            _subscribers.remove(callback)
        except ValueError:
            pass


def install(level=logging.INFO):
    """Install the broadcast handler on the root logger (once only)."""
    global _installed
    if _installed:
        return
    _installed = True
    handler = BroadcastHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
