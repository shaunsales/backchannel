# Backchannel

Local-first daily data sync app that pulls messages, emails, notes, and pages
from multiple services into a unified SQLite database. Includes a React web
dashboard for account management, browsing, and monitoring.

## Current Status

- **Notion** — fully integrated (API key auth, page sync, markdown conversion,
  document versioning, content-hash dedup, incremental sync, deletion detection)
- **Telegram** — fully integrated (multi-step auth, message sync with dialog
  filtering, rate limiting, incremental sync by cursor)
- **Gmail, ProtonMail, WhatsApp** — planned

## Quick Start

### 1. Backend (Python)

```bash
cd backchannel

# Create virtual environment and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Create data directories
mkdir -p data/sessions data/tokens data/logs

# Start the API server
uvicorn api.server:app --port 8787 --reload
```

### 2. Frontend (React)

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.
The frontend proxies `/api/*` requests to the backend on port 8787.

## Pages

| Page | Description |
|---|---|
| **Dashboard** | Stats overview, connected accounts, recent sync activity |
| **Accounts** | Manage connected services, add new accounts via modal dialog |
| **Account Detail** | Rename, sync, disconnect, clear data, view sync history |
| **Documents** | Browse and search synced Notion pages with markdown preview |
| **Document Detail** | Full rendered markdown view of a document |
| **Messages** | Conversation-grouped message threads with search |
| **History** | Full sync run log across all services |
| **Logs** | Real-time log viewer with SSE streaming |

## Connecting Services

### Notion

1. Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations) and copy the token.
2. In Notion, share pages with the integration.
3. In the dashboard, go to **Accounts** → **+ Add Account** → **Notion** → paste the token.
4. Open the account and click **Sync** to pull pages.

### Telegram

1. Create an app at [my.telegram.org/apps](https://my.telegram.org/apps) and note the API ID and API Hash.
2. In the dashboard, go to **Accounts** → **+ Add Account** → **Telegram** → enter API ID, API Hash, and phone number.
3. Complete the verification code and optional 2FA steps.
4. Click **Sync** to pull messages.

## Daily Sync

Run all connected services headless:

```bash
source .venv/bin/activate
python scripts/daily_sync.py
```

Automate with `launchd` (macOS) or `cron`.

## API Endpoints

All return JSON. Backend runs on port 8787.

| Endpoint | Description |
|---|---|
| `GET /api/dashboard` | Stats, accounts, recent sync runs |
| `GET /api/services` | List connected accounts |
| `GET /api/services/{id}` | Account detail with sync history |
| `POST /api/services/{id}/sync` | Trigger a sync |
| `GET /api/documents` | List documents (`?q=` for search) |
| `GET /api/documents/{id}` | Full document with markdown body |
| `GET /api/conversations` | Conversation threads (`?q=` for search) |
| `GET /api/conversations/{name}` | Messages in a thread |
| `GET /api/messages` | Flat message list (`?q=`, `?service=`) |
| `GET /api/history` | Sync run history |
| `GET /api/logs` | In-memory log buffer |
| `GET /api/logs/stream` | SSE real-time log stream |

## Project Structure

```
api/
  server.py            FastAPI REST API (port 8787)
  config.py            Environment variables
  db.py                SQLite schema and init
  logstream.py         Real-time log broadcasting
  pullers/             Data pull engines (base, notion, telegram, gmail, ...)
  services/            Service manager (connect, sync, disconnect)
web/
  src/
    App.tsx            React Router + React Query setup
    components/        Shared UI (sidebar, service icons, error boundary)
    pages/             All page components
    lib/api.ts         Typed API client
scripts/
  daily_sync.py        Headless sync entry point
data/
  backchannel.db       SQLite database (gitignored)
```

## Tech Stack

### Frontend
- **Vite 8** + **React 19** + **TypeScript**
- **Tailwind CSS v4** + **shadcn/ui** (dark mode)
- **React Query** for server state
- **React Router** for SPA navigation
- **react-markdown** for document rendering

### Backend
- **FastAPI** + **Uvicorn** (REST API)
- **SQLite** with FTS5 full-text search
- **SSE** for real-time log streaming

### Service Integrations
- **Notion**: `notion-client` Python SDK
- **Telegram**: `telethon` (multi-step auth, rate limiting)
- **Gmail**: `google-api-python-client` (planned)

## Environment Variables

See `.env.example` for all settings. Service credentials are configured via the
web UI and stored in the database — not in `.env`.

| Variable | Description |
|---|---|
| `DASHBOARD_PORT` | API port (default: `8787`) |
| `DATABASE_PATH` | SQLite file path (default: `data/backchannel.db`) |
| `USER_EMAIL` | Your email (for sender_is_me detection) |
