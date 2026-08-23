"""Tests for CDS URL discovery helpers in probe_urls.py."""

from __future__ import annotations

import json
import unittest

from tools.finder.probe_urls import (
    _save_yaml,
    host_belongs_to_domain,
    is_cds_page,
    looks_like_search_junk,
    select_brave_cds_url,
    should_replace_seed,
    should_skip,
    dedupe_identical_seeds,
    write_probe_summary,
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

    def test_rejects_off_domain_and_search_junk_paths(self) -> None:
        results = [
            {
                "url": "https://search.elms.edu/=327/krespectf/stanford+common+data+set.pdf",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
            {
                "url": "https://other.edu/ir/common-data-set/",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
            {
                "url": "https://www.elms.edu/ir/common-data-set/",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results, "elms.edu"),
            "https://www.elms.edu/ir/common-data-set/",
        )
        self.assertTrue(looks_like_search_junk(results[0]["url"]))
        self.assertTrue(host_belongs_to_domain(results[2]["url"], "elms.edu"))
        self.assertFalse(host_belongs_to_domain(results[1]["url"], "elms.edu"))

    def test_rejects_blog_slugs_that_are_not_cds_paths(self) -> None:
        from tools.finder.probe_urls import looks_like_article_slug

        self.assertTrue(
            looks_like_article_slug(
                "https://www.continents.us/does-harvard-accept-2-9-gpa/"
            )
        )
        self.assertFalse(
            looks_like_article_slug(
                "https://www.albion.edu/offices/registrar/institutional-data/"
            )
        )

    def test_rejects_news_pages_and_non_cds_pdfs(self) -> None:
        from tools.finder.probe_urls import (
            looks_like_news_or_blog,
            looks_like_non_cds_document,
        )

        self.assertTrue(
            looks_like_news_or_blog("https://www.widener.edu/news/noteworthy?page=2")
        )
        self.assertTrue(
            looks_like_non_cds_document(
                "https://www.csuci.edu/budget/documents/otp-budget-presentation-fy17-18.pdf"
            )
        )
        self.assertFalse(
            looks_like_non_cds_document(
                "https://example.edu/ir/CDS_2023-2024.pdf"
            )
        )


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


class CheckpointHelpersTests(unittest.TestCase):
    def test_save_yaml_helper_still_exists(self) -> None:
        self.assertTrue(callable(_save_yaml))

    def test_write_probe_summary_does_not_touch_schools_yaml(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            write_probe_summary(
                path,
                probed=12,
                found=3,
                replaced=2,
                budget_remaining=17,
                still_stuck=9,
            )
            payload = json.loads(path.read_text())
        self.assertEqual(payload["probed"], 12)
        self.assertEqual(payload["found"], 3)
        self.assertEqual(payload["replaced"], 2)
        self.assertEqual(payload["still_stuck"], 9)

    def test_save_yaml_writes_checkpoint(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock

        import tools.finder.probe_urls as probe_urls

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schools.yaml"
            with mock.patch.object(probe_urls, "SCHOOLS_YAML", path):
                probe_urls._save_yaml({"schools": [{"id": "x", "name": "Xavier"}]})
            text = path.read_text()
        self.assertIn("id: x", text)
        self.assertIn("Xavier", text)


if __name__ == "__main__":
    unittest.main()
