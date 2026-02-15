# Epstein Files — Web Frontend

Next.js 16 frontend for the Epstein Files archive. Built with React 19, TypeScript, Tailwind CSS, and shadcn/ui.

## Pages

- **/** — Home page with archive stats and intro
- **/chat** — AI chat interface (RAG with source citations, SSE streaming)
- **/documents** — Full-text search and document browsing

## Development

```bash
npm install
npm run dev
```

Expects the API running at `http://localhost:8000` (or set `NEXT_PUBLIC_API_URL`).

## Components

| Component | Purpose |
|-----------|---------|
| `header.tsx` | Navigation and theme toggle |
| `footer.tsx` | Attribution links |
| `chat-input.tsx` | Message input with send button |
| `chat-message.tsx` | Chat bubbles with source citations |
| `search-input.tsx` | Search box |
| `document-card.tsx` | Document list item with metadata |
| `pagination.tsx` | Page navigation |
| `text-viewer.tsx` | Extracted text display |

## API Client

`lib/api.ts` contains typed fetch wrappers for all API endpoints:

- `fetchStats()` — archive statistics
- `searchDocuments()` — FTS5 search
- `fetchDocuments()` / `fetchDocument()` — browse documents
- `streamChat()` — SSE streaming RAG chat
- `fetchSources()` — list document sources
