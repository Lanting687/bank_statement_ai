import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Standard shadcn/ui helper: merges conditional class lists (clsx) and
// then resolves conflicting Tailwind utility classes (tailwind-merge), so
// e.g. cn("p-2", condition && "p-4") reliably ends up as just "p-4".
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMoney(amount: string, currency: string): string {
  const value = Number(amount);
  if (Number.isNaN(value)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(value);
  } catch {
    // Intl throws for a currency code it doesn't recognise (e.g. DeepSeek
    // returning something non-ISO-4217) -- fall back to plain text rather
    // than crashing the row.
    return `${value.toFixed(2)} ${currency}`;
  }
}
