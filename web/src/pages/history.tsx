import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function HistoryPage() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["history"],
    queryFn: () => api.getHistory(),
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Sync History</h1>
      {!runs || runs.length === 0 ? (
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
              {runs.map((r) => (
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
                  <TableCell className="text-right font-mono text-xs">{r.duration}</TableCell>
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
  );
}
