"""CourtListener REST API — searches Epstein/Maxwell dockets. Needs free API token."""

import logging
from typing import Generator, Tuple

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class CourtListenerSource(BaseSource):
    name = "courtlistener"

    API_BASE = "https://www.courtlistener.com/api/rest/v4"

    # Known docket IDs for key cases
    DOCKET_IDS = [
        # Giuffre v. Maxwell (SDNY 1:15-cv-07433)
        "4154484",
        # United States v. Maxwell (SDNY 1:20-cr-00330)
        "17318376",
        # United States v. Epstein (SDFL 9:08-cr-80736)
        "6302530",
        # Doe v. Epstein
        "67534580",
    ]

    # Search queries for additional dockets
    SEARCH_QUERIES = [
        "jeffrey epstein",
        "ghislaine maxwell trafficking",
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        token = self.source_config.api_token
        if not token:
            logger.warning(f"[{self.name}] No API token configured — skipping. "
                          "Get a free token at https://www.courtlistener.com/sign-in/")
            return

        headers = {"Authorization": f"Token {token}"}
        seen_docs = set()

        # Process known dockets
        for docket_id in self.DOCKET_IDS:
            yield from self._get_docket_entries(docket_id, headers, seen_docs)

        # Search for additional dockets
        for query in self.SEARCH_QUERIES:
            yield from self._search_dockets(query, headers, seen_docs)

    def _get_docket_entries(self, docket_id: str, headers: dict,
                           seen: set) -> Generator[Tuple[str, dict], None, None]:
        """Get all document entries from a docket."""
        url = f"{self.API_BASE}/docket-entries/?docket={docket_id}&page_size=100"

        while url:
            try:
                data = self.downloader.fetch_json(url, self.name,
                                                   self.source_config.rate_limit,
                                                   headers=headers)
            except Exception as e:
                logger.error(f"[{self.name}] Docket {docket_id} error: {e}")
                break

            for entry in data.get("results", []):
                for rd in entry.get("recap_documents", []):
                    doc_id = rd.get("id", "")
                    if doc_id in seen:
                        continue
                    seen.add(doc_id)

                    filepath = rd.get("filepath_ia") or rd.get("filepath_local")
                    if not filepath:
                        continue

                    if filepath.startswith("http"):
                        pdf_url = filepath
                    else:
                        pdf_url = f"https://storage.courtlistener.com/{filepath}"

                    desc = rd.get("description", f"Entry {entry.get('entry_number', '')}")

                    yield pdf_url, {
                        "source_id": str(doc_id),
                        "filename": f"cl-{docket_id}-{doc_id}.pdf",
                        "title": desc,
                        "docket_id": docket_id,
                        "entry_number": entry.get("entry_number"),
                    }

            url = data.get("next")

    def _search_dockets(self, query: str, headers: dict,
                        seen: set) -> Generator[Tuple[str, dict], None, None]:
        """Search for additional dockets."""
        url = f"{self.API_BASE}/search/?q={query}&type=r&page_size=20"

        try:
            data = self.downloader.fetch_json(url, self.name,
                                               self.source_config.rate_limit,
                                               headers=headers)
        except Exception as e:
            logger.error(f"[{self.name}] Search error for '{query}': {e}")
            return

        for result in data.get("results", []):
            docket_id = result.get("docket_id")
            if docket_id:
                yield from self._get_docket_entries(str(docket_id), headers, seen)
