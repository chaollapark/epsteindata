"""Curated list of verified Epstein document URLs."""

from typing import Generator, Tuple

from .base import BaseSource


class DirectURLsSource(BaseSource):
    name = "direct_urls"

    DOCUMENTS = [
        # SDNY Indictment (2019)
        {
            "url": "https://www.justice.gov/usao-sdny/press-release/file/1180481/download",
            "source_id": "sdny-indictment",
            "filename": "epstein-sdny-indictment-2019.pdf",
            "title": "SDNY Indictment of Jeffrey Epstein (2019)",
        },
        # Maxwell indictment (2020)
        {
            "url": "https://www.justice.gov/usao-sdny/press-release/file/1291481/download",
            "source_id": "maxwell-indictment",
            "filename": "maxwell-indictment-2020.pdf",
            "title": "Indictment of Ghislaine Maxwell (2020)",
        },
        # Maxwell superseding indictment (2021)
        {
            "url": "https://www.justice.gov/usao-sdny/press-release/file/1380016/download",
            "source_id": "maxwell-superseding",
            "filename": "maxwell-superseding-indictment-2021.pdf",
            "title": "Superseding Indictment of Ghislaine Maxwell (2021)",
        },
        # DOJ OIG report on Epstein death at MCC
        {
            "url": "https://oig.justice.gov/sites/default/files/reports/24-043.pdf",
            "source_id": "bop-death-report",
            "filename": "doj-oig-epstein-death-report.pdf",
            "title": "DOJ OIG Report on Epstein Death at MCC",
        },
        # Flight manifests (DocumentCloud)
        {
            "url": "https://assets.documentcloud.org/documents/1507315/epstein-flight-manifests.pdf",
            "source_id": "flight-logs",
            "filename": "epstein-flight-manifests.pdf",
            "title": "Epstein Flight Manifests / Logs",
        },
        # Little Black Book (DocumentCloud, redacted)
        {
            "url": "https://assets.documentcloud.org/documents/1508273/jeffrey-epsteins-little-black-book-redacted.pdf",
            "source_id": "black-book",
            "filename": "epstein-little-black-book-redacted.pdf",
            "title": "Jeffrey Epstein's Little Black Book (Redacted)",
        },
        # Palm Beach police report (DocumentCloud)
        {
            "url": "https://assets.documentcloud.org/documents/6250552/Epstein-Police-Report.pdf",
            "source_id": "pb-police-report",
            "filename": "epstein-palm-beach-police-report.pdf",
            "title": "Palm Beach Police Report — Jeffrey Epstein",
        },
        # Non-prosecution agreement (DocumentCloud)
        {
            "url": "https://assets.documentcloud.org/documents/1508967/non-prosecution-agreement.pdf",
            "source_id": "npa-2007",
            "filename": "epstein-non-prosecution-agreement-2007.pdf",
            "title": "Epstein Non-Prosecution Agreement (2007)",
        },
    ]

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        for doc in self.DOCUMENTS:
            yield doc["url"], {
                "source_id": doc["source_id"],
                "filename": doc["filename"],
                "title": doc["title"],
            }
