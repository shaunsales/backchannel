from fasthtml.common import *
from app.components.layout import page
from app.components import alerts
from app.components.auth_forms import notion_auth_form
from app.services import manager


AUTH_FORMS = {
    "notion": notion_auth_form,
}


def register(rt):

    @rt("/auth/{service_id}")
    def get(service_id: str):
        svc = manager.status(service_id)
        if svc is None:
            return page(alerts.error(f"Unknown service: {service_id}"), title="Error")

        form_fn = AUTH_FORMS.get(service_id)
        if form_fn:
            form = form_fn(svc)
        else:
            form = Div(
                P(f"Auth flow for {svc['display_name']} ({svc['auth_type']}) is not yet implemented.",
                  cls="text-sm opacity-70"),
                P("This will be built in a later phase.", cls="text-sm opacity-50 mt-2"),
            )

        return page(
            H2(f"Connect {svc['display_name']}", cls="text-lg font-semibold mb-4"),
            Div(
                Div(form, cls="card-body p-5"),
                cls="card bg-base-200/50 border border-base-content/5",
            ),
            title=f"Connect {svc['display_name']}",
        )

    @rt("/auth/notion/connect")
    def post(token: str):
        try:
            manager.connect("notion", {"token": token})
            ok, msg = manager.test("notion")
            if not ok:
                manager.disconnect("notion")
                return Div(
                    alerts.error(f"Connection failed: {msg}"),
                    notion_auth_form(manager.status("notion")),
                    id="notion-auth-area",
                )
            svc = manager.status("notion")
            return notion_auth_form(svc)
        except Exception as e:
            manager.disconnect("notion")
            return Div(
                alerts.error(str(e)),
                notion_auth_form(manager.status("notion")),
                id="notion-auth-area",
            )

    @rt("/auth/notion/test")
    def post():
        try:
            ok, msg = manager.test("notion")
            if ok:
                return alerts.success("Connection successful")
            return alerts.error(f"Test failed: {msg}")
        except Exception as e:
            return alerts.error(str(e))

    @rt("/auth/notion/disconnect")
    def post():
        manager.disconnect("notion")
        svc = manager.status("notion")
        return notion_auth_form(svc)

    @rt("/auth/{service_id}/disconnect")
    def post(service_id: str):
        try:
            manager.disconnect(service_id)
            return alerts.success(f"Disconnected {service_id}")
        except Exception as e:
            return alerts.error(str(e))
