"""Data models for the scraper."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    url: str
    source: str
    source_id: str = ""
    filename: str = ""
    title: str = ""
    metadata: dict = field(default_factory=dict)
    # Filled after download
    local_path: Optional[str] = None
    sha256: Optional[str] = None
    file_size: Optional[int] = None
    download_status: str = "pending"  # pending, downloaded, failed, skipped
    error: Optional[str] = None
