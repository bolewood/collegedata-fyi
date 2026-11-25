from __future__ import annotations

import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from tools.finder.stuck_pdf_seeds import default_min_fresh_year
from tools.ops import discovery_renewal as dr

SNAPSHOT = Path(
    "/Users/santhonys/orca/workspaces/collegedata-fyi/basslet/scratch/overnight-run/data/manifest-20261124.json"
)


def row(school: str, year: str, *, status: str = "published", removed: str | None = None,
        discovered: str | None = "2026-01-01T00:00:00+00:00") -> dict:
    return {
        "school_id": school,
        "canonical_year": year,
        "participation_status": status,
        "removed_at": removed,
        "discovered_at": discovered,
    }


def many_schools(n: int, *, with_current: int, prev: str = "2024-25", cur: str = "2025-26") -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(row(f"s{i}", prev))
        if i < with_current:
            rows.append(row(f"s{i}", cur))
    return rows


class YearTests(unittest.TestCase):
    def test_unknown_and_malformed_years_are_not_years(self) -> None:
        for bad in ("unknown", "", None, "2024", "2024-26", "2024-2025", "24-25", 2024):
            self.assertIsNone(dr.parse_year(bad), bad)
        self.assertEqual(dr.parse_year("2025-26"), 2025)
        self.assertEqual(dr.parse_year("1999-00"), 1999)

    def test_unknown_is_not_counted_as_the_current_year(self) -> None:
        # `unknown` sorts above every real year as text. It must not make a
        # school look renewed, or the newest year.
        rows = many_schools(400, with_current=0)
        rows += [row(f"s{i}", "unknown") for i in range(400)]
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(len(result.current.renewed), 0)
        self.assertEqual(result.current.pct, 0.0)
        self.assertEqual(dr.missing_worklist(result, {})[0]["newest_year"], "2024-25")

    def test_year_text_comparison_is_not_used(self) -> None:
        # "2099-00" is valid and numerically 2099; "unknown" is not a year.
        # Text order would put 'unknown' above both.
        self.assertGreater(dr.parse_year("2099-00"), dr.parse_year("2025-26"))
        self.assertEqual(dr.school_years([row("a", "unknown"), row("a", "2024-25")]), {"a": {2024}})


class FloorTests(unittest.TestCase):
    def test_python_floor_matches_the_sql_formula_across_boundaries(self) -> None:
        def sql(d: date) -> str:
            # public.cds_freshness_floor, transcribed from the migration.
            if d.month >= 9:
                return f"{d.year - 1}-{str(d.year)[-2:]}"
            return f"{d.year - 2}-{str(d.year - 1)[-2:]}"

        day = date(2023, 1, 1)
        while day <= date(2027, 12, 31):
            self.assertEqual(dr.cds_freshness_floor(day), sql(day), day)
            self.assertEqual(dr.cds_freshness_floor(day), default_min_fresh_year(day), day)
            day += timedelta(days=1)
        self.assertEqual(dr.cds_freshness_floor(date(2026, 8, 31)), "2024-25")
        self.assertEqual(dr.cds_freshness_floor(date(2026, 9, 1)), "2025-26")
        self.assertEqual(dr.cds_freshness_floor(date(2099, 9, 1)), "2098-99")
        self.assertEqual(dr.cds_freshness_floor(date(2100, 9, 1)), "2099-00")

    def test_disagreement_with_sql_is_an_error(self) -> None:
        dr.check_floor_agrees("2025-26", "2025-26")
        with self.assertRaises(dr.RenewalError):
            dr.check_floor_agrees("2025-26", "2024-25")

    def test_months_since_fall(self) -> None:
        self.assertAlmostEqual(dr.months_since_fall(2025, date(2026, 9, 1)), 12.0)
        self.assertAlmostEqual(dr.months_since_fall(2025, date(2026, 11, 24)), 14 + 23 / 30)
        self.assertAlmostEqual(dr.months_since_fall(2026, date(2026, 11, 24)), 2 + 23 / 30)

    def test_curve_points_and_interpolation(self) -> None:
        for months, pct in dr.POSTING_CURVE:
            self.assertAlmostEqual(dr.expected_pct(months), pct)
        self.assertAlmostEqual(dr.expected_pct(2.0), 1.5)  # (0,0) to (4,3)
        self.assertAlmostEqual(dr.expected_pct(7.0), 32.0)  # midway 18..46
        self.assertAlmostEqual(dr.expected_pct(13.5), 81 + 7 * 1.5 / 3)
        self.assertAlmostEqual(dr.expected_pct(40.0), 88.0)
        self.assertAlmostEqual(dr.expected_pct(-3.0), 0.0)

    def test_current_year_floor_values_from_the_brief(self) -> None:
        self.assertAlmostEqual(dr.current_year_floor_pct(12.0), 76.0)
        months = dr.months_since_fall(2025, date(2026, 11, 24))
        self.assertAlmostEqual(dr.current_year_floor_pct(months), 82.4556, places=3)

    def test_next_year_is_tracked_from_march_with_a_relative_floor(self) -> None:
        self.assertFalse(dr.next_year_is_active(dr.months_since_fall(2026, date(2027, 2, 27))))
        self.assertTrue(dr.next_year_is_active(dr.months_since_fall(2026, date(2027, 3, 1))))
        self.assertAlmostEqual(dr.next_year_floor_pct(6.0), 18 * 0.75)


