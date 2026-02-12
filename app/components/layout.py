from fasthtml.common import *


daisyui_css = Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css")
tailwind_script = Script(src="https://cdn.tailwindcss.com")


def head_tags():
    return (
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        daisyui_css,
        tailwind_script,
        Title("Backchannel"),
    )


def sidebar():
    return Nav(
        Ul(
            Li(A("Dashboard", href="/", cls="font-medium")),
            Li(A("History", href="/history", cls="font-medium")),
            Li(Div("Services", cls="menu-title text-xs uppercase tracking-wider opacity-50 mt-4")),
            Li(A("Notion", href="/services/notion")),
            Li(A("Gmail", href="/services/gmail")),
            Li(A("Telegram", href="/services/telegram")),
            Li(A("ProtonMail", href="/services/protonmail")),
            Li(A("WhatsApp", href="/services/whatsapp")),
            cls="menu gap-0.5",
        ),
        cls="w-56 min-h-screen bg-base-200 p-4 pt-20",
    )


def header(title="Dashboard"):
    return Div(
        Div(
            Span("Backchannel", cls="text-lg font-bold tracking-tight"),
            cls="flex items-center px-6",
        ),
        Div(
            Span(title, cls="text-sm opacity-50"),
            cls="flex items-center ml-auto px-6",
        ),
        cls="navbar bg-base-300 fixed top-0 left-0 right-0 z-50 h-14 min-h-0 border-b border-base-content/10",
    )


def page(*content, title="Dashboard"):
    return Div(
        header(title),
        Div(
            sidebar(),
            Div(
                Div(*content, cls="p-6 max-w-5xl"),
                cls="flex-1 pt-14 overflow-y-auto",
            ),
            cls="flex min-h-screen",
        ),
    )
