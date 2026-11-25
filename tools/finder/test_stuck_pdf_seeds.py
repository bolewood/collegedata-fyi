"""Tests for stuck PDF-seed classification and shared-domain ownership."""

from __future__ import annotations

import io
import json
import re
import unittest
import urllib.error
from datetime import date
from pathlib import Path

from tools.finder.stuck_pdf_seeds import (
    SKIP_REASONS,
    check_accounting,
    choose_canonical_school,
    classify_all,
    classify_school,
    fetch_years_by_school,
    load_schools,
    default_min_fresh_year,
    is_direct_doc_seed,
    is_section_seed,
    shared_seed_groups,
)


class FreshYearTests(unittest.TestCase):
    def test_august_uses_prior_complete_cycle(self) -> None:
        self.assertEqual(default_min_fresh_year(date(2026, 8, 21)), "2024-25")

    def test_september_expects_previous_academic_year(self) -> None:
        self.assertEqual(default_min_fresh_year(date(2026, 9, 1)), "2025-26")


class ClassifyTests(unittest.TestCase):
    def test_listing_seed_is_skipped_with_a_reason(self) -> None:
        school = {"id": "ou", "discovery_seed_url": "https://www.ou.edu/irr/other-reports"}
        row = classify_school(school, ["2023-24"], min_fresh_year="2024-25")
        self.assertEqual((row["bucket"], row["reason"]), ("skipped", "listing_seed"))

    def test_stale_single_pdf_is_stuck(self) -> None:
        school = {
            "id": "portland-state-university",
            "discovery_seed_url": "https://example.edu/cds-2023-2024.pdf",
        }
        row = classify_school(
            school, ["2023-24"], min_fresh_year="2024-25"
        )
        self.assertEqual(row["bucket"], "flagged")
        self.assertEqual(row["latest"], "2023-24")

    def test_recent_single_pdf_is_not_coverage_stuck(self) -> None:
        school = {
            "id": "example",
            "discovery_seed_url": "https://example.edu/cds-2024-2025.pdf",
        }
        row = classify_school(school, ["2024-25"], min_fresh_year="2024-25")
        self.assertEqual(row["bucket"], "fresh")

    def test_zero_years_pdf_is_stuck(self) -> None:
        school = {
            "id": "ohio-university-main-campus",
            "discovery_seed_url": "https://www.ohio.edu/instres/commondataset.pdf",
        }
        row = classify_school(school, [], min_fresh_year="2024-25")
        self.assertEqual(row["bucket"], "flagged")
        self.assertEqual(row["n_years"], 0)

    def test_many_stale_years_are_still_stuck(self) -> None:
        # Richmond on 2026-11-24: six archived years from a mirror, a seed
        # that is one 2021-22 file, and nothing newer than 2024-25.
        school = {"id": "x", "discovery_seed_url": "https://example.edu/a.pdf"}
        row = classify_school(
            school,
            ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"],
            min_fresh_year="2025-26",
        )
        self.assertEqual(row["bucket"], "flagged")
        self.assertEqual(row["reason"], "stale_single_document")
        self.assertEqual(row["latest"], "2024-25")
        self.assertEqual(row["n_years"], 6)

    def test_an_undated_document_does_not_make_a_school_look_fresh(self) -> None:
        # "unknown" sorts above every year as a string.
        school = {"id": "x", "discovery_seed_url": "https://example.edu/a.pdf"}
        row = classify_school(
            school, ["2023-24", "2024-25", "unknown"], min_fresh_year="2025-26"
        )
        self.assertEqual(row["bucket"], "flagged")
        self.assertEqual(row["latest"], "2024-25")
        self.assertEqual(row["years"], ["2023-24", "2024-25"])

    def test_many_years_with_a_fresh_one_are_not_stuck(self) -> None:
        school = {"id": "x", "discovery_seed_url": "https://example.edu/a.pdf"}
        row = classify_school(
            school,
            ["2022-23", "2023-24", "2024-25", "2025-26"],
            min_fresh_year="2025-26",
        )
        self.assertEqual(row["bucket"], "fresh")


    def test_section_pdf_seed_is_stuck_even_with_many_fresh_years(self) -> None:
        # Utah's seed was CDS_2022-2023-D.pdf: archive refresh only ever
        # re-verified Section D, and 7 archived years kept it off this list.
        school = {
            "id": "university-of-utah",
            "discovery_seed_url": "https://budget.utah.edu/wp-content/uploads/sites/10/2022/12/CDS_2022-2023-D.pdf",
        }
        row = classify_school(
            school,
            ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"],
            min_fresh_year="2025-26",
        )
        self.assertEqual(row["bucket"], "flagged")
        self.assertEqual(row["reason"], "section_seed")

    def test_section_seed_filename_shapes(self) -> None:
        for url in (
            "https://www.rmc.edu/wp-content/uploads/2024/05/CDS_2023_2024_F.pdf",
            "https://wp.stolaf.edu/iea/files/2021/12/2021-2022-CDS-D.pdf",
            "https://www.depauw.edu/files/resources/cds-c-2223-3.pdf",
            "https://irma.depaul.edu/cds/2023/2023CDS_C.pdf",
            "https://www.fsw.edu/x/CDS%202015-16%20Section%20D%20Transfer%20Admission.pdf",
        ):
            self.assertTrue(is_section_seed(url), url)
        for url in (
            "https://example.edu/a.pdf",
            "https://example.edu/cds-2024-2025.pdf",
            "https://example.edu/CDS_2022-2023.pdf",
            "https://www.ohio.edu/instres/commondataset.pdf",
            "https://example.edu/ir/cds/",
        ):
            self.assertFalse(is_section_seed(url), url)

    def test_stale_seed_reason(self) -> None:
        school = {"id": "x", "discovery_seed_url": "https://example.edu/cds-2023-2024.pdf"}
        row = classify_school(school, ["2023-24"], min_fresh_year="2024-25")
        self.assertEqual(row["reason"], "stale_single_document")


