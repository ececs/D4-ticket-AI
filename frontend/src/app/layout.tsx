/**
 * Root layout — wraps every page in the application.
 *
 * In Next.js App Router, layout.tsx is the outermost shell rendered once
 * and kept alive across navigations (no full-page reloads).
 *
 * Responsibilities:
 *  - Set HTML metadata (title, description).
 *  - Load the global CSS (Tailwind + shadcn/ui tokens).
 *  - Render the Toaster (global toast notifications).
 */

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "D4-Ticket AI",
  description: "Collaborative ticketing system with AI assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  );
}
