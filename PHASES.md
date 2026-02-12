# PHASES.md — Backchannel Implementation Phases

Each phase is broken into numbered sub-tasks with a "done when" gate at the end.
Phases are sequential — each builds on the previous. Within a phase, tasks are
ordered by dependency but can sometimes be parallelised where noted.


---


## Phase 0 — Environment & Tech Stack Setup

Get a working dev environment with all dependencies installed and the project
skeleton in place. Nothing runs yet, but everything is wired to build and start.

### Tasks

- [x] **0.1. Create project directory structure**
  Create every directory from the project structure in PLAN.md:
  `app/`, `app/components/`, `app/routes/`, `app/pullers/`, `app/services/`,
  `data/`, `data/sessions/`, `data/tokens/`, `data/logs/`, `scripts/`.
  Add `__init__.py` files where needed.

- [x] **0.2. Create `.env.example`**
  List every environment variable from PLAN.md with placeholder values and
  comments. Sections: General, Notion, Gmail, Telegram, ProtonMail, WhatsApp.

- [x] **0.3. Create `requirements.txt`**
  Pin all Python dependencies from PLAN.md with compatible versions:
  `python-fasthtml`, `notion-client`, `google-api-python-client`,
  `google-auth-oauthlib`, `google-auth-httplib2`, `telethon`, `imapclient`,
  `mail-parser`, `python-dotenv`, `qrcode[pil]`.

- [x] **0.4. Set up Python virtual environment and install deps**
  Create venv, install from requirements.txt, confirm all imports resolve.

- [x] **0.5. Create `app/config.py`**
  Load `.env` with python-dotenv. Expose a settings object or module-level
  constants for every env var. Include sensible defaults (port 8787,
  database path `data/backchannel.db`, etc.).

- [x] **0.6. Create `app/main.py` — minimal FastHTML app**
  Import FastHTML, create the app instance, mount a single `GET /` that
  returns a plain "Backchannel is running" response. Confirm it starts on
  port 8787.

- [x] **0.7. Verify Tailwind CSS 4 + DaisyUI 4 via CDN**
  Add CDN links to the HTML head. Render a test page with a DaisyUI card
  and a Tailwind utility class. Confirm styling works in the browser.

### Done when
- [x] `python app/main.py` starts a server on localhost:8787
- [x] The test page renders with correct Tailwind/DaisyUI styling
- [x] All Python imports succeed without errors


---


## Phase 1 — Database & App Foundation

Set up the SQLite schema, seed data, layout shell, and the dashboard landing
page with placeholder service cards.

### Tasks

- [x] **1.1. Create `app/db.py` — database layer**
  - `get_db()`: returns a sqlite3 connection with WAL mode, foreign keys on,
    and row factory set to `sqlite3.Row`.
  - `init_db()`: creates all tables if they don't exist (services, sync_runs,
    items, items_fts) and inserts the 5 seed service rows.
  - Schema must match PLAN.md exactly: all fields, indexes, FTS5 virtual
    table, and triggers for FTS sync.

- [x] **1.2. Write and verify seed data**
  Insert the 5 services (notion, gmail, telegram, protonmail, whatsapp) with
  correct display names, auth types, and default status `disconnected`.
  Use `INSERT OR IGNORE` so re-running init is safe.

- [x] **1.3. Create `app/components/layout.py`**
  - `page(*children)`: full HTML document with head (CDN links, meta tags,
    HTMX script), nav bar, main content area, and footer.
  - `nav_bar()`: Backchannel branding/logo, links to Dashboard and History.

- [x] **1.4. Create `app/components/service_card.py`**
  - `service_card(service)`: DaisyUI card showing service icon/name, status
    badge (colour-coded), last sync time, item count, duration, and action
    button (Connect / Sync Now). Wire the `hx-get` attribute pointing to
    `/services/{id}/card` for polling.

