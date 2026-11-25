from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta, timezone
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
                "lapsed_schools", "same_year_duplicates", "flagged_current_docs",
                "sub_institutional_excluded", "outstanding_below_floor", "outstanding_years",
                "arrivals_30d", "arrivals_expected_30d", "arrivals_below_floor",
                "arrivals_60d", "arrivals_expected_60d", "arrivals_window_days",
                "arrivals_checked", "unextracted_next_docs", "arrivals_years",
                *(f"arrivals_{n}_checked_{w}" for n in ("current", "next") for w in (30, 60)),
                *(f"arrivals_{n}_{k}" for n in ("current", "next")
                  for k in ("30d", "60d", "window_days", "checked", "below_floor")),
                *(f"arrivals_expected_{n}_{k}" for n in ("current", "next") for k in ("30d", "60d")),
                "unextracted_current_docs",
                "floor_overridden", "alarm_issue", "run_url",
                "seeds_with_seed", "seeds_without_new_year",
                "seeds_without_new_year_one_file", "seeds_without_new_year_listing_page",
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


class IdentityTests(unittest.TestCase):
    def test_api_requests_identify_as_the_pipeline(self) -> None:
        # PRD 033: pipeline traffic to the public API sends this User-Agent.
        self.assertIn("collegedata-pipeline/", dr._headers("k")["User-Agent"])


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


ARCHIVE_YEARS = Path(__file__).resolve().parents[1] / "finder" / "testdata" / "archive_years_snapshot.json"
ROOT = Path(__file__).resolve().parents[2]


class CommittedSnapshotTests(unittest.TestCase):
    """Runs in CI: the years-per-school snapshot of 2026-11-24 is committed."""

    def rows(self) -> list[dict]:
        years = json.loads(ARCHIVE_YEARS.read_text())
        return [row(school, year) for school, ys in years.items() for year in ys]

    def test_the_committed_snapshot_gives_364_of_479_and_377_of_536(self) -> None:
        result = dr.compute(self.rows(), date(2026, 11, 24))
        self.assertEqual((len(result.current.renewed), len(result.current.prev_schools)), (364, 479))
        self.assertEqual(result.current.pct, 76.0)
        self.assertEqual((len(result.two_year.renewed), len(result.two_year.prev_schools)), (377, 536))
        self.assertEqual(result.two_year.pct, 70.3)
        self.assertTrue(result.below_floor)
        self.assertTrue(result.two_year_below_floor)

    def test_the_same_snapshot_a_year_on_is_judged_by_the_flat_floor(self) -> None:
        # 2027-06-30: 2025-26 is still the current year, 2026-27 is next, at
        # 50.7% of the curve's 67.6 x 0.75.
        result = dr.compute(self.rows(), date(2027, 6, 30))
        self.assertEqual(format_ys(result.current_year), "2025-26")
        self.assertAlmostEqual(result.floor_pct, 83.0)
        nxt = result.year_checks[result.current_year + 1]
        self.assertTrue(nxt.is_next)
        self.assertAlmostEqual(nxt.one_floor, 50.7, places=1)
        self.assertTrue(nxt.one_below)  # 4 of 417

    def test_summary_carries_two_year_below_floor_and_the_web_reads_it(self) -> None:
        summary = dr.summary_dict(dr.compute(self.rows(), date(2026, 11, 24)))
        self.assertIs(summary["two_year_below_floor"], True)
        lamps = (ROOT / "web" / "src" / "lib" / "pipeline-lamps.ts").read_text(encoding="utf-8")
        self.assertIn("two_year_below_floor", lamps)


def format_ys(start: int) -> str:
    return dr.format_year(start)


