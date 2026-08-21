"""Tests for CDS URL discovery helpers in probe_urls.py."""

from __future__ import annotations

import unittest

from tools.finder.probe_urls import is_cds_page, select_brave_cds_url


class SelectBraveCdsUrlTests(unittest.TestCase):
    def test_prefers_html_listing_over_year_specific_pdf(self) -> None:
        results = [
            {
                "url": "https://www.ou.edu/content/dam/irr/docs/CDS%202023-2024%20Combined.pdf",
                "title": "CDS 2023-2024 Combined.pdf",
                "description": "Common Data Set 2023-2024",
            },
            {
                "url": "https://www.ou.edu/irr/other-reports",
                "title": "Other Reports | Institutional Research & Reporting",
                "description": "Facts at a Glance, the Factbook, and the Common Data Set (CDS).",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results),
            "https://www.ou.edu/irr/other-reports",
        )

    def test_falls_back_to_pdf_when_no_listing_mentions_cds(self) -> None:
        results = [
            {
                "url": "https://example.edu/ir/cds-2023-2024.pdf",
                "title": "CDS 2023-2024",
                "description": "Common Data Set",
            },
            {
                "url": "https://example.edu/ir/",
                "title": "Institutional Research",
                "description": "Enrollment dashboards and fact books.",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results),
            "https://example.edu/ir/cds-2023-2024.pdf",
        )

    def test_rejects_definitions_pdf_and_listing(self) -> None:
        results = [
            {
                "url": "https://example.edu/cds-definitions.pdf",
                "title": "Common Data Set Definitions",
                "description": "Common Data Set definitions",
            },
            {
                "url": "https://example.edu/cds-template.pdf",
                "title": "CDS template",
                "description": "Common Data Set",
            },
        ]
        self.assertIsNone(select_brave_cds_url(results))


class IsCdsPageTests(unittest.TestCase):
    def test_mixed_ir_hub_cds_heading_below_5kb_still_matches(self) -> None:
        prefix = ("x" * 6000).encode()
        body = prefix + b"<h2>Common Data Set (CDS)</h2>"
        self.assertTrue(is_cds_page(body, "text/html; charset=utf-8"))


if __name__ == "__main__":
    unittest.main()