- [x] **1.5. Create `app/components/sync_table.py`**
  - `sync_history_table(rows)`: HTML table of sync run records. Columns:
    service, run type, status, items fetched, duration, timestamp.

- [x] **1.6. Create `app/components/alerts.py`**
  - `success(msg)`, `error(msg)`, `warning(msg)`: DaisyUI alert banners
    suitable for HTMX swap targets.

- [x] **1.7. Create `app/routes/dashboard.py` — `GET /`**
  Query services table for all 5 rows. Query sync_runs for the last 10.
  Render the landing page: stats bar, service card grid, recent activity
  table. All cards show `disconnected` at this stage.

- [x] **1.8. Mount routes in `app/main.py`**
  Import and register the dashboard route. Ensure `init_db()` runs on
  startup.

- [x] **1.9. Visual check**
  Open localhost:8787 in a browser. Confirm the layout, nav bar, 5 service
  cards, and empty sync table all render correctly with DaisyUI styling.

### Done when
- [x] `data/backchannel.db` is created on first run with all tables and seed data
- [x] Dashboard at `/` renders 5 disconnected service cards and an empty sync table
- [x] Layout looks clean with Tailwind/DaisyUI


---


## Phase 2 — Puller Architecture & Service Manager

Build the shared puller framework and service lifecycle management before
implementing any individual service.

### Tasks

- [x] **2.1. Create `app/pullers/base.py`**
  - `PullResult` dataclass: `items` (list of dicts), `new_cursor` (str),
    `items_new` (int), `items_updated` (int).
  - `BasePuller` ABC with methods: `test_connection()`, `pull(cursor, since)`,
    `normalize(raw_item)`.

- [x] **2.2. Create `app/services/manager.py`**
  - `connect(service_id, credentials)`: validate and store credentials,
    set status to `connected`.
  - `disconnect(service_id)`: clear credentials, set status to `disconnected`.
  - `test(service_id)`: instantiate the puller, call `test_connection()`,
    return success or error message.
  - `status(service_id)`: return current service row.
  - `get_puller(service_id)`: factory that returns the correct puller instance.

- [x] **2.3. Create `app/routes/services.py`**
  - `GET /services/{service_id}`: service detail page with connection
    section, config section, sync section (placeholder forms for now).
  - `GET /services/{service_id}/card`: returns just the service card HTML
    fragment for HTMX polling.

- [x] **2.4. Create `app/routes/sync.py`**
  - `POST /sync/{service_id}`: trigger a sync for one service. Creates a
    sync_run record, calls the puller, upserts items, updates cursor,
    finalises the run. Returns the updated service card.
  - `POST /sync/all`: loop through all enabled+connected services and sync
    each. Return a status banner.

- [x] **2.5. Create `app/routes/auth.py` — stub**
  Placeholder route handlers for each service's auth flow. Each returns a
  "not yet implemented" message. Will be filled in as each service is built.

- [x] **2.6. Mount all new routes in `main.py`**

### Done when
- [x] Service detail pages render at `/services/notion`, etc.
- [x] HTMX card polling works (card refreshes every 30s)
- [x] `POST /sync/{service_id}` returns an appropriate error for unconnected services
- [x] BasePuller and PullResult are importable and type-correct


---


## Phase 3 — Telegram (First Service)

Telegram is the simplest service to get end-to-end: phone + code auth,
straightforward message iteration, no OAuth complexity.

### Tasks

- [ ] **3.1. Create `app/components/auth_forms.py` — Telegram section**
  - Phone number input form (POST to auth endpoint).
  - Verification code input form (appears after phone submission).
  - Optional 2FA password form.
  All forms use HTMX to swap in-place on the service detail page.

- [ ] **3.2. Implement `app/routes/auth.py` — Telegram flow**
  - `POST /auth/telegram/phone`: send code request via Telethon.
  - `POST /auth/telegram/code`: verify code, complete sign-in.
  - `POST /auth/telegram/password`: handle 2FA if needed.
  - On success: save session file to `data/sessions/`, store credentials,
    set status to `connected`.