class FlaggedAndSubInstitutionTests(unittest.TestCase):
    def base(self) -> list[dict]:
        return many_schools(400, with_current=300)

    def test_a_flagged_current_year_document_does_not_count_as_renewing(self) -> None:
        rows = self.base()
        for r in rows:
            if r["school_id"] in {"s0", "s1", "s2"} and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "blank_template"
        result = dr.compute(rows, date(2026, 11, 24))
        counted = len(result.current.renewed)
        plain = len(dr.compute(self.base(), date(2026, 11, 24)).current.renewed)
        self.assertEqual(plain - counted, 3)
        self.assertEqual({d["school_id"] for d in result.flagged_docs}, {"s0", "s1", "s2"})
        self.assertEqual(dr.summary_dict(result)["flagged_current_docs"], 3)
        self.assertIn("s0", result.current.missing)

    def test_each_uncounted_flag_is_uncounted_and_other_flags_are_not(self) -> None:
        # Fails closed: any flag at all keeps a document from counting, known or not.
        for flag, counts in (("wrong_file", False), ("blank_template", False),
                             ("low_coverage", False), ("some_other_flag", False),
                             ("brand_new_flag_2027", False), ("", True), (None, True)):
            rows = self.base()
            for r in rows:
                if r["school_id"] == "s0" and r["canonical_year"] == "2025-26":
                    r["data_quality_flag"] = flag
            result = dr.compute(rows, date(2026, 11, 24))
            self.assertEqual("s0" in result.current.renewed, counts, flag)

    def test_flagged_documents_do_not_count_in_the_two_year_numerator_either(self) -> None:
        rows = self.base()
        # s0 filed 2024-25 and a flagged 2025-26; s390 filed only 2023-24 (two-year denominator).
        for r in rows:
            if r["school_id"] == "s0" and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "blank_template"
        rows.append(row("old", "2023-24"))
        rows.append({**row("old", "2025-26"), "data_quality_flag": "wrong_file"})
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertNotIn("s0", result.two_year.renewed)
        self.assertIn("old", result.two_year.prev_schools)
        self.assertNotIn("old", result.two_year.renewed)

    def test_flagged_documents_do_not_count_in_the_next_year_numerator(self) -> None:
        rows = many_schools(400, with_current=400)
        rows += [row(f"s{i}", "2026-27") for i in range(30)]
        for r in rows:
            if r["school_id"] in {"s0", "s1"} and r["canonical_year"] == "2026-27":
                r["data_quality_flag"] = "low_coverage"
        result = dr.compute(rows, date(2027, 4, 30))
        self.assertEqual(len(result.next.renewed), 28)
        self.assertEqual(len(result.next.prev_schools), 400)  # flagged-only still files the year

    def test_a_second_unflagged_document_still_renews_the_school(self) -> None:
        rows = self.base()
        for r in rows:
            if r["school_id"] == "s0" and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "wrong_file"
        rows.append(row("s0", "2025-26"))
        self.assertIn("s0", dr.compute(rows, date(2026, 11, 24)).current.renewed)

    def test_a_flagged_previous_year_document_stays_in_the_denominator(self) -> None:
        rows = self.base()
        for r in rows:
            if r["school_id"] == "s350" and r["canonical_year"] == "2024-25":
                r["data_quality_flag"] = "low_coverage"
        self.assertIn("s350", dr.compute(rows, date(2026, 11, 24)).current.prev_schools)

    def test_an_unknown_flag_does_not_count_and_is_visible_in_the_report(self) -> None:
        rows = self.base()
        for r in rows:
            if r["school_id"] in {"s0", "s1"} and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "brand_new_flag_2027"
            if r["school_id"] == "s2" and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "wrong_file"
        result = dr.compute(rows, date(2026, 11, 24))
        for sid in ("s0", "s1", "s2"):
            self.assertNotIn(sid, result.current.renewed)
        text = dr.render_report(result, [], schools={})
        self.assertIn("brand_new_flag_2027 2 (a new value", text)
        self.assertIn("wrong_file 1", text)
        self.assertNotIn("wrong_file 1 (a new value", text)

    def test_the_report_names_flagged_documents(self) -> None:
        rows = self.base()
        for r in rows:
            if r["school_id"] == "s0" and r["canonical_year"] == "2025-26":
                r["data_quality_flag"] = "blank_template"
        result = dr.compute(rows, date(2026, 11, 24))
        text = dr.render_report(result, [], schools={"s0": {"id": "s0", "name": "Zero U"}})
        self.assertIn("1 current-year documents not counted (flagged)", text)
        self.assertIn("[Zero U](https://www.collegedata.fyi/schools/s0) (blank_template)", text)

    def test_sub_institution_rows_do_not_mask_a_missing_main_campus_file(self) -> None:
        rows = self.base()
        # s399 never filed 2025-26 itself; only a sub-program did.
        rows.append({**row("s399", "2025-26"), "sub_institutional": "general-studies"})
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertNotIn("s399", result.current.renewed)
        self.assertIn("s399", result.current.prev_schools)
        self.assertEqual(result.sub_institutional_excluded, 1)
        # A school whose only document is a sub-program's is not a school.
        rows.append({**row("only-sub", "2024-25"), "sub_institutional": "x"})
        self.assertNotIn("only-sub", dr.compute(rows, date(2026, 11, 24)).current.prev_schools)
        text = dr.render_report(result, [])
        self.assertIn("1 sub-institution documents are left out", text)

    def test_the_manifest_query_asks_for_both_columns(self) -> None:
        self.assertIn("data_quality_flag", dr.MANIFEST_QUERY)
        self.assertIn("sub_institutional", dr.MANIFEST_QUERY)


