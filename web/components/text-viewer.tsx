"use client";

interface TextViewerProps {
  text: string;
}

export function TextViewer({ text }: TextViewerProps) {
  // Split on page markers and render with visual separators
  const parts = text.split(/(---\s*Page\s+\d+\s*---)/);

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="max-h-[70vh] overflow-y-auto p-4 font-mono text-sm leading-relaxed">
        {parts.map((part, i) => {
          const pageMatch = part.match(/---\s*Page\s+(\d+)\s*---/);
          if (pageMatch) {
            return (
              <div
                key={i}
                className="my-4 flex items-center gap-3 text-xs text-muted-foreground"
              >
                <div className="h-px flex-1 bg-border" />
                <span className="font-medium">Page {pageMatch[1]}</span>
                <div className="h-px flex-1 bg-border" />
              </div>
            );
          }
          if (!part.trim()) return null;
          return (
            <pre key={i} className="whitespace-pre-wrap break-words text-foreground">
              {part}
            </pre>
          );
        })}
      </div>
    </div>
  );
}
