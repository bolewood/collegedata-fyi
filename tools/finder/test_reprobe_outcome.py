"""Tests for judging the re-probe by result, not by the step finishing (#463)."""

from __future__ import annotations

import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.finder import reprobe_outcome
from tools.finder.reprobe_outcome import (
    classify_all,
    classify_outcome,
    fetch_page,
    newest_year_from_document_url,
    newest_year_in_html,
    summarize,
)

LISTING_HTML = """
<html><body>
<ul>
  <li><a href="/files/cds_2023-2024.pdf">Common Data Set 2023-2024</a></li>
  <li><a href="/files/cds_2024-2025.pdf">CDS 2024-25</a></li>
  <li><a href="/about">About us, founded 1923-24 style text is not a link year</a></li>
</ul>
</body></html>
"""

LISTING_HTML_NEWER = LISTING_HTML.replace(
    "</ul>", '<li><a href="/files/CDS_2025-2026.pdf">2025-2026</a></li></ul>'
)


def flagged(latest="2024-25", seed="https://x.edu/cds-2021-22.pdf", sid="x"):
    return {"id": sid, "seed": seed, "latest": latest, "min_fresh_year": "2025-26"}


def no_fetch(url):  # a document seed must never be fetched
    raise AssertionError(f"unexpected fetch of {url}")


class YearReadingTests(unittest.TestCase):
    def test_newest_year_in_listing_links(self) -> None:
        self.assertEqual(newest_year_in_html(LISTING_HTML), "2024-25")
        self.assertEqual(newest_year_in_html(LISTING_HTML_NEWER), "2025-26")

    def test_year_in_href_only(self) -> None:
        self.assertEqual(
            newest_year_in_html('<a href="/CDS_2025-26.pdf">download</a>'), "2025-26"
        )

    def test_a_year_on_a_non_cds_link_is_ignored(self) -> None:
        # CDS 2023-24 plus an academic calendar 2025-26 is not a 2025-26 CDS.
        html = (
            '<a href="/files/cds_2023-2024.pdf">CDS 2023-24</a>'
            '<a href="/calendar/2025-26.pdf">Academic calendar 2025-26</a>'
        )
        self.assertEqual(newest_year_in_html(html), "2023-24")
        self.assertIsNone(
            newest_year_in_html('<a href="/calendar/2025-26.pdf">Academic calendar 2025-26</a>')
        )

    def test_listing_with_only_non_cds_years_is_unverified(self) -> None:
        html = '<a href="/ir/2025-2026-Factbooks-1.pdf">Factbook 2025-26</a>'
        row = classify_outcome(flagged(), "https://x.edu/ir", fetch=lambda u: html)
        self.assertEqual(row["outcome"], "listing_unverified")

    def test_page_without_years(self) -> None:
        self.assertIsNone(newest_year_in_html("<a href='/x'>Common Data Set</a>"))

    def test_document_url_year(self) -> None:
        self.assertEqual(
            newest_year_from_document_url("https://x.edu/a/CDS_2016-17.pdf"), "2016-17"
        )
        self.assertIsNone(newest_year_from_document_url("https://x.edu/a/cds.pdf"))