class ArrivalsTests(unittest.TestCase):
    """The total-stop check: schools that gained a usable current or next year
    document in the last 30 days, against what the posting curve expects."""

    def archive(self, last_arrival: str, *, schools: int = 400, renewed: int = 200) -> list[dict]:
        rows = []
        for i in range(schools):
            rows.append(row(f"s{i}", "2023-24", discovered="2025-12-01T00:00:00+00:00"))
            rows.append(row(f"s{i}", "2024-25", discovered="2026-01-10T00:00:00+00:00"))
            if i < renewed:
                rows.append(row(f"s{i}", "2025-26", discovered=last_arrival))
        return rows

    def test_a_frozen_archive_fires_within_thirty_days_of_the_freeze(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        fired = None
        for offset in range(0, 60):
            day = date(2026, 5, 1) + timedelta(days=offset)
            res = dr.compute(rows, day)
            if res.arrivals.below_floor:
                fired = offset
                break
        self.assertIsNotNone(fired)
        self.assertLessEqual(fired, 31)
        self.assertGreater(fired, 0)  # not the day of the last arrivals

    def test_new_arrivals_keep_it_quiet(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        # 40 more schools arrive in the last two weeks before 2026-06-02.
        rows += [row(f"s{i}", "2025-26", discovered="2026-05-25T00:00:00+00:00") for i in range(200, 240)]
        res = dr.compute(rows, date(2026, 6, 2))
        self.assertEqual(res.arrivals.next.count_30, 40)
        self.assertGreaterEqual(res.arrivals.next.expected_30, 10)
        self.assertFalse(res.arrivals.below_floor)

    def test_it_says_not_checked_when_even_sixty_days_expect_almost_nothing(self) -> None:
        # A small archive in early January: the mature year expects nothing and
        # the next year has barely started, so there is no verdict, and the
        # report says why.
        res = dr.compute(self.archive("2026-05-01T12:00:00+00:00", schools=100, renewed=50),
                         date(2027, 1, 5), enforce_min_prev=False)
        self.assertEqual(res.arrivals.window_days, 60)
        self.assertLess(res.arrivals.expected_60, dr.ARRIVALS_MIN_EXPECTED)
        self.assertFalse(res.arrivals.checked)
        self.assertFalse(res.arrivals.below_floor)
        summary = dr.summary_dict(res)
        self.assertIs(summary["arrivals_checked"], False)
        self.assertIs(summary["arrivals_below_floor"], False)
        text = dr.render_report(res, [])
        self.assertIn("not checked.", text)
        self.assertIn("60 days:", text)

    def test_both_windows_are_judged_and_each_is_checked_from_its_own_expectation(self) -> None:
        archive = self.archive("2026-12-01T12:00:00+00:00", schools=400, renewed=300)
        winter = dr.compute(archive, date(2027, 1, 10))
        summary = dr.summary_dict(winter)
        self.assertGreaterEqual(summary["arrivals_expected_next_60d"], dr.ARRIVALS_MIN_EXPECTED)
        self.assertIs(summary["arrivals_next_checked_60"], True)
        self.assertEqual(summary["arrivals_next_checked_30"],
                         summary["arrivals_expected_next_30d"] >= dr.ARRIVALS_MIN_EXPECTED_30)
        self.assertEqual(dr.ARRIVALS_MIN_EXPECTED_30, 6.0)
        # A year whose current-year curve has flattened is not judged in either window.
        self.assertIs(summary["arrivals_current_checked_30"], False)
        self.assertIs(summary["arrivals_current_checked_60"], False)
        spring = dr.compute(self.archive("2026-05-01T12:00:00+00:00"), date(2026, 6, 2))
        self.assertEqual(spring.arrivals.window_days, 30)

    def stopped_archive(self, cohort: int, stop: date) -> list[dict]:
        """`cohort` schools filing the current and the next year on the curve's
        timing (87% of them), with nothing arriving after `stop`."""
        def when(year: int, u: float):
            lo, hi = 0.0, 40.0
            for _ in range(60):
                mid = (lo + hi) / 2
                if dr.expected_pct(mid) / 100.0 < u:
                    lo = mid
                else:
                    hi = mid
            return datetime.combine(date(year, 9, 1), datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=hi * 30.4375)

        cutoff = datetime.combine(stop, datetime.max.time(), tzinfo=timezone.utc)
        rows = []
        for i in range(cohort):
            u = (i + 0.5) / cohort
            rows.append(row(f"s{i}", "2023-24", discovered=None))
            rows.append(row(f"s{i}", "2024-25", discovered="2025-06-01T00:00:00+00:00"))
            for year, scale in ((2025, 0.87 / 0.88), (2026, 0.9)):
                if u <= scale * 0.88:
                    filed = when(year, u / scale)
                    if filed <= cutoff:
                        rows.append(row(f"s{i}", dr.format_year(year), discovered=filed.isoformat()))
        return rows

    def first_alarm_day(self, rows, stop: date) -> int | None:
        for offset in range(1, 75):
            day = stop + timedelta(days=offset)
            res = dr.compute(dr.rows_as_of(rows, day), day, enforce_min_prev=False)
            if res.arrivals.below_floor:
                return offset
        return None

    def test_a_total_stop_is_seen_within_a_month_whichever_window_is_in_use(self) -> None:
        # Gemini's three scenarios. With a cohort of 417 the 30-day window expects
        # under 10 from October, so the 60-day window alone would hide a stop for
        # 37 to 53 days (an Oct 1 stop would not fire until Nov 7).
        for cohort, stop in ((417, date(2026, 10, 1)), (480, date(2026, 11, 18)),
                             (417, date(2026, 9, 14))):
            delay = self.first_alarm_day(self.stopped_archive(cohort, stop), stop)
            self.assertIsNotNone(delay, (cohort, stop))
            self.assertLessEqual(delay, 31, (cohort, stop, delay))

    def test_the_sixty_day_window_alone_would_have_been_too_slow(self) -> None:
        stop = date(2026, 10, 1)
        rows = self.stopped_archive(417, stop)
        slow = None
        for offset in range(1, 75):
            day = stop + timedelta(days=offset)
            res = dr.compute(dr.rows_as_of(rows, day), day, enforce_min_prev=False)
            if any(y.below_60 for y in res.arrivals.years):
                slow = offset
                break
        fast = self.first_alarm_day(rows, stop)
        self.assertGreater(slow, 31)  # the 60-day window alone
        self.assertLessEqual(fast, 31)  # with the 30-day window judged too

    def test_either_window_below_its_floor_is_a_breach(self) -> None:
        only_30 = dr.YearArrivals(2025, count_30=1, expected_30=20.0, count_60=40, expected_60=40.0)
        self.assertTrue(only_30.below_30 and not only_30.below_60 and only_30.below_floor)
        self.assertEqual(only_30.window_days, 30)
        only_60 = dr.YearArrivals(2025, count_30=20, expected_30=20.0, count_60=3, expected_60=40.0)
        self.assertTrue(only_60.below_60 and not only_60.below_30 and only_60.below_floor)
        self.assertEqual(only_60.window_days, 60)
        fine = dr.YearArrivals(2025, count_30=20, expected_30=20.0, count_60=40, expected_60=40.0)
        self.assertFalse(fine.below_floor)
        self.assertEqual(fine.window_days, 30)

    def test_a_frozen_archive_from_december_first_fires_by_early_february(self) -> None:
        # 300 schools arrive on 2026-12-01 and then nothing does.
        archive = self.archive("2026-12-01T12:00:00+00:00", schools=400, renewed=300)
        fired = None
        for offset in range(0, 90):
            day = date(2026, 12, 1) + timedelta(days=offset)
            res = dr.compute(archive, day)
            if res.arrivals.below_floor:
                fired = day
                break
        self.assertIsNotNone(fired)
        self.assertLessEqual(fired, date(2027, 2, 5))
        # Each year is judged on its own: nothing for 2026-27 has arrived, so
        # that year trips as soon as its own 60-day window expects 10.
        self.assertGreater(fired, date(2027, 1, 1))

    def test_the_sixty_day_alarm_words_its_own_window(self) -> None:
        archive = self.archive("2026-10-01T12:00:00+00:00", schools=400, renewed=300)
        res = dr.compute(archive, date(2026, 12, 20))
        self.assertEqual(res.arrivals.window_days, 60)
        self.assertTrue(res.arrivals.below_floor)
        text = dr.render_report(res, [], lead="arrivals")
        self.assertIn("in the last 60 days", text)
        ys = dr.year_summary(res.year_checks[res.current_year], res.arrivals)
        self.assertEqual(dr.check_descriptor(ys, "arrivals")["window"], 60)

    def test_the_threshold_is_forty_percent_of_expected(self) -> None:
        self.assertEqual(dr.ARRIVALS_FLOOR_SHARE, 0.4)
        for count, below in ((11, True), (12, False)):  # 0.4 x 30 = 12
            y = dr.YearArrivals(2025, count_30=count, expected_30=30.0)
            self.assertEqual(y.below_floor, below, count)
        # The 30-day window is judged from 6 expected, the 60-day one from 10.
        self.assertTrue(dr.YearArrivals(2025, count_30=0, expected_30=6.0).below_floor)
        self.assertFalse(dr.YearArrivals(2025, count_30=0, expected_30=5.9, expected_60=9.9).below_floor)
        self.assertTrue(dr.YearArrivals(2025, count_30=20, expected_30=5.9, count_60=0, expected_60=10.0).below_floor)

    def test_a_school_counts_once_for_either_year_and_for_a_second_file(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        recent = "2026-05-28T00:00:00+00:00"
        rows += [row("s300", "2024-25", discovered=recent)]  # current year, new file
        rows += [row("s300", "2025-26", discovered=recent)]  # same school, next year
        rows += [row("s0", "2025-26", discovered=recent)]  # s0 already had 2025-26 in May
        res = dr.compute(rows, date(2026, 6, 2))
        self.assertIn("s300", res.arrivals.schools_30)
        self.assertEqual(res.arrivals.count_30, 1)
        self.assertNotIn("s0", res.arrivals.schools_30)

    def test_hand_archived_current_year_files_do_not_mask_a_stopped_next_year(self) -> None:
        """Each year is judged on its own: 2025-26 files archived by hand every few
        weeks must not hide that nothing arrives for the next year."""
        rows = []
        for i in range(400):
            rows.append(row(f"s{i}", "2023-24", discovered="2025-12-01T00:00:00+00:00"))
            rows.append(row(f"s{i}", "2024-25", discovered="2026-01-10T00:00:00+00:00"))
            rows.append(row(f"s{i}", "2025-26", discovered="2026-01-15T00:00:00+00:00"))
        # March 1: 2025-26 is the next year (expected well above 10 a month).
        res = dr.compute(rows, date(2026, 6, 10))
        self.assertTrue(res.arrivals.next.checked)
        self.assertTrue(res.arrivals.next.below_floor)
        # The pooled number would have been healthy: hand-archived current-year files.
        rows += [row(f"h{i}", "2024-25", discovered="2026-06-01T00:00:00+00:00") for i in range(50)]
        rows += [row(f"h{i}", "2023-24") for i in range(50)]
        res = dr.compute(rows, date(2026, 6, 10))
        self.assertGreater(res.arrivals.current.count_30, 0)  # by hand, current year
        self.assertEqual(res.arrivals.next.count_30, 0)
        self.assertTrue(res.arrivals.below_floor)
        summary = dr.summary_dict(res)
        self.assertIs(summary["arrivals_next_below_floor"], True)
        self.assertEqual(summary["arrivals_next_30d"], 0)
        self.assertGreater(summary["arrivals_current_30d"], 0)
        self.assertEqual(summary["arrivals_30d"], res.arrivals.count_30)  # totals kept

    def test_a_current_year_arrival_only_counts_for_a_school_in_the_cohort(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        # `fresh` has 2025-26 (the next year) but never had 2024-25: not in its cohort.
        rows += [row("fresh", "2025-26", discovered="2026-05-28T00:00:00+00:00")]
        res = dr.compute(rows, date(2026, 6, 2))
        self.assertNotIn("fresh", res.arrivals.schools_30)

    def test_unextracted_next_year_documents_do_not_make_a_healthy_run_look_short(self) -> None:
        rows = []
        for i in range(400):
            rows.append(row(f"s{i}", "2024-25"))
            rows.append({**row(f"s{i}", "2025-26", discovered="2026-11-10T00:00:00+00:00"),
                         "extraction_status": "extracted"})
        # Next year's first files, filed but not extracted yet.
        rows += [{**row(f"s{i}", "2026-27", discovered="2026-11-20T00:00:00+00:00"),
                  "extraction_status": "extraction_pending"} for i in range(12)]
        res = dr.compute(rows, date(2026, 11, 24))
        summary = dr.summary_dict(res)
        self.assertEqual(summary["unextracted_next_docs"], 12)
        self.assertEqual(summary["unextracted_current_docs"], 0)
        for flag in ("below_floor", "two_year_below_floor", "arrivals_below_floor",
                     "outstanding_below_floor"):
            self.assertIs(summary[flag], False, flag)
        self.assertIsNot(summary["next_below_floor"], True)
        self.assertEqual((summary["outstanding_years"], summary["arrivals_years"]), ("", ""))
        self.assertEqual(dr.outstanding_years(res), [])
        self.assertIsNone(dr.lead_check(summary))
        self.assertFalse(any(s["below_floor"] for s in dr.arrivals_state(res).values()))

    def test_unextracted_next_year_documents_are_reported_not_alarmed(self) -> None:
        rows = many_schools(400, with_current=400)
        for r in rows:
            r["extraction_status"] = "extracted"
        rows += [{**row(f"s{i}", "2026-27"), "extraction_status": "extraction_pending"} for i in range(5)]
        res = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(res.unextracted_next_docs, 5)
        self.assertEqual(dr.summary_dict(res)["unextracted_next_docs"], 5)
        self.assertIn("5 next-year documents are filed but not extracted yet", dr.render_report(res, []))
        self.assertIn("removed rows are not read", dr.render_report(res, []))

    def test_a_school_gaining_both_years_in_one_window_counts_once(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        recent = "2026-05-28T00:00:00+00:00"
        rows += [row("s350", "2024-25", discovered=recent), row("s350", "2025-26", discovered=recent)]
        res = dr.compute(rows, date(2026, 6, 2))
        self.assertEqual(res.arrivals.count_30, 1)
        self.assertEqual(res.arrivals.schools_30, {"s350"})

    def test_flagged_sub_institution_and_undated_documents_are_not_arrivals(self) -> None:
        rows = self.archive("2026-05-01T12:00:00+00:00")
        recent = "2026-05-28T00:00:00+00:00"
        rows += [{**row("s300", "2025-26", discovered=recent), "data_quality_flag": "wrong_file"}]
        rows += [{**row("s301", "2025-26", discovered=recent), "sub_institutional": "x"}]
        rows += [row("s302", "2025-26", discovered=None)]
        rows += [row("s303", "2025-26", discovered=recent, removed="2026-05-30T00:00:00+00:00")]
        rows += [row("s304", "unknown", discovered=recent)]
        res = dr.compute(rows, date(2026, 6, 2))
        self.assertEqual(res.arrivals.count_30, 0)

    def test_the_summary_and_the_lead_check_carry_it(self) -> None:
        res = dr.compute(self.archive("2026-05-01T12:00:00+00:00"), date(2026, 6, 20))
        summary = dr.summary_dict(res)
        self.assertIs(summary["arrivals_below_floor"], True)
        self.assertEqual(summary["arrivals_30d"], 0)
        self.assertGreaterEqual(summary["arrivals_expected_30d"], 10)
        # Arrivals are their own alarm scope: they are not a renewal check.
        ys = dr.year_summary(res.year_checks[res.current_year])
        self.assertIsNone(dr.lead_check({**ys, "below_floor": False, "two_year_below_floor": False}))
        self.assertEqual(summary["arrivals_years"], dr.format_year(res.current_year + 1))
        self.assertIn(dr.format_year(res.current_year + 1), dr.outstanding_years(res))
        state = dr.arrivals_state(res)
        self.assertEqual(sorted(state), [dr.format_year(res.current_year), dr.format_year(res.current_year + 1)])
        self.assertTrue(state[dr.format_year(res.current_year + 1)]["below_floor"])

    def test_the_report_leads_with_arrivals_when_nothing_else_is_below(self) -> None:
        res = dr.compute(self.archive("2026-05-01T12:00:00+00:00"), date(2026, 6, 20))
        text = dr.render_report(res, [], lead="arrivals")
        self.assertIn("Only 0 schools gained", text)
        self.assertIn("30 days: 0 against about", text)

    def test_unextracted_current_year_documents_are_counted_for_the_report_only(self) -> None:
        rows = many_schools(400, with_current=400)
        for r in rows:
            r["extraction_status"] = "extracted"
        for r in rows[:6]:
            if r["canonical_year"] == "2025-26":
                r["extraction_status"] = "extraction_pending"
        rows[1]["extraction_status"] = "failed"
        result = dr.compute(rows, date(2026, 11, 24))
        self.assertEqual(result.unextracted_current_docs, 3)
        summary = dr.summary_dict(result)
        self.assertEqual(summary["unextracted_current_docs"], 3)
        self.assertEqual(summary["renewed"], 400)  # they still count as filed
        self.assertIn("3 current-year documents are filed but not extracted yet", dr.render_report(result, []))
        self.assertIn("#477", dr.render_report(result, []))

    def test_rows_without_an_extraction_status_column_count_as_zero(self) -> None:
        result = dr.compute(many_schools(400, with_current=400), date(2026, 11, 24))
        self.assertEqual(result.unextracted_current_docs, 0)


class YearReportTests(unittest.TestCase):
    def test_every_evaluated_year_has_checks_and_a_report(self) -> None:
        rows = many_schools(400, with_current=400)
        result = dr.compute(rows, date(2027, 6, 30))
        self.assertEqual(sorted(result.year_checks), list(range(2022, 2027)))
        nxt = result.year_checks[2026]
        self.assertTrue(nxt.is_next)
        text = dr.render_year_report(result, 2026, dr.missing_worklist(result, {}, "current", 2026))
        self.assertIn("Discovery renewal for 2026-27", text)
        self.assertIn("next CDS year", text)
        old = dr.render_year_report(result, 2023, [])
        self.assertIn("earlier CDS year", old)

    def test_an_earlier_year_uses_the_flat_mature_floor(self) -> None:
        rows = many_schools(400, with_current=300)
        # 2026-11-24: 2024-25 is an earlier year, 15+ months past its fall.
        result = dr.compute(rows, date(2026, 11, 24))
        yc = result.year_checks[2024]
        self.assertAlmostEqual(yc.one_floor, 88.0 - dr.CURRENT_YEAR_MARGIN_PTS)
        self.assertAlmostEqual(yc.two_floor, 88.0 - dr.CURRENT_YEAR_MARGIN_PTS - dr.TWO_YEAR_MARGIN_PTS)

    def test_the_next_year_is_untracked_before_march(self) -> None:
        result = dr.compute(many_schools(400, with_current=300), date(2026, 11, 24))
        yc = result.year_checks[2026]
        self.assertIsNone(yc.one_floor)
        self.assertFalse(yc.one_below)
        self.assertFalse(yc.two_below)

    def test_year_summary_matches_the_summary_shape_for_the_current_year(self) -> None:
        result = dr.compute(many_schools(400, with_current=300), date(2026, 11, 24))
        ys = dr.year_summary(result.year_checks[2025])
        full = dr.summary_dict(result)
        for key in ("current_year", "renewed", "prev_schools", "renewal_pct", "floor_pct",
                    "below_floor", "two_year_renewed", "two_year_prev_schools",
                    "two_year_renewal_pct", "two_year_floor_pct", "two_year_below_floor"):
            self.assertEqual(ys[key], full[key], key)
        self.assertIs(type(ys["below_floor"]), bool)

    def test_the_cli_writes_one_report_per_year_and_per_year_state(self) -> None:
        import tempfile
        rows = [row(s, y) for s, ys in json.loads(ARCHIVE_YEARS.read_text()).items() for y in ys]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "m.json").write_text(json.dumps(rows))
            code = dr.main(["--manifest-json", str(tmp / "m.json"), "--as-of", "2027-06-30",
                            "--out-state", str(tmp / "state.json"),
                            "--out-summary", str(tmp / "summary.json"),
                            "--out-report", str(tmp / "report.md"),
                            "--out-year-reports", str(tmp / "yr")])
            self.assertEqual(code, 0)
            state = json.loads((tmp / "state.json").read_text())
            self.assertEqual(state["current_year"], "2025-26")
            self.assertEqual(sorted(state["years"]), ["2022-23", "2023-24", "2024-25", "2025-26", "2026-27"])
            self.assertTrue(state["years"]["2026-27"]["below_floor"])
            self.assertEqual(
                sorted(p.name for p in (tmp / "yr").glob("*.md")),
                sorted([f"{y}.md" for y in state["years"]] + ["arrivals-2025-26.md", "arrivals-2026-27.md"]),
            )
            self.assertEqual(sorted(state["arrivals"]), ["2025-26", "2026-27"])
            self.assertIn("Discovery arrivals for 2026-27", (tmp / "yr" / "arrivals-2026-27.md").read_text())
            # The next year breaches, so the step summary carries it too.
            self.assertIn("Discovery renewal for 2026-27", (tmp / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
