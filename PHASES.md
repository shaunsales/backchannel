# PHASES.md — Backchannel Implementation Phases

Each phase is broken into numbered sub-tasks with a "done when" gate at the end.
Phases are sequential — each builds on the previous. Within a phase, tasks are
ordered by dependency but can sometimes be parallelised where noted.


---


## Phase 0 — Environment & Tech Stack Setup

Get a working dev environment with all dependencies installed and the project
skeleton in place.

### Tasks

- [x] **0.1. Create project directory structure**
  Create `api/`, `api/pullers/`, `api/services/`, `data/`, `data/sessions/`,
  `data/tokens/`, `data/logs/`, `scripts/`.
  Add `__init__.py` files where needed.

- [x] **0.2. Create `.env.example`**
  List environment variables with placeholder values and comments.
  Service credentials are stored in the database, not in .env.

- [x] **0.3. Create `requirements.txt`**
  Pin all Python dependencies with compatible versions:
  `fastapi`, `uvicorn`, `notion-client`, `google-api-python-client`,
  `google-auth-oauthlib`, `google-auth-httplib2`, `telethon`, `imapclient`,
  `mail-parser`, `markdownify`, `python-dotenv`, `qrcode[pil]`.

- [x] **0.4. Set up Python virtual environment and install deps**
  Create venv, install from requirements.txt, confirm all imports resolve.

- [x] **0.5. Create `api/config.py`**
  Load `.env` with python-dotenv. Expose module-level constants for every
  env var. Include sensible defaults (port 8787, database path
  `data/backchannel.db`, etc.).

- [x] **0.6. Create `api/server.py` — minimal FastAPI app**
  Import FastAPI, create the app instance. Confirm it starts on port 8787
  with `uvicorn api.server:app`.

### Done when
- [x] `uvicorn api.server:app --port 8787` starts a server on localhost:8787
- [x] All Python imports succeed without errors


---


## Phase 1 — Database & App Foundation

Set up the SQLite schema, seed data, and the dashboard API endpoint with
placeholder service data.

### Tasks

- [x] **1.1. Create `api/db.py` — database layer**
  - `get_db()`: returns a thread-local sqlite3 connection with WAL mode,
    foreign keys on, and row factory set to `sqlite3.Row`.
  - `init_db()`: creates all tables if they don't exist (services, sync_runs,
    items, items_fts, documents, document_versions, documents_fts) and inserts
    seed service rows. Includes migrations for service_type and thread_id
    columns. Cleans up stale "running" sync runs on restart.
  - Schema matches the data model in PLAN.md.

- [x] **1.2. Write and verify seed data**
  Insert the 5 services (notion, gmail, telegram, protonmail, whatsapp) with
  correct display names, auth types, and default status `disconnected`.
  Use `INSERT OR IGNORE` so re-running init is safe.

- [x] **1.3. Create dashboard API endpoint**
  `GET /api/dashboard`: returns stats, connected accounts, and recent sync runs.

- [x] **1.4. Create services API endpoints**
  `GET /api/services`, `GET /api/services/{id}`: return service data with
  item/doc counts.

### Done when
- [x] `data/backchannel.db` is created on first run with all tables and seed data
- [x] `/api/dashboard` returns JSON with stats and service data
- [x] `/api/services` returns all services


---


## Phase 2 — Puller Architecture & Service Manager

Build the shared puller framework and service lifecycle management before
implementing any individual service.

### Tasks

- [x] **2.1. Create `api/pullers/base.py`**
  - `PullResult` dataclass: `items`, `documents`, `new_cursor`,
    `items_new`, `items_updated`, `docs_new`, `docs_updated`, `all_source_ids`.
  - `BasePuller` ABC with methods: `test_connection()`, `pull(cursor, since)`,
    `normalize(raw_item)`.

- [x] **2.2. Create `api/services/manager.py`**
  - `connect(service_id, credentials)`: validate and store credentials,
    set status to `connected`.
  - `disconnect(service_id)`: clear credentials, set status to `disconnected`.
  - `test(service_id)`: instantiate the puller, call `test_connection()`,
    return success or error message.
  - `run_sync(service_id, run_type)`: create sync_run, call puller, upsert
    items, handle documents with content-hash versioning, run deletion
    detection, finalise run with counts/duration.
  - `add_service_instance()`, `remove_service_instance()`, `rename_service()`,
    `clear_data()`: full service CRUD.
  - `register_puller()`, `get_puller()`: puller registry and factory.

