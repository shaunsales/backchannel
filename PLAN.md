# PLAN.md — Backchannel

## Overview

Backchannel is a local-first daily data sync app that pulls messages, emails,
notes, and pages from multiple services into a unified SQLite database. Runs on
a Mac Mini. Includes a React web dashboard for auth management, monitoring, and
manual sync triggers, plus a FastAPI backend serving a REST API.

Core loop: Every morning at 06:00, Backchannel pulls everything new from all
connected services, stores it in a unified items table, ready for AI agent
ingestion.

### Current Progress

- **Foundation complete**: FastAPI backend, React frontend, SQLite schema,
  dashboard, layout, components
- **Notion fully integrated**: API key auth, page sync with markdown conversion,
  document versioning, content-hash dedup, incremental sync, deletion detection,
  soft-delete (hide/unhide)
- **Telegram fully integrated**: Multi-step phone/code/2FA auth, dialog filtering,
  rate limiting, incremental sync by message ID per dialog, preview sync
- **Gmail fully integrated**: IMAP with App Password auth, folder stats,
  HTML-to-markdown content pipeline, X-GM-THRID thread grouping, incremental
  sync by date
- **JSON API live**: endpoints for dashboard, services CRUD, documents,
  conversations, messages, history, logs
- **React dashboard live**: accounts, documents, messages, history, logs pages
- **Remaining**: ProtonMail, WhatsApp pullers; daily sync automation; launchd
  plists


## Tech Stack

Frontend:           Vite 8, React 19, TypeScript 5.9
CSS:                Tailwind CSS v4, shadcn/ui (Radix Nova preset, dark mode)
State management:   React Query (TanStack Query)
Routing:            React Router
Icons:              Lucide
Backend:            FastAPI + Uvicorn (REST API, port 8787)
Database:           SQLite via sqlite3 (single file, FTS5 for search)
Content processing: markdownify (HTML→markdown), custom pipeline in content.py
Scheduler:          macOS launchd (native, survives reboots)
WhatsApp bridge:    Go binary built on whatsmeow (whatsapp-mcp project, planned)
ProtonMail access:  Proton Mail Bridge (user installs, exposes IMAP, planned)


## Python Dependencies

fastapi
uvicorn
notion-client
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
telethon
imapclient
mail-parser
markdownify
python-dotenv
qrcode[pil]


## Project Structure

backchannel/
  api/
    __init__.py
    server.py                   FastAPI app, all REST endpoints
    config.py                   Reads .env, exposes settings
    db.py                       get_db(), init_db(), schema, migrations
    content.py                  Content processing (HTML→markdown, filtering)
    logstream.py                In-memory log broadcast for real-time panel

    pullers/                    Data pull engines, one per service
      __init__.py
      base.py                   BasePuller ABC and PullResult dataclass
      notion.py                 Notion page sync
      telegram.py               Telegram message sync
      gmail.py                  Gmail IMAP sync

    services/                   Service lifecycle management
      __init__.py
      manager.py                connect, disconnect, sync, CRUD, puller registry

  web/
    src/
      App.tsx                   React Router + React Query setup
      main.tsx                  Entry point
      index.css                 Tailwind v4 styles
      lib/
        api.ts                  Typed fetch wrapper with all API functions
        utils.ts                Utility helpers
      components/
        layout/                 Sidebar + app-shell
        ui/                     shadcn/ui components
        error-boundary.tsx
        service-icon.tsx
      pages/
        dashboard.tsx
        accounts.tsx
        account-detail.tsx
        add-account.tsx
        documents.tsx
        document-detail.tsx
        messages.tsx
        history.tsx
        logs.tsx

  scripts/
    daily_sync.py               Entry point called by launchd

  data/
    backchannel.db              Main SQLite database
    sessions/                   Telegram .session files
    tokens/                     Gmail credentials (planned for OAuth)
    logs/


## Data Model

### services

One row per connected service instance. Tracks connection status, stores
credentials as a JSON blob, and holds the sync cursor that each puller uses
to know where it left off. Supports multiple instances of the same type
(e.g. two Gmail accounts).

Fields: id, service_type, display_name, status, auth_type, credentials (JSON),
config (JSON), enabled, last_sync_at, sync_cursor, created_at, updated_at.

