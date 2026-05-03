from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe import detect_format


def _build_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    return buf.getvalue()


class ProbeDetectFormatTests(unittest.TestCase):
    def test_html_challenge_at_pdf_path_is_other(self):
        fmt, diag = detect_format(
            "school/2025-26/challenge.pdf",
            b"<!DOCTYPE html><html><title>Just a moment...</title></html>",
        )

        self.assertEqual(fmt, "other")
        self.assertIn("html bytes", diag["reason"])

    def test_docx_bytes_at_xlsx_path_are_docx(self):
        data = _build_zip({
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"<w:document/>",
        })

        fmt, _diag = detect_format("school/2025-26/source.xlsx", data)

        self.assertEqual(fmt, "docx")


if __name__ == "__main__":
    unittest.main()
