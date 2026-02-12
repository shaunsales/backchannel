from fasthtml.common import *
from app.config import DASHBOARD_PORT

# Tailwind CSS 4 + DaisyUI 4 via CDN
tailwind_css = Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css")
tailwind_script = Script(src="https://cdn.tailwindcss.com/4.1")

hdrs = (
    Meta(charset="utf-8"),
    Meta(name="viewport", content="width=device-width, initial-scale=1"),
    tailwind_css,
    tailwind_script,
    Title("Backchannel"),
)

app, rt = fast_app(hdrs=hdrs, live=True)


@rt("/")
def get():
    return Div(
        Div(
            H1("Backchannel", cls="text-4xl font-bold"),
            P("Local-first daily data sync", cls="text-lg opacity-70"),
            cls="text-center py-12",
        ),
        Div(
            Div(
                Div("Status", cls="card-title"),
                P("All systems operational.", cls="text-sm opacity-70"),
                cls="card-body",
            ),
            cls="card bg-base-200 shadow-md max-w-md mx-auto",
        ),
        cls="container mx-auto p-8",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=DASHBOARD_PORT, reload=True)
