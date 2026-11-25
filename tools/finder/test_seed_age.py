"""Tests for dating discovery seeds by the last new CDS year they produced."""

from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from tools.finder import seed_age as sa
from tools.ops.discovery_renewal import RenewalError, load_schools

AS_OF = date(2026, 11, 24)  # floor 2025-26
LISTING = "https://a.edu/ir/cds/"
FILE = "https://a.edu/cds_2023-24.pdf"
FIXTURE = Path(__file__).parent / "testdata" / "archive_years_snapshot.json"


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


class WiringTests(unittest.TestCase):
    def _result(self):
        from tools.ops import discovery_renewal as dr
        rows = [doc(f"s{i}", y) for i in range(400) for y in ("2024-25", "2025-26")]
        return dr, dr.compute(rows, AS_OF), rows

    def test_summary_carries_seed_counts_by_kind(self):
        dr, result, _ = self._result()
        ages = sa.compute_seed_ages(
            schools(a=LISTING, b=LISTING, c=FILE), [doc("a", "2023-24"), doc("c", "2022-23")], AS_OF)
        summary = dr.summary_dict(result, seed_summary=sa.summarize(ages))
        self.assertEqual(summary["seeds_with_seed"], 3)
        self.assertEqual(summary["seeds_without_new_year"], 3)
        self.assertEqual(summary["seeds_without_new_year_listing_page"], 2)
        self.assertEqual(summary["seeds_without_new_year_one_file"], 1)

    def test_summary_without_seed_ages_has_null_keys_not_zero(self):
        dr, result, _ = self._result()
        self.assertIsNone(dr.summary_dict(result)["seeds_without_new_year"])

    def test_report_contains_the_seed_section(self):
        dr, result, _ = self._result()
        ages = sa.compute_seed_ages(schools(a=LISTING), [doc("a", "2023-24")], AS_OF)
        md = dr.render_report(result, [], seeds_section=sa.render_section(ages, "2025-26"))
        self.assertIn("## Seeds without a new year", md)
        self.assertIn("| `a` | 2023-24 |", md)


class EndToEndTests(unittest.TestCase):
    def test_renewal_run_writes_seed_counts_and_section(self):
        import tempfile
        from tools.ops import discovery_renewal as dr

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            manifest = tmp / "m.json"
            manifest.write_text(json.dumps(_snapshot_rows()))
            argv = ["--manifest-json", str(manifest), "--as-of", "2026-11-24",
                    "--out-summary", str(tmp / "s.json"), "--out-report", str(tmp / "r.md"),
                    "--out-worklist", str(tmp / "w.json"), "--out-seed-ages", str(tmp / "sa.json"), "--out-state", str(tmp / "st.json")]
            self.assertEqual(dr.main(argv), 0)
            summary = json.loads((tmp / "s.json").read_text())
            self.assertEqual(
                summary["seeds_without_new_year"],
                summary["seeds_without_new_year_one_file"]
                + summary["seeds_without_new_year_listing_page"])
            self.assertGreater(summary["seeds_with_seed"], 0)
            self.assertEqual(len(json.loads((tmp / "sa.json").read_text())), summary["seeds_with_seed"])
            self.assertIn("## Seeds without a new year", (tmp / "r.md").read_text())


class CapAndGuardTests(unittest.TestCase):
    def _many_behind(self, n):
        sc = schools(**{f"s{i:03d}": LISTING for i in range(n)})
        rows = [doc(f"s{i:03d}", "2023-24", f"2026-05-{1 + i % 28:02d}T00:00:00+00:00") for i in range(n)]
        return sc, rows

    def test_section_is_capped_with_a_more_line(self):
        sc, rows = self._many_behind(120)
        md = sa.render_section(sa.compute_seed_ages(sc, rows, AS_OF), "2025-26")
        self.assertEqual(md.count("| `s"), sa.SECTION_ROW_LIMIT)
        self.assertIn("and 70 more; full list in the discovery-renewal artifact", md)
        self.assertLess(len(md), 12000)

    def test_cap_keeps_the_oldest_newest_year_first(self):
        sc = schools(a=LISTING, b=LISTING)
        rows = [doc("a", "2024-25"), doc("b", "2019-20")]
        md = sa.render_section(sa.compute_seed_ages(sc, rows, AS_OF), "2025-26", limit=1)
        self.assertIn("| `b` |", md)
        self.assertNotIn("| `a` |", md)
        self.assertIn("and 1 more", md)

    def _rows(self, n, **kw):
        return [doc(f"d{i}", "2025-26", **kw) for i in range(n)]

    def test_docs_guard_ignores_removed_unpublished_and_unknown(self):
        sc = schools(**{f"s{i}": LISTING for i in range(600)})
        for kw in ({"removed_at": "2026-06-01T00:00:00+00:00"},
                   {"participation_status": "not_published"},
                   {"canonical_year": "unknown"}):
            rows = self._rows(300, **kw)
            with self.assertRaises(RenewalError, msg=str(kw)):
                sa.run_seed_age(sc, rows, AS_OF)

    def test_too_few_seeds_is_an_error(self):
        with self.assertRaises(RenewalError):
            sa.run_seed_age(schools(a=LISTING), self._rows(300), AS_OF)

    def test_enough_seeds_and_docs_pass(self):
        sc = schools(**{f"d{i}": LISTING for i in range(600)})
        ages, summary = sa.run_seed_age(sc, self._rows(300), AS_OF)
        self.assertEqual(summary["seeds"], 600)


