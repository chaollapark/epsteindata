"""Abstract base class for all document sources."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Generator, Tuple
from urllib.parse import urlparse

from ..config import AppConfig, SourceConfig
from ..db import Database
from ..downloader import Downloader
from ..extractor import TextExtractor
from ..models import Document

logger = logging.getLogger("epstein_scraper")


class BaseSource(ABC):
    name: str = ""

    def __init__(self, config: AppConfig, db: Database, downloader: Downloader,
                 extractor: TextExtractor):
        self.config = config
        self.db = db
        self.downloader = downloader
        self.extractor = extractor
        self.source_config: SourceConfig = config.sources.get(
            self.name, SourceConfig()
        )

    @abstractmethod
    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        """Yield (url, metadata) tuples for documents to download."""
        ...

    def run(self):
        """Discover documents, download them, and extract text."""
        logger.info(f"[{self.name}] Starting discovery...")
        discovered = 0
        downloaded = 0
        skipped = 0
        failed = 0

        for url, meta in self.discover():
            discovered += 1

            # URL dedup
            if self.db.url_exists(url):
                skipped += 1
                continue

            source_id = meta.get("source_id", "")
            filename = meta.get("filename", self._filename_from_url(url))
            title = meta.get("title", filename)

            doc_id = self.db.insert_document(
                url=url, source=self.name, source_id=source_id,
                filename=filename, title=title, metadata=meta,
            )

            # Download
            dest_dir = os.path.join(self.config.data_dir, self.name)
            safe_filename = f"{source_id}__{filename}" if source_id else filename

            try:
                local_path, sha256, file_size = self.downloader.download_file(
                    url=url, dest_dir=dest_dir, filename=safe_filename,
                    source=self.name, doc_id=doc_id,
                    source_config=self.source_config,
                )

                # SHA-256 content dedup
                existing = self.db.sha256_exists(sha256)
                if existing:
                    logger.info(f"[{self.name}] Content dedup: {filename} matches {existing}")
                    os.remove(local_path)
                    self.db.update_download(doc_id, "skipped", error=f"duplicate of {existing}")
                    skipped += 1
                    continue

                self.db.update_download(doc_id, "downloaded", local_path, sha256, file_size)
                downloaded += 1
                logger.info(f"[{self.name}] Downloaded: {filename} ({file_size:,} bytes)")

                # Extract text if it's a PDF
                if self.config.extraction.enabled and local_path.lower().endswith(".pdf"):
                    self._extract_text(doc_id, local_path)

            except Exception as e:
                self.db.update_download(doc_id, "failed", error=str(e))
                failed += 1
                logger.error(f"[{self.name}] Failed: {filename}: {e}")

        logger.info(
            f"[{self.name}] Done: {discovered} discovered, {downloaded} downloaded, "
            f"{skipped} skipped, {failed} failed"
        )

    def _extract_text(self, doc_id: int, pdf_path: str):
        """Extract text from a downloaded PDF."""
        try:
            ext_dir = os.path.join(self.config.data_dir, "extracted_text", self.name)
            base = os.path.splitext(os.path.basename(pdf_path))[0]
            output_path = os.path.join(ext_dir, f"{base}.txt")

            page_count, char_count, ocr_pages, method = self.extractor.extract(
                pdf_path, output_path
            )
            self.db.insert_extraction(
                doc_id, output_path, method, page_count, char_count, ocr_pages, "completed"
            )
            logger.info(
                f"[{self.name}] Extracted: {base} ({page_count} pages, "
                f"{char_count:,} chars, {ocr_pages} OCR pages)"
            )
        except Exception as e:
            self.db.insert_extraction(doc_id, "", "error", 0, 0, 0, "failed", str(e))
            logger.error(f"[{self.name}] Extraction failed for {pdf_path}: {e}")

    @staticmethod
    def _filename_from_url(url: str) -> str:
        path = urlparse(url).path
        name = os.path.basename(path)
        return name if name else "document.pdf"
