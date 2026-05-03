"""Unit tests for PRD 007 M1 — content-based DOCX/XLSX sniffing and
DOCX year detection. Self-contained: builds tiny synthetic DOCX/XLSX
ZIP archives in-memory rather than checking real CDS bytes into the
repo. Real fixture validation lives in the M2 extractor tests."""

from __future__ import annotations

import io
import unittest
import zipfile

from worker import (
    choose_source_format,
    detect_year_from_bytes,
    detect_year_from_docx_bytes,
    sniff_format_from_bytes,
    sniff_zip_inner_format,
)


def _build_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    return buf.getvalue()


def _minimal_docx(document_xml: bytes = b"<w:document/>", headers: dict[str, bytes] | None = None) -> bytes:
    entries = {
        "[Content_Types].xml": b"<Types/>",
        "word/document.xml": document_xml,
    }
    for name, body in (headers or {}).items():
        entries[f"word/{name}"] = body
    return _build_zip(entries)


def _minimal_xlsx() -> bytes:
    return _build_zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "xl/workbook.xml": b"<workbook/>",
            "xl/worksheets/sheet1.xml": b"<worksheet/>",
        }
    )


class SniffZipInnerFormatTest(unittest.TestCase):
    def test_minimal_docx_is_docx(self):
        self.assertEqual(sniff_zip_inner_format(_minimal_docx()), "docx")

    def test_minimal_xlsx_is_xlsx(self):
        self.assertEqual(sniff_zip_inner_format(_minimal_xlsx()), "xlsx")

    def test_zip_with_neither_is_other(self):
        data = _build_zip({"random/file.txt": b"hello"})
        self.assertEqual(sniff_zip_inner_format(data), "other")

    def test_zip_with_both_is_other(self):
        # Defensive: if a corrupt or malicious file claims to be both, do
        # not guess. PRD 007 says return "other".
        data = _build_zip(
            {
                "word/document.xml": b"<w:document/>",
                "xl/workbook.xml": b"<workbook/>",
            }
        )
        self.assertEqual(sniff_zip_inner_format(data), "other")

    def test_malformed_zip_is_other(self):
        # ZIP magic bytes followed by truncated junk.
        self.assertEqual(sniff_zip_inner_format(b"PK\x03\x04junk"), "other")


class SniffFormatFromBytesTest(unittest.TestCase):
    """Regression coverage: PDF and HTML routing must not change."""

    def test_pdf_magic_routes_pdf(self):
        # We can't easily build a real PDF without dependencies; just
        # confirm the leading magic-byte branch returns a pdf_* value
        # rather than xlsx for a valid-looking PDF prefix. pypdf will
        # reject the truncated body and the function falls through to
        # "other" — that's fine for this unit; integration tests cover
        # the real PDF routing.
        result = sniff_format_from_bytes(b"%PDF-1.7\nrest of the file")
        self.assertIn(result, ("pdf_flat", "pdf_scanned", "pdf_fillable", "other"))
        self.assertNotIn(result, ("xlsx", "docx"))

    def test_zip_routes_by_inner_format_xlsx(self):
        self.assertEqual(sniff_format_from_bytes(_minimal_xlsx()), "xlsx")

    def test_zip_routes_by_inner_format_docx(self):
        # PRD 007 M1 contract: DOCX bytes return "docx", not "xlsx".
        self.assertEqual(sniff_format_from_bytes(_minimal_docx()), "docx")

    def test_html_still_routes_html(self):
        # PRD 008 regression — make sure ZIP routing change does not
        # break the HTML sniff path that runs after binary magic.
        self.assertEqual(
            sniff_format_from_bytes(b"<!DOCTYPE html><html><body>hi</body></html>"),
            "html",
        )

    def test_unknown_bytes_route_other(self):
        self.assertEqual(sniff_format_from_bytes(b"\x00\x01garbage"), "other")

    def test_choose_source_format_prefers_html_bytes_over_stale_pdf_label(self):
        fmt, corrected = choose_source_format(
            "pdf_flat",
            b"<!DOCTYPE html><html><body>challenge</body></html>",
        )
        self.assertEqual(fmt, "html")
        self.assertTrue(corrected)

    def test_choose_source_format_keeps_declared_when_sniff_unknown(self):
        fmt, corrected = choose_source_format("pdf_flat", b"\x00\x01garbage")
        self.assertEqual(fmt, "pdf_flat")
        self.assertFalse(corrected)


