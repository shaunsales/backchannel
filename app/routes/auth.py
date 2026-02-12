from fasthtml.common import *
from app.components.layout import page
from app.components import alerts
from app.services import manager


def register(rt):

    @rt("/auth/{service_id}")
    def get(service_id: str):
        svc = manager.status(service_id)
        if svc is None:
            return page(alerts.error(f"Unknown service: {service_id}"), title="Error")

        return page(
            H2(f"Connect {svc['display_name']}", cls="text-2xl font-bold mb-6"),
            Div(
                Div(
                    P(f"Auth flow for {svc['display_name']} ({svc['auth_type']}) is not yet implemented.",
                      cls="text-sm opacity-70"),
                    P("This will be built in a later phase.", cls="text-sm opacity-50 mt-2"),
                    cls="card-body p-4",
                ),
                cls="card bg-base-200 shadow-sm",
            ),
            title=f"Connect {svc['display_name']}",
        )

    @rt("/auth/{service_id}/disconnect")
    def post(service_id: str):
        try:
            manager.disconnect(service_id)
            return alerts.success(f"Disconnected {service_id}")
        except Exception as e:
            return alerts.error(str(e))
