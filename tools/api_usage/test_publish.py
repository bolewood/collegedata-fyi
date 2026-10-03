import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.api_usage import publish

CLEAN = {
    "school_cells_off_rule": 0,
    "school_months_incomplete": 0,
    "school_months_without_summary": 0,
    "summary_count_mismatch": 0,
    "days_without_publish_record": 0,
    "unexpected_columns": 0,
    "private_tables_readable_by_anon": 0,
}


class FakeDb:
    def __init__(self, batches, violations=None):
        self.batches = list(batches)
        self.violations = violations or CLEAN
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        if name == "api_usage_publish_pending":
            return self.batches.pop(0)
        if name == "usage_public_violations":
            return self.violations
        raise AssertionError(name)


def batch(days, months=0, waiting=0, stuck=0, expired=0):
    return {"days_published": days, "months_published": months, "days_waiting": waiting,
            "days_stuck": stuck, "days_expired": expired}


class PublishTest(unittest.TestCase):
    def test_single_call_when_under_batch(self):
        db = FakeDb([batch(1, 0, 1)])
        report = publish.run(db, method_version=1)
        self.assertEqual(report["days_published"], 1)
        self.assertEqual(report["days_waiting"], 1)
        self.assertEqual(report["calls"], 1)
        self.assertEqual(db.calls[0], ("api_usage_publish_pending", {"p_method_version": 1, "p_limit": publish.BATCH_DAYS}))
        self.assertEqual(db.calls[-1][0], "usage_public_violations")

    def test_loops_until_a_short_batch(self):
        db = FakeDb([batch(publish.BATCH_DAYS, 1, stuck=9), batch(publish.BATCH_DAYS, 2), batch(publish.BATCH_DAYS - 1, 1, 1, stuck=2, expired=4)])
        report = publish.run(db, method_version=1)
        self.assertEqual(report["calls"], 3)
        self.assertEqual(report["days_published"], 3 * publish.BATCH_DAYS - 1)
        self.assertEqual(report["months_published"], 4)
        self.assertEqual((report["days_waiting"], report["days_stuck"], report["days_expired"]), (1, 2, 4))

    def test_runaway_loop_fails(self):
        db = FakeDb([batch(publish.BATCH_DAYS)] * publish.MAX_CALLS)
        with self.assertRaises(publish.PublishError):
            publish.run(db, method_version=1)

    def test_any_violation_is_reported(self):
        db = FakeDb([batch(0)], {**CLEAN, "school_cells_off_rule": 2})
        report = publish.run(db, method_version=1)
        self.assertEqual(publish.broken_rules(report), ["school_cells_off_rule"])

    def test_nothing_new_still_scans(self):
        db = FakeDb([batch(0)])
        report = publish.run(db, method_version=1)
        self.assertEqual(report["days_published"], 0)
        self.assertEqual([name for name, _ in db.calls], ["api_usage_publish_pending", "usage_public_violations"])
        self.assertTrue(all(value == 0 for value in report["violations"].values()))

    def test_main_writes_counts_only_report(self):
        db = FakeDb([batch(2, 1)])
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(publish, "Db", return_value=db), \
                contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp) / "publish.json"
            self.assertEqual(publish.main(["--out-json", str(out)]), 0)
            report = json.loads(out.read_text())
        self.assertEqual(set(report), {"method_version", "days_published", "months_published",
                                       "days_waiting", "days_stuck", "days_expired", "calls", "violations"})
        for value in report.values():
            self.assertIsInstance(value, (int, dict))

    def test_main_fails_on_violation_and_still_writes_report(self):
        db = FakeDb([batch(0)], {**CLEAN, "unexpected_columns": 1})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(publish, "Db", return_value=db), \
                contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp) / "publish.json"
            self.assertEqual(publish.main(["--out-json", str(out)]), 1)
            self.assertEqual(json.loads(out.read_text())["violations"]["unexpected_columns"], 1)
        self.assertIn("unexpected_columns", stderr.getvalue())

    def test_stuck_days_warn_without_failing(self):
        db = FakeDb([batch(0, stuck=2)])
        stderr = io.StringIO()
        with mock.patch.object(publish, "Db", return_value=db), \
                contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish.main([]), 0)
        self.assertIn("2 day(s) are stuck", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
