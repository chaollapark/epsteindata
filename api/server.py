"""FastAPI server for the Epstein Files RAG API."""

import json
import os
import sqlite3

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

ATTRIBUTION = {"name": "EpsteinData.cc", "url": "https://epsteindata.cc"}

app = FastAPI(
    title="Epstein Files API",
    version="0.1.0",
    description=(
        "Public API for the Epstein Files document archive. "
        "Search, browse, and chat with thousands of pages of court filings, "
        "flight logs, and government records.\n\n"
        "Powered by [EpsteinData.cc](https://epsteindata.cc)"
    ),
)

# --- Rate limiting ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return Response(
        content=json.dumps({"error": "Rate limit exceeded. Please slow down."}),
        status_code=429,
        media_type="application/json",
    )


# --- CORS ---
default_origins = "http://localhost:3000,http://127.0.0.1:3000"
cors_origins = os.environ.get("CORS_ORIGINS", default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Middleware: attribution header + powered_by field ---
@app.middleware("http")
async def attribution_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "epsteindata.cc"
    return response


def get_db() -> sqlite3.Connection:
    db_path = os.environ.get("SQLITE_DB_PATH", "epstein.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not found. Run the scraper first.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_data_dir() -> str:
    return os.environ.get("DATA_DIR", "data")


def add_powered_by(data: dict) -> dict:
    """Add powered_by attribution to a JSON response dict."""
    data["powered_by"] = ATTRIBUTION
    return data


# --- Models ---

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    provider: str = "anthropic"


# --- Routes ---

@app.get("/api/health")
async def health():
    return add_powered_by({"status": "ok", "service": "epstein-files-api"})


@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, req: ChatRequest):
    """RAG chat endpoint. Returns SSE stream."""
    from api.rag import generate

    async def event_stream():
        try:
            # Send attribution event first
            yield f"data: {json.dumps({'type': 'attribution', 'url': 'https://epsteindata.cc'})}\n\n"

            sources, text_stream = await generate(
                query=req.message,
                history=req.history,
                provider=req.provider,
            )

            # Send sources
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Stream text chunks
            async for chunk in text_stream:
                yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"

            # Signal completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/search")
@limiter.limit("30/minute")
async def search_documents(
    request: Request,
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source: str | None = None,
):
    """Full-text search with BM25 ranking and highlighted snippets."""
    from api.search import search

    conn = get_db()
    try:
        results = search(conn, q, page, per_page, source)
        return add_powered_by(results)
    finally:
        conn.close()


@app.get("/api/documents")
@limiter.limit("60/minute")
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    source: str | None = None,
    status: str | None = None,
):
    """List documents with pagination."""
    conn = get_db()
    try:
        offset = (page - 1) * per_page
        where_clauses = []
        params: list = []

        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if status:
            where_clauses.append("download_status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Get total count
        count_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM documents {where}", params
        ).fetchone()
        total = count_row["cnt"]

        # Get page of documents
        rows = conn.execute(
            f"""SELECT id, url, source, filename, title, file_size,
                       download_status, created_at
                FROM documents {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()

        return add_powered_by({
            "documents": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })
    finally:
        conn.close()


@app.get("/api/documents/{doc_id}")
@limiter.limit("60/minute")
async def get_document(request: Request, doc_id: int):
    """Get a single document with its extracted text."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        doc = dict(row)

        # Get extraction info
        extraction = conn.execute(
            """SELECT output_path, method, page_count, char_count, status
               FROM text_extractions WHERE document_id = ? AND status = 'completed'
               ORDER BY created_at DESC LIMIT 1""",
            (doc_id,),
        ).fetchone()

        extracted_text = None
        if extraction:
            doc["extraction"] = dict(extraction)
            output_path = extraction["output_path"]
            if output_path and os.path.exists(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        extracted_text = f.read()
                except (OSError, UnicodeDecodeError):
                    pass

        doc["extracted_text"] = extracted_text
        return add_powered_by(doc)
    finally:
        conn.close()


@app.get("/api/documents/{doc_id}/pdf")
@limiter.limit("20/minute")
async def get_document_pdf(request: Request, doc_id: int):
    """Serve original PDF file for a document."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT local_path, filename, download_status FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        if row["download_status"] != "downloaded":
            raise HTTPException(status_code=404, detail="Document not downloaded")

        local_path = row["local_path"]
        if not local_path:
            raise HTTPException(status_code=404, detail="File path not found")

        # Path traversal protection: resolve and verify within data dir
        data_dir = os.path.realpath(get_data_dir())
        resolved = os.path.realpath(local_path)
        if not resolved.startswith(data_dir):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(resolved):
            raise HTTPException(status_code=404, detail="File not found on disk")

        filename = row["filename"] or os.path.basename(resolved)
        return FileResponse(
            resolved,
            media_type="application/pdf",
            filename=filename,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    finally:
        conn.close()


@app.get("/api/sources")
@limiter.limit("60/minute")
async def list_sources(request: Request):
    """List distinct sources with document counts."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT source,
                   COUNT(*) as count,
                   SUM(CASE WHEN download_status = 'downloaded' THEN 1 ELSE 0 END) as downloaded
            FROM documents
            GROUP BY source
            ORDER BY count DESC
        """).fetchall()

        return [
            {"source": r["source"], "count": r["count"], "downloaded": r["downloaded"]}
            for r in rows
        ]
    finally:
        conn.close()


@app.get("/api/stats")
async def stats():
    """Get scraper and document statistics."""
    db_path = os.environ.get("SQLITE_DB_PATH", "epstein.db")
    if not os.path.exists(db_path):
        return add_powered_by({
            "total_documents": 0,
            "total_downloaded": 0,
            "total_extracted": 0,
            "total_pages": 0,
            "total_size_bytes": 0,
            "sources": {},
            "db_exists": False,
        })

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Overall document counts
        total = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
        downloaded = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE download_status = 'downloaded'"
        ).fetchone()["cnt"]
        total_size = conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) as s FROM documents WHERE download_status = 'downloaded'"
        ).fetchone()["s"]

        # Extraction stats
        extraction_stats = conn.execute("""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(page_count), 0) as pages,
                   COALESCE(SUM(char_count), 0) as chars
            FROM text_extractions WHERE status = 'completed'
        """).fetchone()

        # Per-source breakdown
        source_rows = conn.execute("""
            SELECT source,
                   COUNT(*) as total,
                   SUM(CASE WHEN download_status = 'downloaded' THEN 1 ELSE 0 END) as downloaded,
                   COALESCE(SUM(file_size), 0) as size_bytes
            FROM documents GROUP BY source
        """).fetchall()

        sources = {}
        for row in source_rows:
            sources[row["source"]] = {
                "total": row["total"],
                "downloaded": row["downloaded"],
                "size_bytes": row["size_bytes"],
            }

        return add_powered_by({
            "total_documents": total,
            "total_downloaded": downloaded,
            "total_extracted": extraction_stats["cnt"],
            "total_pages": extraction_stats["pages"],
            "total_chars": extraction_stats["chars"],
            "total_size_bytes": total_size,
            "sources": sources,
            "db_exists": True,
        })
    finally:
        conn.close()
