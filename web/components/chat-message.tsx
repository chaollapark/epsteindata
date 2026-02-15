"use client";

import ReactMarkdown from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Source } from "@/lib/api";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
}

export function ChatMessage({ role, content, sources, isStreaming }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card border border-border",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm">{content}</p>
        ) : (
          <>
            {content ? (
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1">
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
            ) : isStreaming ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-64" />
                <Skeleton className="h-4 w-36" />
              </div>
            ) : null}

            {sources && sources.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-2">
                <span className="text-xs text-muted-foreground mr-1">Sources:</span>
                {sources.map((src, i) => (
                  <Badge
                    key={i}
                    variant="secondary"
                    className="text-xs font-normal"
                  >
                    {src.title || src.filename || src.source}
                    {src.page_num ? ` p.${src.page_num}` : ""}
                  </Badge>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