- [x] **2.3. Create service API endpoints**
  Services CRUD: POST (create), PATCH (rename), DELETE (remove).
  Service actions: connect, disconnect, test, sync, clear, stats.

### Done when
- [x] BasePuller and PullResult are importable and type-correct
- [x] Service CRUD operations work end-to-end via the API
- [x] `POST /api/services/{id}/sync` returns appropriate errors for unconnected services


---


## Phase 3 — Telegram ✅ COMPLETE

Telegram is the simplest service to get end-to-end: phone + code auth,
straightforward message iteration, no OAuth complexity.

### Tasks

- [x] **3.1. Implement `api/pullers/telegram.py`**
  - `test_connection()`: connect with existing session, verify authorised.
  - `pull(cursor, since)`: iterates dialogs with filtering, fetches messages
    per dialog (capped at 200). Cursor is a JSON object with per-dialog
    message IDs and last_sync_ts for incremental sync. Returns PullResult.
  - `normalize(raw_message)`: maps to unified item schema with conversation,
    sender, sender_is_me, body_plain, source_ts, thread_id, metadata.
  - **Dialog filters**: skip archived, bots, broadcast channels, forbidden/
    deleted, inactive >365 days, dialogs where user never replied.
  - **Preview sync**: dry-run mode (`preview_sync()`) returns dialog summary
    without writing to DB.
  - **Rate limiting**: proactive delays (1s between dialogs, 0.5s after
    reply-check requests) to avoid Telegram FloodWaitError.
  - Reads API ID/Hash from DB credentials, not environment variables.

- [x] **3.2. Test initial sync**
  Connected Telegram via dashboard. Full sync with 365-day window.
  Messages land in `items` table with correct fields.

- [x] **3.3. Test incremental sync**
  Cursor-based incremental sync by `min_id` per dialog works correctly.

- [x] **3.4. Verify dashboard updates**
  Service card shows `connected`, correct item count, last sync time.

### Done when
- [x] Telegram auth flow works end-to-end from the dashboard
- [x] Initial sync pulls messages from the last 365 days into the items table
- [x] Incremental sync fetches only new messages using stored cursor
- [x] Service card reflects real status and counts


---


## Phase 4 — Notion ✅ COMPLETE

API key auth is simple, but recursive block fetching adds complexity. Notion
pages are stored as **documents** (markdown in SQLite) rather than items,
since they are mutable documents that change over time.

### Tasks

- [x] **4.1. Add `documents` and `document_versions` tables to `api/db.py`**
  Schema with FTS5 index, triggers, and `hidden` column for soft-delete.

- [x] **4.2. Implement `api/pullers/notion.py`**
  - `test_connection()`: search endpoint with stored token.
  - `pull(cursor, since)`: paginated search, recursive block fetching
    (max_depth=5), markdown conversion. Child pages/databases NOT recursed
    into. Filters: skip archived/trashed, untitled, empty body pages.
    Tracks all live source_ids for deletion detection.
  - `normalize(page, client, max_depth)`: 15+ block types → markdown.
    Returns document dict with source_id, title, body_markdown, metadata,
    source_ts.

- [x] **4.3. Add document API endpoints**
  `GET /api/documents` (with `?q=` search), `GET /api/documents/{id}`.

- [x] **4.4. Test initial and incremental sync**
  Initial sync: ~60s for 36 pages.
  Incremental sync: ~3s (cursor-based skip, still detects deletions).
  Trashed pages in Notion auto-removed from DB.

### Done when
- [x] Notion connects via API key from the dashboard
- [x] Pages sync into `documents` table with markdown content in SQLite
- [x] Content-hash dedup prevents unnecessary version bumps
- [x] Version history is preserved in `document_versions`
- [x] Documents are browsable via the API with search
- [x] Incremental sync by last_edited_time works correctly
- [x] Pages trashed in Notion are auto-removed from DB on next sync


---


## Phase 5 — Gmail ✅ COMPLETE

Gmail via IMAP with App Password authentication. Includes a content processing
pipeline for HTML-to-markdown conversion and thread grouping via Gmail's
X-GM-THRID extension.