class OutcomeTests(unittest.TestCase):
    def test_unchanged(self) -> None:
        row = classify_outcome(flagged(), "https://x.edu/cds-2021-22.pdf", fetch=no_fetch)
        self.assertEqual(row["outcome"], "unchanged")

    def test_missing_new_seed_is_unchanged(self) -> None:
        self.assertEqual(classify_outcome(flagged(), None, fetch=no_fetch)["outcome"], "unchanged")

    def test_old_single_file_is_not_a_fix(self) -> None:
        # Hillsdale 2026-11-02: replaced by a 2016-17 PDF; counted as replaced.
        row = classify_outcome(flagged(), "https://x.edu/CDS_2016-17.pdf", fetch=no_fetch)
        self.assertEqual(row["outcome"], "still_one_file")

    def test_file_with_no_year_is_not_a_fix(self) -> None:
        row = classify_outcome(flagged(), "https://x.edu/cds.pdf", fetch=no_fetch)
        self.assertEqual(row["outcome"], "still_one_file")

    def test_file_the_same_year_as_the_archive_is_not_a_fix(self) -> None:
        row = classify_outcome(flagged(), "https://x.edu/CDS_2024-25.pdf", fetch=no_fetch)
        self.assertEqual(row["outcome"], "still_one_file")

    def test_non_cds_documents_are_not_a_fix(self) -> None:
        # Real bad seeds from #136.
        for url in (
            "https://x.edu/docs/academic-catalog-2017-18.pdf",
            "https://x.edu/docs/IPEDS-Fall-Enrollment-2021-2022.pdf",
            "https://x.edu/docs/2025-2026-Factbooks-1.pdf",
        ):
            row = classify_outcome(flagged(latest="2016-17"), url, fetch=no_fetch)
            self.assertEqual(row["outcome"], "still_one_file", url)

    def test_section_file_is_never_a_fix(self) -> None:
        row = classify_outcome(
            flagged(), "https://x.edu/CDS_2025-2026-D.pdf", fetch=no_fetch
        )
        self.assertEqual(row["outcome"], "still_one_file")

    def test_newer_single_file_is_fixed(self) -> None:
        row = classify_outcome(flagged(), "https://x.edu/CDS_2025-26.pdf", fetch=no_fetch)
        self.assertEqual(row["outcome"], "fixed_newer_year")
        self.assertEqual(row["seed_year"], "2025-26")

    def test_listing_with_newer_year_is_fixed(self) -> None:
        row = classify_outcome(
            flagged(), "https://x.edu/ir/cds", fetch=lambda u: LISTING_HTML_NEWER
        )
        self.assertEqual(row["outcome"], "fixed_newer_year")

    def test_listing_matching_the_archive_is_fixed(self) -> None:
        row = classify_outcome(flagged(), "https://x.edu/ir/cds", fetch=lambda u: LISTING_HTML)
        self.assertEqual(row["outcome"], "fixed_listing_matches")

    def test_listing_behind_the_archive_is_unverified(self) -> None:
        row = classify_outcome(
            flagged(latest="2025-26"), "https://x.edu/ir/cds", fetch=lambda u: LISTING_HTML
        )
        self.assertEqual(row["outcome"], "listing_unverified")

    def test_unfetchable_or_yearless_listing_is_unverified(self) -> None:
        for html in (None, "<a href='/x'>Common Data Set</a>"):
            row = classify_outcome(flagged(), "https://x.edu/ir/cds", fetch=lambda u, h=html: h)
            self.assertEqual(row["outcome"], "listing_unverified")

    def test_old_file_is_not_a_fix_even_when_the_archive_has_nothing(self) -> None:
        # archive_latest None, new seed CDS_2016-17.pdf: older than the current
        # year, so still one old file (#463).
        row = classify_outcome(
            flagged(latest=None), "https://x.edu/CDS_2016-17.pdf", fetch=no_fetch
        )
        self.assertEqual(row["outcome"], "still_one_file")

    def test_current_file_is_a_fix_when_the_archive_has_nothing(self) -> None:
        row = classify_outcome(
            flagged(latest=None), "https://x.edu/CDS_2025-26.pdf", fetch=no_fetch
        )
        self.assertEqual(row["outcome"], "fixed_newer_year")

    def test_newer_than_archive_but_older_than_the_floor_is_not_a_fix(self) -> None:
        row = classify_outcome(
            flagged(latest="2022-23"), "https://x.edu/CDS_2023-24.pdf", fetch=no_fetch
        )
        self.assertEqual(row["outcome"], "still_one_file")

    def test_listing_older_than_the_floor_is_not_a_fix_when_archive_empty(self) -> None:
        html = '<a href="/files/cds_2016-17.pdf">CDS 2016-17</a>'
        row = classify_outcome(flagged(latest=None), "https://x.edu/ir", fetch=lambda u: html)
        self.assertEqual(row["outcome"], "listing_unverified")