class AccountingTests(unittest.TestCase):
    FLOOR = "2025-26"

    def synthetic(self):
        schools = [
            # many mirror years behind a one-file seed (the old two-year cap hid these)
            {"id": "mirror", "discovery_seed_url": "https://a.edu/cds-2021-22.pdf"},
            # undated documents only: `unknown` must not read as newest
            {"id": "undated", "discovery_seed_url": "https://b.edu/cds.pdf"},
            # one-file seed, already holds the current year
            {"id": "current", "discovery_seed_url": "https://c.edu/cds.pdf"},
            # stale listing page
            {"id": "listing", "discovery_seed_url": "https://d.edu/ir/cds/"},
            # section seed with every year archived
            {"id": "section", "discovery_seed_url": "https://e.edu/CDS_2022-2023-D.pdf"},
            {"id": "noseed"},
        ]
        years = {
            "mirror": ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"],
            "undated": ["unknown", "unknown"],
            "current": ["2024-25", "2025-26"],
            "listing": ["2023-24"],
            "section": ["2023-24", "2024-25", "2025-26"],
        }
        return schools, years

    def test_every_school_lands_in_exactly_one_bucket(self) -> None:
        schools, years = self.synthetic()
        flagged, counts = classify_all(schools, years, min_fresh_year=self.FLOOR)
        self.assertEqual(counts["total"], 6)
        self.assertEqual(
            counts["flagged"] + counts["fresh"] + counts["skipped"], counts["total"]
        )
        self.assertEqual(
            sorted(r["id"] for r in flagged), ["mirror", "section", "undated"]
        )
        self.assertEqual(counts["fresh"], 1)
        self.assertEqual(counts["skipped_listing_seed"], 1)
        self.assertEqual(counts["skipped_no_seed"], 1)
        self.assertEqual(
            counts["skipped"], sum(counts[f"skipped_{r}"] for r in SKIP_REASONS)
        )

    def test_many_archived_years_do_not_hide_a_stale_one_file_seed(self) -> None:
        # Six archived years and a one-file seed: flagged. (An earlier cap on
        # archived years skipped these, and a test asserted the cap.)
        schools, years = self.synthetic()
        flagged, _ = classify_all(schools, years, min_fresh_year=self.FLOOR)
        mirror = next(r for r in flagged if r["id"] == "mirror")
        self.assertEqual(mirror["n_years"], 6)
        self.assertEqual(mirror["latest"], "2024-25")

    def test_unknown_year_is_not_the_newest(self) -> None:
        schools, years = self.synthetic()
        flagged, _ = classify_all(schools, years, min_fresh_year=self.FLOOR)
        undated = next(r for r in flagged if r["id"] == "undated")
        self.assertIsNone(undated["latest"])

    def test_an_inconsistent_count_raises(self) -> None:
        schools, years = self.synthetic()
        _, counts = classify_all(schools, years, min_fresh_year=self.FLOOR)
        check_accounting(counts)  # consistent: no error
        for key, delta in (("flagged", 1), ("fresh", -1), ("skipped_no_seed", 1), ("total", 1)):
            bad = {**counts, key: counts[key] + delta}
            with self.assertRaises(RuntimeError, msg=key):
                check_accounting(bad)

    def test_bad_floor_raises(self) -> None:
        with self.assertRaises(ValueError):
            classify_school(
                {"id": "x", "discovery_seed_url": "https://x.edu/a.pdf"},
                [],
                min_fresh_year="unknown",
            )


