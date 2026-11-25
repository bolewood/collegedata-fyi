"""Unit tests for tools/ops/fetch_failures.py."""

from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tools.ops import fetch_failures as ff
from tools.ops.discovery_renewal import RenewalError

LISTING = "https://example.edu/ir/common-data-set"
AS_OF = date(2026, 11, 24)  # current CDS year 2025-26


def attempt(status="failed_permanent", outcome=None, error=None, enq="2026-11-20T00:00:00+00:00"):
    return {
        "school_id": "x",
        "status": status,
        "last_outcome": outcome,
        "last_error": error,
        "enqueued_at": enq,
        "processed_at": enq,
    }


def cause(seed=LISTING, in_waf=False, **kw):
    return ff.classify(in_waf=in_waf, seed_url=seed, attempt=attempt(**kw) if kw else None)[0]


class ClassifyTests(unittest.TestCase):
    def test_waf_listed_is_blocked_even_when_error_is_something_else(self):
        self.assertEqual(
            cause(in_waf=True, outcome="no_pdfs_found", error="resolve no cds found: x"), ff.BLOCKED
        )

    def test_http_403_and_bot_challenge_are_blocked(self):
        self.assertEqual(
            cause(outcome="transient", error="exhausted 3 attempts (last: TransientError: resolve transient: landing HTTP 403)"),
            ff.BLOCKED,
        )
        self.assertEqual(cause(outcome="bot_challenge", error="challenge"), ff.BLOCKED)
        self.assertEqual(cause(outcome="transient", error="download HTTP 429 at https://a.edu/x.pdf"), ff.BLOCKED)

    def test_403_digits_inside_a_url_are_not_a_block(self):
        self.assertEqual(
            cause(outcome="no_pdfs_found", error="no cds found at https://a.edu/file4030.pdf"), ff.OTHER
        )

    def test_blocked_beats_viewer_and_dead(self):
        err = "landing HTTP 403; also https://x.sharepoint.com/a and HTTP 404"
        self.assertEqual(cause(outcome="transient", error=err), ff.BLOCKED)

    def test_viewer_by_outcome_seed_or_error(self):
        self.assertEqual(cause(outcome="auth_walled_microsoft", error="x"), ff.VIEWER)
        self.assertEqual(cause(seed="https://school.app.box.com/s/abc", outcome="no_pdfs_found", error="x"), ff.VIEWER)
        self.assertEqual(
            cause(outcome="wrong_content_type", error="failed: https://www.dropbox.com/scl/fi/abc/cds.pdf: unknown content type"),
            ff.VIEWER,
        )

    def test_section_file_named_in_error(self):
        err = "all 1 candidate(s) failed permanently: https://a.edu/files/CDS_2025-26_Section_C.pdf: HTTP 500"
        self.assertEqual(cause(outcome="permanent_other", error=err), ff.SECTION_FILES)

    def test_section_beats_dead_link(self):
        err = "failed: https://a.edu/files/Section-B.pdf HTTP 404"
        self.assertEqual(cause(outcome="dead_url", error=err), ff.SECTION_FILES)

    def test_dead_link_by_outcome_status_or_dns(self):
        self.assertEqual(cause(outcome="dead_url", error="all 2 candidate(s) failed"), ff.DEAD_LINK)
        self.assertEqual(cause(outcome="transient", error="download HTTP 404 at https://a.edu/x.pdf"), ff.DEAD_LINK)
        self.assertEqual(
            cause(outcome="transient", error="error sending request for url (https://a.edu/) client error (Connect): dns error"),
            ff.DEAD_LINK,
        )

    def test_unclassified_error_is_other(self):
        self.assertEqual(cause(outcome="no_pdfs_found", error="resolve no cds found: two-hop walk"), ff.OTHER)

    def test_clean_attempt_is_no_failure_recorded(self):
        self.assertEqual(cause(status="done", outcome="unchanged_verified"), ff.NO_FAILURE)

    def test_no_attempt_is_no_failure_recorded_and_says_so(self):
        c, evidence = ff.classify(in_waf=False, seed_url=LISTING, attempt=None)
        self.assertEqual(c, ff.NO_FAILURE)
        self.assertIn("no archive attempt", evidence)

    def test_other_reason_labels(self):
        self.assertIn("section files", ff.other_reason("no_pdfs_found", "two-hop walk found multiple CDS-ish docs but none carry a year signal"))
        self.assertIn("no document links", ff.other_reason("no_pdfs_found", "landing parsed, no CDS-ish document anchors"))
        self.assertIn("timeout", ff.other_reason("transient", "exhausted 3 attempts"))


