"""Ingest extracted text files into ChromaDB for RAG retrieval.

Usage: python -m api.ingest
"""

import os
import re
import sqlite3
import sys

import chromadb


def get_db_path() -> str:
    return os.environ.get("SQLITE_DB_PATH", "epstein.db")


def get_chroma_path() -> str:
    return os.environ.get("CHROMA_DB_PATH", "chroma_db")


def get_data_dir() -> str:
    return os.environ.get("DATA_DIR", "data")


def find_extracted_texts(db_path: str, data_dir: str) -> list[dict]:
    """Find all extracted text files from the database and filesystem."""
    texts = []
    seen_paths = set()

    # First: query the database for extraction records
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT d.id, d.source, d.title, d.filename, d.url,
                   t.output_path, t.page_count
            FROM text_extractions t
            JOIN documents d ON d.id = t.document_id
            WHERE t.status = 'completed' AND t.output_path IS NOT NULL
        """).fetchall()

        for row in rows:
            path = row["output_path"]
            if os.path.exists(path) and path not in seen_paths:
                seen_paths.add(path)
                texts.append({
                    "document_id": row["id"],
                    "source": row["source"],
                    "title": row["title"] or row["filename"] or "",
                    "filename": row["filename"] or "",
                    "url": row["url"],
                    "path": path,
                })
        conn.close()

    # Second: scan the extracted_text directory for any files not in the DB
    extracted_dir = os.path.join(data_dir, "extracted_text")
    if os.path.isdir(extracted_dir):
        for root, _, files in os.walk(extracted_dir):
            for fname in files:
                if not fname.endswith(".txt"):
                    continue
                fpath = os.path.join(root, fname)
                if fpath in seen_paths:
                    continue
                seen_paths.add(fpath)
                # Infer source from directory structure: extracted_text/<source>/...
                rel = os.path.relpath(fpath, extracted_dir)
                parts = rel.split(os.sep)
                source = parts[0] if len(parts) > 1 else "unknown"
                texts.append({
                    "document_id": None,
                    "source": source,
                    "title": fname.replace(".txt", ""),
                    "filename": fname,
                    "url": "",
                    "path": fpath,
                })

    return texts


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 200) -> list[dict]:
    """Split text by page markers, then chunk large pages.

    Returns list of {text, page_num, chunk_idx}.
    """
    # Split on page markers: --- Page N ---
    page_pattern = re.compile(r"---\s*Page\s+(\d+)\s*---")
    segments = page_pattern.split(text)

    pages = []
    if segments[0].strip():
        # Text before first page marker
        pages.append((0, segments[0].strip()))

    for i in range(1, len(segments), 2):
        page_num = int(segments[i])
        page_text = segments[i + 1].strip() if i + 1 < len(segments) else ""
        if page_text:
            pages.append((page_num, page_text))

    if not pages:
        # No page markers found - treat entire text as page 1
        pages = [(1, text.strip())]

    chunks = []
    for page_num, page_text in pages:
        if len(page_text) <= max_chars:
            chunks.append({
                "text": page_text,
                "page_num": page_num,
                "chunk_idx": 0,
            })
        else:
            # Split large pages into overlapping chunks
            idx = 0
            start = 0
            while start < len(page_text):
                end = start + max_chars
                chunk = page_text[start:end]
                chunks.append({
                    "text": chunk,
                    "page_num": page_num,
                    "chunk_idx": idx,
                })
                start = end - overlap
                idx += 1

    return chunks


def ingest():
    """Main ingestion pipeline."""
    from dotenv import load_dotenv
    load_dotenv()

    db_path = get_db_path()
    chroma_path = get_chroma_path()
    data_dir = get_data_dir()

    print(f"Database: {db_path}")
    print(f"ChromaDB: {chroma_path}")
    print(f"Data dir: {data_dir}")

    # Find all extracted text files
    texts = find_extracted_texts(db_path, data_dir)
    if not texts:
        print("No extracted text files found. Run the scraper first:")
        print("  python -m epstein_scraper.main")
        sys.exit(1)

    print(f"Found {len(texts)} extracted text files")

    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(
        name="epstein_docs",
        metadata={"hnsw:space": "cosine"},
    )

    existing_count = collection.count()
    print(f"Existing chunks in ChromaDB: {existing_count}")

    # Process each text file
    total_chunks = 0
    batch_ids = []
    batch_docs = []
    batch_metas = []
    batch_size = 100

    for i, text_info in enumerate(texts):
        try:
            with open(text_info["path"], "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"  Skipping {text_info['path']}: {e}")
            continue

        if not content.strip():
            continue

        chunks = chunk_text(content)

        for chunk in chunks:
            chunk_id = f"{text_info['source']}_{text_info['filename']}_{chunk['page_num']}_{chunk['chunk_idx']}"
            # Ensure unique IDs
            chunk_id = chunk_id.replace("/", "_").replace("\\", "_")

            metadata = {
                "source": text_info["source"],
                "title": text_info["title"],
                "filename": text_info["filename"],
                "url": text_info["url"] or "",
                "page_num": chunk["page_num"],
                "chunk_idx": chunk["chunk_idx"],
            }
            if text_info["document_id"] is not None:
                metadata["document_id"] = text_info["document_id"]

            batch_ids.append(chunk_id)
            batch_docs.append(chunk["text"])
            batch_metas.append(metadata)
            total_chunks += 1

            if len(batch_ids) >= batch_size:
                collection.upsert(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_metas,
                )
                batch_ids, batch_docs, batch_metas = [], [], []

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(texts)} files ({total_chunks} chunks)")

    # Flush remaining
    if batch_ids:
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
        )

    final_count = collection.count()
    print(f"\nIngestion complete:")
    print(f"  Files processed: {len(texts)}")
    print(f"  Total chunks: {total_chunks}")
    print(f"  ChromaDB collection size: {final_count}")


if __name__ == "__main__":
    ingest()