- [ ] **3.3. Implement `app/pullers/telegram.py`**
  - `test_connection()`: connect with existing session, verify authorised.
  - `pull(cursor, since)`: if no cursor, iterate all dialogs and fetch
    messages since `since` date. If cursor exists, fetch by `min_id` per
    dialog. Return PullResult.
  - `normalize(raw_message)`: map to unified item schema. Set `item_type`
    to `message`, extract conversation, sender, sender_is_me, body_plain,
    source_ts, metadata.

- [ ] **3.4. Test initial sync**
  Connect Telegram via the dashboard. Trigger a sync with a 90-day window.
  Verify items land in the `items` table with correct fields.

- [ ] **3.5. Test incremental sync**
  Send a test message. Trigger another sync. Verify only new messages are
  fetched and the cursor advances.

- [ ] **3.6. Verify dashboard updates**
  Confirm the Telegram service card shows `connected`, correct item count,
  last sync time, and duration after a successful sync.

### Done when
- [ ] Telegram auth flow works end-to-end from the dashboard
- [ ] Initial sync pulls messages from the last 90 days into the items table
- [ ] Incremental sync fetches only new messages using stored cursor
- [ ] Service card reflects real status and counts


---


## Phase 4 — Gmail

Gmail has the most data and requires OAuth2, but the API is well-documented
and the history endpoint makes incremental sync efficient.

### Tasks

- [ ] **4.1. Add auth form for Gmail in `auth_forms.py`**
  - "Connect Gmail" button that starts the OAuth flow.
  - Status display showing whether tokens exist and are valid.

- [ ] **4.2. Implement `app/routes/auth.py` — Gmail OAuth flow**
  - `POST /auth/gmail/connect`: start InstalledAppFlow, open browser to
    Google consent screen. On callback, save tokens to
    `data/tokens/token.json` and credentials JSON in the services table.
  - Handle token refresh on expiry.

- [ ] **4.3. Implement `app/pullers/gmail.py`**
  - `test_connection()`: build the Gmail service object, call
    `users.getProfile` to verify access.
  - `pull(cursor, since)`: if no cursor, list messages with `after:` date
    query, paginate through all IDs, fetch full message for each. If cursor
    exists, use the history endpoint with `startHistoryId`. Return PullResult.
  - `normalize(raw_message)`: extract From, To, Cc, Subject, Date headers.
    Parse body parts (prefer text/plain, fall back to text/html). Set
    sender_is_me by comparing From to authenticated user email. Map labels.

- [ ] **4.4. Test initial sync**
  Connect Gmail via dashboard. Sync with a date window. Verify emails land
  in items with correct sender, subject, body, labels.

- [ ] **4.5. Test incremental sync**
  Run a second sync. Verify it uses the history endpoint and only fetches
  new/changed messages. Confirm cursor updates.

- [ ] **4.6. Handle edge cases**
  - Token refresh when access token expires.
  - Messages with no text/plain part (HTML-only emails).
  - Large attachments (store metadata only, not content).

### Done when
- [ ] Gmail OAuth works from the dashboard, tokens persist across restarts
- [ ] Initial sync pulls emails into items with correct normalisation
- [ ] Incremental sync via historyId is fast and correct
- [ ] Token refresh works transparently


---


## Phase 5 — ProtonMail

IMAP-based, straightforward once Proton Bridge is running. Similar to Gmail
but using raw IMAP instead of a REST API.

### Tasks

- [ ] **5.1. Add auth form for ProtonMail in `auth_forms.py`**
  - Email and password input fields (bridge credentials).
  - "Test Connection" button.

- [ ] **5.2. Implement `app/routes/auth.py` — ProtonMail flow**
  - `POST /auth/protonmail/connect`: test IMAP connection to localhost:1143
    with provided credentials. On success, store credentials and set status.

