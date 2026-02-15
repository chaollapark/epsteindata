"""DocumentCloud — public search API with cursor-based pagination."""

import logging
from typing import Generator, Tuple

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class DocumentCloudSource(BaseSource):
    name = "documentcloud"

    SEARCH_URL = "https://api.www.documentcloud.org/api/documents/search/"
    QUERIES = [
        "jeffrey epstein",
        "ghislaine maxwell",
        "epstein flight logs",
        "epstein grand jury",
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        seen_ids = set()

        for query in self.QUERIES:
            try:
                yield from self._search(query, seen_ids)
            except Exception as e:
                logger.error(f"[{self.name}] Search failed for '{query}': {e}")

    def _search(self, query: str, seen_ids: set) -> Generator[Tuple[str, dict], None, None]:
        url = f"{self.SEARCH_URL}?q={query}&per_page=100"

        while url:
            try:
                data = self.downloader.fetch_json(url, self.name,
                                                   self.source_config.rate_limit)
            except Exception as e:
                logger.error(f"[{self.name}] API error: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for doc in results:
                doc_id = str(doc.get("id", ""))
                if not doc_id or doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)

                slug = doc.get("slug", "document")
                title = doc.get("title", f"DocumentCloud {doc_id}")

                # Construct PDF URL
                pdf_url = f"https://assets.documentcloud.org/documents/{doc_id}/{slug}.pdf"

                yield pdf_url, {
                    "source_id": doc_id,
                    "filename": f"{doc_id}-{slug}.pdf",
                    "title": title,
                    "dc_id": doc_id,
                    "pages": doc.get("page_count", 0),
                }

            # Cursor-based pagination — follow the "next" URL
            url = data.get("next")
            if url:
                # Save progress
                self.db.save_source_state(self.name, {"next_url": url, "query": query})
