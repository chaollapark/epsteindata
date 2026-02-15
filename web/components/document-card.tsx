import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getPdfUrl } from "@/lib/api";

function formatBytes(bytes: number | null): string {
  if (!bytes) return "";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

interface DocumentCardProps {
  id: number;
  title: string;
  source: string;
  filename: string;
  fileSize: number | null;
  createdAt: string;
  downloadStatus: string;
  snippet?: string;
}

export function DocumentCard({
  id,
  title,
  source,
  filename,
  fileSize,
  createdAt,
  downloadStatus,
  snippet,
}: DocumentCardProps) {
  const displayTitle = title || filename || `Document #${id}`;
  const date = createdAt ? new Date(createdAt).toLocaleDateString() : "";
  const isDownloaded = downloadStatus === "downloaded";

  return (
    <div className="rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent/50">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Link
            href={`/documents/${id}`}
            className="text-sm font-medium text-foreground hover:underline line-clamp-1"
          >
            {displayTitle}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {source}
            </Badge>
            {fileSize ? <span>{formatBytes(fileSize)}</span> : null}
            {date && <span>{date}</span>}
          </div>
          {snippet && (
            <p
              className="mt-2 text-xs text-muted-foreground line-clamp-2"
              dangerouslySetInnerHTML={{ __html: snippet }}
            />
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Link href={`/documents/${id}`}>
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              View
            </Button>
          </Link>
          {isDownloaded && (
            <a href={getPdfUrl(id)} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="h-7 text-xs">
                PDF
              </Button>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
