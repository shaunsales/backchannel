from fasthtml.common import *
from app.db import get_db
from app.components.layout import page
from app.components.service_card import service_card
from app.components.sync_table import sync_history_table


def register(rt):

    @rt("/")
    def get():
        db = get_db()

        services = db.execute("SELECT * FROM services ORDER BY id").fetchall()

        item_counts = {
            r["service_id"]: r["cnt"]
            for r in db.execute(
                "SELECT service_id, COUNT(*) as cnt FROM items GROUP BY service_id"
            ).fetchall()
        }

        service_dicts = []
        for s in services:
            d = dict(s)
            d["item_count"] = item_counts.get(d["id"], 0)
            service_dicts.append(d)

        recent_runs = db.execute(
            "SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()

        total_items = db.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        connected = sum(1 for s in services if s["status"] == "connected")
        last_sync = db.execute(
            "SELECT MAX(started_at) as ts FROM sync_runs"
        ).fetchone()["ts"] or "Never"

        stats = Div(
            Div(
                Div(Span(str(total_items), cls="text-2xl font-bold font-mono"), Span("Total Items", cls="text-xs opacity-50"), cls="flex flex-col items-center"),
                Div(Span(f"{connected}/5", cls="text-2xl font-bold font-mono"), Span("Connected", cls="text-xs opacity-50"), cls="flex flex-col items-center"),
                Div(Span(last_sync, cls="text-sm font-mono"), Span("Last Sync", cls="text-xs opacity-50"), cls="flex flex-col items-center"),
                cls="stats shadow bg-base-200 w-full",
            ),
            cls="mb-6",
        )

        cards = Div(
            *[service_card(s) for s in service_dicts],
            cls="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8",
        )

        history = Div(
            H3("Recent Activity", cls="text-lg font-semibold mb-3"),
            sync_history_table(recent_runs),
        )

        return page(stats, cards, history, title="Dashboard")
