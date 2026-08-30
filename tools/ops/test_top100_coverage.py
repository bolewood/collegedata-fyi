"""Tests for the priority-100 coverage scorer and cohort files."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from tools.ops.top100_coverage import (
    coverage_bar_years,
    hosted_gap_ids,
    load_allowlist,
    load_cohort_ids,
    resolve_residential_only,
    score_school,
    suggested_route,
    summarize,
    year_status,
)

ROOT = Path(__file__).resolve().parents[2]
COHORT = ROOT / "data" / "watchlists" / "priority_coverage.yaml"
ALLOWLIST = ROOT / "data" / "watchlists" / "residential_allowlist.yaml"
SCHOOLS = ROOT / "tools" / "finder" / "schools.yaml"


def _school_ids() -> set[str]:
    doc = yaml.safe_load(SCHOOLS.read_text())
    return {row["id"] for row in doc["schools"] if "id" in row}


class CohortFileTests(unittest.TestCase):
    def test_exactly_100_canonical_ids(self) -> None:
        ids = load_cohort_ids(COHORT)
        self.assertEqual(len(ids), 100)
        known = _school_ids()
        missing = [sid for sid in ids if sid not in known]
        self.assertEqual(missing, [])

    def test_cohort_yaml_has_no_rank_fields(self) -> None:
        doc = yaml.safe_load(COHORT.read_text())
        for row in doc["schools"]:
            self.assertEqual(set(row), {"school_id"})
        self.assertNotIn("usnews", COHORT.read_text().lower().replace(" ", ""))

    def test_allowlist_is_nyu_only(self) -> None:
        allow = load_allowlist(ALLOWLIST)
        self.assertEqual(list(allow), ["nyu"])


class CoverageContractTests(unittest.TestCase):
    def test_year_status_requires_bytes(self) -> None:
        self.assertEqual(year_status(None), "missing")
        self.assertEqual(
            year_status({"published": True, "sha256": None, "has_source_artifact": False}),
            "missing_bytes",
        )
        self.assertEqual(
            year_status({
                "published": True,
                "sha256": "abc",
                "has_source_artifact": False,
                "has_bytes": False,
            }),
            "missing_bytes",
        )
        self.assertEqual(
            year_status({
                "published": True,
                "sha256": "abc",
                "has_source_artifact": True,
                "has_bytes": True,
            }),
            "bytes",
        )

    def test_withdrawn_is_not_covered(self) -> None:
        self.assertEqual(
            year_status({"published": False, "sha256": "abc", "has_source_artifact": True}),
            "missing",
        )

    def test_listing_vs_pdf_seed(self) -> None:
        years = ["2025-26", "2024-25"]
        coverage = {
            year: {
                "published": True,
                "sha256": "x",
                "has_source_artifact": True,
                "has_bytes": True,
            }
            for year in years
        }
        pdf_row = score_school(
            "hamilton",
            {
                "id": "hamilton",
                "discovery_seed_url": "https://example.edu/cds-2020-2021.pdf",
            },
            years,
            coverage,
            starting_urls={},
            waf_ids=set(),
            allowlist={},
        )
        self.assertFalse(pdf_row["listing"])
        self.assertFalse(pdf_row["in_bar"])
        self.assertEqual(pdf_row["gap_reason"], "pdf_seed")

        html_row = score_school(
            "yale",
            {
                "id": "yale",
                "discovery_seed_url": "https://oir.yale.edu/common-data-set",
            },
            years,
            coverage,
            starting_urls={},
            waf_ids=set(),
            allowlist={},
        )
        self.assertTrue(html_row["listing"])
        self.assertTrue(html_row["in_bar"])

    def test_routing_matrix(self) -> None:
        self.assertEqual(
            suggested_route(
                school_id="fordham-university",
                listing=True,
                listing_url="https://www.fordham.edu/common-data-set/",
                in_waf_yaml=True,
                allowlisted=False,
                allowlist_error=None,
                queue_outcome="redirect_loop",
            ),
            "hosted",
        )
        self.assertEqual(
            suggested_route(
                school_id="williams-college",
                listing=True,
                listing_url="https://www.williams.edu/institutional-research/common-data-set/",
                in_waf_yaml=True,
                allowlisted=False,
                allowlist_error=None,
                queue_outcome=None,
            ),
            "hosted",
        )
        self.assertEqual(
            suggested_route(
                school_id="nyu",
                listing=True,
                listing_url="https://www.nyu.edu/factbook.html",
                in_waf_yaml=True,
                allowlisted=True,
                allowlist_error="http_405",
                queue_outcome="bot_challenge",
            ),
            "residential",
        )
        self.assertEqual(
            suggested_route(
                school_id="yale",
                listing=True,
                listing_url="https://oir.yale.edu/common-data-set",
                in_waf_yaml=False,
                allowlisted=False,
                allowlist_error=None,
                queue_outcome=None,
            ),
            "static_html",
        )

    def test_residential_only_cap_and_allowlist(self) -> None:
        allow = {"nyu": {}}
        self.assertEqual(
            resolve_residential_only(dispatch_only="nyu", allowlist=allow),
            ["nyu"],
        )
        with self.assertRaises(SystemExit):
            resolve_residential_only(dispatch_only="fordham-university", allowlist=allow)
        with self.assertRaises(SystemExit):
            resolve_residential_only(
                dispatch_only="a,b,c,d,e,f",
                allowlist={sid: {} for sid in "abcdef"},
            )

    def test_hosted_gap_ids_skip_in_bar_and_residential(self) -> None:
        rows = [
            {"school_id": "yale", "in_bar": True, "route": "static_html"},
            {"school_id": "fordham-university", "in_bar": False, "route": "hosted"},
            {"school_id": "nyu", "in_bar": False, "route": "residential"},
        ]
        self.assertEqual(hosted_gap_ids(rows), ["fordham-university"])

    def test_august_2026_years(self) -> None:
        from datetime import date

        self.assertEqual(coverage_bar_years(date(2026, 8, 30)), ["2025-26", "2024-25"])

    def test_summary_counts(self) -> None:
        rows = [
            {"in_bar": True, "route": "static_html"},
            {"in_bar": False, "route": "hosted"},
            {"in_bar": False, "route": "residential"},
        ]
        summary = summarize(rows)
        self.assertEqual(summary["in_bar"], 1)
        self.assertEqual(summary["gaps"], 2)
        self.assertEqual(summary["routed_hosted"], 1)
        self.assertEqual(summary["routed_residential"], 1)


if __name__ == "__main__":
    unittest.main()
