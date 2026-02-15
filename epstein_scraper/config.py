"""YAML config loader."""

import os
from dataclasses import dataclass, field
from typing import Dict

import yaml


@dataclass
class DownloadConfig:
    timeout: int = 120
    max_retries: int = 3
    backoff_factor: int = 2
    default_rate_limit: float = 2.0
    user_agent: str = "EpsteinDocScraper/1.0 (Academic Research)"
    max_file_size: int = 524288000


@dataclass
class SourceConfig:
    enabled: bool = True
    rate_limit: float = 2.0
    description: str = ""
    api_token: str = ""


@dataclass
class ExtractionConfig:
    enabled: bool = True
    min_chars_per_page: int = 50
    ocr_dpi: int = 300
    tesseract_lang: str = "eng"


@dataclass
class AppConfig:
    data_dir: str = "data"
    db_path: str = "epstein.db"
    log_dir: str = "logs"
    download: DownloadConfig = field(default_factory=DownloadConfig)
    sources: Dict[str, SourceConfig] = field(default_factory=dict)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    dl_raw = raw.get("download", {})
    download = DownloadConfig(**{k: v for k, v in dl_raw.items() if k in DownloadConfig.__dataclass_fields__})

    sources = {}
    for name, src_raw in raw.get("sources", {}).items():
        sources[name] = SourceConfig(**{k: v for k, v in src_raw.items() if k in SourceConfig.__dataclass_fields__})

    ext_raw = raw.get("extraction", {})
    extraction = ExtractionConfig(**{k: v for k, v in ext_raw.items() if k in ExtractionConfig.__dataclass_fields__})

    return AppConfig(
        data_dir=raw.get("data_dir", "data"),
        db_path=raw.get("db_path", "epstein.db"),
        log_dir=raw.get("log_dir", "logs"),
        download=download,
        sources=sources,
        extraction=extraction,
    )
