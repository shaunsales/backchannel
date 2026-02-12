# PLAN.md — Backchannel

## Overview

Backchannel is a local-first daily data sync app that pulls messages, emails,
notes, and pages from 5 services into a unified SQLite database. Runs on a Mac
Mini. Includes a web dashboard for auth management, monitoring, and manual sync
triggers.

Core loop: Every morning at 06:00, Backchannel pulls everything new from all
connected services, stores it in a unified items table, ready for AI agent
ingestion.


## Tech Stack

Web framework:      FastHTML (Python-native HTML, HTMX built-in, no templates)
CSS:                Tailwind CSS 4 and DaisyUI 4 via CDN
Interactivity:      HTMX (bundled with FastHTML)
Database:           SQLite via sqlite3 (single file, FTS5 for search)
Scheduler:          macOS launchd (native, survives reboots)
WhatsApp bridge:    Go binary built on whatsmeow (whatsapp-mcp project)
ProtonMail access:  Proton Mail Bridge (user installs, exposes IMAP on localhost)


## Python Dependencies

python-fasthtml
notion-client
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
telethon
imapclient
mail-parser
python-dotenv
qrcode[pil]


## Project Structure

backchannel/
  app/
    __init__.py
    main.py                     FastHTML app, mounts all routes
    config.py                   Reads .env, exposes settings
    db.py                       get_db(), init_db(), migrations

    components/                 Reusable Python-to-HTML components
      __init__.py
      layout.py                 page(), nav_bar() base shell
      service_card.py           service_card(service) status card
      sync_table.py             sync_history_table(rows) run log
      alerts.py                 success(), error(), warning() banners
      auth_forms.py             Per-service auth UI components

    routes/                     FastHTML route handlers
      __init__.py
      dashboard.py              GET /
      services.py               GET /services/SERVICE_ID and GET /services/SERVICE_ID/card
      auth.py                   Auth flows per service
      sync.py                   POST /sync/SERVICE_ID and POST /sync/all
      history.py                GET /history

    pullers/                    Data pull engines, one per service
      __init__.py
      base.py                   BasePuller ABC and PullResult dataclass
      notion.py
      gmail.py
      telegram.py
      protonmail.py
      whatsapp.py

    services/                   Service lifecycle management
      __init__.py
      manager.py                connect(), disconnect(), test(), status()

  whatsapp-bridge/              Git-ignored, user builds or downloads
    whatsapp-bridge             Compiled Go binary
    store/
      messages.db               Bridge own SQLite (read-only by our app)

  data/
    backchannel.db              Main SQLite database
    sessions/                   Telegram .session files
    tokens/                     Gmail token.json and credentials.json
    logs/

  scripts/
    setup.sh                    Full setup: brew, venv, deps, init db
    daily_sync.py               Entry point called by launchd
    com.backchannel.daily.plist
    com.backchannel.web.plist
    com.backchannel.whatsapp.plist

  requirements.txt
  .env
  .env.example
  PLAN.md
  README.md


## Data Model

### services

One row per service (5 total, seeded on first run). Tracks connection status,
stores credentials as a JSON blob, and holds the sync cursor that each puller
uses to know where it left off.

Fields: id, display_name, status, auth_type, credentials (JSON), config (JSON),
enabled, last_sync_at, sync_cursor, created_at, updated_at.

Status is one of: connected, disconnected, auth_required, error, syncing.

Auth type is one of: api_key (Notion), oauth2 (Gmail), phone_code (Telegram),
imap_login (ProtonMail), qr_link (WhatsApp).

The sync cursor is a string whose format varies by service:
  - Gmail: a historyId string
  - Telegram: JSON mapping chat IDs to last message IDs
  - Notion: ISO timestamp of last edited time
  - ProtonMail: JSON mapping folder names to last UIDs
  - WhatsApp: integer rowid from the bridge database

Seed data inserted on first run:
  notion      Notion       api_key
  gmail       Gmail        oauth2
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

The main data store. Every message, email, page, and database row from every
service ends up here in a common schema. Primary key is SERVICE_ID:SOURCE_ID
so upserts are natural.

Fields: id, service_id, item_type, source_id, conversation, sender,
sender_is_me, recipients (JSON array), subject, body_plain, body_html,
attachments (JSON array), labels (JSON array), metadata (JSON blob),
source_ts, fetched_at, sync_run_id.

