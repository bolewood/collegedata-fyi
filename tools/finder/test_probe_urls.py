"""Tests for CDS URL discovery helpers in probe_urls.py."""

from __future__ import annotations

import unittest

from tools.finder.probe_urls import (
    is_cds_page,
    select_brave_cds_url,
    should_replace_seed,
    should_skip,
    dedupe_identical_seeds,
)


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


class SeedReplaceTests(unittest.TestCase):
    def test_listing_replaces_pdf(self) -> None:
        self.assertTrue(
            should_replace_seed(
                "https://example.edu/cds-2023.pdf",
                "https://example.edu/ir/cds/",
            )
        )

    def test_pdf_does_not_replace_listing(self) -> None:
        self.assertFalse(
            should_replace_seed(
                "https://example.edu/ir/cds/",
                "https://example.edu/cds-2024.pdf",
            )
        )

    def test_pdf_does_not_replace_other_pdf(self) -> None:
        self.assertFalse(
            should_replace_seed(
                "https://example.edu/cds-2023.pdf",
                "https://example.edu/cds-2024.pdf",
            )
        )


class SkipAndDedupeTests(unittest.TestCase):
    def test_found_skips_until_reprobe(self) -> None:
        school = {"probe_state": {"last_result": "found", "last_probed_at": "2026-04-14T00:00:00Z"}}
        self.assertTrue(should_skip(school, 30))
        self.assertFalse(should_skip(school, 30, reprobe_found=True))

    def test_shared_parent_stays_skipped(self) -> None:
        school = {"probe_state": {"last_result": "shared_parent_seed"}}
        self.assertTrue(should_skip(school, 30))

    def test_dedupe_keeps_main_campus(self) -> None:
        url = "https://www.ohio.edu/instres/commondataset.pdf"
        schools = [
            {"id": "ohio-university-chillicothe-campus", "discovery_seed_url": url, "scrape_policy": "active"},
            {"id": "ohio-university-main-campus", "discovery_seed_url": url, "scrape_policy": "active"},
        ]
        cleared = dedupe_identical_seeds(schools)
        self.assertEqual(cleared, [("ohio-university-chillicothe-campus", "ohio-university-main-campus")])
        self.assertNotIn("discovery_seed_url", schools[0])
        self.assertEqual(schools[0]["probe_state"]["last_result"], "shared_parent_seed")
        self.assertEqual(schools[1]["discovery_seed_url"], url)


if __name__ == "__main__":
    unittest.main()
