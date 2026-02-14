from fasthtml.common import *
from app.db import get_db
from app.services import manager
from app.components.service_card import service_card
from app.components import alerts


def register(rt):

    @rt("/sync/{service_id}")
    def post(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return alerts.error(f"Unknown service: {service_id}")

        if service["status"] != "connected":
            return alerts.warning(
                f"{service['display_name']} is not connected. Please connect it first."
            )

        try:
            result = manager.run_sync(service_id, run_type="manual")
            run = db.execute(
                "SELECT items_fetched, items_new, items_updated, duration_sec FROM sync_runs WHERE id = ?",
                (result["run_id"],)
            ).fetchone()
            deleted = result.get("docs_deleted", 0)
            fetched = run["items_fetched"]
            new = run["items_new"]
            updated = run["items_updated"]
            duration = run["duration_sec"]

            if not fetched and not new and not updated and not deleted:
                msg = f"{service['display_name']} — all documents up to date"
                if duration:
                    msg += f" ({duration:.1f}s)"
                return alerts.success(msg)

            parts = []
            if fetched:
                parts.append(f"{fetched} pages fetched")
            if new:
                parts.append(f"{new} new")
            if updated:
                parts.append(f"{updated} updated")
            if deleted:
                parts.append(f"{deleted} removed")
            if duration:
                parts.append(f"{duration:.1f}s")
            return alerts.success(
                f"{service['display_name']} sync complete — {', '.join(parts)}"
            )
        except Exception as e:
            return alerts.error(f"Sync failed: {e}")

    @rt("/sync/all")
    def post():
        db = get_db()
        services = db.execute(
            "SELECT * FROM services WHERE enabled = 1 AND status = 'connected'"
        ).fetchall()

        if not services:
            return alerts.warning("No connected services to sync.")

        results = []
        for s in services:
            try:
                r = manager.run_sync(s["id"], run_type="manual")
                results.append(f"{s['display_name']}: {r['items']} items")
            except Exception as e:
                results.append(f"{s['display_name']}: failed — {e}")

        return alerts.success("Sync complete: " + "; ".join(results))
