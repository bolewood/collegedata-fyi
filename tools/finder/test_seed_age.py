"""Tests for dating discovery seeds by the last new CDS year they produced."""

from __future__ import annotations

import json
import os
import unittest
from datetime import date
from pathlib import Path

from tools.finder import seed_age as sa
from tools.ops.discovery_renewal import RenewalError, load_schools

AS_OF = date(2026, 11, 24)  # floor 2025-26
LISTING = "https://a.edu/ir/cds/"
FILE = "https://a.edu/cds_2023-24.pdf"
FIXTURE = Path(__file__).parent / "testdata" / "archive_years_snapshot.json"
# A local `cds_manifest` dump (rows with school_id, canonical_year, ...).
SNAPSHOT_ENV = "SEED_AGE_MANIFEST_SNAPSHOT"


def doc(school, year, discovered="2026-05-01T00:00:00+00:00", **kw):
    row = {
        "school_id": school,
        "canonical_year": year,
        "discovered_at": discovered,
        "removed_at": None,
        "participation_status": "published",
    }
    row.update(kw)
    return row


def schools(**seeds):
    return {sid: {"id": sid, "discovery_seed_url": url} for sid, url in seeds.items()}


def by_id(ages):
    return {a.school_id: a for a in ages}


class BehindCycleTests(unittest.TestCase):
    def test_listing_seed_with_newest_2023_24_is_behind(self):
        ages = by_id(sa.compute_seed_ages(
            schools(x=LISTING), [doc("x", "2022-23"), doc("x", "2023-24")], AS_OF))
        self.assertTrue(ages["x"].behind_cycle)
        self.assertEqual(ages["x"].newest_year, "2023-24")

    def test_unknown_only_school_is_behind(self):
        # `unknown` sorts above every real year as text; it is not a year.
        ages = by_id(sa.compute_seed_ages(
            schools(x=LISTING), [doc("x", "unknown")], AS_OF))
        self.assertTrue(ages["x"].behind_cycle)
        self.assertIsNone(ages["x"].newest_year)

    def test_unknown_next_to_old_year_does_not_become_newest(self):
        ages = by_id(sa.compute_seed_ages(
            schools(x=LISTING), [doc("x", "unknown"), doc("x", "2023-24")], AS_OF))
        self.assertEqual(ages["x"].newest_year, "2023-24")
        self.assertTrue(ages["x"].behind_cycle)

    def test_current_year_only_is_not_behind(self):
        ages = by_id(sa.compute_seed_ages(
            schools(x=LISTING), [doc("x", "2025-26")], AS_OF))
        self.assertFalse(ages["x"].behind_cycle)

    def test_floor_boundary_and_future_year(self):
        ages = by_id(sa.compute_seed_ages(
            schools(a=LISTING, b=LISTING, c=LISTING),
            [doc("a", "2024-25"), doc("b", "2025-26"), doc("c", "2026-27")], AS_OF))
        self.assertTrue(ages["a"].behind_cycle)
        self.assertFalse(ages["b"].behind_cycle)
        self.assertFalse(ages["c"].behind_cycle)

    def test_school_with_seed_and_no_documents_is_behind(self):
        ages = by_id(sa.compute_seed_ages(schools(x=LISTING), [], AS_OF))
        self.assertTrue(ages["x"].behind_cycle)

    def test_removed_and_unpublished_documents_do_not_count(self):
        rows = [
            doc("x", "2025-26", removed_at="2026-06-01T00:00:00+00:00"),
            doc("x", "2025-26", participation_status="not_published"),
        ]
        ages = by_id(sa.compute_seed_ages(schools(x=LISTING), rows, AS_OF))
        self.assertTrue(ages["x"].behind_cycle)

    def test_no_seed_school_is_not_dated(self):
        sc = {"x": {"id": "x"}, "y": {"id": "y", "discovery_seed_url": LISTING}}
        self.assertEqual([a.school_id for a in sa.compute_seed_ages(sc, [], AS_OF)], ["y"])

    def test_cds_url_hint_counts_as_a_seed(self):
        sc = {"x": {"id": "x", "cds_url_hint": FILE}}
        (a,) = sa.compute_seed_ages(sc, [], AS_OF)
        self.assertEqual(a.seed_kind, "one_file")


