"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchStats, type StatsResponse } from "@/lib/api";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function Home() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {});
  }, []);

  const sourceCount = stats ? Object.keys(stats.sources).length : 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <div className="flex flex-col items-center text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          The Epstein Files
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
          An AI-powered research tool for exploring the Jeffrey Epstein
          document archive. Ask questions, find connections, and search across
          thousands of pages of court filings, flight logs, and government
          records.
        </p>
        <Link href="/chat" className="mt-8">
          <Button size="lg" className="text-base px-8">
            Talk to the Documents
          </Button>
        </Link>
      </div>

      {stats && stats.db_exists && (
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Documents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {stats.total_documents.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Pages Extracted
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {stats.total_pages.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Sources
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{sourceCount}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Archive Size
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {formatBytes(stats.total_size_bytes)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="mt-16 rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">How it works</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          This tool uses Retrieval-Augmented Generation (RAG) to let you
          interact with the document archive. When you ask a question, the
          system searches through all extracted document text to find the most
          relevant passages, then uses an AI model to synthesize an answer
          citing specific documents and page numbers. All responses are
          grounded in the actual documents.
        </p>
        <p className="mt-3 text-xs text-muted-foreground">
          Built and maintained by{" "}
          <a
            href="https://epsteindata.cc"
            className="font-medium text-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            EpsteinData.cc
          </a>
          . All documents are sourced from public records and government releases.
        </p>
      </div>
    </div>
  );
}