- [ ] **5.3. Implement `app/pullers/protonmail.py`**
  - `test_connection()`: connect to bridge IMAP, list folders, disconnect.
  - `pull(cursor, since)`: connect to bridge. For each folder, search for
    messages SINCE date (initial) or UID > last stored UID (incremental).
    Fetch RFC822, parse with mail-parser. Return PullResult.
  - `normalize(raw_email)`: extract headers, body_plain, body_html,
    attachments metadata, folder name. Set sender_is_me by folder (Sent)
    or From address match.

- [ ] **5.4. Test with Proton Bridge running**
  Verify connection, initial sync across folders, and incremental sync by UID.

### Done when
- [ ] ProtonMail connects via bridge credentials from the dashboard
- [ ] Emails from all folders sync into items with correct normalisation
- [ ] Incremental sync by UID works correctly


---


## Phase 6 — Notion

API key auth is simple, but recursive block fetching and database row handling
add complexity. Notion pages are stored as **documents** (markdown in SQLite)
rather than items, since they are mutable documents that change over time.

### Data Model — `documents` table

Notion pages are stored in a dedicated `documents` table in SQLite (not on
disk). Each document holds the full markdown content directly in the DB,
with content-hash dedup and version tracking:

```sql
documents
├── id              (auto PK)
├── service_id      (notion)
├── source_id       (Notion page ID)
├── title           (page title)
├── body_markdown   (full page content as markdown, stored in DB)
├── content_hash    (SHA-256 of body_markdown — skip writes if unchanged)
├── version         (incremented on each real content change)
├── metadata        (JSON — Notion properties, tags, parent, etc.)
├── source_ts       (last_edited_time from Notion)
├── fetched_at
├── sync_run_id
└── UNIQUE(service_id, source_id)
```

**FTS5 index** on `title` and `body_markdown` for full-text search.

**`document_versions` table** for history:

```sql
document_versions
├── id              (auto PK)
├── document_id     (FK → documents)
├── version         (version number at time of snapshot)
├── body_markdown   (content at this version)
├── content_hash
├── source_ts
├── created_at
```

**Sync logic:**
1. Pull page content from Notion → convert blocks to markdown
2. Hash the content → compare to `content_hash` in `documents`
3. If changed: insert snapshot into `document_versions`, update `documents`
   row with new content/hash/version
4. If unchanged: skip (no write, no version bump)

### Tasks

- [ ] **6.1. Add `documents` and `document_versions` tables to `app/db.py`**
  Create the schema as described above with FTS5 index and triggers.

- [ ] **6.2. Add auth form for Notion in `auth_forms.py`**
  - API token input field with a "Save & Test" button.

- [ ] **6.3. Implement `app/routes/auth.py` — Notion flow**
  - `POST /auth/notion/connect`: store the token, test with a search API
    call, set status.

- [ ] **6.4. Implement `app/pullers/notion.py`**
  - `test_connection()`: call the search endpoint with the stored token.
  - `pull(cursor, since)`: search for pages and databases. If cursor exists,
    filter by `last_edited_time > cursor`. For pages, recursively fetch
    block children up to configurable `max_depth` (default 5). Convert
    blocks to markdown. Hash content and compare to stored hash — only
    create a new version if changed. For databases, query all rows.
    Use `collect_paginated_api` for pagination. Return PullResult.
  - `normalize(raw_page)`: convert Notion blocks to clean markdown. Store
    as a document (not an item). Database rows become `item_type: db_row`
    in the items table with properties in metadata.

- [ ] **6.5. Add document browsing to the dashboard**
  - `GET /docs`: list all documents with title, service, version, last
    updated. Searchable via FTS.
  - `GET /docs/{id}`: render the markdown content in the dashboard.
  - `GET /docs/{id}/history`: show version history with diffs.

- [ ] **6.6. Test initial and incremental sync**
  Connect Notion, sync, verify pages land in `documents` with correct
  markdown content. Modify a page, re-sync, verify a new version is
  created and the old version is preserved in `document_versions`.