class ComputeTests(unittest.TestCase):
    def test_a_school_with_only_the_current_year_is_not_in_the_denominator(self) -> None:
        rows = many_schools(400, with_current=200)
        rows += [row(f"only{i}", "2025-26") for i in range(100)]
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(len(result.current.prev_schools), 400)
        self.assertEqual(len(result.current.renewed), 200)
        self.assertEqual(result.current.pct, 50.0)

    def test_only_published_live_documents_count(self) -> None:
        rows = many_schools(400, with_current=0)
        rows += [row(f"s{i}", "2025-26", removed="2026-10-01T00:00:00+00:00") for i in range(50)]
        rows += [row(f"s{i}", "2025-26", status="verified_absent") for i in range(50, 100)]
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(len(result.current.renewed), 0)

    def test_two_documents_of_one_school_count_once(self) -> None:
        rows = many_schools(400, with_current=400)
        rows += [row("s0", "2025-26"), row("s0", "2024-25")]
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(len(result.current.prev_schools), 400)

    def test_low_denominator_raises(self) -> None:
        rows = many_schools(dr.MIN_PREV_SCHOOLS - 1, with_current=0)
        with self.assertRaises(dr.RenewalError):
            dr.compute(rows, date(2026, 11, 24))
        with self.assertRaises(dr.RenewalError):
            dr.compute([], date(2026, 11, 24))
        dr.compute(many_schools(dr.MIN_PREV_SCHOOLS, with_current=0), date(2026, 11, 24))

    def test_below_floor_is_not_an_error_and_override_replaces_the_floor(self) -> None:
        rows = many_schools(400, with_current=300)  # 75%
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertTrue(result.below_floor)
        self.assertFalse(result.floor_overridden)
        result = dr.compute(rows, date(2026, 11, 24), floor_override_pct=10)
        self.assertFalse(result.below_floor)
        self.assertTrue(result.floor_overridden)
        self.assertEqual(dr.summary_dict(result)["floor_pct"], 10.0)

    def test_lapsed_schools_include_those_missing_two_years(self) -> None:
        rows = many_schools(400, with_current=399)
        rows += [row("old", "2023-24")]  # missed 2024-25 and 2025-26
        rows += [row("older", "2022-23")]  # beyond two years back: not counted
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(result.lapsed, {"s399", "old"})
        self.assertEqual(result.current.missing, {"s399"})

    def test_summary_keys_are_the_shared_contract(self) -> None:
        result = dr.compute(many_schools(400, with_current=300), date(2026, 11, 24))
        self.assertEqual(
            set(dr.summary_dict(result)),
            {
                "current_year", "renewed", "prev_schools", "renewal_pct", "floor_pct",
                "months_since_fall", "below_floor", "next_year", "next_renewed",
                "next_prev_schools", "next_renewal_pct", "next_floor_pct",
                "next_below_floor", "two_year_renewed", "two_year_prev_schools",
                "two_year_renewal_pct", "two_year_floor_pct", "two_year_below_floor",
                "lapsed_schools", "floor_overridden", "alarm_issue", "run_url",
            },
        )
        summary = dr.summary_dict(result, run_url="https://x/y")
        # The web lamp fails closed when these are missing or the wrong type.
        self.assertIs(type(summary["below_floor"]), bool)
        self.assertIs(type(summary["renewed"]), int)
        self.assertIs(type(summary["prev_schools"]), int)
        self.assertIs(type(summary["two_year_below_floor"]), bool)
        self.assertIsNone(summary["next_floor_pct"])
        self.assertIsNone(summary["next_below_floor"])
        self.assertEqual(summary["run_url"], "https://x/y")

    def test_next_year_below_floor_is_reported_separately(self) -> None:
        # April 2027: current year 2025-26, next 2026-27 is tracked.
        rows = many_schools(400, with_current=400)
        rows += [row(f"s{i}", "2026-27") for i in range(20)]  # 5% of 400
        result = dr.compute(rows, date(2027, 4, 30))
        self.assertTrue(result.next_active)
        self.assertTrue(result.next_below_floor)
        self.assertFalse(result.below_floor)


