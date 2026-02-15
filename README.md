# The Epstein Files

A full-stack document archive and AI research platform for exploring the Jeffrey Epstein case files. Search, browse, and chat with thousands of court filings, flight logs, and government records.

**Live site:** [epsteindata.cc](https://epsteindata.cc)

## Architecture

```
epstein_scraper/     Multi-source document scraper (Python)
api/                 FastAPI backend — search, chat, document API
web/                 Next.js frontend (TypeScript, React, Tailwind)
deploy/              Production deployment (systemd, nginx)
```

### Data pipeline

```
Scraper (9 sources)
  → Download PDFs to data/
  → Store metadata in epstein.db (SQLite)
  → Extract text (PyMuPDF + Tesseract OCR fallback)
  → Index for full-text search (FTS5 with BM25 ranking)
  → Embed chunks into ChromaDB (vector similarity for RAG)

API (FastAPI)
  → /api/chat      SSE streaming RAG chat (Claude or GPT-4o)
  → /api/search    Full-text search with snippets
  → /api/documents Browse and read documents
  → /api/stats     Archive statistics

Web (Next.js)
  → Home page with archive stats
  → Chat interface with source citations
  → Document search and browsing
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Optional: `tesseract` + `poppler-utils` (OCR), `aria2c` (torrents)

### Setup

```bash
# Clone
git clone https://github.com/chaollapark/epsteindata.git
cd epsteindata

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r api/requirements.txt

# Frontend
cd web && npm install && cd ..

# Environment variables
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and/or OPENAI_API_KEY
```

### Run locally

```bash
# Start both API (port 8000) and frontend (port 3000)
./dev.sh
```

Or run them separately:

```bash
# API
uvicorn api.server:app --reload --port 8000

# Frontend (in another terminal)
cd web && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Populate data

```bash
# 1. Scrape documents (downloads PDFs, extracts text)
python -m epstein_scraper.main

# Run a single source only
python -m epstein_scraper.main --source doj

# Extract text only (skip downloading)
python -m epstein_scraper.main --extract-only

# Show stats
python -m epstein_scraper.main --stats

# 2. Build full-text search index
python -m api.search --init --populate

# 3. Ingest into ChromaDB for RAG
python -m api.ingest
```

## Document sources

| Source | Description | Status |
|--------|-------------|--------|
| `doj` | DOJ Epstein case disclosures (12 datasets, 500K+ docs) | Enabled |
| `direct_urls` | Curated documents (indictments, flight logs, black book) | Enabled |
| `internet_archive` | Internet Archive collections | Enabled |
| `documentcloud` | DocumentCloud public documents | Enabled |
| `house_oversight` | House Oversight Committee releases | Enabled |
| `torrents` | Torrent downloads via aria2c | Enabled |
| `epsteingraph` | EpsteinGraph.com people and connections | Enabled |
| `courtlistener` | CourtListener docket search | Disabled (needs API token) |
| `fbi_vault` | FBI Vault FOIA releases | Disabled (403 blocked) |

Source configuration is in `config.yaml`.

## API reference

All endpoints are prefixed with `/api`. Rate limits are per-IP.

### Chat (RAG)

```
POST /api/chat
Content-Type: application/json

{
  "message": "What do the flight logs show?",
  "history": [],
  "provider": "anthropic"
}
```

Returns Server-Sent Events:

```
data: {"type": "sources", "sources": [...]}
data: {"type": "text", "text": "Based on the documents..."}
data: {"type": "done"}
```

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | User query |
| `history` | array | Previous `{role, content}` messages |
| `provider` | string | `"anthropic"` or `"openai"` |

Rate limit: 10/minute

### Search

```
GET /api/search?q=flight+logs&page=1&per_page=20&source=doj
```

Returns BM25-ranked results with highlighted snippets.

Rate limit: 30/minute

### Documents

```
GET /api/documents?page=1&per_page=50&source=doj
GET /api/documents/:id
GET /api/documents/:id/pdf
```

Rate limit: 60/minute (list/detail), 20/minute (PDF)

### Other

```
GET /api/sources    List sources with document counts
GET /api/stats      Archive statistics
GET /api/health     Health check
```

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (for Claude chat) |
| `OPENAI_API_KEY` | — | OpenAI API key (for GPT-4o chat) |
| `SQLITE_DB_PATH` | `./epstein.db` | SQLite database path |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB storage path |
| `DATA_DIR` | `./data` | Downloaded files directory |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API URL for the frontend |

### Scraper config (`config.yaml`)

```yaml
download:
  timeout: 120              # HTTP timeout (seconds)
  max_retries: 3            # Retry attempts
  default_rate_limit: 2.0   # Seconds between requests

sources:
  doj:
    enabled: true
    rate_limit: 3.0

extraction:
  enabled: true
  min_chars_per_page: 50    # Below this triggers OCR
  ocr_dpi: 300
```

## Production deployment

The `deploy/` directory contains everything for a Linux server deployment:

```bash
# On the server
bash deploy/deploy.sh
```

This will:
1. Install Python and Node dependencies
2. Build FTS index and ChromaDB
3. Build the Next.js frontend
4. Install systemd services (`epstein-api`, `epstein-web`)
5. Configure nginx reverse proxy

Post-deploy:

```bash
# HTTPS
certbot --nginx -d epsteindata.cc -d www.epsteindata.cc

# Incremental search index updates (add to crontab)
*/15 * * * * cd /root/epstein && .venv/bin/python -m api.search --update
```

### Services

| Service | Port | Command |
|---------|------|---------|
| `epstein-api` | 8000 | `uvicorn api.server:app --workers 4` |
| `epstein-web` | 3000 | Next.js standalone server |
| nginx | 80/443 | Reverse proxy to both |

## Project structure

```
.
├── api/
│   ├── server.py          # FastAPI app and routes
│   ├── rag.py             # RAG pipeline (retrieve + generate)
│   ├── search.py          # FTS5 search index
│   ├── ingest.py          # ChromaDB ingestion
│   └── requirements.txt
├── epstein_scraper/
│   ├── main.py            # CLI entry point
│   ├── db.py              # SQLite database
│   ├── downloader.py      # HTTP download engine
│   ├── extractor.py       # Text extraction (PyMuPDF + OCR)
│   └── sources/           # Source adapters (9 sources)
├── web/
│   ├── app/               # Next.js pages (home, chat, documents)
│   ├── components/        # React components
│   └── lib/api.ts         # API client
├── deploy/
│   ├── deploy.sh          # Deployment script
│   ├── nginx.conf         # nginx config
│   └── *.service          # systemd services
├── config.yaml            # Scraper configuration
├── .env.example           # Environment template
├── dev.sh                 # Local dev startup
└── run.sh                 # Scraper launcher
```

## Contributing

Contributions are welcome. The main areas where help is needed:

- **New document sources** — add a source adapter in `epstein_scraper/sources/`
- **Data quality** — improve text extraction, especially for scanned documents
- **Frontend** — UI improvements, new visualizations, graph views
- **API** — new endpoints, better search ranking

To add a new source:

1. Create `epstein_scraper/sources/your_source.py`
2. Subclass `BaseSource` from `sources/base.py`
3. Implement the `discover()` method to yield document URLs
4. Add config to `config.yaml`
5. Register in `sources/__init__.py`

## License

Public domain research project.
