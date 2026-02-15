"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SearchInput } from "@/components/search-input";
import { DocumentCard } from "@/components/document-card";
import { Pagination } from "@/components/pagination";
import {
  searchDocuments,
  fetchDocuments,
  fetchSources,
  type SearchResult,
  type Document,
  type SourceInfo,
} from "@/lib/api";

function DocumentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const q = searchParams.get("q") || "";
  const source = searchParams.get("source") || "";
  const page = Number(searchParams.get("page") || "1");

  const [results, setResults] = useState<SearchResult[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);

  // Update URL params without full navigation
  const updateParams = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, val] of Object.entries(updates)) {
        if (val) {
          params.set(key, val);
        } else {
          params.delete(key);
        }
      }
      // Reset to page 1 when query or source changes
      if ("q" in updates || "source" in updates) {
        params.delete("page");
      }
      router.push(`/documents?${params.toString()}`);
    },
    [router, searchParams],
  );

  // Fetch sources for the filter dropdown
  useEffect(() => {
    fetchSources().then(setSources).catch(() => {});
  }, []);

  // Fetch results whenever params change
  useEffect(() => {
    setLoading(true);

    if (q) {
      searchDocuments(q, page, 20, source || undefined)
        .then((res) => {
          setResults(res.results);
          setDocuments([]);
          setTotal(res.total);
          setPages(res.pages);
        })
        .catch(() => {
          setResults([]);
          setTotal(0);
          setPages(0);
        })
        .finally(() => setLoading(false));
    } else {
      fetchDocuments(page, 20, source || undefined)
        .then((res) => {
          setDocuments(res.documents);
          setResults([]);
          setTotal(res.total);
          setPages(res.pages);
        })
        .catch(() => {
          setDocuments([]);
          setTotal(0);
          setPages(0);
        })
        .finally(() => setLoading(false));
    }
  }, [q, source, page]);

  const isSearch = q.length > 0;
  const items = isSearch
    ? results.map((r) => ({ ...r, downloadStatus: r.download_status, fileSize: r.file_size }))
    : documents.map((d) => ({
        ...d,
        snippet: undefined as string | undefined,
        downloadStatus: d.download_status,
        fileSize: d.file_size,
        rank: 0,
      }));

  return (
    <>
      {/* Search + Filters */}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <SearchInput
            value={q}
            onChange={(v) => updateParams({ q: v })}
            placeholder="Search documents..."
          />
        </div>
        <select
          value={source}
          onChange={(e) => updateParams({ source: e.target.value })}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.source} value={s.source}>
              {s.source} ({s.count})
            </option>
          ))}
        </select>
      </div>

      {/* Results count */}
      <div className="mt-4 text-xs text-muted-foreground">
        {loading
          ? "Loading..."
          : `${total.toLocaleString()} ${isSearch ? "results" : "documents"}${
              source ? ` in ${source}` : ""
            }`}
      </div>

      {/* Results list */}
      <div className="mt-4 space-y-2">
        {items.map((item) => (
          <DocumentCard
            key={item.id}
            id={item.id}
            title={item.title}
            source={item.source}
            filename={item.filename}
            fileSize={item.fileSize}
            createdAt={item.created_at}
            downloadStatus={item.downloadStatus}
            snippet={item.snippet}
          />
        ))}
        {!loading && items.length === 0 && (
          <div className="py-12 text-center text-sm text-muted-foreground">
            {isSearch ? `No results for "${q}"` : "No documents found"}
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="mt-6">
        <Pagination
          page={page}
          pages={pages}
          onPageChange={(p) => updateParams({ page: String(p) })}
        />
      </div>
    </>
  );
}

export default function DocumentsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Search and browse the Epstein document archive
      </p>
      <Suspense
        fallback={
          <div className="mt-8 text-center text-sm text-muted-foreground">Loading...</div>
        }
      >
        <DocumentsContent />
      </Suspense>
    </div>
  );
}
