"""HTTP download engine with rate limiting, retries, SHA-256 dedup, and streaming."""

import hashlib
import logging
import os
import time
from typing import Optional, Tuple

import httpx

from .config import AppConfig, SourceConfig
from .db import Database

logger = logging.getLogger("epstein_scraper")


class Downloader:
    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self._last_request_time: dict = {}  # per-source timestamps
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.config.download.timeout, connect=30),
                follow_redirects=True,
                headers={"User-Agent": self.config.download.user_agent},
                cookies={"justiceGovAgeVerified": "true"},  # DOJ age gate bypass
            )
        return self._client

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()

    def rate_limit(self, source: str, rate: float):
        last = self._last_request_time.get(source, 0)
        elapsed = time.time() - last
        if elapsed < rate:
            time.sleep(rate - elapsed)
        self._last_request_time[source] = time.time()

    def download_file(self, url: str, dest_dir: str, filename: str, source: str,
                      doc_id: int, source_config: SourceConfig) -> Tuple[str, str, int]:
        """Download a file. Returns (local_path, sha256, file_size).
        Raises on failure."""
        os.makedirs(dest_dir, exist_ok=True)
        local_path = os.path.join(dest_dir, filename)

        rate = source_config.rate_limit if source_config else self.config.download.default_rate_limit
        max_retries = self.config.download.max_retries
        backoff = self.config.download.backoff_factor

        last_error = None
        for attempt in range(max_retries):
            try:
                self.rate_limit(source, rate)
                return self._stream_download(url, local_path)
            except (httpx.HTTPStatusError, httpx.TransportError, OSError) as e:
                last_error = e
                wait = backoff ** attempt
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {url}: {e} (wait {wait}s)")
                time.sleep(wait)

        raise last_error

    def _stream_download(self, url: str, local_path: str) -> Tuple[str, str, int]:
        """Stream download with SHA-256 computation."""
        sha = hashlib.sha256()
        size = 0

        with self.client.stream("GET", url) as resp:
            resp.raise_for_status()

            # Detect HTML served instead of expected binary (age gate, error pages)
            ct = resp.headers.get("content-type", "")
            if "text/html" in ct and local_path.lower().endswith((".pdf", ".zip")):
                raise ValueError(f"Expected binary but got HTML (content-type: {ct})")

            # Check content-length if available
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > self.config.download.max_file_size:
                raise ValueError(f"File too large: {content_length} bytes")

            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)
                    if size > self.config.download.max_file_size:
                        raise ValueError(f"File exceeded max size during download: {size} bytes")

        return local_path, sha.hexdigest(), size

    def fetch_json(self, url: str, source: str, rate: float = None,
                   headers: dict = None) -> dict:
        """Fetch JSON from a URL with rate limiting."""
        r = rate or self.config.download.default_rate_limit
        self.rate_limit(source, r)

        resp = self.client.get(url, headers=headers or {})
        resp.raise_for_status()
        return resp.json()

    def fetch_text(self, url: str, source: str, rate: float = None) -> str:
        """Fetch text/HTML from a URL with rate limiting."""
        r = rate or self.config.download.default_rate_limit
        self.rate_limit(source, r)

        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.text
