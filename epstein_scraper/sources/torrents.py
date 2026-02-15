"""Torrent-based downloads using aria2c for verified Epstein document magnets."""

import logging
import os
import subprocess
from typing import Generator, Tuple

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class TorrentSource(BaseSource):
    name = "torrents"

    # Verified magnet links from github.com/yung-megafone/Epstein-Files
    MAGNETS = [
        {
            "magnet": "magnet:?xt=urn:btih:f5cbe5026b1f86617c520d0a9cd610d6254cbe85&dn=epstein-files-structured-full-20250204.tar.zst&xl=221393230690",
            "source_id": "full-structured",
            "filename": "epstein-files-structured-full-20250204.tar.zst",
            "title": "Epstein Files — Full Structured Dataset (221GB)",
        },
        {
            "magnet": "magnet:?xt=urn:btih:7ac8f771678d19c75a26ea6c14e7d4c003fbf9b6&dn=dataset9-more-complete.tar.zst",
            "source_id": "dataset-9-torrent",
            "filename": "dataset9-more-complete.tar.zst",
            "title": "DOJ Data Set 9 (Torrent)",
        },
        {
            "magnet": "magnet:?xt=urn:btih:d509cc4ca1a415a9ba3b6cb920f67c44aed7fe1f&dn=DataSet%2010.zip",
            "source_id": "dataset-10-torrent",
            "filename": "DataSet-10.zip",
            "title": "DOJ Data Set 10 (Torrent)",
        },
        {
            "magnet": "magnet:?xt=urn:btih:59975667f8bdd5baf9945b0e2db8a57d52d32957&dn=DataSet%2011.zip",
            "source_id": "dataset-11-torrent",
            "filename": "DataSet-11.zip",
            "title": "DOJ Data Set 11 (Torrent)",
        },
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_aria2c = self._check_aria2c()
        if not self._has_aria2c:
            logger.warning("[torrents] aria2c not found — torrent downloads disabled. "
                          "Install with: dnf install aria2")

    @staticmethod
    def _check_aria2c() -> bool:
        try:
            subprocess.run(["aria2c", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        """Yield magnet links as URLs."""
        if not self._has_aria2c:
            return

        for torrent in self.MAGNETS:
            yield torrent["magnet"], {
                "source_id": torrent["source_id"],
                "filename": torrent["filename"],
                "title": torrent["title"],
            }

    def run(self):
        """Override run() to use aria2c instead of httpx for magnet downloads."""
        if not self._has_aria2c:
            logger.error("[torrents] aria2c not available, skipping")
            return

        logger.info(f"[{self.name}] Starting torrent downloads...")
        dest_dir = os.path.join(self.config.data_dir, self.name)
        os.makedirs(dest_dir, exist_ok=True)

        for torrent in self.MAGNETS:
            magnet = torrent["magnet"]
            filename = torrent["filename"]

            if self.db.url_exists(magnet):
                logger.info(f"[{self.name}] Already tracked: {filename}")
                continue

            doc_id = self.db.insert_document(
                url=magnet, source=self.name,
                source_id=torrent["source_id"],
                filename=filename, title=torrent["title"],
            )

            try:
                logger.info(f"[{self.name}] Starting: {filename}")
                result = subprocess.run(
                    [
                        "aria2c",
                        "--dir", dest_dir,
                        "--seed-time=0",           # Don't seed after download
                        "--max-tries=5",
                        "--retry-wait=30",
                        "--file-allocation=falloc",
                        "--summary-interval=60",
                        "--bt-stop-timeout=600",   # Stop if no peers for 10 min
                        magnet,
                    ],
                    capture_output=True, text=True, timeout=86400,  # 24h max
                )

                if result.returncode == 0:
                    local_path = os.path.join(dest_dir, filename)
                    if os.path.exists(local_path):
                        file_size = os.path.getsize(local_path)
                        # Compute sha256 for large files in chunks
                        import hashlib
                        sha = hashlib.sha256()
                        with open(local_path, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                sha.update(chunk)
                        self.db.update_download(doc_id, "downloaded", local_path,
                                                sha.hexdigest(), file_size)
                        logger.info(f"[{self.name}] Downloaded: {filename} ({file_size:,} bytes)")
                    else:
                        # aria2c may save with a different name
                        self.db.update_download(doc_id, "downloaded", dest_dir)
                        logger.info(f"[{self.name}] Downloaded: {filename} (saved to {dest_dir})")
                else:
                    error = result.stderr[:500] if result.stderr else f"exit code {result.returncode}"
                    self.db.update_download(doc_id, "failed", error=error)
                    logger.error(f"[{self.name}] Failed: {filename}: {error}")

            except subprocess.TimeoutExpired:
                self.db.update_download(doc_id, "failed", error="Timeout after 24h")
                logger.error(f"[{self.name}] Timeout: {filename}")
            except Exception as e:
                self.db.update_download(doc_id, "failed", error=str(e))
                logger.error(f"[{self.name}] Error: {filename}: {e}")

        logger.info(f"[{self.name}] Done")