class TwoYearTests(unittest.TestCase):
    def erosion_rows(self, renew_pct: float = 0.95) -> list[dict]:
        """500 schools had 2023-24. 150 of them missed 2024-25 and never came
        back; the 350 that kept posting renew 2025-26 at `renew_pct`."""
        rows = []
        for i in range(500):
            rows.append(row(f"s{i}", "2023-24"))
        for i in range(350):
            rows.append(row(f"s{i}", "2024-25"))
            if i < int(350 * renew_pct):
                rows.append(row(f"s{i}", "2025-26"))
        return rows

    def test_one_year_recovers_but_two_year_keeps_the_alarm(self) -> None:
        # The 150 schools left the one-year denominator when they missed
        # 2024-25, so the remaining cohort renews "well" there.
        result = dr.compute(self.erosion_rows(), date(2026, 11, 24))
        summary = dr.summary_dict(result)
        self.assertEqual((summary["renewed"], summary["prev_schools"]), (332, 350))
        self.assertFalse(summary["below_floor"])  # 94.9% against 82.5%
        self.assertEqual((summary["two_year_renewed"], summary["two_year_prev_schools"]), (332, 500))
        self.assertTrue(summary["two_year_below_floor"])  # 66.4% against 74.5%
        self.assertEqual(dr.lead_check(summary), "two_year")

    def test_two_year_floor_is_the_one_year_floor_less_eight_points(self) -> None:
        result = dr.compute(self.erosion_rows(), date(2026, 11, 24))
        self.assertAlmostEqual(result.two_year_floor_pct, result.floor_pct - dr.TWO_YEAR_MARGIN_PTS)
        self.assertEqual(dr.TWO_YEAR_MARGIN_PTS, 8.0)

    def test_two_year_denominator_keeps_schools_with_only_the_older_year(self) -> None:
        by_school = dr.school_years([row("a", "2023-24"), row("b", "2024-25"), row("c", "2025-26"),
                                     row("d", "2022-23")])
        two = dr.two_year_renewal(by_school, 2025)
        self.assertEqual(two.prev_schools, {"a", "b"})  # c has only the current year, d is too old

    def test_lead_check_order_and_none(self) -> None:
        base = {"below_floor": False, "two_year_below_floor": False, "next_below_floor": None}
        self.assertIsNone(dr.lead_check(base))
        self.assertEqual(dr.lead_check({**base, "next_below_floor": True}), "next")
        self.assertEqual(dr.lead_check({**base, "next_below_floor": True, "two_year_below_floor": True}), "two_year")
        self.assertEqual(dr.lead_check({**base, "below_floor": True, "two_year_below_floor": True}), "current")

    def test_worklist_and_report_follow_the_breaching_check(self) -> None:
        result = dr.compute(self.erosion_rows(), date(2026, 11, 24))
        two = dr.missing_worklist(result, {}, "two_year")
        self.assertEqual(len(two), 168)  # 150 gone + 18 that did not renew
        one = dr.missing_worklist(result, {}, "current")
        self.assertEqual(len(one), 18)
        text = dr.render_report(result, two, lead="two_year")
        self.assertIn("332 of 500 schools (66.4%) that have 2024-25 or 2023-24 also have 2025-26", text)
        self.assertIn("Schools missing for the two-year check (168)", text)

    def test_next_year_worklist_is_schools_with_the_current_year_but_not_the_next(self) -> None:
        rows = many_schools(400, with_current=400)
        rows += [row(f"s{i}", "2026-27") for i in range(20)]
        result = dr.compute(rows, date(2027, 4, 30))
        work = dr.missing_worklist(result, {}, "next")
        self.assertEqual(len(work), 380)
        self.assertEqual({w["newest_year"] for w in work}, {"2025-26"})

    def test_floor_override_needs_test_mode(self) -> None:
        for argv, ok in (
            (["--floor-override-pct", "99"], False),
            (["--floor-override-pct", "99", "--test-mode"], True),
        ):
            args = dr.build_parser().parse_args(
                ["--manifest-json", "/nonexistent.json", "--as-of", "2026-11-24", *argv])
            try:
                dr.run(args)
            except dr.RenewalError as exc:
                self.assertNotIn("test runs only", str(exc)) if ok else self.assertIn("test runs only", str(exc))
            except OSError:
                self.assertTrue(ok)  # got past the guard, then missed the file

    def test_main_exits_nonzero_for_an_override_outside_test_mode(self) -> None:
        self.assertEqual(dr.main(["--floor-override-pct", "99", "--as-of", "2026-11-24"]), 1)


