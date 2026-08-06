// Mirrors backend/schemas.py exactly -- keep these two in sync by hand.
// (A prototype-scale choice: generating this from the FastAPI OpenAPI
// schema would remove the risk of drift, but is more machinery than this
// codebase needs right now. See docs/CODING_STANDARDS.md.)

export type OcrStatus = "pending" | "done" | "error";

export interface DocumentSummary {
  document_id: string;
  filename: string;
  page_count: number;
  ocr_status: OcrStatus;
  ocr_error: string | null;
  has_extraction: boolean;
}

export interface OcrPage {
  page_number: number;
  text: string;
}

export interface OcrResultOut {
  document_id: string;
  ocr_status: OcrStatus;
  ocr_error: string | null;
  page_count: number;
  pages: OcrPage[];
}

export interface TransactionOut {
  date: string;
  iso_date: string;
  description: string;
  amount: string;
}

export interface ExtractionOut {
  document_id: string;
  source_currency: string;
  transactions: TransactionOut[];
}

export interface ComputeRequest {
  threshold: number;
  target_currency: string;
  start_date: string | null;
  end_date: string | null;
}

export interface ComputedRow {
  date: string;
  iso_date: string;
  description: string;
  converted_amount: string;
}

export interface ComputedDocument {
  document_id: string;
  filename: string;
  display_currency: string;
  rows: ComputedRow[];
  selected_indices: number[];
  warning: string | null;
}

export interface ComputeResponse {
  documents: ComputedDocument[];
}

export interface ExportRequest {
  selections: Record<string, number[]>;
}

// Frontend-only state, not returned by the backend: which document is
// currently open in the review workspace and what page it's on. Kept in
// React state in app/page.tsx, analogous to the Dash version's
// review-active-store / review-store.current_page.
export interface ReviewPosition {
  documentId: string | null;
  page: number;
}