def school(sid, seed=LISTING, policy="active", name=None):
    row = {"id": sid, "name": name or sid.title(), "scrape_policy": policy}
    if seed:
        row["discovery_seed_url"] = seed
    return row


def doc(sid, year, removed=None, status="published"):
    return {
        "school_id": sid,
        "canonical_year": year,
        "removed_at": removed,
        "participation_status": status,
    }


class PopulationTests(unittest.TestCase):
    def build(self, schools, waf=None, manifest=(), queue=()):
        return ff.build_cases(
            schools={s["id"]: s for s in schools},
            waf=waf or {},
            manifest_rows=list(manifest),
            queue_rows=list(queue),
            as_of=AS_OF,
        )[0]

    def test_only_listing_page_seeds_or_waf_schools_without_a_current_document(self):
        cases = self.build(
            [
                school("listing"),
                school("onefile", seed="https://a.edu/cds.pdf"),
                school("noseed", seed=None),
                school("waf-one-file", seed="https://b.edu/cds.pdf"),
                school("has-current"),
                school("verified-absent", policy="verified_absent"),
            ],
            waf={"waf-one-file": "W", "not-canonical-alias": "A"},
            manifest=[doc("has-current", "2025-26")],
        )
        self.assertEqual([c.school_id for c in cases], ["listing", "waf-one-file"])

    def test_unknown_removed_and_unpublished_documents_do_not_count_as_current(self):
        cases = self.build(
            [school("a"), school("b"), school("c")],
            manifest=[
                doc("a", "unknown"),
                doc("b", "2025-26", removed="2026-01-01T00:00:00Z"),
                doc("c", "2025-26", status="not_published"),
            ],
        )
        self.assertEqual({c.school_id for c in cases}, {"a", "b", "c"})

    def test_newest_year_uses_integer_years(self):
        cases = self.build([school("a")], manifest=[doc("a", "2023-24"), doc("a", "2024-25"), doc("a", "unknown")])
        self.assertEqual(cases[0].newest_year, "2024-25")

    def test_newest_attempt_per_school_wins(self):
        old = {**attempt(error="landing HTTP 403", outcome="transient"), "school_id": "a", "enqueued_at": "2026-10-20T00:00:00+00:00"}
        new = {**attempt(status="done", outcome="unchanged_verified"), "school_id": "a", "enqueued_at": "2026-11-20T00:00:00+00:00"}
        for queue in ([old, new], [new, old]):
            cases = self.build([school("a")], queue=queue)
            self.assertEqual(cases[0].cause, ff.NO_FAILURE)

    def test_ready_row_with_leftover_error_counts(self):
        row = {**attempt(status="ready", error="attempt 2 TransientError: resolve transient: landing HTTP 403"), "school_id": "a"}
        self.assertEqual(self.build([school("a")], queue=[row])[0].cause, ff.BLOCKED)


