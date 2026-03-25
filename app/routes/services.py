from datetime import datetime
from fasthtml.common import *
from app.db import get_db
from app.components.service_card import service_card
from app.components import alerts
from app.services import manager


def register(rt):

    @rt("/services/add")
    def get():
        """Redirect old add page to accounts page."""
        return RedirectResponse("/accounts", status_code=301)

    @rt("/services/create")
    def post(service_type: str, display_name: str):
        """Create a new service instance."""
        display_name = display_name.strip()
        if not display_name:
            return alerts.error("Account name is required.")
        try:
            new_id = manager.add_service_instance(service_type, display_name)
            return Div(
                alerts.success(f"Created {display_name}"),
                Script(f"setTimeout(function(){{ window.location='/accounts/{new_id}'; }}, 500);"),
            )
        except Exception as e:
            return alerts.error(str(e))

    @rt("/services/{service_id}/remove")
    def post(service_id: str):
        """Remove a service instance (not the base one)."""
        try:
            manager.remove_service_instance(service_id)
            return Div(
                alerts.success(f"Removed {service_id}"),
                Script("setTimeout(function(){ window.location='/'; }, 500);"),
            )
        except Exception as e:
            return alerts.error(str(e))

    @rt("/services/{service_id}")
    def get(service_id: str):
        """Redirect old service URLs to new accounts page."""
        return RedirectResponse(f"/accounts/{service_id}", status_code=301)

    @rt("/services/{service_id}/card")
    def get(service_id: str):
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return Div("Unknown service", cls="text-error text-sm")
        s = dict(service)
        items = db.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE service_id = ?", (service_id,)
        ).fetchone()["cnt"]
        docs = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE service_id = ? AND hidden = 0", (service_id,)
        ).fetchone()["cnt"]
        s["item_count"] = items + docs
        s["last_sync_ago"] = _humanize_time(s["last_sync_at"]) if s["last_sync_at"] else "Never"
        return service_card(s)


def _humanize_time(ts_str: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        delta = datetime.utcnow() - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''} ago"
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    except (ValueError, TypeError):
        return ts_str