Status is one of: connected, disconnected, auth_required, error, syncing.

Auth type is one of: api_key (Notion), app_password (Gmail), phone_code
(Telegram), imap_login (ProtonMail), qr_link (WhatsApp).

The sync cursor is a string whose format varies by service:
  - Gmail: ISO timestamp of last sync
  - Telegram: JSON with per-dialog last message IDs and last_sync_ts
  - Notion: ISO timestamp of last edited time
  - ProtonMail: JSON mapping folder names to last UIDs (planned)
  - WhatsApp: integer rowid from the bridge database (planned)

Seed data inserted on first run:
  notion      Notion       api_key
  gmail       Gmail        app_password
  telegram    Telegram     phone_code
  protonmail  ProtonMail   imap_login
  whatsapp    WhatsApp     qr_link

### sync_runs

One row per sync attempt. Provides a full audit trail. Tracks which service,
whether it was scheduled or manual, success or failure, how many items were
fetched, how long it took, and any error message.

Fields: id, service_id, run_type, status, started_at, completed_at,
items_fetched, items_new, items_updated, cursor_before, cursor_after,
error_message, duration_sec.

### items

The main data store. Every message and email from every service ends up here
in a common schema. Primary key is SERVICE_ID:SOURCE_ID so upserts are natural.

Fields: id, service_id, item_type, source_id, thread_id, conversation, sender,
sender_is_me, recipients (JSON array), subject, body_plain, body_html,
attachments (JSON array), labels (JSON array), metadata (JSON blob),
source_ts, fetched_at, sync_run_id.

item_type is one of: email, message, page, db_row.

thread_id groups messages into threads across services (e.g. "telegram:12345",
"gmail:thread_abc").

sender_is_me is a boolean flag indicating whether I sent or authored this item.

Indexes on: service_id, source_ts descending, item_type, thread_id, and a
composite index on sender_is_me plus source_ts for fast "things I said" queries.

### items_fts

An FTS5 virtual table mirroring the subject, body_plain, sender, and
conversation columns from items. Kept in sync via insert/delete/update
triggers. Enables instant full-text search across all services.

### documents

Notion pages are stored as full markdown documents in SQLite (not on disk).
Each document holds the complete page content with content-hash dedup and
version tracking.

Fields: id, service_id, source_id, title, body_markdown, content_hash,
version, hidden, metadata (JSON), source_ts, fetched_at, sync_run_id.
UNIQUE(service_id, source_id).

The `hidden` column (integer, default 0) enables soft-delete: hidden documents
are excluded from API results by default but persist across syncs and can be
unhidden at any time.

Indexes on: service_id, source_ts descending.

### document_versions

Stores prior versions of documents when content changes. On each sync, if the
content hash differs from the stored hash, the current content is snapshotted
here before the document is updated.

Fields: id, document_id (FK), version, body_markdown, content_hash, source_ts,
created_at.

Index on: document_id + version descending.

### documents_fts

FTS5 virtual table on title and body_markdown from documents. Kept in sync
via insert/delete/update triggers. Enables full-text search across all pages.


## Service Details


### 1. Notion ✅ COMPLETE

Library: notion-client
Auth type: api_key
Status: Fully implemented and working

Auth flow:
  User creates an internal integration at notion.so/my-integrations and copies
  the token. User pastes it into the Backchannel dashboard. We verify it with
  a test API call. User must also share each top-level page with the
  integration from within Notion itself (this is a Notion requirement).

Initial sync:
  Use the search endpoint to discover all pages the integration can access.
  For each page, recursively fetch block children to get the full content tree
  (max_depth configurable, default 5). Child pages and child databases are NOT
  recursed into — they are fetched independently as standalone documents.
  Pagination handled via start_cursor.

Filters applied during sync:
  - Skip archived or trashed pages
  - Skip untitled pages (no title property)
  - Skip pages with empty body content after markdown conversion

Incremental sync:
  Search returns all pages. Pages not edited since the stored cursor are
  skipped for content re-download but still tracked for deletion detection.
  All live source_ids are collected; any DB documents whose source_id is no
  longer present are deleted (handles pages trashed in Notion).

Soft-delete:
  Documents can be hidden via the UI (hidden column). Hidden documents are
  excluded from API by default, and preserved across syncs (the hidden flag
  is never touched by sync logic).

