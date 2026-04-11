# Backchannel

Local-first daily data sync app that pulls messages, emails, notes, and pages
from multiple services into a unified SQLite database. Includes a React web
dashboard for account management, browsing, and monitoring.

## Current Status

- **Notion** — fully integrated (API key auth, page sync, markdown conversion,
  document versioning, content-hash dedup, incremental sync, deletion detection)
- **Telegram** — fully integrated (multi-step auth, message sync with dialog
  filtering, rate limiting, incremental sync by cursor)
- **Gmail** — fully integrated (IMAP with App Password auth, folder stats,
  thread grouping via X-GM-THRID, HTML-to-markdown content pipeline,
  incremental sync by date)
- **Vector Search** — fully integrated (sqlite-vec for database-native KNN,
  sentence-transformers for local embeddings, hybrid semantic + keyword search)
- **WhatsApp** — planned

## Quick Start

### 1. Backend (Python)

```bash
cd backchannel

# Ensure Python has SQLite extension loading support (required for sqlite-vec).
# If using pyenv, rebuild with:
LDFLAGS="-L/opt/homebrew/opt/sqlite/lib" \
CPPFLAGS="-I/opt/homebrew/opt/sqlite/include" \
PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" \
pyenv install -f 3.12.6

# Create virtual environment and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Create data directories
mkdir -p data/sessions data/tokens data/logs

# Start the API server (port matches api.config / .env — see below)
uvicorn api.server:app --port "$(python -c 'from api.config import DASHBOARD_PORT; print(DASHBOARD_PORT)')" --reload
```

### 2. Frontend (React)

```bash
cd web
npm install
npm run dev
```

Vite prints the local URL when it starts. The dev server picks a stable port from
your checkout path (or `WEB_DEV_PORT` in `.env`) and proxies `/api/*` to the
API port (`DASHBOARD_PORT` or the same path-based default). To see both ports
without starting servers:

```bash
python -c "from api.config import DASHBOARD_PORT, WEB_DEV_PORT; print(f'API={DASHBOARD_PORT}  Web={WEB_DEV_PORT}')"
```

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

### Gmail

1. Enable IMAP in your Gmail settings and generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. In the dashboard, go to **Accounts** → **+ Add Account** → **Gmail** → enter your email and App Password.
3. Click **Sync** to pull emails.

**Large mailboxes:** Gmail uses the shared **UID + SINCE** batching in [`api/pullers/imap_uid_sync.py`](api/pullers/imap_uid_sync.py) (IMAPClient, oldest messages first within each search window). After each batch, the **cursor is committed** so a dropped connection can resume. On a **fresh account** (no stored items yet), the first import widens the lookback to `sync_days` capped at **20 years** (`MAX_SYNC_LOOKBACK_DAYS`). Optional service `config` JSON: `sync_days`, `max_messages` (total **UID slots** processed across batches toward a long backfill; `0` = unlimited), `imap_batch_size` (default **100**). These are **Backchannel limits**, not provider caps.


## Daily Sync

Run all connected services headless:

```bash
source .venv/bin/activate
python scripts/daily_sync.py
```

Automate with `launchd` (macOS) or `cron`.

### OpenClaw and other automations

Set **`READ_API_KEY`** in `.env` to enable **`POST /api/context/build`**. Send header
`Authorization: Bearer <READ_API_KEY>` and JSON body
`{ "q": "…", "mode": "hybrid", "limit": 15, "service_id": null, … }`.
The response includes **`context_markdown`** (capped text you can paste into a Claude
Sonnet prompt in OpenClaw) plus **`citations`** for traceability. No Ollama or in-app
LLM is involved — only your existing hybrid search and SQLite content.

## API Endpoints

All return JSON. Backend listens on `DASHBOARD_PORT` (see Quick Start).