class SummaryTests(unittest.TestCase):
    def cases(self, causes):
        out = []
        for i, c in enumerate(causes):
            case = ff.Case(f"s{i}", f"S{i}", LISTING, "listing_page", None, False, None)
            case.cause = c
            out.append(case)
        return out

    def test_total_is_the_five_failure_causes_and_excludes_no_failure(self):
        s = ff.summary_dict(
            self.cases([ff.BLOCKED, ff.BLOCKED, ff.VIEWER, ff.SECTION_FILES, ff.DEAD_LINK, ff.OTHER, ff.NO_FAILURE, ff.NO_FAILURE])
        )
        self.assertEqual(
            s,
            {
                "fetch_failures": 6,
                "fetch_failures_blocked": 2,
                "fetch_failures_viewer": 1,
                "fetch_failures_section_files": 1,
                "fetch_failures_dead_link": 1,
                "fetch_failures_other": 1,
            },
        )

    def test_report_groups_every_cause_and_keeps_the_raw_error(self):
        cases = self.cases([ff.OTHER, ff.NO_FAILURE])
        cases[0].raw_error = "PermanentError: odd | thing"
        text = ff.render_report(cases, current_year=2025, as_of=AS_OF)
        for cause_name in ff.CAUSE_ORDER:
            self.assertIn(ff.CAUSE_HEADINGS[cause_name], text)
        self.assertIn("odd \\| thing", text)


class FetchQueueTests(unittest.TestCase):
    SINCE = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def getter(self, pages, totals):
        calls = iter(zip(pages, totals))
        self.offsets = []

        def get(url, headers, *a, **k):
            page, total = next(calls)
            self.assertIn("archive_queue?select=", url)
            self.assertIn("enqueued_at=gte.2026-10-10T00%3A00%3A00Z", url)
            self.offsets.append(int(re.search(r"offset=(\d+)", url).group(1)))
            return page, {"content-range": f"0-0/{total}"}

        return get

    def test_reads_all_pages(self):
        with patch.object(ff, "PAGE_SIZE", 2):
            rows = ff.fetch_queue_rows(
                "https://x.supabase.co", "k", since=self.SINCE,
                get=self.getter([[{"school_id": "a"}, {"school_id": "b"}], [{"school_id": "c"}]], [3, 3]),
            )
        self.assertEqual(len(rows), 3)
        self.assertEqual(self.offsets, [0, 2])

    def test_pages_are_read_at_the_offset_requested(self):
        data = [{"school_id": f"s{i}"} for i in range(5)]

        def get(url, headers, *a, **k):
            offset = int(re.search(r"offset=(\d+)", url).group(1))
            limit = int(re.search(r"limit=(\d+)", url).group(1))
            return data[offset:offset + limit], {"content-range": f"0-0/{len(data)}"}

        with patch.object(ff, "PAGE_SIZE", 2):
            rows = ff.fetch_queue_rows("https://x.supabase.co", "k", since=self.SINCE, get=get)
        self.assertEqual([r["school_id"] for r in rows], ["s0", "s1", "s2", "s3", "s4"])

    def test_empty_queue_is_an_error(self):
        with self.assertRaises(RenewalError):
            ff.fetch_queue_rows("https://x.supabase.co", "k", since=self.SINCE, get=self.getter([[]], [0]))

    def test_short_read_is_an_error(self):
        with self.assertRaises(RenewalError):
            ff.fetch_queue_rows(
                "https://x.supabase.co", "k", since=self.SINCE,
                get=self.getter([[{"school_id": "a"}], []], [3, 3]),
            )

    def test_count_changing_while_paging_is_an_error(self):
        with patch.object(ff, "PAGE_SIZE", 1), self.assertRaises(RenewalError):
            ff.fetch_queue_rows(
                "https://x.supabase.co", "k", since=self.SINCE,
                get=self.getter([[{"school_id": "a"}], [{"school_id": "b"}]], [2, 3]),
            )

    def test_missing_content_range_is_an_error(self):
        def get(url, headers, *a, **k):
            return [{"school_id": "a"}], {}

        with self.assertRaises(RenewalError):
            ff.fetch_queue_rows("https://x.supabase.co", "k", since=self.SINCE, get=get)


