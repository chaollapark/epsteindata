"""DOJ Epstein Library — 12 data sets released under the Epstein Files Transparency Act.

The DOJ released documents at justice.gov/epstein starting Dec 19, 2025.
Each data set has a paginated index with ~50 PDFs per page.
Data Set 10 alone has 10,000+ pages. Total corpus is 500K+ documents.
"""

import logging
import re
from typing import Generator, Tuple
from urllib.parse import urljoin, unquote

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class DOJSource(BaseSource):
    name = "doj"

    # Paginated index pages for each data set
    DATA_SET_BASE = "https://www.justice.gov/epstein/doj-disclosures/data-set-{n}-files"

    # Page counts discovered empirically (caps to avoid infinite loops)
    DATA_SET_PAGES = {
        1: 62, 2: 11, 3: 1, 4: 3, 5: 2, 6: 1, 7: 1,
        8: 219, 9: 1974, 10: 10027, 11: 2595, 12: 2,
    }

    # Additional DOJ pages with court records
    COURT_PAGES = [
        "https://www.justice.gov/epstein/court-records/giuffre-v-maxwell-no-115-cv-07433-sdny-2015",
        "https://www.justice.gov/usao-sdny/united-states-v-jeffrey-epstein",
        "https://www.justice.gov/usao-sdny/united-states-v-ghislaine-maxwell",
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        state = self.db.get_source_state(self.name)

        # Paginate through each data set
        for ds_num in range(1, 13):
            max_page = self.DATA_SET_PAGES.get(ds_num, 1)
            state_key = f"ds{ds_num}_page"
            start_page = state.get(state_key, 0)

            logger.info(f"[{self.name}] Data Set {ds_num}: pages {start_page}-{max_page}")

            for page in range(start_page, max_page + 1):
                base_url = self.DATA_SET_BASE.format(n=ds_num)
                url = base_url if page == 0 else f"{base_url}?page={page}"

                try:
                    html = self.downloader.fetch_text(url, self.name,
                                                       self.source_config.rate_limit)
                    count = 0
                    for item in self._extract_pdf_links(html, url, ds_num):
                        count += 1
                        yield item

                    if count == 0 and page > 0:
                        # Empty page means we've gone past the end
                        logger.info(f"[{self.name}] Data Set {ds_num}: no PDFs on page {page}, stopping")
                        break

                except Exception as e:
                    logger.error(f"[{self.name}] Data Set {ds_num} page {page}: {e}")
                    # Don't break — try next page

                # Save pagination state every page
                state[state_key] = page
                self.db.save_source_state(self.name, state)

        # Court record pages
        for page_url in self.COURT_PAGES:
            try:
                html = self.downloader.fetch_text(page_url, self.name,
                                                   self.source_config.rate_limit)
                yield from self._extract_pdf_links(html, page_url, 0)
            except Exception as e:
                logger.error(f"[{self.name}] Failed to scrape {page_url}: {e}")

    def _extract_pdf_links(self, html: str, base_url: str,
                           ds_num: int) -> Generator[Tuple[str, dict], None, None]:
        """Extract PDF links from HTML content."""
        pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.IGNORECASE)
        seen = set()

        for match in pdf_pattern.finditer(html):
            href = match.group(1)
            url = urljoin(base_url, href)

            if url in seen:
                continue
            seen.add(url)

            filename = unquote(url.split("/")[-1])

            yield url, {
                "source_id": f"ds{ds_num}-{filename}" if ds_num else f"court-{filename}",
                "filename": filename,
                "title": f"DOJ DataSet {ds_num}: {filename}" if ds_num else f"DOJ Court: {filename}",
                "dataset": ds_num,
            }
