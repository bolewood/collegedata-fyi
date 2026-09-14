"""URL-side academic year parser, including pre-2000 CDS files."""

from __future__ import annotations

import unittest

from tools.finder.academic_year import normalize_academic_year
from tools.finder.headless_download import normalize_year
from tools.finder.playwright_collect import normalize_year as collect_normalize_year


class AcademicYearTests(unittest.TestCase):
    def test_parses_1997_98_filename(self) -> None:
        self.assertEqual(
            normalize_academic_year(
                "https://data-apps.ir.aa.ufl.edu/public/cds/cds1997-98.pdf"
            ),
            "1997-98",
        )

    def test_parses_modern_full_span(self) -> None:
        self.assertEqual(
            normalize_academic_year("CDS_2024-2025_UFMAIN_Post_v4.pdf"),
            "2024-25",
        )

    def test_rejects_drupal_upload_month(self) -> None:
        self.assertIsNone(
            normalize_academic_year("/sites/default/files/2020-04/notes.pdf")
        )

    def test_headless_and_collect_share_the_parser(self) -> None:
        url = "https://example.edu/cds1997-98.pdf"
        self.assertEqual(normalize_year(url), "1997-98")
        self.assertEqual(collect_normalize_year(url), "1997-98")


if __name__ == "__main__":
    unittest.main()
