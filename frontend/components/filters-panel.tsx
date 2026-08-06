"use client";

import { Download, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

const CURRENCY_OPTIONS = ["AUTO", "GBP", "USD", "EUR", "JPY", "AUD", "CAD", "CHF", "CNY", "INR"];

export function FiltersPanel({
  threshold,
  onThresholdChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  currency,
  onCurrencyChange,
  onExtractAll,
  extractingAll,
  extractableCount,
  onDownload,
  downloading,
  hasComputedRows,
}: {
  threshold: number;
  onThresholdChange: (v: number) => void;
  startDate: string;
  endDate: string;
  onStartDateChange: (v: string) => void;
  onEndDateChange: (v: string) => void;
  currency: string;
  onCurrencyChange: (v: string) => void;
  onExtractAll: () => void;
  extractingAll: boolean;
  extractableCount: number;
  onDownload: () => void;
  downloading: boolean;
  hasComputedRows: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Filters</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="threshold">Minimum payment amount</Label>
          <Input
            id="threshold"
            type="number"
            min={0}
            value={threshold}
            onChange={(e) => onThresholdChange(Number(e.target.value))}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Date range</Label>
          <div className="flex items-center gap-2">
            <Input type="date" value={startDate} onChange={(e) => onStartDateChange(e.target.value)} aria-label="Start date" />
            <span className="text-xs text-muted-foreground">to</span>
            <Input type="date" value={endDate} onChange={(e) => onEndDateChange(e.target.value)} aria-label="End date" />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="currency">Display currency</Label>
          <Select id="currency" value={currency} onChange={(e) => onCurrencyChange(e.target.value)}>
            {CURRENCY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>

        <Button
          className="w-full"
          onClick={onExtractAll}
          disabled={extractableCount === 0 || extractingAll}
        >
          {extractingAll ? <Spinner /> : <Sparkles className="h-4 w-4" />}
          Extract Transactions{extractableCount > 0 ? ` (${extractableCount})` : ""}
        </Button>

        <Button
          variant="success"
          className="w-full"
          onClick={onDownload}
          disabled={!hasComputedRows || downloading}
        >
          {downloading ? <Spinner /> : <Download className="h-4 w-4" />}
          Download Excel
        </Button>
      </CardContent>
    </Card>
  );
}
