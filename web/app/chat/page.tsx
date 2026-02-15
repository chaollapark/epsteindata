"use client";

import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat-input";
import { ChatMessage } from "@/components/chat-message";
import { streamChat, type ChatMessage as ChatMsg, type Source } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

const SUGGESTED_QUESTIONS = [
  "Who visited Epstein's island?",
  "What do the flight logs show?",
  "Summarize the FBI investigation",
  "What was in the non-prosecution agreement?",
  "Who is mentioned in the black book?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }, []);

  async function sendMessage(text?: string) {
    const messageText = text || input.trim();
    if (!messageText || isStreaming) return;

    setInput("");
    const userMsg: Message = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMsg]);

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMsg]);
    setIsStreaming(true);
    scrollToBottom();

    const history: ChatMsg[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        messageText,
        history,
        provider,
        {
          onSources(sources) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = { ...last, sources };
              }
              return updated;
            });
          },
          onText(chunk) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + chunk,
                };
              }
              return updated;
            });
            scrollToBottom();
          },
          onDone() {
            setIsStreaming(false);
          },
          onError(error) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: `Error: ${error}`,
                };
              }
              return updated;
            });
            setIsStreaming(false);
          },
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: `Connection error. Is the API server running on port 8000?`,
            };
          }
          return updated;
        });
      }
      setIsStreaming(false);
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setIsStreaming(false);
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      {/* Provider toggle */}
      <div className="flex items-center justify-end gap-2 border-b border-border px-4 py-2">
        <span className="text-xs text-muted-foreground">Provider:</span>
        <div className="flex rounded-md border border-border">
          <button
            onClick={() => setProvider("anthropic")}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              provider === "anthropic"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            } rounded-l-md`}
          >
            Anthropic
          </button>
          <button
            onClick={() => setProvider("openai")}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              provider === "openai"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            } rounded-r-md`}
          >
            OpenAI
          </button>
        </div>
      </div>

      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center px-4">
            <h2 className="text-2xl font-bold">Talk to the Documents</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Ask questions about the Epstein document archive
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <Button
                  key={q}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                role={msg.role}
                content={msg.content}
                sources={msg.sources}
                isStreaming={
                  isStreaming && i === messages.length - 1 && msg.role === "assistant"
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Input area */}
      {isStreaming ? (
        <div className="flex items-center justify-center border-t border-border p-4">
          <Button variant="outline" size="sm" onClick={handleStop}>
            Stop generating
          </Button>
        </div>
      ) : (
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => sendMessage()}
          disabled={isStreaming}
        />
      )}
    </div>
  );
}
