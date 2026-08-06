"use client";

import { Receipt } from "lucide-react";
import type { ComputedDocument } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert } from "@/components/ui/alert";
import { formatMoney } from "@/lib/utils";

export function TransactionsTable({
  documents,
  selections,
  onToggleRow,
}: {
  documents: ComputedDocument[];
  selections: Record<string, number[]>;
  onToggleRow: (documentId: string, rowIndex: number) => void;
}) {
  if (documents.length === 0) {
    return (
      <div className="flex min-h-[20rem] flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <Receipt className="h-8 w-8" />
        <p className="text-sm">Extract transactions from a document to review them here.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {documents.map((doc) => {
        const selected = new Set(selections[doc.document_id] ?? []);
        return (
          <Card key={doc.document_id}>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>{doc.filename}</CardTitle>
                <p className="mt-1 text-xs text-muted-foreground">
                  {doc.rows.length} payment{doc.rows.length === 1 ? "" : "s"} &middot; showing amounts in {doc.display_currency}
                </p>
              </div>
              <span className="text-xs text-muted-foreground">{selected.size} selected</span>
            </CardHeader>
            <CardContent>
              {doc.warning && (
                <Alert variant="warning" className="mb-3">
                  {doc.warning}
                </Alert>
              )}
              {doc.rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No payments found in this document.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10"></TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="text-right">Amount ({doc.display_currency})</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {doc.rows.map((row, i) => (
                      <TableRow
                        key={i}
                        className={selected.has(i) ? "bg-success/5" : undefined}
                      >
                        <TableCell>
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-input accent-current text-primary"
                            checked={selected.has(i)}
                            onChange={() => onToggleRow(doc.document_id, i)}
                            aria-label={`Select transaction on ${row.date}: ${row.description}`}
                          />
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-sm">{row.date}</TableCell>
                        <TableCell className="text-sm">{row.description}</TableCell>
                        <TableCell className="whitespace-nowrap text-right text-sm font-medium">
                          {formatMoney(row.converted_amount, doc.display_currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
