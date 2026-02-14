from fasthtml.common import *


daisyui_css = Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css")
tailwind_script = Script(src="https://cdn.tailwindcss.com")

CUSTOM_CSS = Style("""
    .sidebar-link { transition: all 0.15s ease; }
    .sidebar-link:hover { background: oklch(var(--b3)); }
    .stat-card { transition: transform 0.15s ease; }
    .stat-card:hover { transform: translateY(-1px); }
""")


def logo(size=28):
    return NotStr(f'''<svg width="{size}" height="{size}" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="32" height="32" rx="8" fill="oklch(var(--p))"/>
        <path d="M8 11C8 9.89543 8.89543 9 10 9H22C23.1046 9 24 9.89543 24 11V17C24 18.1046 23.1046 19 22 19H18L14 23V19H10C8.89543 19 8 18.1046 8 17V11Z" fill="oklch(var(--pc))" opacity="0.9"/>
        <circle cx="12.5" cy="14" r="1.5" fill="oklch(var(--p))"/>
        <circle cx="16" cy="14" r="1.5" fill="oklch(var(--p))"/>
        <circle cx="19.5" cy="14" r="1.5" fill="oklch(var(--p))"/>
    </svg>''')


SERVICE_ICONS = {
    "notion": '<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="currentColor"><path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L18.29 2.39c-.42-.326-.98-.7-2.055-.607L3.01 2.96c-.467.047-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.166V6.354c0-.606-.233-.933-.748-.886l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952l1.449.327s0 .84-1.168.84l-3.222.187c-.093-.187 0-.653.327-.726l.84-.234V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.234 4.764 7.28v-6.44l-1.215-.14c-.093-.514.28-.886.747-.933zM2.332 1.68L16.04.753c1.682-.14 2.1.093 2.8.606l3.876 2.706c.467.327.607.747.607 1.307v16.085c0 .98-.373 1.54-1.682 1.634L6.32 23.977c-.98.047-1.448-.093-1.962-.747L1.26 19.39c-.56-.747-.793-1.307-.793-1.96V3.24c0-.84.374-1.54 1.866-1.56z"/></svg>',
    "gmail": '<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="currentColor"><path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/></svg>',
    "telegram": '<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
    "protonmail": '<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="currentColor"><path d="M3.2 3C1.434 3 0 4.434 0 6.2v.752l11.983 7.572L24 6.952V6.2C24 4.434 22.566 3 20.8 3zm-3.2 6.16V17.8C0 19.566 1.434 21 3.2 21h17.6c1.766 0 3.2-1.434 3.2-3.2V9.16l-12.017 7.59z"/></svg>',
    "whatsapp": '<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>',
}


def head_tags():
    return (
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        daisyui_css,
        tailwind_script,
        CUSTOM_CSS,
        Title("Backchannel"),
    )


def sidebar():
    nav_items = [
        ("Dashboard", "/", '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1"/></svg>'),
        ("Documents", "/docs", '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>'),
        ("History", "/history", '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'),
    ]

    service_items = [
        ("Notion", "/services/notion", "notion"),
        ("Gmail", "/services/gmail", "gmail"),
        ("Telegram", "/services/telegram", "telegram"),
        ("ProtonMail", "/services/protonmail", "protonmail"),
        ("WhatsApp", "/services/whatsapp", "whatsapp"),
    ]

    nav_links = [
        Li(A(
            NotStr(icon), Span(label),
            href=href,
            cls="sidebar-link flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
        ))
        for label, href, icon in nav_items
    ]

    svc_links = [
        Li(A(
            NotStr(SERVICE_ICONS.get(sid, "")), Span(label),
            href=href,
            cls="sidebar-link flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm",
        ))
        for label, href, sid in service_items
    ]

    return Nav(
        Div(
            A(
                Div(logo(24), Span("Backchannel", cls="text-base font-bold tracking-tight"), cls="flex items-center gap-2.5"),
                href="/",
                cls="block px-3 py-2 mb-2",
            ),
            Div(cls="border-b border-base-content/5 mx-2 mb-3"),
            Ul(*nav_links, cls="flex flex-col space-y-0.5 mb-2"),
            Div(
                Span("Services", cls="text-[10px] uppercase tracking-widest opacity-40 font-semibold px-3"),
                cls="mb-2 mt-4",
            ),
            Ul(*svc_links, cls="flex flex-col space-y-0.5"),
            cls="flex flex-col",
        ),
        cls="w-60 min-h-screen bg-base-200/80 p-3 pt-5 border-r border-base-content/5",
    )


def header(title="Dashboard"):
    return Div(
        Div(
            Div(
                Span(title, cls="text-sm font-semibold"),
                cls="flex items-center gap-3",
            ),
            Div(
                Button(
                    NotStr('<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'),
                    Span("Sync All", cls="text-xs"),
                    hx_post="/sync/all",
                    hx_target="#sync-banner",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm gap-1.5 h-8 min-h-0",
                ),
                cls="flex items-center gap-2",
            ),
            cls="flex items-center justify-between w-full px-6",
        ),
        Div(id="sync-banner"),
        cls="bg-base-100 sticky top-0 z-50 h-12 min-h-0 flex flex-col justify-center border-b border-base-content/5",
    )


def page(*content, title="Dashboard"):
    return Div(
        Div(
            sidebar(),
            Div(
                header(title),
                Div(*content, cls="p-6 max-w-6xl"),
                cls="flex-1 overflow-y-auto min-h-screen bg-base-100",
            ),
            cls="flex",
        ),
        data_theme="dark",
    )
