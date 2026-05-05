"""Tests for tools/extraction_worker/source_metadata.py.

Pure-function unit tests; no DB or network. Date-parsing and
format-routing logic only — actual PDF/XLSX byte parsing is exercised
via fixtures the caller supplies (kept inline to keep the suite
self-contained).
"""

from __future__ import annotations

import unittest

from source_metadata import (
    extract_source_metadata,
    parse_pdf_date,
)


class ParsePdfDateTests(unittest.TestCase):
    """PDF dates per PDF 1.7 §7.9.4 are awful — many partial forms,
    optional Z/+HH'mm offset suffix. Lock down the cases we observed
    in the wild."""

    def test_full_with_negative_offset(self):
        # Northern Kentucky 2025-26: D:20260423094838-04'00'
        self.assertEqual(
            parse_pdf_date("D:20260423094838-04'00'"),
            "2026-04-23T13:48:38+00:00",  # -04 shifted to UTC
        )

    def test_full_with_positive_offset(self):
        # CDS Initiative 2025-26 fillable PDF template: D:20251015192248+08'00'
        self.assertEqual(
            parse_pdf_date("D:20251015192248+08'00'"),
            "2025-10-15T11:22:48+00:00",  # +08 shifted to UTC
        )

    def test_full_with_zulu_suffix(self):
        self.assertEqual(
            parse_pdf_date("D:20260101000000Z"),
            "2026-01-01T00:00:00+00:00",
        )

    def test_naive_treated_as_utc(self):
        # Some PDFs omit the offset entirely. Treat naive as UTC.
        self.assertEqual(
            parse_pdf_date("D:20260101000000"),
            "2026-01-01T00:00:00+00:00",
        )

    def test_year_only(self):
        # PDF spec allows partial dates; year-only is valid.
        self.assertEqual(
            parse_pdf_date("D:2026"),
            "2026-01-01T00:00:00+00:00",
        )

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_pdf_date("not a date"))
        self.assertIsNone(parse_pdf_date(""))
        self.assertIsNone(parse_pdf_date(None))

    def test_implausible_year_rejected(self):
        # Don't trust 1066, 9999, etc. Outside [1900, 2200] is a parser
        # bug or template-default placeholder, not a real date.
        self.assertIsNone(parse_pdf_date("D:18990101000000"))
        self.assertIsNone(parse_pdf_date("D:99990101000000"))

    def test_offset_without_minutes(self):
        # Some PDFs emit just the hour offset: D:20260423094838-04
        self.assertEqual(
            parse_pdf_date("D:20260423094838-04"),
            "2026-04-23T13:48:38+00:00",
        )


class ExtractSourceMetadataRoutingTests(unittest.TestCase):
    """The router in extract_source_metadata picks the right extractor
    based on source_format. We exercise the empty/unknown paths here;
    real PDF/XLSX parsing is tested in the format-specific extractor
    tests once the fixture infrastructure is in place."""

    def test_empty_bytes_returns_empty(self):
        self.assertEqual(extract_source_metadata(b"", "pdf_flat"), {})

    def test_none_format_returns_empty(self):
        self.assertEqual(extract_source_metadata(b"%PDF-1.7\n", None), {})

    def test_html_format_returns_empty(self):
        # HTML has no embedded creation date in a useful shape; we
        # rely on HTTP Last-Modified instead, captured by archive.ts.
        self.assertEqual(extract_source_metadata(b"<html>", "html"), {})

    def test_docx_format_returns_empty(self):
        # DOCX docProps support exists in python-docx but we don't
        # currently read DOCX in the extraction worker (PRD 007 not
        # shipped). Stays empty until DOCX extraction lands.
        self.assertEqual(extract_source_metadata(b"PK\x03\x04", "docx"), {})

    def test_unknown_format_returns_empty(self):
        self.assertEqual(extract_source_metadata(b"\xff\xff", "rtf"), {})

    def test_garbage_pdf_bytes_returns_empty(self):
        # bad bytes that don't open as a PDF must not raise; the
        # caller depends on this so metadata capture never blocks
        # extraction.
        self.assertEqual(
            extract_source_metadata(b"not a pdf", "pdf_flat"),
            {},
        )

    def test_garbage_xlsx_bytes_returns_empty(self):
        self.assertEqual(
            extract_source_metadata(b"not an xlsx", "xlsx"),
            {},
        )


if __name__ == "__main__":
    unittest.main()
