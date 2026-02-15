"""CLI entry point and orchestrator."""

import argparse
import sys

from .config import load_config
from .db import Database
from .downloader import Downloader
from .extractor import TextExtractor
from .logger import setup_logger
from .sources import ALL_SOURCES


def run_scraper(config, db, source_name=None):
    """Run discovery + download for sources."""
    downloader = Downloader(config, db)
    extractor = TextExtractor(
        min_chars_per_page=config.extraction.min_chars_per_page,
        ocr_dpi=config.extraction.ocr_dpi,
        tesseract_lang=config.extraction.tesseract_lang,
    )

    try:
        if source_name:
            sources_to_run = {source_name: ALL_SOURCES[source_name]}
        else:
            sources_to_run = ALL_SOURCES

        for name, source_cls in sources_to_run.items():
            src_config = config.sources.get(name)
            if src_config and not src_config.enabled:
                print(f"[{name}] Disabled in config, skipping.")
                continue

            print(f"\n{'='*60}")
            print(f"  Source: {name}")
            print(f"{'='*60}")

            source = source_cls(config, db, downloader, extractor)
            source.run()

    finally:
        downloader.close()


def run_extract_only(config, db, source_name=None):
    """Run text extraction on already-downloaded documents."""
    extractor = TextExtractor(
        min_chars_per_page=config.extraction.min_chars_per_page,
        ocr_dpi=config.extraction.ocr_dpi,
        tesseract_lang=config.extraction.tesseract_lang,
    )

    docs = db.get_downloaded_docs(source_name)
    print(f"Found {len(docs)} documents needing text extraction.")

    import os
    for doc in docs:
        local_path = doc["local_path"]
        if not local_path or not local_path.lower().endswith(".pdf"):
            continue
        if not os.path.exists(local_path):
            continue

        source = doc["source"]
        ext_dir = os.path.join(config.data_dir, "extracted_text", source)
        base = os.path.splitext(os.path.basename(local_path))[0]
        output_path = os.path.join(ext_dir, f"{base}.txt")

        try:
            page_count, char_count, ocr_pages, method = extractor.extract(
                local_path, output_path
            )
            db.insert_extraction(
                doc["id"], output_path, method, page_count, char_count, ocr_pages, "completed"
            )
            print(f"  [{source}] {base}: {page_count} pages, {char_count:,} chars, {ocr_pages} OCR")
        except Exception as e:
            db.insert_extraction(doc["id"], "", "error", 0, 0, 0, "failed", str(e))
            print(f"  [{source}] {base}: FAILED — {e}")


def show_stats(db):
    """Display download and extraction statistics."""
    print("\n" + "=" * 70)
    print("  DOWNLOAD STATISTICS")
    print("=" * 70)
    print(f"{'Source':<20} {'Status':<12} {'Count':>8} {'Size':>14}")
    print("-" * 70)

    stats = db.get_stats()
    total_docs = 0
    total_bytes = 0
    for source, status, count, total_b in stats:
        size_str = _format_bytes(total_b)
        print(f"{source:<20} {status:<12} {count:>8} {size_str:>14}")
        total_docs += count
        if status == "downloaded":
            total_bytes += total_b

    print("-" * 70)
    print(f"{'TOTAL':<20} {'':12} {total_docs:>8} {_format_bytes(total_bytes):>14}")

    ext_stats = db.get_extraction_stats()
    if ext_stats:
        print("\n" + "=" * 70)
        print("  EXTRACTION STATISTICS")
        print("=" * 70)
        print(f"{'Source':<20} {'Status':<12} {'Count':>8} {'Chars':>14} {'OCR Pages':>10}")
        print("-" * 70)
        for source, status, count, total_chars, total_ocr in ext_stats:
            print(f"{source:<20} {status:<12} {count:>8} {total_chars:>14,} {total_ocr:>10}")

    print()


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    else:
        return f"{n / 1024 ** 3:.2f} GB"


def main():
    parser = argparse.ArgumentParser(description="Epstein Document Scraper")
    parser.add_argument("--source", type=str, default=None,
                        choices=list(ALL_SOURCES.keys()),
                        help="Run a single source instead of all")
    parser.add_argument("--extract-only", action="store_true",
                        help="Only run text extraction on already-downloaded files")
    parser.add_argument("--stats", action="store_true",
                        help="Show download/extraction statistics")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logger(config.log_dir)
    db = Database(config.db_path)

    if args.stats:
        show_stats(db)
        return

    if args.extract_only:
        run_extract_only(config, db, args.source)
        return

    print("Epstein Document Scraper")
    print(f"Data directory: {config.data_dir}")
    print(f"Database: {config.db_path}")

    run_scraper(config, db, args.source)
    show_stats(db)


if __name__ == "__main__":
    main()
