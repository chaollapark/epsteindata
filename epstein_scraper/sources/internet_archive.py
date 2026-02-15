"""Internet Archive — verified collection identifiers + search API."""

import logging
from typing import Generator, Tuple
from urllib.parse import quote

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class InternetArchiveSource(BaseSource):
    name = "internet_archive"

    SEARCH_URL = "https://archive.org/services/search/v1/scrape"
    METADATA_URL = "https://archive.org/metadata/{identifier}"
    DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"

    # Verified collection identifiers
    KNOWN_COLLECTIONS = [
        "epstein-documents-943-pages",
        "epstein-documents-943-pages-1",
        "j-epstein-files",
        "final-epstein-documents",
        "jeffrey-epstein-court-documents",
        "epsteindocs",
        "epstein-doj-datasets-9-11-jan2026",
        "Epstein-Data-Sets-So-Far",
    ]

    # Search queries for additional items
    QUERIES = [
        'subject:"jeffrey epstein" AND mediatype:texts',
        'subject:"ghislaine maxwell" AND mediatype:texts',
        'creator:"Department of Justice" AND title:"epstein" AND mediatype:texts',
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        seen_identifiers = set()

        # First: process known collections
        for identifier in self.KNOWN_COLLECTIONS:
            if identifier not in seen_identifiers:
                seen_identifiers.add(identifier)
                yield from self._get_collection_files(identifier)

        # Then: search for more items
        state = self.db.get_source_state(self.name)

        for i, query in enumerate(self.QUERIES):
            cursor_key = f"cursor_{i}"
            cursor = state.get(cursor_key)

            try:
                yield from self._search_query(query, cursor, state, cursor_key,
                                              seen_identifiers)
            except Exception as e:
                logger.error(f"[{self.name}] Search query failed: {query}: {e}")

    def _search_query(self, query: str, cursor: str, state: dict, cursor_key: str,
                      seen: set) -> Generator[Tuple[str, dict], None, None]:
        params_base = f"?q={quote(query)}&fields=identifier,title&count=100"

        while True:
            url = self.SEARCH_URL + params_base
            if cursor:
                url += f"&cursor={cursor}"

            try:
                data = self.downloader.fetch_json(url, self.name,
                                                   self.source_config.rate_limit)
            except Exception as e:
                logger.error(f"[{self.name}] Search API error: {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                identifier = item.get("identifier", "")
                if identifier and identifier not in seen:
                    seen.add(identifier)
                    yield from self._get_collection_files(identifier)

            cursor = data.get("cursor")
            if not cursor:
                break

            state[cursor_key] = cursor
            self.db.save_source_state(self.name, state)

    def _get_collection_files(self, identifier: str) -> Generator[Tuple[str, dict], None, None]:
        url = self.METADATA_URL.format(identifier=identifier)

        try:
            data = self.downloader.fetch_json(url, self.name,
                                               self.source_config.rate_limit)
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to get metadata for {identifier}: {e}")
            return

        files = data.get("files", [])
        title = data.get("metadata", {}).get("title", identifier)
        if isinstance(title, list):
            title = title[0] if title else identifier

        for f in files:
            fname = f.get("name", "")
            fmt = f.get("format", "").lower()
            # Download PDFs, text, ZIPs, and common doc formats
            valid_exts = (".pdf", ".txt", ".doc", ".docx", ".zip")
            if not any(fname.lower().endswith(ext) for ext in valid_exts):
                continue

            download_url = self.DOWNLOAD_URL.format(
                identifier=identifier, filename=fname
            )

            yield download_url, {
                "source_id": f"{identifier}/{fname}",
                "filename": f"{identifier}__{fname}".replace("/", "_"),
                "title": f"{title} — {fname}",
                "ia_identifier": identifier,
            }
