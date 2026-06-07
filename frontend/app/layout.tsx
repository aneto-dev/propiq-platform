import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

/**
 * Root application layout.
 *
 * Wraps all pages. Auth guard and app shell are added in Commit 7.3
 * via the (app) route group layout.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.1.
 */
export const metadata: Metadata = {
  title: "PropIQ",
  description: "UK property investment analysis platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
