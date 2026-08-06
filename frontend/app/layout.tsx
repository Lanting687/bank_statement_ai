import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bank Statement AI",
  description:
    "Review OCR against original bank statement pages, extract transactions, and export to Excel.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