| Endpoint | Description |
|---|---|
| `GET /api/dashboard` | Stats, accounts, recent sync runs |
| `GET /api/services` | List connected accounts |
| `GET /api/services/{id}` | Account detail with sync history |
| `POST /api/services` | Create a new service instance |
| `PATCH /api/services/{id}` | Rename a service |
| `DELETE /api/services/{id}` | Remove a service instance and its data |
| `POST /api/services/{id}/connect` | Connect with credentials |
| `POST /api/services/{id}/disconnect` | Disconnect a service |
| `POST /api/services/{id}/test` | Test connection |
| `POST /api/services/{id}/sync` | Trigger a sync |
| `POST /api/services/{id}/clear` | Clear all synced data for a service |
| `GET /api/services/{id}/stats` | Remote service stats (e.g. Gmail folders) |
| `GET /api/documents` | List documents (`?q=` for search) |
| `GET /api/documents/{id}` | Full document with markdown body |
| `GET /api/conversations` | Conversation threads (`?q=` for search) |
| `GET /api/conversations/{name}` | Messages in a thread (`?service=`, `?thread_id=`) |
| `GET /api/messages` | Flat message list (`?q=`, `?service=`, `?limit=`) |
| `GET /api/search` | Unified search (`?q=`, `?mode=semantic|keyword|hybrid`, `?limit=`) |
| `POST /api/context/build` | Retrieval-only markdown for an external LLM (requires `READ_API_KEY`; see below) |
| `POST /api/embeddings/backfill` | Index all un-embedded items and documents |
| `GET /api/embeddings/stats` | Embedding index coverage statistics |
| `GET /api/history` | Sync run history (`?limit=`) |
| `GET /api/logs` | In-memory log buffer |
| `GET /api/logs/stream` | SSE real-time log stream |

## Project Structure

```
api/
  server.py            FastAPI REST API (`DASHBOARD_PORT` / path-derived default)
  config.py            Environment variables
  db.py                SQLite schema, init, sqlite-vec extension loading
  content.py           Content processing pipeline (HTML→markdown, filtering, truncation)
  embeddings.py        Vector embeddings: chunking, indexing, semantic/hybrid search
  context_build.py     Assemble capped markdown context for external LLMs (OpenClaw)
  logstream.py         Real-time log broadcasting
  pullers/             Data pull engines
    base.py            BasePuller ABC and PullResult dataclass
    notion.py          Notion page sync (recursive block→markdown)
    telegram.py        Telegram message sync (Telethon, multi-step auth)
    gmail.py           Gmail IMAP sync (App Password, thread grouping)
    imap_uid_sync.py   Shared UID + SINCE incremental IMAP helpers
  services/
    manager.py         Service lifecycle (connect, sync, disconnect, CRUD)
web/
  src/
    App.tsx            React Router + React Query setup
    main.tsx           Entry point
    index.css          Tailwind v4 styles
    lib/
      api.ts           Typed fetch wrapper with all API functions
      utils.ts         Utility helpers (cn for class merging)
    components/
      layout/          Sidebar + app-shell
      ui/              shadcn/ui components (button, card, badge, dialog, etc.)
      error-boundary.tsx
      service-icon.tsx
    pages/
      dashboard.tsx    Stats overview
      accounts.tsx     Service list
      account-detail.tsx  Per-service detail + sync controls
      add-account.tsx  Add account modal
      documents.tsx    Document browser
      document-detail.tsx  Rendered markdown view
      messages.tsx     Conversation-grouped messages
      history.tsx      Sync run history
      logs.tsx         Real-time log viewer
scripts/
  daily_sync.py        Headless sync entry point
data/
  backchannel.db       SQLite database (gitignored)
```

## Tech Stack

### Frontend
- **Vite 8** + **React 19** + **TypeScript 5.9**
- **Tailwind CSS v4** + **shadcn/ui** (Radix Nova preset, dark mode)
- **React Query** for server state
- **React Router** for SPA navigation
- **react-markdown** + **remark-gfm** for document rendering
- **Lucide** icons

### Backend
- **FastAPI** + **Uvicorn** (REST API)
- **SQLite** with FTS5 full-text search
- **sqlite-vec** for database-native vector similarity search (vec0 virtual tables)
- **sentence-transformers** (`all-MiniLM-L6-v2`) for local embedding generation
- **SSE** for real-time log streaming
- **markdownify** for HTML-to-markdown content processing

### Service Integrations
- **Notion**: `notion-client` Python SDK (API key auth)
- **Telegram**: `telethon` (multi-step phone/code auth, rate limiting)
- **Gmail**: `imaplib` (App Password auth, IMAP with X-GM-THRID thread grouping)
- **WhatsApp**: Go bridge binary on `whatsmeow` (planned)

## Environment Variables

See `.env.example` for all settings. Service credentials are configured via the
web UI and stored in the database — not in `.env`.

| Variable | Description |
|---|---|
| `DASHBOARD_PORT` | API port (optional; if unset, derived from the project folder path) |
| `WEB_DEV_PORT` | Vite dev server port (optional; same path-based default when unset) |
| `DATABASE_PATH` | SQLite file path (default: `data/backchannel.db`) |
| `USER_EMAIL` | Your email (for sender_is_me detection) |
| `EMBEDDING_MODEL` | Sentence-transformers model (default: `all-MiniLM-L6-v2`) |
| `EMBEDDING_DIM` | Embedding vector dimensions (default: `384`) |
