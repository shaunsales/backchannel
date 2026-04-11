import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv

# Project root is one level up from app/
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _stable_port(project_root: str, role: str, lo: int, hi: int) -> int:
    """Deterministic port from checkout path (must stay in sync with web/vite.config.ts)."""
    digest = hashlib.sha256(f"{role}:{project_root}".encode()).digest()
    n = int.from_bytes(digest[:4], "big")
    return lo + (n % (hi - lo + 1))


def _env_port(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    return int(raw.strip())


# Role strings and ranges must match web/vite.config.ts
_API_ROLE = "backchannel-api"
_API_RANGE = (20000, 29999)
_WEB_ROLE = "backchannel-web"
_WEB_RANGE = (31000, 39999)

# --- General -----------------------------------------------------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/backchannel.db")
DATABASE_PATH = str(BASE_DIR / DATABASE_PATH) if not os.path.isabs(DATABASE_PATH) else DATABASE_PATH

_p_api = _env_port("DASHBOARD_PORT")
DASHBOARD_PORT = _p_api if _p_api is not None else _stable_port(str(BASE_DIR), _API_ROLE, *_API_RANGE)

_p_web = _env_port("WEB_DEV_PORT")
WEB_DEV_PORT = _p_web if _p_web is not None else _stable_port(str(BASE_DIR), _WEB_ROLE, *_WEB_RANGE)

USER_EMAIL = os.getenv("USER_EMAIL", "")

# --- Read API (automation / OpenClaw) ---------------------------------------
# When unset, POST /api/context/build returns 404 (no accidental exposure).
READ_API_KEY = (os.getenv("READ_API_KEY") or "").strip() or None

# --- Embeddings --------------------------------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# --- Notion ------------------------------------------------------------------
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")

# --- Gmail -------------------------------------------------------------------
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "data/tokens/credentials.json")
GMAIL_CREDENTIALS_PATH = str(BASE_DIR / GMAIL_CREDENTIALS_PATH) if not os.path.isabs(GMAIL_CREDENTIALS_PATH) else GMAIL_CREDENTIALS_PATH

GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "data/tokens/token.json")
GMAIL_TOKEN_PATH = str(BASE_DIR / GMAIL_TOKEN_PATH) if not os.path.isabs(GMAIL_TOKEN_PATH) else GMAIL_TOKEN_PATH

# --- Telegram ----------------------------------------------------------------
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SESSION_PATH = os.getenv("TELEGRAM_SESSION_PATH", "data/sessions/backchannel.session")
TELEGRAM_SESSION_PATH = str(BASE_DIR / TELEGRAM_SESSION_PATH) if not os.path.isabs(TELEGRAM_SESSION_PATH) else TELEGRAM_SESSION_PATH

# --- WhatsApp ----------------------------------------------------------------
WHATSAPP_BRIDGE_BINARY = os.getenv("WHATSAPP_BRIDGE_BINARY", "whatsapp-bridge/whatsapp-bridge")
WHATSAPP_BRIDGE_BINARY = str(BASE_DIR / WHATSAPP_BRIDGE_BINARY) if not os.path.isabs(WHATSAPP_BRIDGE_BINARY) else WHATSAPP_BRIDGE_BINARY

WHATSAPP_BRIDGE_DB = os.getenv("WHATSAPP_BRIDGE_DB", "whatsapp-bridge/store/messages.db")
WHATSAPP_BRIDGE_DB = str(BASE_DIR / WHATSAPP_BRIDGE_DB) if not os.path.isabs(WHATSAPP_BRIDGE_DB) else WHATSAPP_BRIDGE_DB