class RealSchoolsTests(unittest.TestCase):
    """The goal, over the real schools.yaml and a committed archive snapshot.

    The snapshot is {school_id: sorted distinct canonical_years of live
    published documents} from cds_manifest on 2026-11-24. Rebuild it with
    tools/finder/testdata/build_archive_years_snapshot.py MANIFEST.json.
    """

    FLOOR = "2025-26"

    @classmethod
    def setUpClass(cls) -> None:
        here = Path(__file__).resolve().parent
        cls.schools = load_schools(here / "schools.yaml")
        cls.years = json.loads(
            (here / "testdata" / "archive_years_snapshot.json").read_text()
        )

    def test_identity_holds_over_every_school(self) -> None:
        flagged, counts = classify_all(
            self.schools, self.years, min_fresh_year=self.FLOOR
        )
        self.assertEqual(counts["total"], len(self.schools))
        self.assertEqual(
            counts["flagged"] + counts["fresh"] + counts["skipped"], counts["total"]
        )
        self.assertEqual(counts["flagged"], len(flagged))

    def test_every_stale_one_file_seed_is_flagged(self) -> None:
        # Independent of classify_school: recompute the goal from raw data.
        flagged, _ = classify_all(self.schools, self.years, min_fresh_year=self.FLOOR)
        flagged_ids = {r["id"] for r in flagged}
        behind = set()
        for s in self.schools:
            seed = s.get("discovery_seed_url") or ""
            if not is_direct_doc_seed(seed):
                continue
            real = [y for y in self.years.get(s["id"], []) if re.match(r"^\d{4}-\d{2}$", y)]
            newest = max((int(y[:4]) for y in real), default=None)
            if newest is None or newest < 2025:
                behind.add(s["id"])
        self.assertTrue(behind, "snapshot should contain stale one-file seeds")
        self.assertLessEqual(behind, flagged_ids)

    def test_a_school_with_many_years_and_a_stale_one_file_seed_is_flagged(self) -> None:
        flagged, _ = classify_all(self.schools, self.years, min_fresh_year=self.FLOOR)
        many = [r for r in flagged if r["n_years"] > 2 and r["reason"] == "stale_single_document"]
        self.assertTrue(many, "real data has such schools (90 on 2026-11-24)")


class FetchYearsTests(unittest.TestCase):
    def _opener(self, pages, total_header=None):
        calls = []

        class Resp:
            def __init__(self, rows, header):
                self._rows, self.headers = rows, {"Content-Range": header}

            def read(self):
                return json.dumps(self._rows).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=0):
            i = len(calls)
            calls.append(req)
            rows = pages[i] if i < len(pages) else []
            header = total_header(i) if callable(total_header) else total_header
            return Resp(rows, header)

        opener.calls = calls
        return opener

    def rows(self, n, start=0):
        return [{"school_id": f"s{start + i}", "canonical_year": "2024-25"} for i in range(n)]

    def test_reads_every_page_and_returns_years(self) -> None:
        op = self._opener([self.rows(2), self.rows(1, 2)], lambda i: "0-1/3" if i == 0 else "2-2/3")
        out = fetch_years_by_school("https://x", "key", page=2, opener=op)
        self.assertEqual(sorted(out), ["s0", "s1", "s2"])
        self.assertEqual(len(op.calls), 2)
        self.assertEqual(op.calls[0].get_header("Prefer"), "count=exact")

    def test_short_read_raises(self) -> None:
        # Total says 5 rows; the server stops after 2. The old loop broke on a
        # short page and called that done.
        op = self._opener([self.rows(2), []], "0-1/5")
        with self.assertRaises(SystemExit):
            fetch_years_by_school("https://x", "key", page=2, opener=op)

    def test_zero_rows_raises(self) -> None:
        op = self._opener([[]], "*/0")
        with self.assertRaises(SystemExit):
            fetch_years_by_school("https://x", "key", opener=op)

    def test_missing_content_range_raises(self) -> None:
        op = self._opener([self.rows(1)], None)
        with self.assertRaises(SystemExit):
            fetch_years_by_school("https://x", "key", opener=op)

    def test_missing_anon_key_raises(self) -> None:
        with self.assertRaises(SystemExit):
            fetch_years_by_school("https://x", "")

    def test_reads_past_50000_rows(self) -> None:
        pages = [self.rows(1000, i * 1000) for i in range(52)]
        op = self._opener(pages, lambda i: f"{i * 1000}-{i * 1000 + 999}/52000")
        out = fetch_years_by_school("https://x", "key", page=1000, opener=op)
        self.assertEqual(len(out), 52000)

    def test_http_error_raises(self) -> None:
        def opener(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, io.BytesIO(b""))

        with self.assertRaises(SystemExit):
            fetch_years_by_school("https://x", "key", opener=opener)


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