class ReportSizeTests(unittest.TestCase):
    def test_real_fixture_report_fits_and_has_both_sections(self):
        from tools.ops import discovery_renewal as dr

        rows = _snapshot_rows()
        result = dr.compute(rows, AS_OF)
        sc = load_schools(Path(__file__).parent / "schools.yaml")
        ages, _ = sa.run_seed_age(sc, rows, AS_OF)
        worklist = dr.missing_worklist(result, sc, "current")
        report = dr.render_report(
            result, worklist, seeds_section=sa.render_section(ages, "2025-26"))
        self.assertLessEqual(len(report), 60000)
        self.assertIn("## Seeds without a new year", report)
        self.assertIn("## Schools missing for the", report)
        self.assertGreater(report.index("## Seeds without a new year"),
                           report.index("## Schools missing for the"))

    def test_long_worklist_is_cut_not_the_seed_section(self):
        from tools.ops import discovery_renewal as dr

        rows = [doc(f"s{i}", y) for i in range(400) for y in ("2024-25", "2025-26")]
        result = dr.compute(rows, AS_OF)
        worklist = [{"school_id": f"w{i}", "name": "N" * 80, "seed_kind": "listing_page",
                     "seed_url": "https://x.edu/" + "p" * 80, "newest_year": "2024-25"}
                    for i in range(2000)]
        ages = sa.compute_seed_ages(schools(a=LISTING), [doc("a", "2023-24")], AS_OF)
        report = dr.render_report(result, worklist, seeds_section=sa.render_section(ages, "2025-26"))
        self.assertLessEqual(len(report), 60000)
        self.assertIn("List cut to fit", report)
        self.assertIn("## Seeds without a new year", report)
        self.assertIn("| `a` |", report)


class ScriptErrorPathTests(unittest.TestCase):
    def test_seed_age_error_is_caught_when_run_as_a_script(self):
        # As a script the renewal module is __main__; seed_age's RenewalError
        # must still be the class main() catches (exit 1, no traceback).
        import subprocess
        import sys
        import tempfile

        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = [doc(f"s{i}", y) for i in range(400) for y in ("2024-25", "2025-26")]
            (tmp / "m.json").write_text(json.dumps(rows))
            (tmp / "schools.yaml").write_text(
                "schools:\n  - id: s1\n    discovery_seed_url: https://x.edu/cds/\n")
            proc = subprocess.run(
                [sys.executable, str(root / "tools/ops/discovery_renewal.py"),
                 "--manifest-json", str(tmp / "m.json"), "--as-of", "2026-11-24",
                 "--schools-yaml", str(tmp / "schools.yaml")],
                capture_output=True, text=True, cwd=root)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("::error::discovery renewal:", proc.stderr)
        self.assertIn("schools have a seed", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class QueryTests(unittest.TestCase):
    def test_renewal_manifest_query_carries_discovered_at(self):
        # seed_age reuses the renewal fetch; it must select the first-seen date.
        from tools.ops.discovery_renewal import MANIFEST_QUERY

        self.assertIn("discovered_at", MANIFEST_QUERY)
        self.assertIn("removed_at=is.null", MANIFEST_QUERY)


def _snapshot_rows():
    """Manifest-shaped rows from the committed years-per-school fixture."""
    years = json.loads(FIXTURE.read_text())
    rows = [
        doc(sid, y, "2026-05-01T00:00:00+00:00")
        for sid, ys in years.items()
        for y in ys
    ]
    if len(rows) < 1000:
        raise AssertionError(f"fixture looks truncated: {len(rows)} rows")
    return rows


class RealSchoolsTests(unittest.TestCase):
    """Identity on the real schools.yaml and a manifest snapshot."""

    def test_every_school_with_a_seed_lands_in_exactly_one_kind(self):
        rows = _snapshot_rows()
        sc = load_schools(Path(__file__).parent / "schools.yaml")
        ages, summary = sa.run_seed_age(sc, rows, AS_OF)
        with_seed = [s for s in sc.values() if sa.seed_for(s)[1] != "no_seed"]
        self.assertEqual(len(ages), len(with_seed))
        kinds = summary["by_kind"]
        self.assertEqual(kinds["one_file"]["seeds"] + kinds["listing_page"]["seeds"], len(with_seed))
        self.assertEqual(len({a.school_id for a in ages}), len(ages))


if __name__ == "__main__":
    unittest.main()
