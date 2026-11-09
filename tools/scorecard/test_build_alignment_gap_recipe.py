"""Unit tests for canonical slug resolution in build_alignment_gap_recipe.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.scorecard.build_alignment_gap_recipe import (
    build_endowment_panel,
    build_merit_panel,
)


def _filler_scorecard_rows(count: int = 50) -> list[dict[str, object]]:
    rows = []
    for index in range(1, count + 1):
        ipeds_id = f"900{index:03d}"
        rows.append(
            {
                "ipeds_id": ipeds_id,
                "scorecard_data_year": "2022-23",
                "earnings_10yr_median": 65000 + index * 100,
                "median_debt_monthly_payment": 250.0,
                "median_debt_completers": 24000,
                "avg_net_price": 28000,
                "endowment_end": 120000000,
                "instructional_expenditure_fte": 18000,
                "enrollment": 3000,
            }
        )
    return rows


def _filler_directory_rows(count: int = 50) -> list[dict[str, object]]:
    return [
        {
            "ipeds_id": f"900{index:03d}",
            "school_id": f"filler-college-{index:03d}",
            "school_name": f"Filler College {index:03d}",
            "undergraduate_enrollment": 3000,
        }
        for index in range(1, count + 1)
    ]


def _filler_browser_rows(count: int = 50) -> list[dict[str, object]]:
    return [
        {
            "school_id": f"filler-college-{index:03d}",
            "canonical_year": "2024-25",
            "year_start": 2024,
            "sat_composite_p50": 1300,
            "undergrad_enrollment_scorecard": 3000,
            "sub_institutional": None,
        }
        for index in range(1, count + 1)
    ]


def _filler_merit_rows(count: int = 50) -> list[dict[str, object]]:
    return [
        {
            "school_id": f"filler-college-{index:03d}",
            "school_name": f"Filler College {index:03d}",
            "ipeds_id": f"900{index:03d}",
            "canonical_year": "2024-25",
            "merit_profile_quality": "strong",
            "non_need_aid_share_first_year_ft": 0.25,
            "avg_non_need_grant_first_year_ft": 12000,
            "earnings_10yr_median": 65000 + index * 100,
            "median_debt_completers": 24000,
            "median_debt_monthly_payment": 250.0,
            "avg_net_price": 28000,
        }
        for index in range(1, count + 1)
    ]


class AlignmentGapRecipeCanonicalSlugTests(unittest.TestCase):
    def test_endowment_panel_emits_canonical_slugs_for_renamed_schools(self) -> None:
        scorecard_rows = _filler_scorecard_rows() + [
            {
                "ipeds_id": "160755",
                "scorecard_data_year": "2022-23",
                "earnings_10yr_median": 75690,
                "median_debt_monthly_payment": 265.04,
                "median_debt_completers": 25000,
                "avg_net_price": 47593,
                "endowment_end": 1820356000,
                "instructional_expenditure_fte": 48441,
                "enrollment": 8151,
            }
        ]
        directory_rows = _filler_directory_rows() + [
            {
                "ipeds_id": "160755",
                "school_id": "tulane-university-of-louisiana",
                "school_name": "Tulane University of Louisiana",
                "undergraduate_enrollment": 8151,
            }
        ]
        browser_rows = _filler_browser_rows() + [
            {
                "school_id": "tulane-university-of-louisiana",
                "canonical_year": "2025-26",
                "year_start": 2025,
                "sat_composite_p50": 1490,
                "sub_institutional": None,
            }
        ]

        def fake_get_all(_base_url: str, _api_key: str, table: str, _params: object):
            if table == "scorecard_summary":
                return scorecard_rows
            if table == "institution_directory":
                return directory_rows
            if table == "school_browser_rows":
                return browser_rows
            raise AssertionError(f"Unexpected table {table}")

        with patch(
            "tools.scorecard.build_alignment_gap_recipe.postgrest_get_all",
            side_effect=fake_get_all,
        ):
            panel = build_endowment_panel(
                "https://api.collegedata.fyi",
                "anon-key",
                generated_at="2026-11-09",
            )

        school_ids = {row["schoolId"] for row in panel["schools"]}
        self.assertIn("tulane-university", school_ids)
        self.assertNotIn("tulane-university-of-louisiana", school_ids)

    def test_merit_panel_emits_canonical_slugs_for_renamed_schools(self) -> None:
        merit_rows = _filler_merit_rows() + [
            {
                "school_id": "virginia-polytechnic-institute-and-state-university",
                "school_name": "Virginia Polytechnic Institute and State University",
                "ipeds_id": "233921",
                "canonical_year": "2025-26",
                "merit_profile_quality": "strong",
                "non_need_aid_share_first_year_ft": 0.081523,
                "avg_non_need_grant_first_year_ft": 3918,
                "earnings_10yr_median": 86411,
                "median_debt_completers": 23500,
                "median_debt_monthly_payment": 249.14,
                "avg_net_price": 21162,
            },
            {
                "school_id": "tulane-university-of-louisiana",
                "school_name": "Tulane University",
                "ipeds_id": "160755",
                "canonical_year": "2025-26",
                "merit_profile_quality": "strong",
                "non_need_aid_share_first_year_ft": 0.252855,
                "avg_non_need_grant_first_year_ft": 25440,
                "earnings_10yr_median": 75690,
                "median_debt_completers": 25000,
                "median_debt_monthly_payment": 265.04,
                "avg_net_price": 47593,
            },
        ]
        scorecard_rows = _filler_scorecard_rows() + [
            {
                "ipeds_id": "233921",
                "endowment_end": 1824998501,
                "instructional_expenditure_fte": 15000,
                "enrollment": 30428,
                "scorecard_data_year": "2022-23",
            },
            {
                "ipeds_id": "160755",
                "endowment_end": 1820356000,
                "instructional_expenditure_fte": 48441,
                "enrollment": 8151,
                "scorecard_data_year": "2022-23",
            },
        ]
        browser_rows = _filler_browser_rows() + [
            {
                "school_id": "virginia-tech",
                "canonical_year": "2025-26",
                "year_start": 2025,
                "undergrad_enrollment_scorecard": 30428,
                "sub_institutional": None,
            },
            {
                "school_id": "tulane-university-of-louisiana",
                "canonical_year": "2025-26",
                "year_start": 2025,
                "undergrad_enrollment_scorecard": 8151,
                "sub_institutional": None,
            },
        ]

        def fake_get_all(_base_url: str, _api_key: str, table: str, _params: object):
            if table == "school_merit_profile":
                return merit_rows
            if table == "scorecard_summary":
                return scorecard_rows
            if table == "school_browser_rows":
                return browser_rows
            raise AssertionError(f"Unexpected table {table}")

        with patch(
            "tools.scorecard.build_alignment_gap_recipe.postgrest_get_all",
            side_effect=fake_get_all,
        ):
            panel = build_merit_panel(
                "https://api.collegedata.fyi",
                "anon-key",
                generated_at="2026-11-09",
                canonical_median_burden=0.044,
                canonical_median_endowment=40000.0,
            )

        school_ids = {row["schoolId"] for row in panel["schools"]}
        self.assertIn("virginia-tech", school_ids)
        self.assertIn("tulane-university", school_ids)
        self.assertNotIn(
            "virginia-polytechnic-institute-and-state-university", school_ids
        )
        self.assertNotIn("tulane-university-of-louisiana", school_ids)


if __name__ == "__main__":
    unittest.main()
