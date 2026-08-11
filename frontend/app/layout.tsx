import type { Metadata } from "next";
import { GoogleAnalytics } from "@next/third-parties/google";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bank Statement AI",
  description:
    "Review OCR against original bank statement pages, extract transactions, and export to Excel.",
};

// Reads NEXT_PUBLIC_GA_ID at build time (Next.js inlines NEXT_PUBLIC_* vars
// into the client bundle when `next build` runs -- setting it after the
// build, e.g. only in the systemd service's Environment=, has no effect).
// GA is opt-in: with no ID set, GoogleAnalytics is skipped entirely and
// nothing is sent to Google -- see deploy/DEPLOY.md for how to set this on
// the server. Only page views are tracked here, never PDF/OCR/transaction
// content -- nothing from backend/store.py ever reaches the browser's
// analytics script.
const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
      {GA_ID && <GoogleAnalytics gaId={GA_ID} />}
    </html>
  );
}
