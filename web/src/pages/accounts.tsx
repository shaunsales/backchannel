import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { ServiceIcon } from "@/components/service-icon";
import { AddAccountDialog } from "./add-account";

export default function AccountsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { data: accounts, isLoading } = useQuery({
    queryKey: ["services"],
    queryFn: api.listServices,
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Accounts</h1>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1 h-4 w-4" /> Add Account
        </Button>
      </div>

      <AddAccountDialog open={dialogOpen} onOpenChange={setDialogOpen} />

      {!accounts || accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No accounts yet.{" "}
          <button onClick={() => setDialogOpen(true)} className="text-primary hover:underline">
            Add your first account.
          </button>
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {accounts.map((a) => (
            <Link key={a.id} to={`/accounts/${a.id}`} className="no-underline">
              <Card className="transition-colors hover:border-border">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <ServiceIcon type={a.service_type} className="h-4 w-4 opacity-80" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold leading-tight text-foreground">
                        {a.display_name}
                      </p>
                      <div className="flex items-center gap-1.5">
                        <span className={`inline-block h-1.5 w-1.5 rounded-full ${a.status === "connected" ? "bg-green-500" : "bg-red-400"}`} />
                        <p className="text-[11px] capitalize text-muted-foreground">
                          {a.service_type}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-right">
                    <div>
                      <p className="text-[10px] text-muted-foreground">Stored</p>
                      <p className="text-sm font-mono font-semibold text-foreground">
                        {a.stored.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted-foreground">Last sync</p>
                      <p className="text-[11px] text-muted-foreground">{a.last_sync}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
