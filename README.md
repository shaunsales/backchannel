# Backchannel

Local-first daily data sync app that pulls messages, emails, notes, and pages
from multiple services into a unified SQLite database. Runs on a Mac Mini with
a web dashboard for auth management, monitoring, and manual sync triggers.

## Current Status

- **Notion** — fully integrated (API key auth, page sync, markdown conversion,
  document versioning, soft-delete, grid UI, search)
- **Telegram** — fully integrated (multi-step auth via Web UI, message sync
  with dialog filtering, preview sync, rate limiting, FTS5 search)
- **Messages page** — browse all synced messages with FTS5 search, service
  filter pills, conversation drill-down, thread context view
- **JSON API** — endpoints for documents, items, search, and stats
- **Dashboard** — service cards, sync history, real-time log panel, custom branding
- **Gmail, ProtonMail, WhatsApp** — planned

## Quick Start

```bash
# Clone and enter the project
cd backchannel

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Create data directories
mkdir -p data/sessions data/tokens data/logs

# Run the dashboard
python -m app.main
```

Open [http://localhost:8787](http://localhost:8787) in your browser.

## Connecting Services

### Notion

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
   and create an internal integration. Copy the token.
2. In Notion, share each top-level page you want synced with the integration.
3. In the Backchannel dashboard, click **Notion** → paste the token → **Save & Test**.
4. Click **Sync** to pull pages.

Pages are converted to markdown, versioned with SHA-256 content hashing, and
stored in SQLite. Subsequent syncs skip unchanged pages and automatically
remove pages that have been trashed in Notion.

### Telegram

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps) and create an
   app. Note the API ID and API Hash.
2. In the dashboard, click **Telegram** → enter API ID, API Hash, and phone number.
3. Enter the verification code sent to your Telegram app (and 2FA password if enabled).
4. Use **Preview Sync** to review which dialogs will be synced.
5. Click **Sync Now** to pull messages.

Dialogs are filtered automatically: bots, broadcast channels, archived chats,
inactive conversations (>1 year), and chats where you never replied are skipped.
Messages are capped at 200 per dialog. Rate limiting prevents Telegram API
flood errors.

## Daily Sync

Run all connected services headless:

```bash
python scripts/daily_sync.py
```

Or automate with `launchd` (macOS) or `cron`.

## API Endpoints

All return JSON. Useful for AI agent ingestion.

| Endpoint | Description |
|---|---|
| `GET /api/stats` | Doc/item counts, service statuses |
| `GET /api/documents` | List docs (`?q=`, `?limit=`, `?offset=`, `?service=`) |
| `GET /api/documents/{id}` | Single doc with body + version history |
| `GET /api/documents/{id}/markdown` | Raw markdown (`text/markdown`) |
| `GET /api/items` | List items (`?q=`, `?service=`, `?item_type=`) |
| `GET /api/items/{id}` | Single item |
| `GET /api/search?q=...` | Unified FTS across docs and items |

## Project Structure

```
app/
  main.py              FastHTML app entry point (port 8787)
  config.py            Environment variables
  db.py                SQLite schema and init
  logstream.py         Real-time log broadcasting (SSE)
  components/          UI components (layout, cards, alerts, forms)
  routes/              Route handlers (dashboard, docs, messages, services, sync, api, history)
  pullers/             Data pull engines (base.py, notion.py, telegram.py, ...)
  static/              Logo and favicon assets
  services/            Service manager (sync orchestration, versioning)
scripts/
  daily_sync.py        Headless sync entry point
data/
  backchannel.db       SQLite database (gitignored)
```

## Tech Stack

- **Web**: FastHTML + HTMX + Tailwind CSS + DaisyUI
- **Database**: SQLite with FTS5 full-text search
- **Notion**: `notion-client` Python SDK
- **Telegram**: `telethon` (multi-step auth, message sync, rate limiting)
- **Gmail**: `google-api-python-client` (planned)

## Environment Variables

See `.env.example` for all available settings. Service credentials (Notion
token, Telegram API keys, etc.) are configured via the Web UI and stored in
the database — not in `.env`.

| Variable | Description |
|---|---|
| `DASHBOARD_PORT` | Web UI port (default: 8787) |
| `DATABASE_PATH` | SQLite file path (default: `data/backchannel.db`) |
| `USER_EMAIL` | Your email (used for sender_is_me detection) |