item_type is one of: email, message, page, db_row.

sender_is_me is a boolean flag indicating whether I sent or authored this item.
This is critical for the AI agent to extract my own todos and commitments.

Indexes on: service_id, source_ts descending, item_type, and a composite
index on sender_is_me plus source_ts for fast "things I said" queries.

### items_fts

An FTS5 virtual table mirroring the subject, body_plain, sender, and
conversation columns from items. Kept in sync via insert/delete/update
triggers. Enables instant full-text search across all services.


## Service Details


### 1. Notion

Library: notion-client
Auth type: api_key

Auth flow:
  User creates an internal integration at notion.so/my-integrations and copies
  the token. User pastes it into the Backchannel dashboard. We verify it with
  a test API call. User must also share each top-level page with the
  integration from within Notion itself (this is a Notion requirement).

Initial sync:
  Use the search endpoint to discover all pages and databases the integration
  can access. For each page, recursively fetch block children to get the full
  content tree. For each database, query all rows. Use the
  collect_paginated_api helper to handle pagination. Only sync items with
  last_edited_time within the last 90 days.

Incremental sync:
  Search with a filter on last_edited_time greater than the stored cursor.
  Only re-fetch pages and databases that changed. Update cursor to current
  timestamp after success.

Normalization:
  Pages become item_type "page" with the title as subject and block content
  concatenated as body_plain. Database rows become item_type "db_row" with
  properties stored in metadata. sender_is_me is always 1 since it is your
  own workspace.


### 2. Gmail

Library: google-api-python-client, google-auth-oauthlib
Auth type: oauth2

Prerequisites:
  User creates a Google Cloud project, enables the Gmail API, creates OAuth
  credentials (Desktop app type), and downloads a credentials.json file. This
  file goes in data/tokens/. Required scope: gmail.readonly.

Auth flow:
  User clicks Connect Gmail on the Backchannel dashboard. Server starts the
  OAuth flow using InstalledAppFlow. Browser opens the Google consent screen.
  On approval, tokens are saved to data/tokens/token.json. The refresh token
  is also stored in the services credentials JSON so we can refresh without
  re-auth.

Initial sync:
  List messages using the Gmail API with a date query (e.g. after:2024/11/01).
  Paginate through all matching message IDs. For each ID, fetch the full
  message including headers (From, To, Cc, Subject, Date), body parts
  (prefer text/plain, fall back to text/html), label list, and attachment
  metadata. Use batch requests where possible for speed.

Incremental sync:
  Call the history endpoint with the stored historyId as the starting point.
  This returns only message IDs that were added, deleted, or had labels
  changed since that point. Fetch full content only for new or changed
  messages. This is very fast for daily runs.

Normalization:
  item_type is "email". Subject from header. Sender from the From header.
  sender_is_me is 1 if the From address matches the authenticated user.
  Recipients built from To and Cc. Labels from the Gmail label list.


### 3. Telegram

Library: telethon
Auth type: phone_code

Prerequisites:
  User registers an app at my.telegram.org/apps and gets an api_id (integer)
  and api_hash (string). These go in the .env file.

Auth flow:
  User enters their phone number in the Backchannel dashboard. Server sends a
  code request via Telethon. User receives a code in the Telegram app and
  enters it in the dashboard. If 2FA is enabled, a follow-up form asks for
  the password. A session file is saved to data/sessions/ and persists across
  restarts. No need to re-authenticate unless the session is revoked.

Initial sync:
  List all dialogs (private chats, groups, channels) via get_dialogs. For each
  dialog, iterate messages using get_messages with an offset_date of 90 days
  ago. Telethon handles pagination internally. Store each message with the
  chat name, sender name, text content, timestamp, and media info.

Incremental sync:
  For each dialog, request messages with min_id set to the last seen message
  ID for that chat. Only new messages are returned. Very efficient since
  Telegram message IDs are sequential per chat.

Normalization:
  item_type is "message". Conversation is the chat or group title. Sender is
  the first name plus last name or username. sender_is_me is 1 if the sender
  matches the authenticated Telegram user. Metadata includes message ID,
  reply-to ID, forwarding info, and media type.


### 4. ProtonMail

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
  messages are fetched. Very efficient for daily runs since typically only a
  handful of new messages per day.

