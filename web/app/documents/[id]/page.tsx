"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TextViewer } from "@/components/text-viewer";
import { fetchDocument, getPdfUrl, type Document } from "@/lib/api";

function formatBytes(bytes: number | null): string {
  if (!bytes) return "Unknown";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export default function DocumentViewerPage() {
  const params = useParams();
  const docId = Number(params.id);
  const [doc, setDoc] = useState<Document | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) return;
    fetchDocument(docId)
      .then(setDoc)
      .catch((e) => setError(e.message));
  }, [docId]);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center">
        <p className="text-destructive">Error: {error}</p>
        <Link href="/documents" className="mt-4 inline-block text-sm text-muted-foreground hover:underline">
          Back to documents
        </Link>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center text-muted-foreground">
        Loading...
      </div>
    );
  }

  const isDownloaded = doc.download_status === "downloaded";
  const displayTitle = doc.title || doc.filename || `Document #${doc.id}`;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Breadcrumb */}
      <Link
        href="/documents"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        Documents
      </Link>
      <span className="mx-2 text-sm text-muted-foreground">/</span>

      {/* Header */}
      <h1 className="mt-2 text-xl font-bold tracking-tight">{displayTitle}</h1>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <Badge variant="secondary">{doc.source}</Badge>
        {doc.filename && <span>{doc.filename}</span>}
        {doc.file_size && <span>{formatBytes(doc.file_size)}</span>}
        {doc.extraction?.page_count && (
          <span>{doc.extraction.page_count} pages</span>
        )}
        {doc.extraction?.char_count && (
          <span>{doc.extraction.char_count.toLocaleString()} chars</span>
        )}
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        {isDownloaded && (
          <a href={getPdfUrl(doc.id)} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">
              Download PDF
            </Button>
          </a>
        )}
        {doc.url && (
          <a href={doc.url} target="_blank" rel="noopener noreferrer">
            <Button variant="ghost" size="sm">
              Original Source
            </Button>
          </a>
        )}
      </div>

      {/* Extracted text */}
      {doc.extracted_text ? (
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Extracted Text
          </h2>
          <TextViewer text={doc.extracted_text} />
        </div>
      ) : (
        <div className="mt-6 rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
          No extracted text available for this document.
        </div>
      )}
    </div>
  );
}
