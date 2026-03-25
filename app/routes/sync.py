import json
import asyncio
import threading
from starlette.responses import StreamingResponse
from fasthtml.common import *
from app.db import get_db
from app.services import manager
from app.components.service_card import service_card
from app.components import alerts
from app import logstream


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

    @rt("/sync/{service_id}/preview")
    def post(service_id: str):
        """Dry-run preview: show what would be synced without writing to DB."""
        try:
            puller = manager.get_puller(service_id)
            if not hasattr(puller, "preview_sync"):
                return alerts.warning(f"Preview not available for {service_id}")

            results = puller.preview_sync()
            to_sync = [r for r in results if r["status"] == "sync"]
            skipped = [r for r in results if r["status"] == "skip"]

            rows = []
            for r in to_sync:
                rows.append(Tr(
                    Td(r["name"], cls="text-sm"),
                    Td(Span(r["type"], cls="badge badge-sm badge-ghost"), cls="text-xs"),
                    Td(str(r["messages"]), cls="font-mono text-sm"),
                    Td(r.get("last_active", ""), cls="text-xs opacity-60"),
                ))
            for r in skipped:
                rows.append(Tr(
                    Td(r["name"], cls="text-sm opacity-40"),
                    Td(Span(r["type"], cls="badge badge-sm badge-ghost opacity-40")),
                    Td("—", cls="opacity-40"),
                    Td(r["reason"], cls="text-xs opacity-40"),
                ))

            total_msgs = sum(r["messages"] for r in to_sync)
            summary = f"Will sync {len(to_sync)} dialogs (~{total_msgs:,} messages). {len(skipped)} skipped."

            return Div(
                Div(alerts.success(summary), cls="mb-3"),
                Table(
                    Thead(Tr(Th("Dialog"), Th("Type"), Th("Messages"), Th("Info"))),
                    Tbody(*rows),
                    cls="table table-sm table-zebra",
                ),
                cls="overflow-x-auto",
            )
        except Exception as e:
            return alerts.error(f"Preview failed: {e}")

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

    @rt("/sync/{service_id}/stream")
    async def get(service_id: str):
        """SSE endpoint: runs sync in a background thread and streams log lines."""
        db = get_db()
        service = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if service is None:
            return alerts.error(f"Unknown service: {service_id}")

        queue: asyncio.Queue = asyncio.Queue()
        done_event = asyncio.Event()
        result_holder = {}

        def on_log(entry):
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

        def run_sync():
            try:
                r = manager.run_sync(service_id, run_type="manual")
                from app.db import get_db as _get_db
                _db = _get_db()
                run = _db.execute(
                    "SELECT items_fetched, items_new, items_updated, duration_sec FROM sync_runs WHERE id = ?",
                    (r["run_id"],)
                ).fetchone()
                deleted = r.get("docs_deleted", 0)
                fetched = run["items_fetched"]
                new = run["items_new"]
                updated = run["items_updated"]
                duration = run["duration_sec"]

                if not fetched and not new and not updated and not deleted:
                    msg = f"All up to date"
                    if duration:
                        msg += f" ({duration:.1f}s)"
                    result_holder["status"] = "success"
                    result_holder["message"] = msg
                else:
                    parts = []
                    if fetched:
                        parts.append(f"{fetched} fetched")
                    if new:
                        parts.append(f"{new} new")
                    if updated:
                        parts.append(f"{updated} updated")
                    if deleted:
                        parts.append(f"{deleted} removed")
                    if duration:
                        parts.append(f"{duration:.1f}s")
                    result_holder["status"] = "success"
                    result_holder["message"] = f"Sync complete — {', '.join(parts)}"
            except Exception as e:
                result_holder["status"] = "error"
                result_holder["message"] = f"Sync failed: {e}"
            finally:
                done_event.set()

        logstream.subscribe(on_log)

        async def event_generator():
            try:
                # Start sync in background thread
                thread = threading.Thread(target=run_sync, daemon=True)
                thread.start()

                yield f"data: {json.dumps({'type': 'start', 'msg': 'Starting sync...'})}\n\n"

                while not done_event.is_set():
                    try:
                        entry = await asyncio.wait_for(queue.get(), timeout=0.5)
                        yield f"data: {json.dumps({'type': 'log', 'msg': entry['msg'], 'level': entry['level']})}\n\n"
                    except asyncio.TimeoutError:
                        pass

                # Drain remaining log entries
                while not queue.empty():
                    try:
                        entry = queue.get_nowait()
                        yield f"data: {json.dumps({'type': 'log', 'msg': entry['msg'], 'level': entry['level']})}\n\n"
                    except asyncio.QueueEmpty:
                        break

                yield f"data: {json.dumps({'type': 'done', 'status': result_holder.get('status', 'error'), 'msg': result_holder.get('message', 'Unknown error')})}\n\n"
            finally:
                logstream.unsubscribe(on_log)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
