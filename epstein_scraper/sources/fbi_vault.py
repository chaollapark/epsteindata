"""FBI Vault FOIA release — 22 parts with correct URL pattern."""

import logging
from typing import Generator, Tuple

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")


class FBIVaultSource(BaseSource):
    name = "fbi_vault"

    # Correct URL pattern: "Jeffrey%20Epstein%20Part%20{NN}" (space-encoded, no "of-22")
    # Direct PDF download uses /at_download/file
    BASE_URL = "https://vault.fbi.gov/jeffrey-epstein/Jeffrey%20Epstein%20Part%20{part:02d}/at_download/file"

    # Part 22 has a special suffix
    PART_22_URL = "https://vault.fbi.gov/jeffrey-epstein/Jeffrey%20Epstein%20Part%2022%20(Final)/at_download/file"

    TOTAL_PARTS = 22

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        for part in range(1, self.TOTAL_PARTS + 1):
            if part == 22:
                url = self.PART_22_URL
            else:
                url = self.BASE_URL.format(part=part)

            yield url, {
                "source_id": f"part-{part:02d}",
                "filename": f"jeffrey-epstein-fbi-vault-part-{part:02d}.pdf",
                "title": f"Jeffrey Epstein FBI Vault Part {part} of 22",
                "part": part,
            }
