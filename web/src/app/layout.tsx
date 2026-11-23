import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Enterprise RAG Ops Copilot — Thai–English Hybrid RAG & Ticket Triage",
  description:
    "No-Login Live Demo: Thai-English Hybrid RAG Copilot (pgvector + PyThaiNLP + pg_trgm RRF), 3-Stage Groundedness Guardrails, Pydantic v2 Ticket Triage, and 25-Case Golden Eval Gate.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased selection:bg-indigo-500/30 selection:text-indigo-200">
        {children}
      </body>
    </html>
  );
}
