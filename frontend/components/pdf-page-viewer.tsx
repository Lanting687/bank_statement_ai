"use client";

import * as React from "react";
import { FileWarning } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

// Renders one page of a PDF straight in the browser with pdf.js
// (pdfjs-dist) -- this is the "client-side rendering" choice made for this
// feature: the original Dash version rendered pages to PNGs on the server
// (src/pdf_review.py); here the backend only needs the PDF bytes to run
// OCR, never to produce a preview image, so a page is only ever "rendered"
// once, in the browser, at whatever resolution the panel actually is.
//
// Trade-off worth knowing: this only works while the browser still holds
// the original File object from the upload <input> -- reloading the page
// loses it (browsers don't let JS re-read a file from disk without the
// user picking it again), so a full-page refresh mid-review shows the
// "re-upload to preview" state below even though OCR text/extraction
// (server-cached, see backend/store.py) survive the reload fine.

let workerConfigured = false;

export function PdfPageViewer({ file, page }: { file: File | null; page: number }) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const pdfDocRef = React.useRef<{ file: File; doc: import("pdfjs-dist").PDFDocumentProxy } | null>(null);
  const [status, setStatus] = React.useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!file) {
        setStatus("idle");
        return;
      }

      setStatus("loading");
      setError(null);

      try {
        const pdfjsLib = await import("pdfjs-dist");

        if (!workerConfigured) {
          // Served as a plain static file from public/ (copied there by the
          // "postinstall" script in package.json) rather than bundled via
          // `new URL(..., import.meta.url)`. That pattern works in `next
          // dev`, but in a production `next build`, Next.js runs the
          // resulting chunk through Terser -- and pdfjs-dist ships this
          // worker as a real ES module (import/export), which Terser's
          // default script parser can't handle, so the build fails. Routing
          // it through public/ keeps webpack from touching the file at all.
          pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
          workerConfigured = true;
        }

        let doc = pdfDocRef.current?.file === file ? pdfDocRef.current.doc : null;
        if (!doc) {
          const buffer = await file.arrayBuffer();
          doc = await pdfjsLib.getDocument({ data: buffer }).promise;
          pdfDocRef.current = { file, doc };
        }

        if (cancelled) return;
        if (page < 1 || page > doc.numPages) return;

        const pdfPage = await doc.getPage(page);
        if (cancelled) return;

        const canvas = canvasRef.current;
        const context = canvas?.getContext("2d");
        if (!canvas || !context) return;

        const containerWidth = containerRef.current?.clientWidth ?? 700;
        const baseViewport = pdfPage.getViewport({ scale: 1 });
        const scale = Math.max(containerWidth / baseViewport.width, 0.1);
        const viewport = pdfPage.getViewport({ scale });

        const outputScale = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        await pdfPage.render({
          canvasContext: context,
          viewport,
          transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
        }).promise;

        if (!cancelled) setStatus("idle");
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setError(err instanceof Error ? err.message : "Failed to render this page.");
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [file, page]);

  if (!file) {
    return (
      <div className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
        <FileWarning className="h-6 w-6" />
        <p>PDF preview isn&apos;t available for this document in the current browser session.</p>
        <p>Re-upload the file to preview it again (OCR text is unaffected).</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative flex min-h-[24rem] items-start justify-center">
      {status === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/60">
          <Spinner className="h-6 w-6" />
        </div>
      )}
      {status === "error" && (
        <p className="p-4 text-center text-sm text-destructive">{error}</p>
      )}
      <canvas ref={canvasRef} className="max-w-full rounded-md border border-border shadow-sm" />
    </div>
  );
}