Normalization:
  Pages become documents (not items) with full markdown content stored in
  the body_markdown column. Block types converted: paragraphs, headings,
  lists (bulleted, numbered, to-do), toggles, code blocks, quotes, callouts,
  dividers, images, bookmarks, tables, child_page references, child_database
  references.

Performance:
  Initial full sync: ~60 seconds for 36 pages.
  Incremental sync: ~3 seconds (skips content download, still detects deletions).


### 2. Telegram ✅ COMPLETE

Library: telethon
Auth type: phone_code
Status: Fully implemented and working

Prerequisites:
  User registers an app at my.telegram.org/apps and gets an api_id (integer)
  and api_hash (string). These are entered via the dashboard and stored in the
  database credentials JSON (not in .env).

Auth flow:
  User enters API ID, API Hash, and phone number in the Backchannel dashboard.
  Server sends a code request via Telethon. User receives a code in the
  Telegram app and enters it in the dashboard. If 2FA is enabled, a follow-up
  form asks for the password. A per-instance session file is saved to
  data/sessions/ and persists across restarts.

Initial sync:
  List all dialogs (private chats, groups, channels) via get_dialogs. For each
  dialog, iterate messages with a cap of 200 per dialog. Telethon handles
  pagination internally. Store each message with the chat name, sender name,
  text content, timestamp, and media info.

Dialog filters:
  - Skip archived dialogs
  - Skip bots
  - Skip broadcast channels (keep supergroups)
  - Skip forbidden/deleted chats
  - Skip inactive dialogs (no messages within sync window, default 365 days)
  - Skip dialogs where user never replied (checks first 50 messages)

Rate limiting:
  Proactive delays: 1s between dialogs, 0.5s after reply-check requests.
  Telethon auto-sleeps on any remaining Telegram FloodWaitError.

Preview sync:
  Dry-run mode (preview_sync()) returns dialog summary without writing to DB.

Incremental sync:
  For each dialog, request messages with min_id set to the last seen message
  ID for that chat. Only new messages are returned. Cursor is a JSON object
  with per-dialog message IDs and last_sync_ts.

Normalization:
  item_type is "message". Conversation is the chat or group title. Sender is
  the entity display name. sender_is_me is 1 if the sender matches the
  authenticated Telegram user. thread_id is "telegram:{chat_id}". Metadata
  includes message ID, chat ID, reply-to ID, forwarding info, and media type.


### 3. Gmail ✅ COMPLETE

Library: imaplib (standard library)
Auth type: app_password (IMAP with App Password)
Status: Fully implemented and working

Prerequisites:
  User enables IMAP access in Gmail settings and generates an App Password
  from their Google account security settings.

Auth flow:
  User enters their Gmail address and App Password in the Backchannel
  dashboard. We test the connection by logging into imap.gmail.com and
  selecting INBOX. On success, credentials are stored in the database.

Initial sync:
  Connect to Gmail IMAP. Select [Gmail]/All Mail folder. Search for messages
  SINCE a configurable date (default 365 days). Fetch each message's full
  RFC822 body plus X-GM-THRID (Gmail thread ID) via IMAP extension. Parse
  with Python's email module. Run through content pipeline (HTML→markdown
  conversion, binary filtering, truncation). Cap at configurable max messages
  (default 100).

Incremental sync:
  Use the stored cursor (ISO timestamp) as the SINCE date for IMAP search.
  Only messages after that date are fetched. New cursor is set to current
  timestamp after successful sync.

Content pipeline (api/content.py):
  1. If HTML available → convert to markdown via markdownify
  2. If only plain text → light cleanup (normalize line endings, collapse blanks)
  3. Filter binary/garbage content (base64 blocks, hex blocks, low printable ratio)
  4. Truncate to 50K characters at paragraph/line boundaries

Service stats:
  get_stats() returns folder list with message counts, total messages in
  All Mail, oldest/newest message dates.

Normalization:
  item_type is "email". Subject from header. Sender from the From header.
  sender_is_me is 1 if the From address matches the configured email.
  Recipients built from To and Cc headers. thread_id is "gmail:{X-GM-THRID}".
  Conversation is the subject with Re:/Fwd: prefixes stripped. Attachments
  stored as metadata only (filename, content type, size — no binary content).


