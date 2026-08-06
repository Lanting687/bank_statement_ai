"use client";

import * as React from "react";
import { Landmark } from "lucide-react";
import type { ComputeResponse, DocumentSummary, OcrResultOut } from "@/lib/types";
import * as api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UploadZone } from "@/components/upload-zone";
import { DocumentList } from "@/components/document-list";
import { ReviewWorkspace } from "@/components/review-workspace";
import { FiltersPanel } from "@/components/filters-panel";
import { TransactionsTable } from "@/components/transactions-table";

interface Filters {
  threshold: number;
  currency: string;
  startDate: string;
  endDate: string;
}

export default function Home() {
  const [documents, setDocuments] = React.useState<DocumentSummary[]>([]);
  const [filesById, setFilesById] = React.useState<Record<string, File>>({});
  const [ocrResultsById, setOcrResultsById] = React.useState<Record<string, OcrResultOut>>({});
  const [reviewPageById, setReviewPageById] = React.useState<Record<string, number>>({});
  const [activeDocumentId, setActiveDocumentId] = React.useState<string | null>(null);
  const [activeTab, setActiveTab] = React.useState<"review" | "transactions">("review");

  const [computeResponse, setComputeResponse] = React.useState<ComputeResponse | null>(null);
  const [selections, setSelections] = React.useState<Record<string, number[]>>({});
  const [filters, setFilters] = React.useState<Filters>({
    threshold: 50,
    currency: "AUTO",
    startDate: "",
    endDate: "",
  });

  const [ocrRunningIds, setOcrRunningIds] = React.useState<Set<string>>(new Set());
  const [extractingIds, setExtractingIds] = React.useState<Set<string>>(new Set());
  const [extractingAll, setExtractingAll] = React.useState(false);
  const [downloading, setDownloading] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  // Resume any documents already known to the backend (e.g. after a page
  // reload) -- OCR text/extractions survive server-side, only the PDF
  // preview needs the browser's in-memory File object, which does not.
  React.useEffect(() => {
    api.listDocuments().then(setDocuments).catch(() => {});
  }, []);

  function reportError(err: unknown, fallback: string) {
    setErrorMessage(err instanceof api.ApiError ? err.message : fallback);
  }

  async function runOcrFor(documentId: string) {
    setOcrRunningIds((prev) => new Set(prev).add(documentId));
    try {
      const result = await api.runOcr(documentId);
      setOcrResultsById((prev) => ({ ...prev, [documentId]: result }));
      setDocuments((prev) =>
        prev.map((d) =>
          d.document_id === documentId
            ? { ...d, ocr_status: result.ocr_status, ocr_error: result.ocr_error }
            : d,
        ),
      );
      setReviewPageById((prev) => ({ ...prev, [documentId]: prev[documentId] ?? 1 }));
    } catch (err) {
      reportError(err, "OCR failed unexpectedly.");
    } finally {
      setOcrRunningIds((prev) => {
        const next = new Set(prev);
        next.delete(documentId);
        return next;
      });
    }
  }

  async function handleFilesSelected(files: File[]) {
    setErrorMessage(null);
    for (const file of files) {
      try {
        const summary = await api.uploadDocument(file);
        setFilesById((prev) => ({ ...prev, [summary.document_id]: file }));
        setDocuments((prev) => [...prev.filter((d) => d.document_id !== summary.document_id), summary]);
        setActiveDocumentId((prev) => prev ?? summary.document_id);
        // OCR is local/free (docTR), so it starts automatically -- unlike
        // DeepSeek extraction below, which costs money and always waits
        // for an explicit click.
        runOcrFor(summary.document_id);
      } catch (err) {
        reportError(err, `Could not upload ${file.name}.`);
      }
    }
  }

  async function handleDelete(documentId: string) {
    try {
      await api.deleteDocument(documentId);
    } catch (err) {
      reportError(err, "Could not remove this document.");
      return;
    }
    setDocuments((prev) => prev.filter((d) => d.document_id !== documentId));
    setFilesById((prev) => {
      const next = { ...prev };
      delete next[documentId];
      return next;
    });
    setOcrResultsById((prev) => {
      const next = { ...prev };
      delete next[documentId];
      return next;
    });
    setSelections((prev) => {
      const next = { ...prev };
      delete next[documentId];
      return next;
    });
    if (activeDocumentId === documentId) setActiveDocumentId(null);
  }

  async function extractOne(documentId: string) {
    setExtractingIds((prev) => new Set(prev).add(documentId));
    try {
      await api.extractTransactions(documentId);
      setDocuments((prev) =>
        prev.map((d) => (d.document_id === documentId ? { ...d, has_extraction: true } : d)),
      );
    } catch (err) {
      reportError(err, "DeepSeek extraction failed for this document.");
    } finally {
      setExtractingIds((prev) => {
        const next = new Set(prev);
        next.delete(documentId);
        return next;
      });
    }
  }

  async function handleContinueToExtraction(documentId: string) {
    await extractOne(documentId);
    setActiveTab("transactions");
  }

  const extractableIds = documents
    .filter((d) => d.ocr_status === "done" && !d.has_extraction)
    .map((d) => d.document_id);

  async function handleExtractAll() {
    setExtractingAll(true);
    try {
      for (const id of extractableIds) {
        await extractOne(id);
      }
      setActiveTab("transactions");
    } finally {
      setExtractingAll(false);
    }
  }

  // Recompute filtered/converted rows whenever filters change or a new
  // extraction completes. Debounced slightly so typing in the threshold
  // field doesn't fire a request per keystroke. Depends on the *count* of
  // extracted documents, not just whether any exist -- a boolean wouldn't
  // change (and so wouldn't re-trigger this effect) when a second, third,
  // etc. document finishes extraction after the first already had.
  const extractedCount = documents.filter((d) => d.has_extraction).length;
  React.useEffect(() => {
    if (extractedCount === 0) {
      setComputeResponse(null);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const response = await api.computeTransactions({
          threshold: filters.threshold,
          target_currency: filters.currency,
          start_date: filters.startDate || null,
          end_date: filters.endDate || null,
        });
        setComputeResponse(response);
        // Matches the original Dash behaviour: every recompute resets
        // ticked rows back to the auto-threshold selection, rather than
        // trying to preserve manual edits across a filter change.
        setSelections(
          Object.fromEntries(response.documents.map((d) => [d.document_id, d.selected_indices])),
        );
      } catch (err) {
        reportError(err, "Could not recompute transactions.");
      }
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extractedCount, filters.threshold, filters.currency, filters.startDate, filters.endDate]);

  function toggleRow(documentId: string, rowIndex: number) {
    setSelections((prev) => {
      const current = new Set(prev[documentId] ?? []);
      if (current.has(rowIndex)) current.delete(rowIndex);
      else current.add(rowIndex);
      return { ...prev, [documentId]: Array.from(current).sort((a, b) => a - b) };
    });
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      const blob = await api.exportExcel({ selections });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "transactions.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      reportError(err, "Could not generate the Excel export.");
    } finally {
      setDownloading(false);
    }
  }

  const activeDocument = documents.find((d) => d.document_id === activeDocumentId) ?? null;
  const activePage = activeDocumentId ? reviewPageById[activeDocumentId] ?? 1 : 1;

  return (
    <main className="mx-auto flex min-h-screen max-w-[1400px] flex-col gap-6 p-6">
      <header className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Landmark className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-semibold leading-tight">Bank Statement AI</h1>
          <p className="text-sm text-muted-foreground">Review OCR, extract transactions, export to Excel</p>
        </div>
      </header>

      {errorMessage && (
        <Alert variant="destructive">
          <span className="flex flex-wrap items-center justify-between gap-3">
            <span>{errorMessage}</span>
            <button className="shrink-0 text-xs underline" onClick={() => setErrorMessage(null)}>
              dismiss
            </button>
          </span>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <aside className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Upload statements</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <UploadZone onFilesSelected={handleFilesSelected} />
              <DocumentList
                documents={documents}
                activeDocumentId={activeDocumentId}
                onSelect={setActiveDocumentId}
                onRunOcr={runOcrFor}
                onDelete={handleDelete}
                ocrRunningIds={ocrRunningIds}
              />
            </CardContent>
          </Card>

          <FiltersPanel
            threshold={filters.threshold}
            onThresholdChange={(v) => setFilters((f) => ({ ...f, threshold: v }))}
            startDate={filters.startDate}
            endDate={filters.endDate}
            onStartDateChange={(v) => setFilters((f) => ({ ...f, startDate: v }))}
            onEndDateChange={(v) => setFilters((f) => ({ ...f, endDate: v }))}
            currency={filters.currency}
            onCurrencyChange={(v) => setFilters((f) => ({ ...f, currency: v }))}
            onExtractAll={handleExtractAll}
            extractingAll={extractingAll}
            extractableCount={extractableIds.length}
            onDownload={handleDownload}
            downloading={downloading}
            hasComputedRows={(computeResponse?.documents.length ?? 0) > 0}
          />
        </aside>

        <section>
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "review" | "transactions")}>
            <TabsList>
              <TabsTrigger value="review">Review OCR</TabsTrigger>
              <TabsTrigger value="transactions">Transactions</TabsTrigger>
            </TabsList>

            <TabsContent value="review">
              <Card>
                <CardContent className="pt-5">
                  <ReviewWorkspace
                    document={activeDocument}
                    file={activeDocumentId ? filesById[activeDocumentId] ?? null : null}
                    ocrResult={activeDocumentId ? ocrResultsById[activeDocumentId] ?? null : null}
                    ocrRunning={activeDocumentId ? ocrRunningIds.has(activeDocumentId) : false}
                    page={activePage}
                    onPageChange={(page) =>
                      activeDocumentId && setReviewPageById((prev) => ({ ...prev, [activeDocumentId]: page }))
                    }
                    onContinue={() => activeDocumentId && handleContinueToExtraction(activeDocumentId)}
                    extracting={activeDocumentId ? extractingIds.has(activeDocumentId) : false}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="transactions">
              <TransactionsTable
                documents={computeResponse?.documents ?? []}
                selections={selections}
                onToggleRow={toggleRow}
              />
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </main>
  );
}
