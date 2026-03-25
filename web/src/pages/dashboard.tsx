import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Archive, Zap, Clock } from "lucide-react";
import { ServiceIcon } from "@/components/service-icon";

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
  });

  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div>
      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Archive className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="text-xl font-bold font-mono leading-tight">
                {data.total_stored.toLocaleString()}
              </p>
              <p className="text-[11px] text-muted-foreground">Items Stored</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Zap className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="text-xl font-bold font-mono leading-tight">
                {data.connected_count}
              </p>
              <p className="text-[11px] text-muted-foreground">Accounts Connected</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Clock className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="text-xl font-bold font-mono leading-tight">
                {data.last_sync_ago}
              </p>
              <p className="text-[11px] text-muted-foreground">Last Sync</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Connected Accounts */}
      <div className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Connected Accounts</h2>
          <Link to="/accounts" className="text-[11px] text-primary opacity-70 hover:opacity-100">
            Manage
          </Link>
        </div>
        {data.accounts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No connected accounts.{" "}
            <Link to="/accounts/add" className="text-primary hover:underline">
              Add one.
            </Link>
          </p>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Stored</TableHead>
                  <TableHead className="text-right">Last Sync</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.accounts.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Link
                        to={`/accounts/${a.id}`}
                        className="flex items-center gap-2 text-sm font-medium text-foreground hover:text-primary transition-colors no-underline"
                      >
                        <ServiceIcon type={a.service_type} className="h-4 w-4 opacity-60" />
                        {a.display_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs capitalize text-muted-foreground">
                      {a.service_type}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {a.stored.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">
                      {a.last_sync}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>

      {/* Recent Activity */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Recent Activity</h2>
          <Link to="/history" className="text-[11px] text-primary opacity-70 hover:opacity-100">
            View all
          </Link>
        </div>
        {data.recent_runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sync runs yet.</p>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Service</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_runs.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link
                        to={`/accounts/${r.service_id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        {r.service_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs">{r.run_type}</TableCell>
                    <TableCell>
                      <Badge variant={r.status === "success" ? "default" : "destructive"}>
                        {r.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {r.items_fetched}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {r.duration}
                    </TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground">
                      {r.time}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}

