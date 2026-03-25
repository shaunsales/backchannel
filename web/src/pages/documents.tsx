import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, X } from "lucide-react";
import { ServiceIcon } from "@/components/service-icon";

export default function DocumentsPage() {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");

  const { data: docs, isLoading } = useQuery({
    queryKey: ["documents", search],
    queryFn: () => api.listDocuments({ q: search || undefined }),
  });

  const doSearch = () => setSearch(query);
  const resetSearch = () => { setQuery(""); setSearch(""); };

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Documents</h1>

      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Search documents…"
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
      ) : !docs || docs.length === 0 ? (
        <p className="text-sm text-muted-foreground">{search ? "No documents match your search." : "No documents yet. Sync an account to get started."}</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {docs.map((d) => (
            <Link key={d.id} to={`/docs/${d.id}`} className="no-underline">
              <Card className="h-full transition-colors hover:border-border">
                <CardContent className="p-3">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <ServiceIcon type={d.service_id.replace(/-\d+$/, "")} className="h-3 w-3 text-muted-foreground" />
                    <span className="text-[10px] text-muted-foreground">{d.service_id}</span>
                  </div>
                  <p className="mb-1 text-sm font-semibold leading-tight text-foreground line-clamp-1">
                    {d.title}
                  </p>
                  <p className="text-xs text-muted-foreground line-clamp-3">{d.preview}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
