import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: doc, isLoading } = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.getDocument(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (!doc) {
    return <p className="text-sm text-muted-foreground">Document not found.</p>;
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/docs">
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Link>
        </Button>
      </div>

      <div className="mb-3">
        <h1 className="text-lg font-semibold">{doc.title}</h1>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Source: {doc.service_id}</span>
          <span>v{doc.version}</span>
          <span>{doc.time}</span>
        </div>
      </div>

      <Card>
        <CardContent className="p-6">
          <div className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed text-foreground [&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_hr]:border-border [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_table]:w-full [&_th]:border [&_th]:border-border [&_th]:p-2 [&_td]:border [&_td]:border-border [&_td]:p-2 [&_input[type=checkbox]]:mr-2">
            <Markdown remarkPlugins={[remarkGfm]}>{doc.body}</Markdown>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
