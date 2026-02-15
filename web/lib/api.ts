const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Source {
  title: string;
  filename: string;
  page_num: number | null;
  source: string;
  url: string;
  distance: number;
}

export interface StatsResponse {
  total_documents: number;
  total_downloaded: number;
  total_extracted: number;
  total_pages: number;
  total_chars: number;
  total_size_bytes: number;
  sources: Record<string, { total: number; downloaded: number; size_bytes: number }>;
  db_exists: boolean;
}

export interface Document {
  id: number;
  url: string;
  source: string;
  filename: string;
  title: string;
  file_size: number | null;
  download_status: string;
  created_at: string;
  local_path?: string;
  extraction?: {
    output_path: string;
    method: string;
    page_count: number;
    char_count: number;
    status: string;
  };
  extracted_text?: string | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface SearchResult {
  id: number;
  title: string;
  source: string;
  filename: string;
  file_size: number | null;
  url: string;
  download_status: string;
  created_at: string;
  snippet: string;
  rank: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  query: string;
}

export interface SourceInfo {
  source: string;
  count: number;
  downloaded: number;
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function searchDocuments(
  q: string,
  page: number = 1,
  perPage: number = 20,
  source?: string,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, page: String(page), per_page: String(perPage) });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/api/search?${params}`);
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function fetchDocuments(
  page: number = 1,
  perPage: number = 20,
  source?: string,
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/api/documents?${params}`);
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function fetchDocument(id: number): Promise<Document> {
  const res = await fetch(`${API_BASE}/api/documents/${id}`);
  if (!res.ok) throw new Error("Failed to fetch document");
  return res.json();
}

export async function fetchSources(): Promise<SourceInfo[]> {
  const res = await fetch(`${API_BASE}/api/sources`);
  if (!res.ok) throw new Error("Failed to fetch sources");
  return res.json();
}

export function getPdfUrl(docId: number): string {
  return `${API_BASE}/api/documents/${docId}/pdf`;
}

export interface StreamCallbacks {
  onSources: (sources: Source[]) => void;
  onText: (text: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

export async function streamChat(
  message: string,
  history: ChatMessage[],
  provider: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, provider }),
    signal,
  });

  if (!res.ok) {
    callbacks.onError(`API error: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const event = JSON.parse(jsonStr);
        switch (event.type) {
          case "sources":
            callbacks.onSources(event.sources);
            break;
          case "text":
            callbacks.onText(event.text);
            break;
          case "done":
            callbacks.onDone();
            break;
          case "error":
            callbacks.onError(event.error);
            break;
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }
}