class FirstSeenTests(unittest.TestCase):
    def test_first_seen_is_earliest_discovery_of_newest_year(self):
        rows = [
            doc("x", "2024-25", "2026-04-01T00:00:00+00:00"),
            doc("x", "2024-25", "2026-06-10T00:00:00+00:00"),
            doc("x", "2023-24", "2026-01-01T00:00:00+00:00"),
        ]
        (a,) = sa.compute_seed_ages(schools(x=LISTING), rows, AS_OF)
        self.assertTrue(a.first_seen_known)
        self.assertTrue(a.newest_year_first_seen.startswith("2026-04-01"))

    def test_null_discovered_at_on_newest_year_is_unknown(self):
        rows = [doc("x", "2024-25", "2026-04-01T00:00:00+00:00"), doc("x", "2024-25", None)]
        (a,) = sa.compute_seed_ages(schools(x=LISTING), rows, AS_OF)
        self.assertFalse(a.first_seen_known)
        self.assertIsNone(a.newest_year_first_seen)

    def test_null_discovered_at_on_older_year_does_not_matter(self):
        rows = [doc("x", "2024-25", "2026-04-01T00:00:00+00:00"), doc("x", "2022-23", None)]
        (a,) = sa.compute_seed_ages(schools(x=LISTING), rows, AS_OF)
        self.assertTrue(a.first_seen_known)

    def test_fractional_seconds_parse(self):
        (a,) = sa.compute_seed_ages(
            schools(x=LISTING), [doc("x", "2024-25", "2026-11-24T23:28:31.3+00:00")], AS_OF)
        self.assertTrue(a.first_seen_known)


class SummaryTests(unittest.TestCase):
    def test_counts_by_kind(self):
        ages = sa.compute_seed_ages(
            schools(a=LISTING, b=LISTING, c=FILE, d=FILE),
            [doc("a", "2023-24"), doc("b", "2025-26"), doc("c", "2022-23"), doc("d", "2025-26")],
            AS_OF)
        s = sa.summarize(ages)
        self.assertEqual(s["seeds"], 4)
        self.assertEqual(s["seeds_without_new_year"], 2)
        self.assertEqual(s["by_kind"]["listing_page"], {"seeds": 2, "behind": 1})
        self.assertEqual(s["by_kind"]["one_file"], {"seeds": 2, "behind": 1})

    def test_accounting_raises_when_kinds_do_not_add_up(self):
        bad = {"seeds": 3, "seeds_without_new_year": 1,
               "by_kind": {"one_file": {"seeds": 1, "behind": 1},
                           "listing_page": {"seeds": 1, "behind": 0}}}
        with self.assertRaises(RenewalError):
            sa.check_accounting(bad)

    def test_report_lists_only_behind_listing_seeds(self):
        ages = sa.compute_seed_ages(
            schools(a=LISTING, b="https://b.edu/cds/", c=FILE),
            [doc("a", "2023-24"), doc("b", "2025-26"), doc("c", "2022-23")], AS_OF)
        md = sa.render_section(ages, "2025-26")
        self.assertIn("| `a` |", md)
        self.assertNotIn("| `b` |", md)
        self.assertNotIn("| `c` |", md)
        self.assertIn("2023-24", md)


class RunGuardTests(unittest.TestCase):
    def test_small_manifest_is_an_error_not_zero_found(self):
        with self.assertRaises(RenewalError):
            sa.run_seed_age(schools(x=LISTING), [doc("x", "2025-26")], AS_OF)


class FetchTests(unittest.TestCase):
    def _get(self, pages, total):
        calls = iter(pages)

        def get(url, headers, method="GET", body=None):
            return next(calls), {"content-range": f"0-0/{total}"}

        return get

    def test_pages_until_total(self):
        rows = sa.fetch_seed_age_rows(
            "https://x", "k",
            get=self._get([[doc("a", "2025-26")] * 1000, [doc("b", "2025-26")] * 5], 1005))
        self.assertEqual(len(rows), 1005)

    def test_short_read_raises(self):
        with self.assertRaises(RenewalError):
            sa.fetch_seed_age_rows("https://x", "k", get=self._get([[doc("a", "2025-26")], []], 5))

    def test_zero_rows_raises(self):
        with self.assertRaises(RenewalError):
            sa.fetch_seed_age_rows("https://x", "k", get=self._get([[]], 0))

    def test_query_selects_discovered_at_and_filters_live(self):
        self.assertIn("discovered_at", sa.SEED_AGE_QUERY)
        self.assertIn("removed_at=is.null", sa.SEED_AGE_QUERY)


def _snapshot_rows():
    for path in (FIXTURE, Path(os.environ.get(SNAPSHOT_ENV, "/nonexistent"))):
        if path.exists():
            rows = json.loads(path.read_text())
            if isinstance(rows, list) and rows and "canonical_year" in rows[0]:
                return rows
    return None


class RealSchoolsTests(unittest.TestCase):
    """Identity on the real schools.yaml and a manifest snapshot."""

    def test_every_school_with_a_seed_lands_in_exactly_one_kind(self):
        rows = _snapshot_rows()
        if rows is None:
            self.skipTest(f"no manifest snapshot (fixture or ${SNAPSHOT_ENV})")
        sc = load_schools(Path(__file__).parent / "schools.yaml")
        ages, summary = sa.run_seed_age(sc, rows, AS_OF)
        with_seed = [s for s in sc.values() if sa.seed_for(s)[1] != "no_seed"]
        self.assertEqual(len(ages), len(with_seed))
        kinds = summary["by_kind"]
        self.assertEqual(kinds["one_file"]["seeds"] + kinds["listing_page"]["seeds"], len(with_seed))
        self.assertEqual(len({a.school_id for a in ages}), len(ages))


if __name__ == "__main__":
    unittest.main()
