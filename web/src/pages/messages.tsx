import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Search, X, MessageSquare } from "lucide-react";
import { ServiceIcon } from "@/components/service-icon";

export default function MessagesPage() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [activeConv, setActiveConv] = useState<{ name: string; service: string } | null>(null);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations", search],
    queryFn: () => api.listConversations({ q: search || undefined }),
  });

  const { data: threadMessages, isLoading: threadLoading } = useQuery({
    queryKey: ["conversation", activeConv?.name, activeConv?.service],
    queryFn: () => api.getConversation(activeConv!.name, activeConv!.service),
    enabled: !!activeConv,
  });

  const doSearch = () => setSearch(query);
  const resetSearch = () => {
    setQuery("");
    setSearch("");
  };

  // Thread view
  if (activeConv) {
    return (
      <div>
        <div className="mb-4 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => setActiveConv(null)}>
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <div className="flex items-center gap-2">
            <ServiceIcon type={activeConv.service.replace(/-\d+$/, "")} className="h-4 w-4 text-muted-foreground" />
            <h1 className="text-lg font-semibold">{activeConv.name}</h1>
          </div>
        </div>

        {threadLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !threadMessages || threadMessages.length === 0 ? (
          <p className="text-sm text-muted-foreground">No messages.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {threadMessages.map((m) => (
              <div key={m.id} className="rounded-lg border border-border/40 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs font-medium text-foreground">{m.sender}</span>
                  <span className="text-[10px] text-muted-foreground">{m.time}</span>
                </div>
                <p className="whitespace-pre-wrap text-xs text-muted-foreground">{m.body}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Conversations list
  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Messages</h1>

      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Search messages…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSearch()}
        />
        <Button size="sm" onClick={doSearch}>
          <Search className="h-4 w-4" />
        </Button>
        {search && (
          <Button size="sm" variant="outline" onClick={resetSearch}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {search && (
        <p className="mb-3 text-xs text-muted-foreground">
          Showing results for "<span className="text-foreground">{search}</span>"
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !conversations || conversations.length === 0 ? (
        <p className="text-sm text-muted-foreground">No conversations found.</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {conversations.map((c, i) => (
            <Card
              key={`${c.conversation}-${c.service_id}-${i}`}
              className="cursor-pointer transition-colors hover:border-border"
              onClick={() => setActiveConv({ name: c.conversation, service: c.service_id })}
            >
              <CardContent className="p-3">
                <div className="mb-1 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ServiceIcon type={c.service_id.replace(/-\d+$/, "")} className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{c.conversation}</span>
                    <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                      <MessageSquare className="h-2.5 w-2.5" /> {c.msg_count}
                    </span>
                  </div>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{c.time}</span>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  <span className="font-medium text-muted-foreground/80">{c.last_sender}: </span>
                  {c.preview}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
