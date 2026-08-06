"use client";

import { ChevronLeft, ChevronRight, FileSearch } from "lucide-react";
import type { DocumentSummary, OcrResultOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Alert } from "@/components/ui/alert";
import { PdfPageViewer } from "@/components/pdf-page-viewer";

export function ReviewWorkspace({
  document,
  file,
  ocrResult,
  ocrRunning,
  page,
  onPageChange,
  onContinue,
  extracting,
}: {
  document: DocumentSummary | null;
  file: File | null;
  ocrResult: OcrResultOut | null;
  ocrRunning: boolean;
  page: number;
  onPageChange: (page: number) => void;
  onContinue: () => void;
  extracting: boolean;
}) {
  if (!document) {
    return (
      <div className="flex min-h-[28rem] flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <FileSearch className="h-8 w-8" />
        <p className="text-sm">Upload a PDF and run OCR to start reviewing.</p>
      </div>
    );
  }

  const pageCount = document.page_count;
  const ocrPage = ocrResult?.pages.find((p) => p.page_number === page) ?? null;

  let ocrPanelContent: React.ReactNode;
  if (document.ocr_status === "error") {
    ocrPanelContent = (
      <Alert variant="destructive">OCR failed: {document.ocr_error ?? "unknown error"}</Alert>
    );
  } else if (ocrRunning || document.ocr_status === "pending") {
    ocrPanelContent = (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Running OCR&hellip;
      </div>
    );
  } else if (!ocrPage) {
    ocrPanelContent = <p className="text-sm text-muted-foreground">OCR text unavailable for this page.</p>;
  } else if (!ocrPage.text) {
    ocrPanelContent = <p className="text-sm text-muted-foreground">No text was recognised on this page.</p>;
  } else {
    ocrPanelContent = <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed">{ocrPage.text}</pre>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{document.filename}</p>
          <p className="text-xs text-muted-foreground">
            {document.ocr_status === "done" ? "OCR complete" : document.ocr_status === "error" ? "OCR unavailable" : "Processing OCR"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-muted-foreground">Original PDF</h3>
          <div className="review-scroll max-h-[70vh] overflow-auto rounded-lg border border-border bg-muted/20 p-3">
            <PdfPageViewer file={file} page={page} />
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-muted-foreground">OCR Extracted Text</h3>
          <div className="review-scroll max-h-[70vh] overflow-auto rounded-lg border border-border bg-muted/20 p-3">
            {ocrPanelContent}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
          >
            <ChevronLeft className="h-4 w-4" /> Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {pageCount || "?"}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
          >
            Next <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button onClick={onContinue} disabled={document.ocr_status !== "done" || extracting}>
          {extracting ? <Spinner /> : null}
          Continue to Extraction
        </Button>
      </div>
    </div>
  );
}
