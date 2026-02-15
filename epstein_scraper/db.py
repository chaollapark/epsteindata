"""SQLite database for tracking documents, extractions, and source state."""

import json
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple


class Database:
    def __init__(self, db_path: str = "epstein.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT DEFAULT '',
                filename TEXT DEFAULT '',
                title TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                local_path TEXT,
                sha256 TEXT,
                file_size INTEGER,
                download_status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            );

            CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(download_status);
            CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);

            CREATE TABLE IF NOT EXISTS text_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                output_path TEXT,
                method TEXT,
                page_count INTEGER,
                char_count INTEGER,
                ocr_pages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS source_state (
                source TEXT PRIMARY KEY,
                state TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

    def url_exists(self, url: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM documents WHERE url = ?", (url,)).fetchone()
        return row is not None

    def sha256_exists(self, sha256: str) -> Optional[str]:
        """Return the local_path of an existing file with the same hash, or None."""
        row = self._conn.execute(
            "SELECT local_path FROM documents WHERE sha256 = ? AND download_status = 'downloaded' LIMIT 1",
            (sha256,),
        ).fetchone()
        return row["local_path"] if row else None

    def insert_document(self, url: str, source: str, source_id: str = "",
                        filename: str = "", title: str = "", metadata: dict = None) -> int:
        meta_json = json.dumps(metadata or {})
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO documents (url, source, source_id, filename, title, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, source, source_id, filename, title, meta_json),
        )
        self._conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        # Already exists, get its id
        row = self._conn.execute("SELECT id FROM documents WHERE url = ?", (url,)).fetchone()
        return row["id"]

    def update_download(self, doc_id: int, status: str, local_path: str = None,
                        sha256: str = None, file_size: int = None, error: str = None):
        self._conn.execute(
            """UPDATE documents SET download_status = ?, local_path = ?, sha256 = ?,
               file_size = ?, error = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, local_path, sha256, file_size, error, doc_id),
        )
        self._conn.commit()

    def insert_extraction(self, document_id: int, output_path: str, method: str,
                          page_count: int, char_count: int, ocr_pages: int, status: str,
                          error: str = None):
        self._conn.execute(
            """INSERT INTO text_extractions
               (document_id, output_path, method, page_count, char_count, ocr_pages, status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (document_id, output_path, method, page_count, char_count, ocr_pages, status, error),
        )
        self._conn.commit()

    def get_downloaded_docs(self, source: str = None) -> List[dict]:
        """Get documents that are downloaded but not yet extracted."""
        if source:
            rows = self._conn.execute(
                """SELECT d.* FROM documents d
                   LEFT JOIN text_extractions t ON d.id = t.document_id AND t.status = 'completed'
                   WHERE d.download_status = 'downloaded' AND d.source = ? AND t.id IS NULL""",
                (source,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT d.* FROM documents d
                   LEFT JOIN text_extractions t ON d.id = t.document_id AND t.status = 'completed'
                   WHERE d.download_status = 'downloaded' AND t.id IS NULL""",
            ).fetchall()
        return [dict(r) for r in rows]

    def get_pending_docs(self, source: str) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE source = ? AND download_status = 'pending'",
            (source,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> List[Tuple]:
        rows = self._conn.execute(
            """SELECT source, download_status, COUNT(*) as cnt,
                      COALESCE(SUM(file_size), 0) as total_bytes
               FROM documents GROUP BY source, download_status ORDER BY source, download_status"""
        ).fetchall()
        return [tuple(r) for r in rows]

    def get_extraction_stats(self) -> List[Tuple]:
        rows = self._conn.execute(
            """SELECT d.source, t.status, COUNT(*) as cnt,
                      COALESCE(SUM(t.char_count), 0) as total_chars,
                      COALESCE(SUM(t.ocr_pages), 0) as total_ocr_pages
               FROM text_extractions t
               JOIN documents d ON d.id = t.document_id
               GROUP BY d.source, t.status ORDER BY d.source"""
        ).fetchall()
        return [tuple(r) for r in rows]

    def save_source_state(self, source: str, state: dict):
        self._conn.execute(
            """INSERT INTO source_state (source, state, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(source) DO UPDATE SET state = ?, updated_at = CURRENT_TIMESTAMP""",
            (source, json.dumps(state), json.dumps(state)),
        )
        self._conn.commit()

    def get_source_state(self, source: str) -> dict:
        row = self._conn.execute(
            "SELECT state FROM source_state WHERE source = ?", (source,)
        ).fetchone()
        return json.loads(row["state"]) if row else {}
