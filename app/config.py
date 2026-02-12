import os
from pathlib import Path
from dotenv import load_dotenv

# Project root is one level up from app/
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# --- General -----------------------------------------------------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/backchannel.db")
DATABASE_PATH = str(BASE_DIR / DATABASE_PATH) if not os.path.isabs(DATABASE_PATH) else DATABASE_PATH

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8787"))
USER_EMAIL = os.getenv("USER_EMAIL", "")

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

# --- ProtonMail --------------------------------------------------------------
PROTONMAIL_BRIDGE_HOST = os.getenv("PROTONMAIL_BRIDGE_HOST", "127.0.0.1")
PROTONMAIL_BRIDGE_PORT = int(os.getenv("PROTONMAIL_BRIDGE_PORT", "1143"))
PROTONMAIL_BRIDGE_EMAIL = os.getenv("PROTONMAIL_BRIDGE_EMAIL", "")
PROTONMAIL_BRIDGE_PASSWORD = os.getenv("PROTONMAIL_BRIDGE_PASSWORD", "")

# --- WhatsApp ----------------------------------------------------------------
WHATSAPP_BRIDGE_BINARY = os.getenv("WHATSAPP_BRIDGE_BINARY", "whatsapp-bridge/whatsapp-bridge")
WHATSAPP_BRIDGE_BINARY = str(BASE_DIR / WHATSAPP_BRIDGE_BINARY) if not os.path.isabs(WHATSAPP_BRIDGE_BINARY) else WHATSAPP_BRIDGE_BINARY

WHATSAPP_BRIDGE_DB = os.getenv("WHATSAPP_BRIDGE_DB", "whatsapp-bridge/store/messages.db")
WHATSAPP_BRIDGE_DB = str(BASE_DIR / WHATSAPP_BRIDGE_DB) if not os.path.isabs(WHATSAPP_BRIDGE_DB) else WHATSAPP_BRIDGE_DB
