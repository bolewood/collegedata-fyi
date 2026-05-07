import unittest
from datetime import datetime, timezone

from tools.ops import automation_health as health


class AutomationHealthTests(unittest.TestCase):
    def test_http_content_category_classifies_archive_failures(self):
        self.assertEqual(
            health.http_content_category('{"error":"RPC returned row with null claimed_at"}', 500),
            "archive_process_null_claim",
        )
        self.assertEqual(
            health.http_content_category('{"code":"IDLE_TIMEOUT"}', 504),
            "edge_idle_timeout",
        )
        self.assertEqual(
            health.http_content_category('{"status":"queue_drained"}', 200),
            "archive_process_queue_drained",
        )
        self.assertEqual(
            health.http_content_category('{"rows_written":6322,"coverage_status_histogram":{}}', 200),
            "refresh_coverage",
        )

    def test_evaluate_flags_poison_archive_rows_and_edge_errors(self):
        now = datetime(2026, 5, 7, 19, 0, tzinfo=timezone.utc)
        report = {
            "database": {
                "cron_jobs": [
                    {"jobname": "archive-process-every-30s", "active": True},
                    {"jobname": "refresh-coverage-every-15min", "active": True},
                ],
                "cron_recent_failures": [],
                "http_response_categories": {
                    "refresh_coverage": 4,
                    "archive_process_null_claim": 10,
                },
                "archive_queue_open": [
                    {
                        "school_id": "los-angeles-pacific-university",
                        "status": "processing",
                        "attempts": 2701,
                    }
                ],
                "coverage_refresh": [
                    {"newest_updated": "2026-05-07T18:45:00Z"},
                ],
            },
            "github_actions": {
                "available": True,
                "recent_runs": [],
            },
        }

        issues = health.evaluate(report, now)

        self.assertTrue(any("edge HTTP errors" in issue for issue in issues))
        self.assertTrue(any("poison rows" in issue for issue in issues))

    def test_evaluate_accepts_clean_report(self):
        now = datetime(2026, 5, 7, 19, 0, tzinfo=timezone.utc)
        report = {
            "database": {
                "cron_jobs": [
                    {"jobname": "archive-process-every-30s", "active": True},
                    {"jobname": "refresh-coverage-every-15min", "active": True},
                ],
                "cron_recent_failures": [],
                "http_response_categories": {
                    "refresh_coverage": 4,
                    "archive_process_queue_drained": 100,
                },
                "archive_queue_open": [],
                "coverage_refresh": [
                    {"newest_updated": "2026-05-07T18:45:00Z"},
                ],
            },
            "github_actions": {
                "available": True,
                "recent_runs": [],
            },
        }

        self.assertEqual(health.evaluate(report, now), [])


if __name__ == "__main__":
    unittest.main()