class CliTests(unittest.TestCase):
    def test_missing_service_key_writes_no_keys_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.json"
            summary.write_text('{"fetch_failures": 0}')
            report = Path(tmp) / "report.md"
            err = io.StringIO()
            with patch.dict("os.environ", {}, clear=True), redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = ff.main(["--out-summary", str(summary), "--out-report", str(report)])
            self.assertEqual(code, 0)
            self.assertFalse(summary.exists(), "a stale or zero summary must not survive a skipped run")
            self.assertIn("SKIPPED", err.getvalue())
            self.assertIn("No counts are reported", report.read_text())

    def test_merge_summary_adds_keys_and_keeps_the_renewal_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "schools.yaml").write_text(
                f"schools:\n  - {{id: a, name: A, scrape_policy: active, discovery_seed_url: '{LISTING}'}}\n"
            )
            (t / "waf.yaml").write_text("schools:\n  a:\n    school_name: A\n")
            (t / "m.json").write_text("[]")
            (t / "q.json").write_text(json.dumps([{**attempt(), "school_id": "a"}]))
            renewal = t / "renewal.json"
            renewal.write_text(json.dumps({"renewal_pct": 41.2}))
            argv = [
                "--schools-yaml", str(t / "schools.yaml"), "--waf-yaml", str(t / "waf.yaml"),
                "--manifest-json", str(t / "m.json"), "--queue-json", str(t / "q.json"),
                "--as-of", "2026-11-24", "--merge-summary", str(renewal),
            ]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ff.main(argv), 0)
            merged = json.loads(renewal.read_text())
            self.assertEqual(merged["renewal_pct"], 41.2)
            self.assertEqual(merged["fetch_failures_blocked"], 1)

    def test_skipped_run_leaves_the_renewal_summary_without_fetch_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            renewal = Path(tmp) / "renewal.json"
            renewal.write_text(json.dumps({"renewal_pct": 41.2}))
            with patch.dict("os.environ", {}, clear=True), redirect_stderr(io.StringIO()):
                self.assertEqual(ff.main(["--merge-summary", str(renewal)]), 0)
            self.assertEqual(json.loads(renewal.read_text()), {"renewal_pct": 41.2})

    def test_local_run_writes_summary_report_and_worklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            schools = tmp_path / "schools.yaml"
            schools.write_text(
                "schools:\n"
                f"  - {{id: a, name: A U, scrape_policy: active, discovery_seed_url: '{LISTING}'}}\n"
                f"  - {{id: b, name: B U, scrape_policy: active, discovery_seed_url: '{LISTING}'}}\n"
            )
            waf = tmp_path / "waf.yaml"
            waf.write_text("schools:\n  b:\n    school_name: B U\n")
            manifest = tmp_path / "manifest.json"
            manifest.write_text(json.dumps([doc("a", "2024-25")]))
            queue = tmp_path / "queue.json"
            queue.write_text(
                json.dumps([{**attempt(outcome="dead_url", error="all 1 candidate(s) failed"), "school_id": "a"}])
            )
            out = tmp_path / "out"
            with redirect_stdout(io.StringIO()):
                code = ff.main(
                    [
                        "--schools-yaml", str(schools), "--waf-yaml", str(waf),
                        "--manifest-json", str(manifest), "--queue-json", str(queue),
                        "--as-of", "2026-11-24",
                        "--out-summary", str(out / "s.json"), "--out-report", str(out / "r.md"),
                        "--out-worklist", str(out / "w.json"),
                    ]
                )
            self.assertEqual(code, 0)
            summary = json.loads((out / "s.json").read_text())
            self.assertEqual(summary["fetch_failures"], 2)
            self.assertEqual(summary["fetch_failures_dead_link"], 1)
            self.assertEqual(summary["fetch_failures_blocked"], 1)
            self.assertEqual({w["school_id"] for w in json.loads((out / "w.json").read_text())}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