class WorklistTests(unittest.TestCase):
    def test_seed_kinds(self) -> None:
        self.assertEqual(dr.seed_for(None), ("", "no_seed"))
        self.assertEqual(dr.seed_for({"id": "a"}), ("", "no_seed"))
        self.assertEqual(
            dr.seed_for({"discovery_seed_url": "https://x.edu/cds/2024.pdf?v=1"}),
            ("https://x.edu/cds/2024.pdf?v=1", "one_file"),
        )
        self.assertEqual(dr.seed_for({"cds_url_hint": "https://x.edu/cds"})[1], "listing_page")
        self.assertEqual(
            dr.seed_for({"discovery_seed_url": "https://a/", "cds_url_hint": "https://b/x.pdf"})[0],
            "https://a/",
        )

    def test_report_groups_by_kind_and_links_schools(self) -> None:
        rows = many_schools(500, with_current=497)
        result = dr.compute(rows, date(2026, 11, 24))
        schools = {
            "s497": {"id": "s497", "name": "One File U", "discovery_seed_url": "https://a.edu/cds.pdf"},
            "s498": {"id": "s498", "name": "Listing U", "discovery_seed_url": "https://a.edu/cds"},
        }
        worklist = dr.missing_worklist(result, schools)
        self.assertEqual([w["seed_kind"] for w in worklist], ["one_file", "listing_page", "no_seed"])
        text = dr.render_report(result, worklist, run_url="https://run")
        self.assertIn("[One File U](https://www.collegedata.fyi/schools/s497)", text)
        self.assertLess(text.index("One File U"), text.index("Listing U"))
        self.assertIn("497 of 500 schools (99.4%)", text)
        self.assertIn("https://run", text)