Normalization:
  item_type is "email". Subject and sender from parsed headers. sender_is_me
  is 1 if the message is from a Sent folder or the From address matches the
  user. Recipients from To and Cc. Metadata includes the folder name, flags,
  and message-id header.


### 5. WhatsApp

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
  dashboard using the qrcode Python library. The QR display auto-refreshes
  via HTMX polling every 2 seconds until the user scans it with their phone.
  Once scanned, the bridge confirms authentication and begins receiving
  messages. The session lasts approximately 20 days before re-authentication
  is needed.

Initial sync:
  When linked, the WhatsApp primary device sends a bundle of recent messages
  to the companion device. The bridge stores these automatically in its own
  SQLite database. Our puller reads from this database in read-only mode. The
  amount of history depends on what WhatsApp sends, typically a few months of
  active chats.

Incremental sync:
  The bridge runs continuously and captures all incoming and outgoing messages
  in real time into its SQLite database. Our puller simply queries for rows
  with a rowid greater than the last stored cursor. This is the simplest of
  all five pullers.

Normalization:
  item_type is "message". Conversation is the chat JID mapped to a contact
  name where possible. Sender is the sender JID mapped to a contact name.
  sender_is_me is 1 if the sender matches our own WhatsApp JID. Metadata
  includes message ID, chat JID, sender JID, whether it is a group message,
  and any media type.

Bridge management:
  The Backchannel dashboard shows whether the bridge process is running or
  stopped with start and stop buttons. Bridge stdout and stderr are captured
  to the logs directory. Health check verifies the process is alive and the
  messages database is being written to.


## Dashboard Pages


### Landing Page (GET /)

Top section: overall stats bar showing total items across all services, number
of services connected out of 5, and time of last full sync.

Middle section: 5 service cards in a responsive grid (1 column on mobile, 2
on tablet, 3 on desktop). Each card shows the service icon and name, status
badge (connected, disconnected, error, syncing), last sync time, item count,
last sync duration, and an action button (Sync Now if connected, Connect if
not). Cards auto-refresh via HTMX polling every 30 seconds.

Bottom section: recent sync activity table showing the last 10 sync runs
across all services with columns for service name, run type, status, items
fetched, duration, and timestamp. Links to the full history page.


### Service Detail Page (GET /services/SERVICE_ID)

Connection section: current status with a large badge, the auth form specific
to this service (API key input for Notion, OAuth button for Gmail, phone and
code form for Telegram, email and password form for ProtonMail, QR code
display for WhatsApp), connect and disconnect buttons, and a test connection
button.

Configuration section: enable/disable toggle, service-specific settings such
as which Notion pages to sync or which Gmail labels to include, and a sync
window setting controlling how far back the initial sync goes (default 90
days).

Sync section: a Sync Now button with a progress indicator, the current cursor
value for debugging, and a table of the last 20 sync runs for this service.


### Sync History Page (GET /history)

Full paginated table of all sync runs across all services. Columns: ID,
service name, run type, status, started, completed, items fetched, items new,
duration, and error message. Filterable by service and by status. Sorted by
date descending.


### HTMX Partial Endpoints

These return HTML fragments rather than full pages and are used by HTMX for
in-place updates without page reloads:

  GET /services/SERVICE_ID/card     Returns just one service card (for polling)
  POST /sync/SERVICE_ID             Triggers sync, returns updated card
  POST /sync/all                    Triggers all services, returns status banner
  GET /history/table?page=N         Returns table rows for pagination


## Puller Architecture

All five pullers inherit from a BasePuller abstract class that defines three
methods:

  test_connection: Verifies that credentials are still valid. Returns true or
  raises an exception with a descriptive message.

  pull: Accepts a cursor (string or None) and a since date. If cursor is None
  this is an initial sync and the since date is used as the starting point. If
  cursor is present this is an incremental sync from that position. Returns a
  PullResult containing a list of normalized item dicts, an updated cursor,
  and counts of new and updated items.

  normalize: Converts a raw service-specific response into the unified item
  schema. Must populate item_type, source_id, conversation, sender,
  sender_is_me, subject, body_plain, and source_ts. Optionally populates
  body_html, recipients, attachments, labels, and metadata.


## Daily Sync Flow

The daily_sync.py script is called by launchd at 06:00 each morning. It can
also be triggered manually from the Backchannel dashboard.