class FetchTests(unittest.TestCase):
    def test_incomplete_read_is_unverified_not_a_crash(self) -> None:
        def opener(req, timeout=0):
            raise http.client.IncompleteRead(b"partial")

        self.assertIsNone(fetch_page("https://x.edu/ir", opener=opener))

    def test_bad_status_and_invalid_url_are_unverified(self) -> None:
        def bad_status(req, timeout=0):
            raise http.client.BadStatusLine("x")

        self.assertIsNone(fetch_page("https://x.edu/ir", opener=bad_status))
        # Request() itself raises ValueError on a malformed URL.
        self.assertIsNone(fetch_page("not a url", opener=bad_status))
        self.assertIsNone(fetch_page("http://exa mple.com:bad/", opener=bad_status))


class CliTests(unittest.TestCase):
    def run_main(self, flagged_rows, with_summary):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "stuck.json").write_text(json.dumps({
                "counts": {"total": 3, "flagged": len(flagged_rows), "fresh": 1, "skipped": 1},
                "stuck": flagged_rows,
            }))
            (d / "schools.yaml").write_text("schools: []\n")
            argv = ["x", "--flagged", str(d / "stuck.json"),
                    "--schools-yaml", str(d / "schools.yaml"),
                    "--probe-summary", str(d / "summary.json"),
                    "--out-heartbeat", str(d / "hb.json")]
            if with_summary:
                (d / "summary.json").write_text(json.dumps({"probed": 1}))
            with mock.patch("sys.argv", argv):
                code = reprobe_outcome.main()
            return code, json.loads((d / "hb.json").read_text())

    def test_missing_probe_summary_with_flagged_schools_fails(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_main([flagged()], with_summary=False)

    def test_missing_probe_summary_is_fine_when_nothing_was_flagged(self) -> None:
        code, hb = self.run_main([], with_summary=False)
        self.assertEqual(code, 0)
        self.assertEqual((hb["stuck"], hb["reprobed"]), (0, 0))

    def test_with_summary_reports_reprobed(self) -> None:
        code, hb = self.run_main([flagged()], with_summary=True)
        self.assertEqual((code, hb["reprobed"], hb["stuck"]), (0, 1, 1))


class SummaryTests(unittest.TestCase):
    COUNTS = {"total": 190, "flagged": 4, "fresh": 100, "skipped": 86}

    def outcomes(self):
        rows = [flagged(sid=s) for s in "abcd"]
        seeds = {
            "a": "https://x.edu/CDS_2016-17.pdf",  # still_one_file
            "b": "https://x.edu/CDS_2025-26.pdf",  # fixed_newer_year
            "c": "https://x.edu/ir/cds",  # listing, unverified (fetch fails)
            "d": rows[3]["seed"],  # unchanged
        }
        return classify_all(rows, seeds, fetch=lambda u: None)

    def test_only_fixed_buckets_count_as_fixed(self) -> None:
        # Seven "replaced" schools out of 78 on 2026-11-02 were reported as the
        # fix rate; here three of four were replaced and one is fixed.
        s = summarize(self.outcomes(), self.COUNTS, reprobed=4)
        self.assertEqual(s["fixed"], 1)
        self.assertEqual(s["still_stuck"], 3)
        self.assertEqual(s["stuck"], 4)
        self.assertEqual(s["listing_unverified"], 1)
        self.assertEqual((s["total"], s["fresh"], s["skipped"]), (190, 100, 86))
        self.assertEqual(s["reprobed"], 4)

    def test_page_fetches_are_capped(self) -> None:
        rows = [flagged(sid=str(i)) for i in range(5)]
        seeds = {r["id"]: f"https://x.edu/{r['id']}/cds" for r in rows}
        seen = []

        def fetch(url):
            seen.append(url)
            return LISTING_HTML_NEWER

        out = classify_all(rows, seeds, fetch=fetch, max_pages=2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(
            [r["outcome"] for r in out],
            ["fixed_newer_year"] * 2 + ["listing_unverified"] * 3,
        )

    def test_count_mismatch_with_classifier_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            summarize(self.outcomes(), {**self.COUNTS, "flagged": 5}, reprobed=4)


if __name__ == "__main__":
    unittest.main()