### 4. ProtonMail (planned)

Library: imapclient, mail-parser
Auth type: imap_login

Prerequisites:
  User must have a paid Proton plan and install Proton Mail Bridge on the Mac
  Mini. Bridge runs as a background app and exposes IMAP on 127.0.0.1 port
  1143. User copies the bridge-generated email address and password from the
  Bridge settings UI.

Auth flow:
  User enters the bridge email and bridge password in the Backchannel
  dashboard. We test the connection by connecting to localhost port 1143 with
  IMAPClient and listing folders. If it works, credentials are stored and
  status set to connected.

Initial sync:
  Connect to Bridge IMAP. For each folder (Inbox, Sent, Archive, etc), search
  for messages since a date 90 days ago. Fetch full RFC822 content for each
  UID. Parse with mail-parser to extract headers, plain text body, HTML body,
  and attachment metadata.

Incremental sync:
  For each folder, search for UIDs greater than the last stored UID. Only new
  messages are fetched.

Normalization:
  item_type is "email". Subject and sender from parsed headers. sender_is_me
  is 1 if the message is from a Sent folder or the From address matches the
  user. Recipients from To and Cc. Metadata includes the folder name, flags,
  and message-id header.


### 5. WhatsApp (planned)

Bridge: whatsapp-mcp Go binary (built on whatsmeow)
Auth type: qr_link

Prerequisites:
  Go toolchain installed (brew install go). Build the whatsapp-bridge binary
  from the whatsapp-mcp repository, or download a pre-built binary. The binary
  lives in the whatsapp-bridge/ directory.

Auth flow:
  User clicks Connect WhatsApp on the Backchannel dashboard. Server starts
  the Go bridge process if it is not already running. On first run the bridge
  outputs a QR code. Server captures the QR data and renders it in the
  dashboard using the qrcode Python library. The session lasts approximately
  20 days before re-authentication is needed.

Initial sync:
  When linked, the WhatsApp primary device sends a bundle of recent messages
  to the companion device. The bridge stores these automatically in its own
  SQLite database. Our puller reads from this database in read-only mode.

Incremental sync:
  The bridge runs continuously and captures all incoming and outgoing messages
  in real time into its SQLite database. Our puller simply queries for rows
  with a rowid greater than the last stored cursor.

Normalization:
  item_type is "message". Conversation is the chat JID mapped to a contact
  name where possible. Sender is the sender JID mapped to a contact name.
  sender_is_me is 1 if the sender matches our own WhatsApp JID. Metadata
  includes message ID, chat JID, sender JID, whether it is a group message,
  and any media type.


## Dashboard Pages

The frontend is a React SPA (Vite + React 19 + TypeScript) with React Router
for navigation and React Query for server state. The app shell includes a
collapsible sidebar with navigation links.

### Dashboard (/)

Stats overview showing total stored items, connected account count, and last
sync time. Connected accounts listed with item counts and last sync time.
Recent sync activity table showing the last 10 runs across all services.

### Accounts (/accounts)

Grid of connected service cards with stored count and last sync time. "Add
Account" button triggers a modal to create a new service instance by selecting
the service type and providing a display name.

### Account Detail (/accounts/:id)

Per-service management page. Connect/disconnect controls, rename, sync trigger,
clear data, view service stats (where supported). Recent sync history table.

### Documents (/docs)

Browse and search synced Notion pages. Search by title/content via the API's
`?q=` parameter. Grid of document cards with title and preview.

### Document Detail (/docs/:id)

Full rendered markdown view of a document using react-markdown + remark-gfm.

### Messages (/messages)

Conversation-grouped message view. Search across all messages via FTS. Service
filter pills. Drill into conversation threads.

### History (/history)

Full sync run log across all services with status, items fetched, duration, and
error messages.

### Logs (/logs)

Real-time log viewer with SSE streaming. Displays the in-memory log buffer and
streams new entries as they arrive.


## REST API Endpoints

All endpoints return JSON. Backend runs on port 8787. The frontend's Vite dev
server proxies `/api/*` to `http://localhost:8787`.

### Dashboard
  GET /api/dashboard             Stats, accounts, recent sync runs

