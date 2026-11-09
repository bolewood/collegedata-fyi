"""Per-page PDF text with a pdfium fallback when pypdf cannot read a page.

pypdf (6.2x and 7.0) raises on some font descriptors, e.g. "More than one
/FontFile found" when a descriptor carries both /FontFile and /FontFile3.
Callers used to catch that and treat the page as empty, so a PDF with a good
text layer was sniffed as scanned and force-OCR'd (Grinnell 2023-24 dropped
from 411 to 122 fields), and the layout-text supplement came back empty.

pypdf stays the primary reader so output for every PDF it already handles is
unchanged; pdfium is used only for the pages pypdf fails on.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import pypdf

PdfSource = Union[bytes, str, Path]


class PdfPageTexts:
    """Lazily extract page text, falling back to pdfium per failing page."""

    def __init__(self, source: PdfSource):
        self._source = source
        self.reader = pypdf.PdfReader(
            BytesIO(source) if isinstance(source, bytes) else str(source)
        )
        self._pdfium = None
        self._pdfium_failed = False

    def __len__(self) -> int:
        return len(self.reader.pages)

    def _pdfium_text(self, index: int) -> Optional[str]:
        if self._pdfium_failed:
            return None
        try:
            if self._pdfium is None:
                import pypdfium2

                self._pdfium = pypdfium2.PdfDocument(
                    self._source if isinstance(self._source, bytes) else str(self._source)
                )
            return self._pdfium[index].get_textpage().get_text_range()
        except Exception as exc:  # pdfium missing or unreadable page
            print(
                f"    pdf_text: pdfium fallback failed on page {index}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            self._pdfium_failed = self._pdfium is None
            return None

    def text(self, index: int, layout: bool = False) -> Optional[str]:
        """Text of one page, or None when neither library can read it."""
        page = self.reader.pages[index]
        try:
            if layout:
                try:
                    return page.extract_text(extraction_mode="layout") or ""
                except Exception:
                    pass
            return page.extract_text() or ""
        except Exception:
            return self._pdfium_text(index)
