"""Text extraction from PDFs: PyMuPDF native text + tesseract OCR fallback.

OCR is capped at MAX_OCR_PAGES per document to avoid blocking on huge scanned PDFs.
"""

import logging
import os
import subprocess
import tempfile
from typing import Tuple

logger = logging.getLogger("epstein_scraper")

MAX_OCR_PAGES = 50  # Don't OCR more than 50 pages per document


class TextExtractor:
    def __init__(self, min_chars_per_page: int = 50, ocr_dpi: int = 300,
                 tesseract_lang: str = "eng"):
        self.min_chars = min_chars_per_page
        self.ocr_dpi = ocr_dpi
        self.tesseract_lang = tesseract_lang
        self._has_tesseract = self._check_cmd("tesseract")
        self._has_pdftoppm = self._check_cmd("pdftoppm")
        if not self._has_tesseract:
            logger.warning("tesseract not found — OCR fallback disabled")
        if not self._has_pdftoppm:
            logger.warning("pdftoppm not found — OCR fallback disabled")

    @staticmethod
    def _check_cmd(cmd: str) -> bool:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def extract(self, pdf_path: str, output_path: str) -> Tuple[int, int, int, str]:
        """Extract text from a PDF.

        Returns (page_count, char_count, ocr_pages, method).
        Writes extracted text to output_path.
        """
        import fitz  # PyMuPDF

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        all_text = []
        ocr_pages = 0
        method = "pymupdf"
        can_ocr = self._has_tesseract and self._has_pdftoppm

        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text().strip()

            if len(text) < self.min_chars and can_ocr and ocr_pages < MAX_OCR_PAGES:
                ocr_text = self._ocr_page(pdf_path, page_num)
                if ocr_text and len(ocr_text) > len(text):
                    text = ocr_text
                    ocr_pages += 1
                    method = "pymupdf+ocr"

            all_text.append(f"--- Page {page_num + 1} ---\n{text}")

        doc.close()

        full_text = "\n\n".join(all_text)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        if ocr_pages >= MAX_OCR_PAGES:
            logger.warning(f"OCR capped at {MAX_OCR_PAGES} pages for {pdf_path}")

        return page_count, len(full_text), ocr_pages, method

    def _ocr_page(self, pdf_path: str, page_num: int) -> str:
        """OCR a single page using pdftoppm + tesseract."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                img_prefix = os.path.join(tmpdir, "page")
                p = page_num + 1
                subprocess.run(
                    ["pdftoppm", "-f", str(p), "-l", str(p),
                     "-r", str(self.ocr_dpi), "-png", pdf_path, img_prefix],
                    capture_output=True, timeout=60, check=True,
                )

                images = [f for f in os.listdir(tmpdir) if f.endswith(".png")]
                if not images:
                    return ""

                img_path = os.path.join(tmpdir, images[0])
                result = subprocess.run(
                    ["tesseract", img_path, "stdout", "-l", self.tesseract_lang],
                    capture_output=True, text=True, timeout=120,
                )
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            logger.debug(f"OCR failed for {pdf_path} page {page_num}: {e}")
            return ""
