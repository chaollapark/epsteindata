"""FTS5 full-text search index management and search queries.

Usage:
    python -m api.search --init --populate   # Initial setup
    python -m api.search --update            # Incremental update (for cron)
"""

import argparse
import os
import sqlite3
import sys

from dotenv import load_dotenv


def get_db_path() -> str:
    return os.environ.get("SQLITE_DB_PATH", "epstein.db")


def get_data_dir() -> str:
    return os.environ.get("DATA_DIR", "data")


def init_fts(db_path: str):
    """Create FTS5 tables and triggers."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS document_texts (
            document_id INTEGER PRIMARY KEY,
            full_text TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, full_text,
            content=document_texts, content_rowid=document_id,
            tokenize='porter unicode61'
        );

        -- Triggers to keep FTS in sync
        CREATE TRIGGER IF NOT EXISTS document_texts_ai AFTER INSERT ON document_texts BEGIN
            INSERT INTO documents_fts(rowid, title, full_text)
            SELECT NEW.document_id,
                   COALESCE((SELECT title FROM documents WHERE id = NEW.document_id), ''),
                   NEW.full_text;
        END;

        CREATE TRIGGER IF NOT EXISTS document_texts_ad AFTER DELETE ON document_texts BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, full_text)
            VALUES('delete', OLD.document_id,
                   COALESCE((SELECT title FROM documents WHERE id = OLD.document_id), ''),
                   OLD.full_text);
        END;

        CREATE TRIGGER IF NOT EXISTS document_texts_au AFTER UPDATE ON document_texts BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, full_text)
            VALUES('delete', OLD.document_id,
                   COALESCE((SELECT title FROM documents WHERE id = OLD.document_id), ''),
                   OLD.full_text);
            INSERT INTO documents_fts(rowid, title, full_text)
            SELECT NEW.document_id,
                   COALESCE((SELECT title FROM documents WHERE id = NEW.document_id), ''),
                   NEW.full_text;
        END;
    """)
    conn.commit()
    conn.close()
    print("FTS5 tables and triggers created.")


def populate_fts(db_path: str, data_dir: str):
    """Read all extracted .txt files and populate the FTS index."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Find all documents with completed extractions
    rows = conn.execute("""
        SELECT d.id, d.title, t.output_path
        FROM text_extractions t
        JOIN documents d ON d.id = t.document_id
        WHERE t.status = 'completed' AND t.output_path IS NOT NULL
    """).fetchall()

    # Also scan extracted_text directory for files not in DB
    extracted_dir = os.path.join(data_dir, "extracted_text")
    db_paths = {r["output_path"] for r in rows}

    inserted = 0
    skipped = 0

    for row in rows:
        doc_id = row["id"]
        output_path = row["output_path"]

        if not os.path.exists(output_path):
            skipped += 1
            continue

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue

        if not text.strip():
            skipped += 1
            continue

        conn.execute(
            "INSERT OR REPLACE INTO document_texts (document_id, full_text) VALUES (?, ?)",
            (doc_id, text),
        )
        inserted += 1

        if inserted % 100 == 0:
            conn.commit()
            print(f"  Indexed {inserted} documents...")

    conn.commit()

    # Rebuild the FTS index for consistency
    print("Rebuilding FTS index...")
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

    print(f"FTS populate complete: {inserted} indexed, {skipped} skipped.")


def update_fts(db_path: str, data_dir: str):
    """Incremental update — index documents not yet in document_texts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    rows = conn.execute("""
        SELECT d.id, d.title, t.output_path
        FROM text_extractions t
        JOIN documents d ON d.id = t.document_id
        LEFT JOIN document_texts dt ON dt.document_id = d.id
        WHERE t.status = 'completed' AND t.output_path IS NOT NULL
              AND dt.document_id IS NULL
    """).fetchall()

    if not rows:
        print("No new documents to index.")
        conn.close()
        return

    inserted = 0
    for row in rows:
        output_path = row["output_path"]
        if not os.path.exists(output_path):
            continue

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        if not text.strip():
            continue

        conn.execute(
            "INSERT OR REPLACE INTO document_texts (document_id, full_text) VALUES (?, ?)",
            (row["id"], text),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Incremental update: {inserted} new documents indexed.")


def search(
    conn: sqlite3.Connection,
    query: str,
    page: int = 1,
    per_page: int = 20,
    source: str | None = None,
) -> dict:
    """Full-text search with BM25 ranking and highlighted snippets."""
    offset = (page - 1) * per_page

    # Build WHERE clause for source filter
    source_filter = ""
    params: list = []
    if source:
        source_filter = "AND d.source = ?"
        params.append(source)

    # Count total matches
    count_sql = f"""
        SELECT COUNT(*) as cnt
        FROM documents_fts fts
        JOIN documents d ON d.id = fts.rowid
        WHERE documents_fts MATCH ?
        {source_filter}
    """
    count_row = conn.execute(count_sql, [query] + params).fetchone()
    total = count_row[0] if count_row else 0

    # Search with BM25 ranking and snippets
    search_sql = f"""
        SELECT d.id, d.title, d.source, d.filename, d.file_size, d.url,
               d.download_status, d.created_at,
               snippet(documents_fts, 1, '<mark>', '</mark>', '...', 48) as snippet,
               bm25(documents_fts) as rank
        FROM documents_fts fts
        JOIN documents d ON d.id = fts.rowid
        WHERE documents_fts MATCH ?
        {source_filter}
        ORDER BY rank
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(search_sql, [query] + params + [per_page, offset]).fetchall()

    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "title": row[1],
            "source": row[2],
            "filename": row[3],
            "file_size": row[4],
            "url": row[5],
            "download_status": row[6],
            "created_at": row[7],
            "snippet": row[8],
            "rank": row[9],
        })

    return {
        "results": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
        "query": query,
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="FTS5 search index management")
    parser.add_argument("--init", action="store_true", help="Create FTS tables and triggers")
    parser.add_argument("--populate", action="store_true", help="Populate FTS from extracted texts")
    parser.add_argument("--update", action="store_true", help="Incremental update (new docs only)")
    parser.add_argument("--search", type=str, help="Test search query")
    args = parser.parse_args()

    db_path = get_db_path()
    data_dir = get_data_dir()

    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        sys.exit(1)

    if args.init:
        init_fts(db_path)

    if args.populate:
        populate_fts(db_path, data_dir)

    if args.update:
        update_fts(db_path, data_dir)

    if args.search:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        results = search(conn, args.search)
        conn.close()
        print(f"Found {results['total']} results for '{args.search}':")
        for r in results["results"]:
            print(f"  [{r['source']}] {r['title'] or r['filename']} (score: {r['rank']:.3f})")
            if r["snippet"]:
                print(f"    {r['snippet'][:120]}...")


if __name__ == "__main__":
    main()
