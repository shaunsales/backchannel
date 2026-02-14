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
            parts = [f"{run['items_fetched']} pages fetched"]
            if run["items_new"]:
                parts.append(f"{run['items_new']} new")
            if run["items_updated"]:
                parts.append(f"{run['items_updated']} updated")
            if run["duration_sec"]:
                parts.append(f"{run['duration_sec']:.1f}s")
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
