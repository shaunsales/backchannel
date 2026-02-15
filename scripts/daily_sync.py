#!/usr/bin/env python3
"""
Backchannel daily sync — headless entry point.

Runs all connected services sequentially. Designed to be called from
launchd, cron, or manually:

    python scripts/daily_sync.py
"""
import sys
import logging
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import init_db, get_db
from app.services.manager import register_puller, run_sync
from app.pullers.notion import NotionPuller

# Configure logging
LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "sync.log"),
    ],
)
log = logging.getLogger("daily_sync")


def main():
    log.info("Starting daily sync")

    init_db()
    register_puller("notion", NotionPuller)

    db = get_db()
    services = db.execute(
        "SELECT id, display_name FROM services WHERE enabled = 1 AND status = 'connected'"
    ).fetchall()

    if not services:
        log.info("No connected services to sync")
        return

    log.info("Found %d connected service(s)", len(services))

    successes = 0
    failures = 0

    for svc in services:
        sid = svc["id"]
        name = svc["display_name"]
        try:
            log.info("Syncing %s...", name)
            result = run_sync(sid, run_type="scheduled")
            deleted = result.get("docs_deleted", 0)
            log.info("%s sync complete (run_id=%d, deleted=%d)", name, result["run_id"], deleted)
            successes += 1
        except Exception as e:
            log.error("%s sync failed: %s", name, e, exc_info=True)
            failures += 1

    log.info("Daily sync finished: %d succeeded, %d failed", successes, failures)


if __name__ == "__main__":
    main()