class FetchTests(unittest.TestCase):
    def fake_get(self, pages: list[list[dict]], total: int | None = None, range_header: str | None = None):
        calls = []

        def get(url, headers, method="GET", body=None):
            calls.append(url)
            index = len(calls) - 1
            page = pages[index] if index < len(pages) else []
            t = sum(len(p) for p in pages) if total is None else total
            header = range_header or f"0-{max(len(page) - 1, 0)}/{t}"
            return page, {"content-range": header}

        get.calls = calls  # type: ignore[attr-defined]
        return get

    def test_pages_until_every_row_arrived(self) -> None:
        pages = [[{"school_id": f"a{i}"} for i in range(dr.PAGE_SIZE)], [{"school_id": "z"}] * 5]
        get = self.fake_get(pages)
        rows = dr.fetch_live_manifest("https://api", "k", get=get)
        self.assertEqual(len(rows), dr.PAGE_SIZE + 5)
        self.assertEqual(len(get.calls), 2)
        self.assertIn("offset=1000", get.calls[1])
        self.assertIn("removed_at=is.null", get.calls[0])

    def test_short_page_raises(self) -> None:
        # Content-Range says 2000; the server only hands back 1000 and then
        # nothing (a row cap, or rows deleted mid-read).
        pages = [[{"school_id": "a"}] * 1000]
        with self.assertRaises(dr.RenewalError) as ctx:
            dr.fetch_live_manifest("https://api", "k", get=self.fake_get(pages, total=2000))
        self.assertIn("short read", str(ctx.exception))

    def test_empty_result_raises(self) -> None:
        with self.assertRaises(dr.RenewalError):
            dr.fetch_live_manifest("https://api", "k", get=self.fake_get([[]], total=0))

    def test_missing_or_inexact_content_range_raises(self) -> None:
        for header in ("0-9/*", "garbage"):
            with self.assertRaises(dr.RenewalError):
                dr.fetch_live_manifest(
                    "https://api", "k", get=self.fake_get([[{"school_id": "a"}]], range_header=header)
                )

    def test_total_changing_between_pages_raises(self) -> None:
        calls = []

        def get(url, headers, method="GET", body=None):
            calls.append(url)
            if len(calls) == 1:
                return [{"school_id": "a"}] * dr.PAGE_SIZE, {"content-range": "0-999/1500"}
            return [{"school_id": "a"}] * 500, {"content-range": "1000-1499/1400"}

        with self.assertRaises(dr.RenewalError):
            dr.fetch_live_manifest("https://api", "k", get=get)

    def test_sql_floor_must_be_a_string(self) -> None:
        def get(url, headers, method="GET", body=None):
            return "2025-26", {}

        self.assertEqual(dr.fetch_sql_floor("https://api", "k", date(2026, 11, 24), get=get), "2025-26")
        with self.assertRaises(dr.RenewalError):
            dr.fetch_sql_floor("https://api", "k", date(2026, 11, 24), get=lambda *a, **k: (None, {}))


