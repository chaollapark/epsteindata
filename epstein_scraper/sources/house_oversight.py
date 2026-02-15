"""House Oversight Committee Epstein document releases."""

import logging
import re
from typing import Generator, Tuple
from urllib.parse import urljoin

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class HouseOversightSource(BaseSource):
    name = "house_oversight"

    # Verified Oversight Committee release pages
    PAGES = [
        "https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/",
        "https://oversight.house.gov/release/oversight-committee-releases-additional-epstein-estate-documents/",
        "https://oversight.house.gov/release/oversight-committee-releases-records-provided-by-the-epstein-estate-chairman-comer-provides-statement/",
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        # Scrape committee pages for PDF/document links
        for page_url in self.PAGES:
            try:
                html = self.downloader.fetch_text(page_url, self.name,
                                                   self.source_config.rate_limit)
                yield from self._extract_links(html, page_url)
            except Exception as e:
                logger.error(f"[{self.name}] Failed to scrape {page_url}: {e}")

    def _extract_links(self, html: str, base_url: str) -> Generator[Tuple[str, dict], None, None]:
        """Extract PDF and document links from committee pages."""
        pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.IGNORECASE)
        seen = set()

        for match in pdf_pattern.finditer(html):
            href = match.group(1)
            url = urljoin(base_url, href)

            if url in seen:
                continue
            seen.add(url)

            filename = url.split("/")[-1]
            from urllib.parse import unquote
            clean_name = unquote(filename)

            yield url, {
                "source_id": f"house-{clean_name}",
                "filename": clean_name,
                "title": f"House Oversight: {clean_name}",
            }