### Tasks

- [x] **5.1. Implement `api/pullers/gmail.py`**
  - `test_connection()`: connect to imap.gmail.com with App Password,
    select INBOX, verify access.
  - `get_stats()`: list folders with message counts, total messages,
    oldest/newest dates.
  - `pull(cursor, since)`: connect to [Gmail]/All Mail. Search SINCE date.
    Fetch RFC822 + X-GM-THRID per message. Parse with Python email module.
    Run through content pipeline. Cap at configurable max messages.
  - `normalize(msg, my_email, gmail_thread_id)`: extract headers, parse
    body via content pipeline, set sender_is_me by From address, build
    thread_id from X-GM-THRID, strip Re:/Fwd: from conversation name.

- [x] **5.2. Create `api/content.py` — content processing pipeline**
  - `html_to_markdown()`: HTML → clean markdown via markdownify.
  - `text_to_markdown()`: light cleanup of plain text.
  - `_is_binary_garbage()`, `_strip_binary_blocks()`: detect and filter
    base64/hex blocks.
  - `_truncate()`: cap at 50K chars with smart paragraph/line breaking.
  - `process_content()`: main pipeline combining all steps.

- [x] **5.3. Test initial sync**
  Connected Gmail via dashboard with App Password. Sync pulls emails into
  items with correct sender, subject, markdown body, thread grouping.

- [x] **5.4. Test incremental sync**
  Second sync uses stored cursor (ISO timestamp) as SINCE date. Only new
  messages are fetched.

### Done when
- [x] Gmail connects via IMAP App Password from the dashboard
- [x] Initial sync pulls emails into items with correct normalisation
- [x] HTML emails are converted to clean markdown
- [x] Thread grouping works via X-GM-THRID
- [x] Incremental sync by date is fast and correct
- [x] Service stats endpoint returns folder counts and date range


---


## Phase 6 — Messages, Conversations & Search ✅ COMPLETE

Build conversation-grouped message browsing and full-text search across all
synced content.

### Tasks

- [x] **6.1. Add conversation API endpoints**
  `GET /api/conversations` with `?q=` FTS search and `?limit=`.
  `GET /api/conversations/{name}` with `?service=`, `?thread_id=`, `?limit=`.
  Groups by thread_id when available, falls back to conversation + service_id.

- [x] **6.2. Add messages API endpoint**
  `GET /api/messages` with `?q=` FTS search, `?service=` filter, `?limit=`.

- [x] **6.3. Add sync history API endpoint**
  `GET /api/history` with `?limit=`.

- [x] **6.4. Add logging endpoints**
  `GET /api/logs` returns in-memory log buffer.
  `GET /api/logs/stream` SSE real-time log stream.
  `api/logstream.py` implements BroadcastHandler, buffer, subscribe/unsubscribe.

- [x] **6.5. Verify FTS5 triggers**
  FTS5 triggers for both items and documents are working. Insert, update,
  and delete operations keep the virtual tables in sync.

### Done when
- [x] `/api/conversations` returns grouped conversations with search
- [x] `/api/messages` returns flat message list with FTS search
- [x] `/api/history` returns sync run table
- [x] FTS5 stays in sync with items and documents on insert/update/delete
- [x] Real-time log streaming works via SSE


---


## Phase 7 — React Frontend ✅ COMPLETE

Migrate the frontend from the original Python-based UI to a React SPA with
Vite, TypeScript, Tailwind v4, and shadcn/ui.

### Tasks

- [x] **7.1. Scaffold React app with Vite**
  Vite 8, React 19, TypeScript 5.9. Configure Vite proxy for `/api/*` to
  `http://localhost:8787`. Set up path alias `@/` → `src/`.

- [x] **7.2. Install and configure Tailwind v4 + shadcn/ui**
  Radix Nova preset, dark mode, Lucide icons. Add shadcn/ui components:
  button, card, badge, dialog, input, table, tooltip, scroll-area, separator.

- [x] **7.3. Create `web/src/lib/api.ts` — typed API client**
  Typed fetch wrapper with interfaces for all API response shapes:
  DashboardData, AccountSummary, AccountDetail, RunSummary, DocSummary,
  DocDetail, MessageItem, ConversationSummary, ServiceStats, SyncResult.
  API functions matching all backend endpoints.