class BacktestTests(unittest.TestCase):
    def test_month_range(self) -> None:
        days = dr.parse_month_range("2026-11..2027-02")
        self.assertEqual(days, [date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31), date(2027, 2, 28)])
        with self.assertRaises(dr.RenewalError):
            dr.parse_month_range("2026-11")
        with self.assertRaises(dr.RenewalError):
            dr.parse_month_range("2026-11..2026-05")

    def test_replay_uses_discovery_and_removal_dates(self) -> None:
        rows = []
        for i in range(250):
            rows.append(row(f"s{i}", "2024-25", discovered="2026-03-01T00:00:00+00:00"))
        # 100 renew in October, 50 more in November.
        for i in range(100):
            rows.append(row(f"s{i}", "2025-26", discovered="2026-10-10T00:00:00+00:00"))
        for i in range(100, 150):
            rows.append(row(f"s{i}", "2025-26", discovered="2026-11-10T00:00:00+00:00"))
        # One renewed document was removed again on Nov 15; one has no date.
        rows[250]["removed_at"] = "2026-11-15T00:00:00+00:00"
        rows.append(row("s200", "2025-26", discovered=None))
        table = dr.backtest(rows, [date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 30)])
        self.assertEqual([t["current_year"] for t in table], ["2025-26"] * 3)
        # Null discovered_at counts as always present (s200 renewed throughout).
        self.assertEqual([t["renewed"] for t in table], [1, 101, 150])
        self.assertEqual([t["prev"] for t in table], [250, 250, 250])
        self.assertTrue(all(t["below"] for t in table))
        text = dr.render_backtest(table, 1)
        self.assertIn("null discovered_at", text)
        self.assertIn("2026-10-31", text)

    def test_timestamps_with_any_fraction_length_parse(self) -> None:
        # Python before 3.11 only takes 3 or 6 fraction digits.
        base = dr._parse_ts("2026-11-24T23:28:31+00:00")
        for text, micro in (
            ("2026-11-24T23:28:31.88+00:00", 880000),
            ("2026-11-24T23:28:31.12345+00:00", 123450),
            ("2026-11-24T23:28:31.1234567+00:00", 123456),
            ("2026-11-24T23:28:31.5Z", 500000),
            ("2026-11-24T23:28:31.339+00:00", 339000),
        ):
            parsed = dr._parse_ts(text)
            self.assertEqual(parsed, base.replace(microsecond=micro), text)
        self.assertIsNone(dr._parse_ts(None))
        self.assertIsNone(dr._parse_ts(""))

    def test_unparseable_timestamp_raises_instead_of_being_ignored(self) -> None:
        for bad in ("yesterday", "2026-13-45T00:00:00+00:00", "not a date"):
            with self.assertRaises(dr.RenewalError):
                dr._parse_ts(bad)
        with self.assertRaises(dr.RenewalError):
            dr.rows_as_of([row("a", "2024-25", discovered="garbage")], date(2026, 11, 30))

    def test_rows_as_of_honours_odd_fractions(self) -> None:
        rows = [
            row("a", "2025-26", discovered="2026-11-10T10:00:00.88+00:00"),
            row("b", "2025-26", discovered="2026-10-10T10:00:00.12345+00:00",
                removed="2026-10-20T10:00:00.5+00:00"),
            row("c", "2025-26", discovered="2026-12-01T00:00:00.9+00:00"),
        ]
        ids = lambda day: [r["school_id"] for r in dr.rows_as_of(rows, day)]  # noqa: E731
        self.assertEqual(ids(date(2026, 10, 15)), ["b"])
        self.assertEqual(ids(date(2026, 10, 31)), [])  # b removed on the 20th
        self.assertEqual(ids(date(2026, 11, 30)), ["a"])  # c not yet discovered

    def test_replay_crosses_the_august_september_year_switch(self) -> None:
        rows = many_schools(250, with_current=0, prev="2024-25", cur="2025-26")
        table = dr.backtest(rows, [date(2026, 8, 31), date(2026, 9, 30)])
        self.assertEqual([t["current_year"] for t in table], ["2024-25", "2025-26"])


@unittest.skipUnless(SNAPSHOT.is_file(), "local manifest snapshot not present")
class SnapshotTests(unittest.TestCase):
    def test_snapshot_reproduces_364_of_479(self) -> None:
        rows = [r for r in json.loads(SNAPSHOT.read_text()) if not r.get("removed_at")]
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(
            (len(result.current.renewed), len(result.current.prev_schools)), (364, 479)
        )
        self.assertEqual(result.current.pct, 76.0)
        self.assertTrue(result.below_floor)
        self.assertEqual(
            (len(result.two_year.renewed), len(result.two_year.prev_schools)), (377, 536)
        )
        self.assertEqual(result.two_year.pct, 70.3)
        self.assertTrue(result.two_year_below_floor)


if __name__ == "__main__":
    unittest.main()
