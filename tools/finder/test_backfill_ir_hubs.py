"""Tests for the IR-hub backfill selector. No production writes."""

from __future__ import annotations

import unittest

from tools.finder.backfill_ir_hubs import (
    crawl_school_bounded,
    homepage_start_urls,
    is_homepage_seed,
    sanitize_url,
    select_backfill_rows,
    select_recrawl_unitids,
)


class HomepageSeedTests(unittest.TestCase):
    def test_directory_homepage_matches_website(self) -> None:
        self.assertTrue(
            is_homepage_seed("https://www.tulsacc.edu/", "www.tulsacc.edu/")
        )
        self.assertTrue(
            is_homepage_seed(
                "https://www.tulsacc.edu/index.html",
                "https://www.tulsacc.edu/",
            )
        )

    def test_ir_listing_is_not_a_homepage_seed(self) -> None:
        self.assertFalse(
            is_homepage_seed(
                "https://www.tulsacc.edu/about-tcc/institutional-research",
                "https://www.tulsacc.edu/",
            )
        )


class SelectBackfillRowsTests(unittest.TestCase):
    def test_selects_homepage_no_pdfs_found_and_never_checked(self) -> None:
        csv_rows = [
            {
                "unitid": "207935",
                "name": "Tulsa Community College",
                "school_id": "tulsa-community-college",
                "website_domain": "tulsacc.edu",
                "website_url": "https://www.tulsacc.edu/",
                "archive_last_outcome": "no_pdfs_found",
                "latest_seed_url": "https://www.tulsacc.edu/",
                "coverage_status": "no_public_cds_found",
            },
            {
                "unitid": "138187",
                "name": "Valencia College",
                "school_id": "valencia-college",
                "website_domain": "valenciacollege.edu",
                "website_url": "https://valenciacollege.edu/",
                "archive_last_outcome": "",
                "latest_seed_url": "",
                "coverage_status": "not_checked",
            },
            {
                "unitid": "166027",
                "name": "Harvard University",
                "school_id": "harvard",
                "website_domain": "harvard.edu",
                "website_url": "https://www.harvard.edu/",
                "archive_last_outcome": "no_pdfs_found",
                "latest_seed_url": "https://oira.harvard.edu/common-data-set/",
                "coverage_status": "no_public_cds_found",
            },
        ]
        yaml_schools = [
            {
                "id": "tulsa-community-college",
                "name": "Tulsa Community College",
                "domain": "tulsacc.edu",
                "ipeds_id": "207935",
            }
        ]
        selected = select_backfill_rows(csv_rows, yaml_schools)
        ids = {row["ipeds_id"] for row in selected}
        self.assertEqual(ids, {"207935", "138187"})
        tulsa = next(row for row in selected if row["ipeds_id"] == "207935")
        self.assertEqual(tulsa["school_id"], "tulsa-community-college")
        self.assertEqual(tulsa["domain"], "tulsacc.edu")


class RecrawlHelperTests(unittest.TestCase):
    def test_sanitize_url_encodes_spaces(self) -> None:
        self.assertEqual(
            sanitize_url("https://example.edu/common data set/"),
            "https://example.edu/common%20data%20set/",
        )
        self.assertEqual(
            sanitize_url("www.normandale.edu/"),
            "https://www.normandale.edu/",
        )

    def test_homepage_variants_include_http_and_www_flip(self) -> None:
        urls = homepage_start_urls(
            "https://www.alc.edu/",
            "alc.edu",
            variants=True,
        )
        self.assertEqual(
            urls[:4],
            [
                "https://www.alc.edu/",
                "https://alc.edu/",
                "http://www.alc.edu/",
                "http://alc.edu/",
            ],
        )

    def test_default_start_urls_stay_https_only(self) -> None:
        urls = homepage_start_urls("https://www.alc.edu/", "alc.edu")
        self.assertEqual(
            urls,
            ["https://www.alc.edu/", "https://alc.edu/"],
        )

    def test_select_recrawl_unitids_keeps_timeout_dns_and_crawl_errors(self) -> None:
        rows = [
            {
                "ipeds_id": "1",
                "cds": "unclear",
                "notes": "homepage_unreachable homepage_fail:https://a.edu/",
            },
            {
                "ipeds_id": "2",
                "cds": "unclear",
                "notes": "homepage_unreachable dns_miss:www.b.edu",
            },
            {"ipeds_id": "3", "cds": "unclear", "notes": "crawl_error:InvalidURL"},
            {"ipeds_id": "4", "cds": "yes", "notes": "cds_on_ir_hub"},
            {"ipeds_id": "5", "cds": "no", "notes": "no_cds_on_ir_hubs"},
        ]
        self.assertEqual(select_recrawl_unitids(rows), {"1", "2", "3"})


class SchoolDeadlineTests(unittest.TestCase):
    def test_fetch_runs_inside_the_per_school_process(self) -> None:
        # Port 9 on localhost refuses the connection, so nothing leaves the
        # machine. With a deadline the school runs in its own process, and
        # the fetch inside it must still be able to start.
        row = {
            "school_id": "local",
            "name": "Local",
            "ipeds_id": "0",
            "domain": "",
            "website_url": "http://127.0.0.1:9/",
        }
        kwargs = {"rps": 0, "timeout": 3, "retries": 0, "backoff": 0, "variants": False}
        result = crawl_school_bounded(row, 60, kwargs)
        self.assertEqual(result["cds"], "unclear")
        self.assertIn("homepage_fail:network:http://127.0.0.1:9/", result["notes"])
        self.assertNotIn("AssertionError", result["notes"])

if __name__ == "__main__":
    unittest.main()
