"""Tests for the IR-hub backfill selector. No production writes."""

from __future__ import annotations

import unittest

from tools.finder.backfill_ir_hubs import is_homepage_seed, select_backfill_rows


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


if __name__ == "__main__":
    unittest.main()
