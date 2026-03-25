import { useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pause, Play, Trash2 } from "lucide-react";

interface LogEntry {
  ts: string;
  level: string;
  name: string;
  msg: string;
}

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "text-red-400",
  WARNING: "text-yellow-400",
  INFO: "text-blue-400",
  DEBUG: "text-muted-foreground",
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  // Keep ref in sync so the SSE callback sees the latest value
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // Load initial buffer + start SSE
  useEffect(() => {
    fetch("/api/logs")
      .then((r) => r.json())
      .then((data: LogEntry[]) => setLogs(data))
      .catch(() => {});

    const es = new EventSource("/api/logs/stream");
    es.onmessage = (e) => {
      if (pausedRef.current) return;
      const entry: LogEntry = JSON.parse(e.data);
      setLogs((prev) => {
        const next = [...prev, entry];
        return next.length > 500 ? next.slice(-500) : next;
      });
    };

    return () => es.close();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (!paused) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, paused]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Logs</h1>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPaused((p) => !p)}
          >
            {paused ? (
              <><Play className="mr-1 h-3 w-3" /> Resume</>
            ) : (
              <><Pause className="mr-1 h-3 w-3" /> Pause</>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLogs([])}
          >
            <Trash2 className="mr-1 h-3 w-3" /> Clear
          </Button>
        </div>
      </div>

      <Card className="h-[calc(100vh-12rem)] overflow-hidden">
        <div className="h-full overflow-y-auto p-3 font-mono text-xs">
          {logs.length === 0 ? (
            <p className="text-muted-foreground">Waiting for logs…</p>
          ) : (
            logs.map((entry, i) => (
              <div key={i} className="flex gap-2 py-0.5 hover:bg-muted/30">
                <span className="shrink-0 text-muted-foreground">{entry.ts}</span>
                <span className={`shrink-0 w-12 ${LEVEL_COLORS[entry.level] ?? "text-foreground"}`}>
                  {entry.level}
                </span>
                <span className="shrink-0 w-24 truncate text-muted-foreground">{entry.name}</span>
                <span className="text-foreground">{entry.msg}</span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </Card>
    </div>
  );
}
