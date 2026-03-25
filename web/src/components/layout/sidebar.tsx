import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  MessageCircle,
  Users,
  Clock,
  ScrollText,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { section: "Browse" },
  { label: "Documents", href: "/docs", icon: FileText },
  { label: "Messages", href: "/messages", icon: MessageCircle },
  { section: "Manage" },
  { label: "Accounts", href: "/accounts", icon: Users },
  { section: "System" },
  { label: "History", href: "/history", icon: Clock },
  { label: "Logs", href: "/logs", icon: ScrollText },
] as const;

export function Sidebar() {
  const { pathname } = useLocation();

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border/40 bg-muted/30 p-3 pt-5">
      {/* Logo */}
      <Link
        to="/"
        className="mb-2 flex items-center gap-2 px-3 py-2 text-foreground no-underline"
      >
        <Zap className="h-5 w-5 text-primary" />
        <span className="text-base font-bold tracking-tight">Backchannel</span>
      </Link>

      <hr className="mx-2 mb-1 border-border/40" />

      <nav className="flex flex-col gap-0.5">
        {NAV.map((item, i) => {
          if ("section" in item) {
            return (
              <span
                key={i}
                className="mt-4 mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50"
              >
                {item.section}
              </span>
            );
          }
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors no-underline",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 opacity-60" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
