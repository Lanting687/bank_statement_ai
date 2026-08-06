import type {
  ComputeRequest,
  ComputeResponse,
  DocumentSummary,
  ExportRequest,
  ExtractionOut,
  OcrResultOut,
} from "./types";

// Every call goes to a relative /api/... path, which next.config.js
// rewrites to the FastAPI backend (see backend/main.py) -- so this file
// never needs to know the backend's actual host/port.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText above
    }
    throw new ApiError(res.status, detail);
  }
  // 204 No Content (delete_document) has no body to parse.
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentSummary>("/api/documents", { method: "POST", body: form });
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>("/api/documents");
}

export async function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`/api/documents/${documentId}`, { method: "DELETE" });
}

export async function runOcr(documentId: string): Promise<OcrResultOut> {
  return request<OcrResultOut>(`/api/documents/${documentId}/ocr`, { method: "POST" });
}

export async function extractTransactions(documentId: string): Promise<ExtractionOut> {
  return request<ExtractionOut>(`/api/documents/${documentId}/extract`, { method: "POST" });
}

export async function computeTransactions(body: ComputeRequest): Promise<ComputeResponse> {
  return request<ComputeResponse>("/api/transactions/compute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function exportExcel(body: ExportRequest): Promise<Blob> {
  const res = await fetch("/api/export/excel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText);
  }
  return res.blob();
}
