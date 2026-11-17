"""Unit tests for revalidate_pages (database reads and HTTP mocked)."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import revalidate_pages as rp  # noqa: E402

ENV = {
    "COLLEGEDATA_REVALIDATE_URL": "https://example.test/api/revalidate",
    "REVALIDATE_SECRET": "s3cret",
    "SUPABASE_URL": "https://db.example.test",
    "SUPABASE_SERVICE_ROLE_KEY": "service",
}
NOW = datetime(2026, 11, 17, 13, 35, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status=200, body=b"[]"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    """Stands in for urlopen on the revalidate endpoint."""

    def __init__(self, status=200):
        self.bodies = []
        self.status = status

    def __call__(self, request, timeout=None):
        self.bodies.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(self.status)


class FakeDb:
    """fetch(table, params) over canned rows; records every call."""

    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def __call__(self, table, params):
        self.calls.append((table, dict(params)))
        key = table
        if table == "cds_documents" and "id" in params:
            key = "cds_documents:by_id"
        if table == "scholarship_programs" and "program_id" in params:
            key = "scholarship_programs:by_id"
        return list(self.tables.get(key, []))


def run(argv, *, db=None, opener=None, env=ENV):
    lines = []
    code = rp.run(rp.parse_args(argv), env, fetch=db, opener=opener or Recorder(), now=NOW, out=lines.append)
    return code, lines


class SweepTests(unittest.TestCase):
    def test_collects_every_source_and_sends_one_deduplicated_batch(self):
        db = FakeDb(
            {
                "cds_documents": [{"school_id": "yale"}, {"school_id": "yale"}, {"school_id": None}],
                "school_browser_rows": [{"school_id": "mit"}],
                "cds_field_change_events": [{"school_id": "brown"}],
                "cds_artifacts": [{"document_id": "d1"}, {"document_id": "d1"}],
                "cds_documents:by_id": [{"school_id": "duke"}],
                "scholarship_programs": [{"program_id": "p-load"}],
                "scholarship_version_checks": [{"program_id": "p-check"}],
                "scholarship_programs:by_id": [
                    {
                        "school_id": "unc",
                        "participating_schools": [
                            {"school_id": "duke", "ipeds_id": "198419"},
                            {"school_id": "ncsu", "ipeds_id": "199193"},
                        ],
                    }
                ],
            }
        )
        opener = Recorder()
        code, lines = run(["--changed-since-hours", "26"], db=db, opener=opener)
        self.assertEqual(code, 0)
        self.assertEqual(len(opener.bodies), 1)
        self.assertEqual(opener.bodies[0]["school_ids"], ["brown", "duke", "mit", "ncsu", "unc", "yale"])
        self.assertIs(opener.bodies[0]["scholarships"], True)
        self.assertIn("6 school(s) changed in 26 h", lines[0])

    def test_window_and_scholarship_check_filter_reach_the_database(self):
        db = FakeDb({})
        run(["--changed-since-hours", "26", "--dry-run"], db=db)
        by_table = {t: p for t, p in db.calls}
        self.assertEqual(by_table["cds_documents"]["updated_at"], "gt.2026-11-16T11:35:00Z")
        self.assertEqual(
            by_table["cds_documents"]["or"],
            "(last_verified_at.is.null,last_verified_at.lt.2026-11-16T11:35:00Z)",
        )
        self.assertEqual(by_table["cds_artifacts"]["created_at"], "gt.2026-11-16T11:35:00Z")
        for table, params in db.calls:
            self.assertIn("order", params, table)
        self.assertEqual(
            by_table["scholarship_version_checks"]["or"],
            "(needs_review.is.true,result.in.(changed,conflicting))",
        )
        self.assertNotIn("institution_cds_coverage", by_table)

    def test_no_changes_sends_nothing_and_succeeds(self):
        opener = Recorder()
        code, lines = run(["--changed-since-hours", "26"], db=FakeDb({}), opener=opener)
        self.assertEqual((code, opener.bodies), (0, []))
        self.assertIn("nothing to refresh", lines[-1])

    def test_scholarship_flag_is_off_without_scholarship_changes(self):
        opener = Recorder()
        run(["--changed-since-hours", "26"], db=FakeDb({"cds_documents": [{"school_id": "yale"}]}), opener=opener)
        self.assertNotIn("scholarships", opener.bodies[0])

    def test_sends_every_batch_past_the_worker_cap(self):
        rows = [{"school_id": f"school-{i:04d}"} for i in range(2350)]
        opener = Recorder()
        original, rp.BATCH_PAUSE_SECONDS = rp.BATCH_PAUSE_SECONDS, 0
        try:
            code, lines = run(["--changed-since-hours", "26"], db=FakeDb({"cds_documents": rows}), opener=opener)
        finally:
            rp.BATCH_PAUSE_SECONDS = original
        self.assertEqual(code, 0)
        self.assertEqual(len(opener.bodies), 24)
        self.assertEqual(sum(len(b["school_ids"]) for b in opener.bodies), 2350)
        self.assertIn("refreshed 2350/2350", lines[-1])

    def test_dry_run_sends_nothing_and_never_prints_school_ids(self):
        opener = Recorder()
        code, lines = run(
            ["--changed-since-hours", "26", "--dry-run"],
            db=FakeDb({"cds_documents": [{"school_id": "yale"}]}),
            opener=opener,
        )
        self.assertEqual((code, opener.bodies), (0, []))
        self.assertNotIn("yale", "\n".join(lines))

    def test_failed_refresh_request_exits_nonzero(self):
        with redirect_stderr(io.StringIO()):
            code, _ = run(
                ["--changed-since-hours", "26"],
                db=FakeDb({"cds_documents": [{"school_id": "yale"}]}),
                opener=Recorder(status=500),
            )
        self.assertEqual(code, 1)

    def test_one_rejected_batch_does_not_stop_the_rest(self):
        import urllib.error

        class FirstBatchRejected(Recorder):
            def __call__(self, request, timeout=None):
                response = super().__call__(request, timeout)
                if len(self.bodies) == 1:
                    raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)
                return response

        opener = FirstBatchRejected()
        rows = [{"school_id": f"school-{i:04d}"} for i in range(250)]
        original, rp.BATCH_PAUSE_SECONDS = rp.BATCH_PAUSE_SECONDS, 0
        try:
            with redirect_stderr(io.StringIO()):
                code, lines = run(["--changed-since-hours", "26"], db=FakeDb({"cds_documents": rows}), opener=opener)
        finally:
            rp.BATCH_PAUSE_SECONDS = original
        self.assertEqual(len(opener.bodies), 3)
        self.assertEqual(code, 1)
        self.assertIn("refreshed 150/250", lines[-1])

    def test_missing_revalidate_settings_exit_nonzero(self):
        with redirect_stderr(io.StringIO()) as err:
            code, _ = run(["--school-id", "yale"], env={})
        self.assertEqual(code, 1)
        self.assertIn("REVALIDATE_SECRET", err.getvalue())

    def test_failed_read_exits_nonzero(self):
        def broken(table, params):
            raise rp.SweepError(f"read of {table} failed: HTTP 503")

        with redirect_stderr(io.StringIO()):
            code, _ = run(["--changed-since-hours", "26"], db=broken)
        self.assertEqual(code, 1)


class OtherModesTests(unittest.TestCase):
    def test_named_schools(self):
        opener = Recorder()
        code, _ = run(["--school-id", "yale", "--school-id", "mit", "--school-id", "yale"], opener=opener)
        self.assertEqual(code, 0)
        self.assertEqual(opener.bodies, [{"school_ids": ["mit", "yale"]}])

    def test_all(self):
        opener = Recorder()
        code, _ = run(["--all"], opener=opener)
        self.assertEqual((code, opener.bodies), (0, [{"all": True}]))

    def test_all_dry_run_sends_nothing(self):
        opener = Recorder()
        code, _ = run(["--all", "--dry-run"], opener=opener)
        self.assertEqual((code, opener.bodies), (0, []))

    def test_modes_are_exclusive_and_window_is_bounded(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                rp.parse_args(["--all", "--school-id", "yale"])
            with self.assertRaises(SystemExit):
                rp.parse_args(["--changed-since-hours", "0"])
            with self.assertRaises(SystemExit):
                rp.parse_args([])


class RestFetcherTests(unittest.TestCase):
    def test_pages_until_a_short_page_and_sends_the_service_key(self):
        seen = []

        def opener(request, timeout=None):
            seen.append(request)
            offset = int(dict(p.split("=") for p in request.full_url.split("?")[1].split("&"))["offset"])
            size = rp.PAGE_SIZE if offset == 0 else 3
            return FakeResponse(body=json.dumps([{"school_id": f"s{offset + i}"} for i in range(size)]).encode())

        rows = rp.rest_fetcher(ENV, opener)("cds_documents", {"select": "school_id"})
        self.assertEqual(len(rows), rp.PAGE_SIZE + 3)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0].get_header("Apikey"), "service")
        self.assertTrue(seen[0].full_url.startswith("https://db.example.test/rest/v1/cds_documents?"))

    def test_requires_database_settings(self):
        with self.assertRaises(rp.SweepError):
            rp.rest_fetcher({})


if __name__ == "__main__":
    unittest.main()
