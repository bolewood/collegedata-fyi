"""Tests for stuck PDF-seed classification and shared-domain ownership."""

from __future__ import annotations

import unittest
from datetime import date

from tools.finder.stuck_pdf_seeds import (
    choose_canonical_school,
    classify_school,
    default_min_fresh_year,
    is_direct_doc_seed,
    shared_seed_groups,
)


class FreshYearTests(unittest.TestCase):
    def test_august_uses_prior_complete_cycle(self) -> None:
        self.assertEqual(default_min_fresh_year(date(2026, 8, 21)), "2024-25")

    def test_september_expects_previous_academic_year(self) -> None:
        self.assertEqual(default_min_fresh_year(date(2026, 9, 1)), "2025-26")


class ClassifyTests(unittest.TestCase):
    def test_listing_seed_is_not_stuck(self) -> None:
        school = {"id": "ou", "discovery_seed_url": "https://www.ou.edu/irr/other-reports"}
        self.assertIsNone(
            classify_school(school, ["2023-24"], min_fresh_year="2024-25", max_years=2)
        )

    def test_stale_single_pdf_is_stuck(self) -> None:
        school = {
            "id": "portland-state-university",
            "discovery_seed_url": "https://example.edu/cds-2023-2024.pdf",
        }
        row = classify_school(
            school, ["2023-24"], min_fresh_year="2024-25", max_years=2
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["latest"], "2023-24")

    def test_recent_single_pdf_is_not_coverage_stuck(self) -> None:
        school = {
            "id": "example",
            "discovery_seed_url": "https://example.edu/cds-2024-2025.pdf",
        }
        self.assertIsNone(
            classify_school(school, ["2024-25"], min_fresh_year="2024-25", max_years=2)
        )

    def test_zero_years_pdf_is_stuck(self) -> None:
        school = {
            "id": "ohio-university-main-campus",
            "discovery_seed_url": "https://www.ohio.edu/instres/commondataset.pdf",
        }
        row = classify_school(school, [], min_fresh_year="2024-25", max_years=2)
        self.assertIsNotNone(row)
        self.assertEqual(row["n_years"], 0)

    def test_many_years_not_stuck_even_if_pdf(self) -> None:
        school = {"id": "x", "discovery_seed_url": "https://example.edu/a.pdf"}
        self.assertIsNone(
            classify_school(
                school,
                ["2020-21", "2021-22", "2022-23"],
                min_fresh_year="2024-25",
                max_years=2,
            )
        )


class SharedSeedTests(unittest.TestCase):
    def test_direct_doc_detection(self) -> None:
        self.assertTrue(is_direct_doc_seed("https://x.edu/a.pdf"))
        self.assertFalse(is_direct_doc_seed("https://x.edu/ir/cds/"))

    def test_kent_main_beats_regional_campuses(self) -> None:
        schools = [
            {"id": "kent-state-university-at-tuscarawas"},
            {"id": "kent-state-university-at-kent"},
            {"id": "kent-state-university-at-salem"},
        ]
        self.assertEqual(
            choose_canonical_school(schools)["id"],
            "kent-state-university-at-kent",
        )

    def test_manoa_beats_system_office(self) -> None:
        schools = [
            {"id": "university-of-hawaii-system-office"},
            {"id": "university-of-hawaii-at-manoa"},
        ]
        self.assertEqual(
            choose_canonical_school(schools)["id"],
            "university-of-hawaii-at-manoa",
        )

    def test_shared_seed_groups(self) -> None:
        url = "https://www.ohio.edu/instres/commondataset.pdf"
        schools = [
            {"id": "ohio-university-chillicothe-campus", "discovery_seed_url": url},
            {"id": "ohio-university-main-campus", "discovery_seed_url": url},
            {"id": "yale", "discovery_seed_url": "https://oir.yale.edu/common-data-set"},
        ]
        groups = shared_seed_groups(schools)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["keeper_id"], "ohio-university-main-campus")


if __name__ == "__main__":
    unittest.main()