- [x] **7.4. Create app shell and layout**
  `web/src/components/layout/sidebar.tsx` — collapsible sidebar with nav links.
  `web/src/components/layout/app-shell.tsx` — layout wrapper with sidebar + outlet.
  `web/src/App.tsx` — React Router routes + React Query provider.

- [x] **7.5. Create all page components**
  - `dashboard.tsx` — stats overview, connected accounts, recent sync activity
  - `accounts.tsx` — service grid with add-account modal
  - `account-detail.tsx` — per-service management (connect, sync, clear, stats)
  - `add-account.tsx` — add account form (navigates back to accounts)
  - `documents.tsx` — document browser with search
  - `document-detail.tsx` — rendered markdown view
  - `messages.tsx` — conversation-grouped messages with search
  - `history.tsx` — sync run history table
  - `logs.tsx` — real-time log viewer with SSE

- [x] **7.6. Add shared components**
  `error-boundary.tsx` — React error boundary.
  `service-icon.tsx` — Lucide icon per service type.

### Done when
- [x] React SPA runs on port 5173 with Vite proxy to backend
- [x] All pages render with correct data from the API
- [x] shadcn/ui components render correctly with dark mode
- [x] Typed API client matches all backend endpoints


---


## Phase 8 — Vector Search & Embeddings ✅ COMPLETE

Add semantic search across all synced content using sqlite-vec for
database-native vector similarity search and sentence-transformers for
local embedding generation.

### Tasks

- [x] **8.1. Rebuild Python with SQLite extension support**
  pyenv Python 3.12.6 rebuilt with `--enable-loadable-sqlite-extensions`
  flag and Homebrew SQLite headers. Required for sqlite-vec extension loading.

- [x] **8.2. Add sqlite-vec extension loading to `api/db.py`**
  Load sqlite-vec on every connection via `sqlite_vec.load(conn)`. Create
  `chunks` table for text storage and `vec_chunks` vec0 virtual table for
  384-dimensional float32 embeddings.

- [x] **8.3. Create `api/embeddings.py`**
  - `embed()`: generate normalized embeddings via sentence-transformers
    (all-MiniLM-L6-v2, 384 dimensions, ~80MB model, runs locally).
  - `chunk_text()`: split documents at paragraph boundaries (~1000 chars
    per chunk, merge tiny trailing chunks).
  - `index_item()`, `index_document()`: embed and store in chunks + vec_chunks.
  - `remove_for_service()`: clean up embeddings when service data is cleared.
  - `index_new_for_service()`: index un-embedded content after sync.
  - `backfill()`: batch-index all un-embedded content across all services.
  - `search_semantic()`: KNN via sqlite-vec `WHERE embedding MATCH ? AND k = ?`.
  - `search_keyword()`: FTS5 search across items_fts and documents_fts.
  - `search_hybrid()`: Reciprocal Rank Fusion combining semantic + keyword.

- [x] **8.4. Hook embeddings into sync pipeline**
  `api/services/manager.py` calls `index_new_for_service()` after each
  successful sync. `clear_data()` and `remove_service_instance()` clean up
  associated chunks and vectors.

- [x] **8.5. Add search and embeddings API endpoints**
  `GET /api/search?q=...&mode=hybrid&limit=20` — unified search endpoint.
  `POST /api/embeddings/backfill` — index all un-embedded content.
  `GET /api/embeddings/stats` — coverage statistics.

- [x] **8.6. Backfill existing content**
  Ran backfill on 7,259 items + 22 documents → 7,291 chunks indexed.
  100% coverage. Semantic search ~100ms, keyword ~60ms, hybrid ~190ms.

### Done when
- [x] sqlite-vec loads on every connection and vec_chunks table exists
- [x] All items and documents are embedded with 100% coverage
- [x] Semantic, keyword, and hybrid search all return ranked results
- [x] New content is auto-indexed after each sync
- [x] Clearing/removing a service also removes its embeddings


---


## Phase 9 — ProtonMail (planned)

IMAP-based, straightforward once Proton Bridge is running. Similar to Gmail
but using imapclient + mail-parser instead of the standard library.

### Tasks