### Services CRUD
  GET /api/services              List connected accounts
  GET /api/services/{id}         Account detail with sync history
  POST /api/services             Create new service instance (body: service_type, display_name)
  PATCH /api/services/{id}       Rename service (body: display_name)
  DELETE /api/services/{id}      Remove instance and all its data

### Service Actions
  POST /api/services/{id}/connect     Connect with credentials
  POST /api/services/{id}/disconnect  Disconnect
  POST /api/services/{id}/test        Test connection
  POST /api/services/{id}/sync        Trigger sync
  POST /api/services/{id}/clear       Clear synced data (keep credentials)
  GET /api/services/{id}/stats        Remote service stats (e.g. Gmail folder counts)

### Documents
  GET /api/documents             List docs (?q= for search)
  GET /api/documents/{id}        Single doc with full markdown body

### Messages
  GET /api/conversations         Conversation threads (?q= for search, ?limit=)
  GET /api/conversations/{name}  Messages in a thread (?service=, ?thread_id=, ?limit=)
  GET /api/messages              Flat message list (?q=, ?service=, ?limit=)

### History & Logs
  GET /api/history               Sync run log (?limit=)
  GET /api/logs                  In-memory log buffer
  GET /api/logs/stream           SSE real-time log stream


## Puller Architecture

All pullers inherit from a BasePuller abstract class (api/pullers/base.py)
that defines three methods:

  test_connection: Verifies that credentials are still valid. Returns true or
  raises an exception with a descriptive message.

  pull: Accepts a cursor (string or None) and a since date. If cursor is None
  this is an initial sync and the since date is used as the starting point. If
  cursor is present this is an incremental sync from that position. Returns a
  PullResult containing lists of normalized items and documents, an updated
  cursor, counts, and (for document-producing pullers) all_source_ids for
  deletion detection.

  normalize: Converts a raw service-specific response into the unified items
  schema. Must populate item_type, source_id, conversation, sender,
  sender_is_me, subject, body_plain, and source_ts. Optionally populates
  body_html, recipients, attachments, labels, metadata, and thread_id.

PullResult fields: items, documents, new_cursor, items_new, items_updated,
docs_new, docs_updated, all_source_ids.


## Daily Sync Flow

The daily_sync.py script is called by launchd at 06:00 each morning. It can
also be run manually.

Steps:
  1. Open database connection via init_db().
  2. Register pullers for each known service type.
  3. Query all services where enabled is true and status is connected.
  4. For each service:
     a. Call run_sync() from the service manager.
     b. run_sync creates a sync_runs record, calls the puller, upserts items,
        handles document versioning, runs deletion detection, and finalises
        the sync run with counts and duration.
     c. On exception, the sync run is marked as failed and the error is logged.
     d. Each service is committed independently so one failure does not block others.
  5. Log a summary of successes and failures.


## Process Management

Three long-running processes managed by macOS launchd (planned):

  com.backchannel.web.plist: The FastAPI backend. Runs on localhost port
  8787. KeepAlive set to true so it restarts if it crashes.

  com.backchannel.whatsapp.plist: The WhatsApp Go bridge. KeepAlive true.
  Working directory set to whatsapp-bridge/.

  com.backchannel.daily.plist: The daily sync script. Runs at 06:00 via
  StartCalendarInterval. Not kept alive, just triggered on schedule.


## Environment Variables

Stored in .env, loaded by python-dotenv. Service credentials are configured via
the web UI and stored in the database — only general settings go in .env.

  General: DATABASE_PATH, DASHBOARD_PORT, USER_EMAIL


## Open Questions

1. Should we store raw API responses alongside normalized items? Useful for
   debugging but doubles storage. Could add a raw_data field to items or use
   a separate table.

2. Attachment handling: download files to disk or just store metadata? Files
   are useful for AI ingestion but use more space. Could be a per-service
   config toggle.

3. WhatsApp bridge database schema needs to be confirmed by actually running
   the bridge and inspecting the SQLite file. Table and column names should be
   verified during implementation.

4. Rate limiting: Gmail has quota limits, Telegram has flood wait limits,
   Notion has rate limits. Each puller should implement basic backoff and
   retry. Telegram already has proactive delays; Gmail and Notion need similar.

5. Identifying "me" across services: store my email addresses, phone number,
   Telegram user ID, and WhatsApp JID in config. Check against these during
   normalization to set the sender_is_me flag reliably.
