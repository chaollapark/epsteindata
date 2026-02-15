"use client";

import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null;

  // Show up to 5 page buttons centered around current page
  const range: number[] = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(pages, start + 4);
  for (let i = Math.max(1, end - 4); i <= end; i++) {
    range.push(i);
  }

  return (
    <div className="flex items-center justify-center gap-1">
      <Button
        variant="outline"
        size="sm"
        className="h-8"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </Button>
      {range[0] > 1 && (
        <>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => onPageChange(1)}
          >
            1
          </Button>
          {range[0] > 2 && <span className="px-1 text-xs text-muted-foreground">...</span>}
        </>
      )}
      {range.map((p) => (
        <Button
          key={p}
          variant={p === page ? "default" : "ghost"}
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => onPageChange(p)}
        >
          {p}
        </Button>
      ))}
      {range[range.length - 1] < pages && (
        <>
          {range[range.length - 1] < pages - 1 && (
            <span className="px-1 text-xs text-muted-foreground">...</span>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => onPageChange(pages)}
          >
            {pages}
          </Button>
        </>
      )}
      <Button
        variant="outline"
        size="sm"
        className="h-8"
        disabled={page >= pages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}