### Done when
- [ ] Notion connects via API key from the dashboard
- [ ] Pages sync into `documents` table with markdown content in SQLite
- [ ] Content-hash dedup prevents unnecessary version bumps
- [ ] Version history is preserved in `document_versions`
- [ ] Documents are browsable in the dashboard with rendered markdown
- [ ] Incremental sync by last_edited_time works correctly


---


## Phase 7 — WhatsApp

The most complex auth flow (QR code + bridge process management) but the
simplest puller (read from the bridge's SQLite DB).

### Tasks

- [ ] **7.1. Verify or build the whatsapp-bridge Go binary**
  Clone whatsapp-mcp repo, build the binary, place in `whatsapp-bridge/`.
  Run it once manually to confirm it creates `store/messages.db` and
  outputs a QR code.

- [ ] **7.2. Implement bridge process management in `app/services/manager.py`**
  - `start_bridge()`: launch the Go binary as a subprocess, capture stdout/
    stderr to `data/logs/`.
  - `stop_bridge()`: terminate the process gracefully.
  - `bridge_health()`: check if the process is alive and the messages.db
    is being written to.

- [ ] **7.3. Add auth form for WhatsApp in `auth_forms.py`**
  - Start/Stop bridge buttons.
  - QR code display area that auto-refreshes via HTMX polling every 2s.
  - Status indicator (waiting for scan / connected / error).

- [ ] **7.4. Implement `app/routes/auth.py` — WhatsApp flow**
  - `POST /auth/whatsapp/start`: start the bridge, begin capturing QR data.
  - `GET /auth/whatsapp/qr`: return the current QR code as an image
    rendered by the `qrcode` Python library. Returns empty/success state
    once scanned.

- [ ] **7.5. Implement `app/pullers/whatsapp.py`**
  - `test_connection()`: verify bridge is running and messages.db exists.
  - `pull(cursor, since)`: open messages.db in read-only mode. Query rows
    with `rowid > cursor` (or all rows for initial sync). Return PullResult.
  - `normalize(raw_row)`: map bridge DB columns to unified schema. Map JIDs
    to contact names where possible. Set sender_is_me by comparing sender
    JID to own JID.

- [ ] **7.6. Inspect bridge SQLite schema**
  Run the bridge, inspect `store/messages.db` with `.schema`. Document
  actual table and column names. Adjust puller queries accordingly.

- [ ] **7.7. Test initial and incremental sync**
  Scan QR, let bridge receive messages, trigger sync, verify items. Send a
  message, re-sync, verify incremental by rowid.

### Done when
- [ ] Bridge starts/stops from the dashboard
- [ ] QR code displays and refreshes until scanned
- [ ] Messages sync from the bridge DB into items
- [ ] Incremental sync by rowid works correctly


---


## Phase 8 — Sync History, Full-Text Search & API

Build the history page, wire up FTS5 search, and add a JSON/Markdown API
layer for programmatic access (e.g. AI agent ingestion).

### Tasks

- [ ] **8.1. Create `app/routes/history.py` — `GET /history`**
  Full paginated table of all sync runs. Columns: ID, service, run type,
  status, started, completed, items fetched, items new, duration, error.
  Filterable by service and status via query params.

- [ ] **8.2. Implement `GET /history/table?page=N`**
  HTMX partial that returns just the table rows for a given page. Wire
  pagination controls.

- [ ] **8.3. Verify FTS5 triggers**
  Insert, update, and delete items and documents. Confirm the FTS virtual
  tables stay in sync via the triggers created in earlier phases.

- [ ] **8.4. Create `app/routes/api.py` — JSON + Markdown API**
  All endpoints return JSON by default. Add `?format=markdown` query param
  for markdown output (ideal for AI agent consumption).

  **Items (messages/emails):**
  - `GET /api/items` — list items with filters: `service`, `type`, `sender`,
    `since`, `until`, `q` (FTS search), `limit`, `offset`.
  - `GET /api/items/{id}` — single item with full body.
  - `GET /api/items/search?q=...` — full-text search across all items.
  - `GET /api/services` — all services with status + item/doc counts.
  - `GET /api/services/{id}/items` — items for a specific service.
  - `GET /api/sync-runs` — recent sync history.
  - `GET /api/stats` — summary stats (counts by service, date range, etc.).

  **Documents (Notion pages):**
  - `GET /api/docs` — list all documents with metadata (title, version,
    last updated). Searchable via `?q=` FTS param.
  - `GET /api/docs/{id}` — latest document content (JSON with metadata,
    or raw markdown with `?format=markdown`).
  - `GET /api/docs/{id}/history` — list of versions with dates and hashes.
  - `GET /api/docs/{id}/version/{version}` — specific historical version.

  **Markdown format** groups items by conversation and reads naturally:
  ```
  ## Telegram — Family Group
  **Alice** (2026-02-12 18:30):
  Hey, are we still on for dinner?
  ---
  **Bob** (2026-02-12 18:32):
  Yes! 7pm at the usual place.
  ```

- [ ] **8.5. Mount API routes in `main.py`**

### Done when
- [ ] `/history` renders a paginated, filterable sync run table
- [ ] FTS5 stays in sync with items and documents on insert/update/delete
- [ ] `/api/items` returns JSON with filtering and pagination
- [ ] `/api/docs` returns JSON with document metadata
- [ ] `/api/docs/{id}` returns document content in JSON or markdown
- [ ] `/api/items?format=markdown` returns conversation-grouped markdown


---


## Phase 9 — Daily Sync, launchd & Polish

Wire up the automated daily sync, launchd plists, error handling, and the
setup script. Make everything production-ready for the Mac Mini.

### Tasks

- [ ] **9.1. Create `scripts/daily_sync.py`**
  Standalone entry point. Opens DB, queries enabled+connected services,
  runs each puller sequentially, commits after each, writes summary to log.
  Matches the flow described in PLAN.md exactly.

- [ ] **9.2. Create launchd plist files**
  - `com.backchannel.web.plist`: FastHTML on port 8787, KeepAlive true.
  - `com.backchannel.whatsapp.plist`: bridge binary, KeepAlive true.
  - `com.backchannel.daily.plist`: daily_sync.py at 06:00 via
    StartCalendarInterval.

- [ ] **9.3. Create `scripts/setup.sh`**
  Full setup script: check brew, create venv, install deps, copy .env.example
  to .env if missing, run init_db, symlink plists to ~/Library/LaunchAgents/,
  load agents.

- [ ] **9.4. Error handling & retry in pullers**
  - Gmail: handle quota limits with exponential backoff.
  - Telegram: handle FloodWaitError with sleep.
  - Notion: handle rate limit (429) with retry-after header.
  - ProtonMail: handle IMAP disconnects with reconnect.
  - WhatsApp: handle bridge not running gracefully.

- [ ] **9.5. Logging improvements**
  Structured logging to `data/logs/` with rotation. Include timestamps,
  service names, item counts, errors. One log file per day.

- [ ] **9.6. Create `README.md`**
  Full setup instructions: prerequisites, environment setup, first run,
  connecting each service, how the daily sync works, troubleshooting.

- [ ] **9.7. Resolve open questions from PLAN.md**
  Make decisions on: raw API response storage, attachment downloads,
  Notion recursion depth, Gmail batch API, "me" identity config.

### Done when
- [ ] `scripts/daily_sync.py` runs successfully and syncs all connected services
- [ ] All three launchd plists load and work (web server, bridge, daily sync)
- [ ] `scripts/setup.sh` sets up a fresh Mac Mini from scratch
- [ ] README covers the full setup and usage flow
- [ ] Error handling prevents one service failure from blocking others