Steps:
  1. Open database connection.
  2. Query all services where enabled is true and status is connected.
  3. For each service:
     a. Instantiate the appropriate puller.
     b. Create a sync_runs record with status running.
     c. Call the puller pull method with the stored cursor.
     d. Upsert each returned item into the items table.
     e. Update the service sync_cursor and last_sync_at.
     f. Finalize the sync_runs record with counts, duration, and status.
     g. On exception, mark the sync run as failed and store the error message.
     h. Commit after each service so one failure does not roll back others.
  4. Write a summary to the log file.


## Process Management

Three long-running processes managed by macOS launchd:

  com.backchannel.web.plist: The FastHTML dashboard. Runs on localhost port
  8787. KeepAlive set to true so it restarts if it crashes.

  com.backchannel.whatsapp.plist: The WhatsApp Go bridge. KeepAlive true.
  Working directory set to whatsapp-bridge/.

  com.backchannel.daily.plist: The daily sync script. Runs at 06:00 via
  StartCalendarInterval. Not kept alive, just triggered on schedule.

All three plists live in the scripts/ directory and get symlinked or copied
to ~/Library/LaunchAgents/ during setup.


## Environment Variables

Stored in .env, loaded by python-dotenv:

  General: database path, dashboard port, user email address
  Notion: integration token
  Gmail: paths to credentials.json and token.json
  Telegram: api_id, api_hash, phone number, session file path
  ProtonMail: bridge host, bridge port, bridge email, bridge password
  WhatsApp: path to bridge binary, path to bridge messages database


## Build Order

Phase 1 - Foundation:
  FastHTML app scaffold with main.py, config.py, db.py. Create the SQLite
  schema and seed the 5 service rows. Build the layout component (page shell
  with Backchannel branding, nav bar). Build the dashboard landing page with
  5 placeholder service cards showing disconnected status. Verify it runs and
  looks right on localhost:8787.

Phase 2 - Telegram (easiest service):
  Implement the Telegram puller. Build the phone number and code input forms
  on the service detail page. Test initial sync with a 90 day window. Test
  incremental sync by message ID. Verify items land in the database and the
  dashboard card updates with real counts.

Phase 3 - Gmail (most data):
  Implement the Gmail puller. Build the OAuth flow with browser redirect and
  callback handler. Handle token storage and refresh. Test initial sync with
  a date query. Test incremental sync via the history endpoint. Parse email
  bodies and attachment metadata.

Phase 4 - ProtonMail:
  Implement the ProtonMail puller. Build the IMAP credential form. Test
  connection to Proton Bridge. Sync across all folders. Test incremental
  sync by UID.

Phase 5 - Notion:
  Implement the Notion puller. Build the API key input form. Handle recursive
  block fetching and database row fetching. Handle pagination. Test
  incremental sync by last_edited_time.

Phase 6 - WhatsApp:
  Build or download the whatsapp-bridge Go binary. Implement bridge process
  management (start, stop, health check). Build the QR code display with HTMX
  polling. Implement the puller that reads from the bridge SQLite database.
  Test incremental sync by rowid.

Phase 7 - Polish:
  Sync history page with filtering and pagination. Error handling and retry
  logic in pullers. Rate limit handling (Gmail quotas, Telegram flood waits,
  Notion rate limits). Logging improvements. The setup.sh script. All three
  launchd plist files. README with full setup instructions.


## Open Questions

1. Should we store raw API responses alongside normalized items? Useful for
   debugging but doubles storage. Could add a raw_data field to items or use
   a separate table.

2. Attachment handling: download files to disk or just store metadata? Files
   are useful for AI ingestion but use more space. Could be a per-service
   config toggle.

3. WhatsApp bridge database schema needs to be confirmed by actually running
   the bridge and inspecting the SQLite file. Table and column names should be
   verified during Phase 6.

4. Gmail batch API is worth implementing for initial sync speed but adds
   complexity. Start with sequential fetches and optimize later if needed.

5. Notion content depth: how many levels deep to recurse into nested blocks.
   Suggest a configurable max_depth defaulting to 5 levels.

6. Rate limiting: Gmail has quota limits, Telegram has flood wait limits,
   Notion has rate limits. Each puller should implement basic backoff and
   retry. Start simple and add sophistication as needed.

7. Identifying "me" across services: store my email addresses, phone number,
   Telegram user ID, and WhatsApp JID in config. Check against these during
   normalization to set the sender_is_me flag reliably.