- [ ] **9.1. Implement `api/pullers/protonmail.py`**
  - `test_connection()`: connect to bridge IMAP, list folders, disconnect.
  - `pull(cursor, since)`: connect to bridge. For each folder, search for
    messages SINCE date (initial) or UID > last stored UID (incremental).
    Fetch RFC822, parse with mail-parser. Return PullResult.
  - `normalize(raw_email)`: extract headers, body_plain, body_html,
    attachments metadata, folder name. Set sender_is_me by folder (Sent)
    or From address match.

- [ ] **9.2. Test with Proton Bridge running**
  Verify connection, initial sync across folders, and incremental sync by UID.

### Done when
- [ ] ProtonMail connects via bridge credentials from the dashboard
- [ ] Emails from all folders sync into items with correct normalisation
- [ ] Incremental sync by UID works correctly


---


## Phase 10 — WhatsApp (planned)

The most complex auth flow (QR code + bridge process management) but the
simplest puller (read from the bridge's SQLite DB).

### Tasks

- [ ] **10.1. Verify or build the whatsapp-bridge Go binary**
  Clone whatsapp-mcp repo, build the binary, place in `whatsapp-bridge/`.
  Run it once manually to confirm it creates `store/messages.db` and
  outputs a QR code.

- [ ] **10.2. Implement bridge process management in `api/services/manager.py`**
  - `start_bridge()`: launch the Go binary as a subprocess.
  - `stop_bridge()`: terminate the process gracefully.
  - `bridge_health()`: check if the process is alive and the messages.db
    is being written to.

- [ ] **10.3. Implement `api/pullers/whatsapp.py`**
  - `test_connection()`: verify bridge is running and messages.db exists.
  - `pull(cursor, since)`: open messages.db in read-only mode. Query rows
    with `rowid > cursor` (or all rows for initial sync). Return PullResult.
  - `normalize(raw_row)`: map bridge DB columns to unified schema. Map JIDs
    to contact names where possible. Set sender_is_me by comparing sender
    JID to own JID.

- [ ] **10.4. Inspect bridge SQLite schema**
  Run the bridge, inspect `store/messages.db` with `.schema`. Document
  actual table and column names. Adjust puller queries accordingly.

- [ ] **10.5. Test initial and incremental sync**
  Scan QR, let bridge receive messages, trigger sync, verify items.

### Done when
- [ ] Bridge starts/stops from the dashboard
- [ ] QR code displays and refreshes until scanned
- [ ] Messages sync from the bridge DB into items
- [ ] Incremental sync by rowid works correctly


---


## Phase 11 — Daily Sync, launchd & Polish

Wire up the automated daily sync, launchd plists, error handling, and the
setup script.

### Tasks

- [x] **11.1. Create `scripts/daily_sync.py`**
  Standalone entry point. Opens DB, registers pullers, queries
  enabled+connected services, runs each sequentially via run_sync(),
  commits after each, logs summary.

- [ ] **11.2. Create launchd plist files**
  - `com.backchannel.web.plist`: FastAPI on port 8787, KeepAlive true.
  - `com.backchannel.whatsapp.plist`: bridge binary, KeepAlive true.
  - `com.backchannel.daily.plist`: daily_sync.py at 06:00 via
    StartCalendarInterval.

- [ ] **11.3. Create `scripts/setup.sh`**
  Full setup script: check brew, create venv, install deps, copy .env.example
  to .env if missing, run init_db, symlink plists to ~/Library/LaunchAgents/,
  load agents.

- [ ] **11.4. Error handling & retry in pullers**
  - [x] Telegram: proactive rate limiting (1s between dialogs, 0.5s after
    reply checks) to avoid FloodWaitError. Telethon auto-sleeps on any
    remaining flood waits.
  - [ ] Notion: handle rate limit (429) with retry-after header.
  - [ ] Gmail: handle IMAP connection timeouts gracefully.
  - [ ] ProtonMail: handle IMAP disconnects with reconnect.
  - [ ] WhatsApp: handle bridge not running gracefully.

### Done when
- [ ] `scripts/daily_sync.py` runs successfully and syncs all connected services
- [ ] All three launchd plists load and work (web server, bridge, daily sync)
- [ ] `scripts/setup.sh` sets up a fresh Mac Mini from scratch
- [ ] Error handling prevents one service failure from blocking others
