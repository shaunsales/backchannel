import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2, Pencil, X } from "lucide-react";
import { ServiceIcon } from "@/components/service-icon";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: acct, isLoading } = useQuery({
    queryKey: ["service", id],
    queryFn: () => api.getService(id!),
    enabled: !!id,
  });

  const [renaming, setRenaming] = useState(false);
  const [nameVal, setNameVal] = useState("");
  const [syncStatus, setSyncStatus] = useState("");

  const renameMut = useMutation({
    mutationFn: (name: string) => api.renameService(id!, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["service", id] });
      setRenaming(false);
    },
  });

  const syncMut = useMutation({
    mutationFn: () => api.syncService(id!),
    onSuccess: (r) => {
      setSyncStatus(`✓ Sync complete — ${r.items_fetched} fetched, ${r.items_new} new, ${r.items_updated} updated, ${r.duration}`);
      qc.invalidateQueries({ queryKey: ["service", id] });
    },
    onError: (e: Error) => setSyncStatus(`✗ ${e.message}`),
  });

  const clearMut = useMutation({
    mutationFn: () => api.clearServiceData(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["service", id] }),
  });

  const disconnectMut = useMutation({
    mutationFn: () => api.disconnectService(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["service", id] }),
  });

  const removeMut = useMutation({
    mutationFn: () => api.deleteService(id!),
    onSuccess: () => navigate("/accounts"),
  });

  if (isLoading || !acct) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          <ServiceIcon type={acct.service_type} className="h-5 w-5 opacity-80" />
        </div>
        <div className="flex-1">
          {renaming ? (
            <div className="flex items-center gap-2">
              <Input
                value={nameVal}
                onChange={(e) => setNameVal(e.target.value)}
                className="h-8 text-lg font-semibold"
                autoFocus
              />
              <Button
                size="sm"
                onClick={() => renameMut.mutate(nameVal)}
                disabled={renameMut.isPending}
              >
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setRenaming(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <h1
              className="cursor-pointer text-lg font-semibold leading-tight hover:text-primary transition-colors"
              onClick={() => {
                setNameVal(acct.display_name);
                setRenaming(true);
              }}
              title="Click to rename"
            >
              {acct.display_name}
              <Pencil className="ml-1.5 inline h-3 w-3 opacity-30" />
            </h1>
          )}
          <div className="flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 rounded-full ${acct.status === "connected" ? "bg-green-500" : "bg-red-400"}`}
            />
            <span className="text-sm text-muted-foreground">{acct.status}</span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-4 flex gap-8">
        <div>
          <p className="text-[11px] text-muted-foreground">Stored</p>
          <p className="text-lg font-mono font-semibold">{acct.stored.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-[11px] text-muted-foreground">Last sync</p>
          <p className="text-xs text-muted-foreground">{acct.last_sync}</p>
        </div>
      </div>

      {/* Connection card */}
      {acct.status === "connected" ? (
        <Card className="mb-4">
          <CardContent className="p-5">
            <h2 className="mb-3 text-sm font-semibold">Connection</h2>
            <div className="mb-2 flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium">Connected</span>
            </div>
            {acct.phone && (
              <p className="text-xs font-mono text-muted-foreground">
                <strong>Phone:</strong> {acct.phone}
              </p>
            )}
            {acct.email && (
              <p className="text-xs font-mono text-muted-foreground">
                <strong>Email:</strong> {acct.email}
              </p>
            )}
            {acct.token_preview && (
              <p className="text-xs font-mono text-muted-foreground">
                <strong>Token:</strong> {acct.token_preview}
              </p>
            )}

            {/* Sync controls */}
            <div className="mt-4 flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => {
                  setSyncStatus("");
                  syncMut.mutate();
                }}
                disabled={syncMut.isPending}
              >
                {syncMut.isPending ? (
                  <>
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" /> Syncing…
                  </>
                ) : (
                  "Sync Now"
                )}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-destructive border-destructive/20"
                onClick={() => disconnectMut.mutate()}
                disabled={disconnectMut.isPending}
              >
                Disconnect
              </Button>
            </div>

            {syncStatus && (
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`text-sm font-medium ${syncStatus.startsWith("✓") ? "text-green-500" : "text-destructive"}`}
                >
                  {syncStatus}
                </span>
                <button onClick={() => setSyncStatus("")} className="opacity-40 hover:opacity-100">
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-4">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Account is disconnected.</p>
          </CardContent>
        </Card>
      )}

      {/* Sync history */}
      <div className="mb-4">
        <h2 className="mb-3 text-sm font-semibold">Sync History</h2>
        {acct.recent_runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sync runs yet.</p>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {acct.recent_runs.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-xs">{r.run_type}</TableCell>
                    <TableCell>
                      <Badge variant={r.status === "success" ? "default" : "destructive"}>
                        {r.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">{r.items_fetched}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{r.duration}</TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">{r.time}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>

      {/* Danger zone */}
      <hr className="my-4 border-border/40" />
      <div className="flex gap-2">
        {acct.status === "connected" && acct.stored > 0 && (
          <Button
            size="sm"
            variant="outline"
            className="text-yellow-500 border-yellow-500/20"
            onClick={() => clearMut.mutate()}
            disabled={clearMut.isPending}
          >
            Clear Synced Data
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="text-destructive border-destructive/20"
          onClick={() => {
            if (confirm("Remove this account and all its data?")) removeMut.mutate();
          }}
          disabled={removeMut.isPending}
        >
          Remove Account
        </Button>
      </div>
    </div>
  );
}