class DetectYearFromDocxBytesTest(unittest.TestCase):
    def test_year_in_body(self):
        body = b"""<?xml version='1.0'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
<w:body><w:p><w:r><w:t>Common Data Set 2024-2025</w:t></w:r></w:p></w:body>
</w:document>"""
        self.assertEqual(detect_year_from_docx_bytes(_minimal_docx(body)), "2024-25")

    def test_year_only_in_header_xml(self):
        # JMU 2024-25 case: title lives in word/header*.xml, not the
        # body. Detector must read header parts.
        header = b"""<?xml version='1.0'?>
<w:hdr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
<w:p><w:r><w:t>Common Data Set 2024-2025</w:t></w:r></w:p>
</w:hdr>"""
        data = _minimal_docx(b"<w:document/>", headers={"header1.xml": header})
        self.assertEqual(detect_year_from_docx_bytes(data), "2024-25")

    def test_split_runs_with_whitespace(self):
        # Word splits a single phrase across multiple <w:t> runs. After
        # tag stripping the year regex must still match across the
        # collapsed whitespace.
        body = b"""<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
<w:body>
  <w:p>
    <w:r><w:t>Common Data </w:t></w:r>
    <w:r><w:t xml:space='preserve'>Set </w:t></w:r>
    <w:r><w:t>2025-26</w:t></w:r>
  </w:p>
</w:body>
</w:document>"""
        self.assertEqual(detect_year_from_docx_bytes(_minimal_docx(body)), "2025-26")

    def test_no_year_returns_none(self):
        body = b"<w:document><w:body><w:p><w:r><w:t>just words</w:t></w:r></w:p></w:body></w:document>"
        self.assertIsNone(detect_year_from_docx_bytes(_minimal_docx(body)))

    def test_invalid_year_span_returns_none(self):
        # 2024-2026 is not a valid one-year span and must be rejected.
        body = b"<w:document><w:body><w:p><w:r><w:t>Common Data Set 2024-2026</w:t></w:r></w:p></w:body></w:document>"
        self.assertIsNone(detect_year_from_docx_bytes(_minimal_docx(body)))

    def test_multiple_distinct_years_returns_none(self):
        # Strict invariant: ambiguous → None, never guess.
        body = b"""<w:document><w:body>
<w:p><w:r><w:t>Common Data Set 2023-2024</w:t></w:r></w:p>
<w:p><w:r><w:t>Common Data Set 2024-2025</w:t></w:r></w:p>
</w:body></w:document>"""
        self.assertIsNone(detect_year_from_docx_bytes(_minimal_docx(body)))

    def test_non_docx_zip_returns_none(self):
        self.assertIsNone(detect_year_from_docx_bytes(_minimal_xlsx()))

    def test_non_zip_returns_none(self):
        self.assertIsNone(detect_year_from_docx_bytes(b"%PDF-1.7"))


class DetectYearFromBytesDispatchTest(unittest.TestCase):
    def test_dispatches_to_docx_for_docx_bytes(self):
        body = b"<w:document><w:body><w:p><w:r><w:t>Common Data Set 2025-2026</w:t></w:r></w:p></w:body></w:document>"
        self.assertEqual(detect_year_from_bytes(_minimal_docx(body)), "2025-26")

    def test_returns_none_for_xlsx_bytes(self):
        # Year detection from XLSX is intentionally unimplemented; PRD
        # 007 only adds DOCX parity. The dispatcher must not crash.
        self.assertIsNone(detect_year_from_bytes(_minimal_xlsx()))

    def test_returns_none_for_unknown_bytes(self):
        self.assertIsNone(detect_year_from_bytes(b"random garbage"))


if __name__ == "__main__":
    unittest.main()
