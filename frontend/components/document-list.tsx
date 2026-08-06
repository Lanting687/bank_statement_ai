"use client";

import { FileText, Loader2, Trash2 } from "lucide-react";
import type { DocumentSummary } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function StatusBadge({ doc, running }: { doc: DocumentSummary; running: boolean }) {
  if (running) {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" /> Running OCR
      </Badge>
    );
  }
  if (doc.ocr_status === "error") {
    return <Badge variant="destructive">OCR failed</Badge>;
  }
  if (doc.ocr_status === "pending") {
    return <Badge variant="secondary">Not processed</Badge>;
  }
  if (doc.has_extraction) {
    return <Badge variant="success">Extracted</Badge>;
  }
  return <Badge variant="success">OCR complete</Badge>;
}

export function DocumentList({
  documents,
  activeDocumentId,
  onSelect,
  onRunOcr,
  onDelete,
  ocrRunningIds,
}: {
  documents: DocumentSummary[];
  activeDocumentId: string | null;
  onSelect: (id: string) => void;
  onRunOcr: (id: string) => void;
  onDelete: (id: string) => void;
  ocrRunningIds: Set<string>;
}) {
  if (documents.length === 0) {
    return <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {documents.map((doc) => {
        const running = ocrRunningIds.has(doc.document_id);
        const active = doc.document_id === activeDocumentId;
        return (
          <li key={doc.document_id}>
            <div
              className={cn(
                "flex items-center gap-3 rounded-md border px-3 py-2.5 transition-colors",
                active ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(doc.document_id)}
                className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
              >
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{doc.filename}</span>
                  <span className="block text-xs text-muted-foreground">
                    {doc.page_count} page{doc.page_count === 1 ? "" : "s"}
                  </span>
                </span>
              </button>
              <StatusBadge doc={doc} running={running} />
              {(doc.ocr_status === "pending" || doc.ocr_status === "error") && !running && (
                <Button size="sm" variant="outline" onClick={() => onRunOcr(doc.document_id)}>
                  {doc.ocr_status === "error" ? "Retry OCR" : "Run OCR"}
                </Button>
              )}
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove ${doc.filename}`}
                onClick={() => onDelete(doc.document_id)}
              >
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
