import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools.ops import directory_enqueue_batches as batches


class FakeClient:
    def __init__(self) -> None:
        self.function_calls = []
        self.rest_calls = []
        self.queue_pages = []
        self.queue_errors = []
        self.coverage_rows = [
            {"coverage_status": "not_checked"},
            {"coverage_status": "not_checked"},
            {"coverage_status": "cds_available_current"},
        ]

    def post_function(self, name, params):
        self.function_calls.append((name, params))
        if name == "directory-enqueue" and params.get("dry_run") == "true":
            return {
                "mode": "dry_run",
                "run_id": "dry-run-id",
                "considered": 100,
                "would_enqueue": 1,
                "sample_school_ids": ["school-1"],
                "skipped": {"schools_yaml_covered": 3},
            }
        if name == "directory-enqueue":
            return {
                "mode": "enqueue",
                "run_id": params.get("run_id", "real-run-id"),
                "considered": 100,
                "enqueued": 1,
                "skipped_existing": 0,
                "skipped": {"schools_yaml_covered": 3},
            }
        if name == "refresh-coverage":
            return {
                "rows_written": 3,
                "refresh_duration_ms": 10,
                "total_duration_ms": 20,
                "coverage_status_histogram": {
                    "not_checked": 1,
                    "cds_available_current": 1,
                    "no_public_cds_found": 1,
                },
            }
        raise AssertionError(f"unexpected function call: {name}")

    def rest_get(self, table, params, *, page=None):
        self.rest_calls.append((table, params, page))
        if table == "institution_cds_coverage" and params.get("coverage_status") == "eq.not_checked":
            return [
                {
                    "school_id": "school-1",
                    "school_name": "Example State",
                    "state": "CA",
                    "undergraduate_enrollment": 50000,
                }
            ]
        if table == "institution_cds_coverage":
            return self.coverage_rows
        if table == "institution_directory":
            return [
                {
                    "school_id": "school-1",
                    "school_name": "Example State",
                    "state": "CA",
                    "undergraduate_enrollment": 50000,
                }
            ]
        if table == "archive_queue" and "enqueued_run_id" in params:
            if self.queue_errors:
                raise self.queue_errors.pop(0)
            if self.queue_pages:
                return self.queue_pages.pop(0)
            return [
                {
                    "school_id": "school-1",
                    "school_name": "Example State",
                    "status": "done",
                    "last_outcome": "cds_available_current",
                }
            ]
        if table == "archive_queue":
            return []
        raise AssertionError(f"unexpected rest call: {table}, {params}")


class DirectoryEnqueueBatchTests(unittest.TestCase):
    def test_dry_run_only_never_enqueues_or_refreshes(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            logger = batches.JsonlLogger(Path(tmp))
            with redirect_stdout(StringIO()):
                report = batches.run_batch(
                    client,
                    limit=25,
                    apply=False,
                    options=batches.DirectoryEnqueueOptions(),
                    logger=logger,
                    timeout_seconds=60,
                    poll_interval_seconds=1,
                    stall_timeout_seconds=30,
                    unexpected_outcome_rate=0.10,
                )

        self.assertFalse(report["applied"])
        self.assertEqual(
            client.function_calls,
            [("directory-enqueue", {"limit": "25", "dry_run": "true"})],
        )

    def test_real_enqueue_records_run_id_and_refreshes_after_drain(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            logger = batches.JsonlLogger(Path(tmp))
            with redirect_stdout(StringIO()):
                report = batches.run_batch(
                    client,
                    limit=25,
                    apply=True,
                    options=batches.DirectoryEnqueueOptions(),
                    logger=logger,
                    timeout_seconds=60,
                    poll_interval_seconds=1,
                    stall_timeout_seconds=30,
                    unexpected_outcome_rate=0.10,
                )
            log_lines = logger.path.read_text(encoding="utf-8").splitlines()

        self.assertTrue(report["applied"])
        self.assertEqual(report["enqueue"]["run_id"], "dry-run-id")
        self.assertIn(("refresh-coverage", {}), client.function_calls)
        self.assertTrue(any('"event": "enqueue"' in line and '"run_id": "dry-run-id"' in line for line in log_lines))

    def test_polling_exits_when_all_rows_are_terminal(self):
        client = FakeClient()
        client.queue_pages = [
            [
                {"school_id": "school-1", "status": "processing", "last_outcome": None},
                {"school_id": "school-2", "status": "done", "last_outcome": "no_pdfs_found"},
            ],
            [
                {"school_id": "school-1", "status": "done", "last_outcome": "cds_available_current"},
                {"school_id": "school-2", "status": "done", "last_outcome": "no_pdfs_found"},
            ],
        ]
        clock = FakeClock()

        with redirect_stdout(StringIO()):
            drained = batches.poll_until_drained(
                client,
                "run-id",
                timeout_seconds=60,
                poll_interval_seconds=5,
                stall_timeout_seconds=30,
                now=clock.now,
                sleep=clock.sleep,
            )

        self.assertEqual(drained["summary"]["active"], 0)
        self.assertEqual(drained["summary"]["terminal"], 2)
        self.assertEqual(clock.sleeps, [5])

    def test_polling_timeout_raises(self):
        client = FakeClient()
        client.queue_pages = [[{"school_id": "school-1", "status": "ready"}]] * 10
        clock = FakeClock()

        with self.assertRaises(TimeoutError):
            with redirect_stdout(StringIO()):
                batches.poll_until_drained(
                    client,
                    "run-id",
                    timeout_seconds=10,
                    poll_interval_seconds=5,
                    stall_timeout_seconds=60,
                    now=clock.now,
                    sleep=clock.sleep,
                )

    def test_polling_retries_transient_read_error(self):
        client = FakeClient()
        client.queue_errors = [batches.OpsError("temporary timeout")]
        client.queue_pages = [[{"school_id": "school-1", "status": "done", "last_outcome": "no_pdfs_found"}]]
        clock = FakeClock()

        with redirect_stdout(StringIO()):
            drained = batches.poll_until_drained(
                client,
                "run-id",
                timeout_seconds=60,
                poll_interval_seconds=5,
                stall_timeout_seconds=30,
                now=clock.now,
                sleep=clock.sleep,
            )

        self.assertEqual(drained["summary"]["active"], 0)
        self.assertEqual(clock.sleeps, [5])

    def test_histogram_delta(self):
        self.assertEqual(
            batches.histogram_delta(
                {"not_checked": 10, "cds_available_current": 2},
                {"not_checked": 7, "cds_available_current": 4, "extract_failed": 1},
            ),
            {"cds_available_current": 2, "extract_failed": 1, "not_checked": -3},
        )


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


if __name__ == "__main__":
    unittest.main()
