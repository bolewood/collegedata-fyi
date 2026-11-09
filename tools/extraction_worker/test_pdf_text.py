from __future__ import annotations

import unittest
from unittest import mock

import pypdf

import worker
from pdf_text import PdfPageTexts

LINE = "Common Data Set 2023-2024 A. General Information and enrollment figures"


def _text_pdf(pages: int = 3) -> bytes:
    """A minimal PDF with one line of Helvetica text per page."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    font_obj = 3 + 2 * pages
    for i in range(pages):
        stream = f"BT /F1 12 Tf 50 700 Td ({LINE} page {i}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _font_error(*_args, **_kwargs):
    # What pypdf 6.2x/7.0 raises on Grinnell 2023-24's Times-Roman descriptor.
    raise pypdf.errors.PdfReadError("More than one /FontFile found")


class PdfPageTextsTest(unittest.TestCase):
    def test_reads_with_pypdf_when_it_works(self):
        pages = PdfPageTexts(_text_pdf())
        self.assertIn("General Information", pages.text(0))

    def test_falls_back_to_pdfium_when_pypdf_raises(self):
        pages = PdfPageTexts(_text_pdf())
        with mock.patch.object(pypdf.PageObject, "extract_text", _font_error):
            text = pages.text(0)
            layout_text = pages.text(1, layout=True)
        self.assertIn("General Information", text)
        self.assertIn("page 1", layout_text)

    def test_unreadable_by_both_is_none(self):
        pages = PdfPageTexts(_text_pdf())
        with mock.patch.object(pypdf.PageObject, "extract_text", _font_error), \
             mock.patch.object(PdfPageTexts, "_pdfium_text", return_value=None):
            self.assertIsNone(pages.text(0))


class SniffFormatTest(unittest.TestCase):
    def test_text_pdf_is_flat(self):
        self.assertEqual(worker.sniff_format_from_bytes(_text_pdf()), "pdf_flat")

    def test_pypdf_font_error_does_not_mark_pdf_scanned(self):
        # Grinnell 2023-24: pypdf raised on every sampled page, the sniff
        # counted zero text, and the worker force-OCR'd a PDF with a full
        # text layer (411 -> 122 fields).
        with mock.patch.object(pypdf.PageObject, "extract_text", _font_error):
            self.assertEqual(worker.sniff_format_from_bytes(_text_pdf()), "pdf_flat")

    def test_unreadable_sample_is_unknown_not_scanned(self):
        with mock.patch.object(pypdf.PageObject, "extract_text", _font_error), \
             mock.patch.object(PdfPageTexts, "_pdfium_text", return_value=None):
            self.assertEqual(worker.sniff_format_from_bytes(_text_pdf()), "other")


if __name__ == "__main__":
    unittest.main()
