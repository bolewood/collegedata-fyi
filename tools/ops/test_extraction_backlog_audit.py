import unittest
from datetime import datetime, timezone

from tools.ops import extraction_backlog_audit as audit


class FakeClient:
    def __init__(self) -> None:
        self.rest_calls = []

    def rest_get(self, table, params, *, page=None):
        self.rest_calls.append((table, params, page))
        if table == "cds_documents":
            return [
                {
                    "id": "doc-1",
                    "school_id": "large-state",
                    "cds_year": "2024-25",
                    "detected_year": None,
                    "source_format": "pdf_flat",
                    "source_provenance": "school_direct",
                    "extraction_status": "extraction_pending",
                    "created_at": "2026-04-30T00:00:00.1+00:00",
                    "updated_at": "2026-04-30T00:00:00.1+00:00",
                    "source_url": "https://example.edu/cds.pdf",
                    "ipeds_id": "1",
                },
                {
                    "id": "doc-2",
                    "school_id": "small-college",
                    "cds_year": "2024-25",
                    "detected_year": None,
                    "source_format": None,
                    "source_provenance": "operator_manual",
                    "extraction_status": "extraction_pending",
                    "created_at": "2026-04-30T12:00:00+00:00",
                    "updated_at": "2026-04-30T12:00:00+00:00",
                    "source_url": "https://small.edu/cds.pdf",
                    "ipeds_id": "2",
                },
            ]
        if table == "institution_directory":
            return [
                {
                    "school_id": "large-state",
                    "school_name": "Large State University",
                    "state": "CA",
                    "undergraduate_enrollment": 42000,
                    "website_url": "https://example.edu",
                },
                {
                    "school_id": "small-college",
                    "school_name": "Small College",
                    "state": "VT",
                    "undergraduate_enrollment": 1800,
                    "website_url": "https://small.edu",
                },
            ]
        raise AssertionError(f"unexpected table {table}")


class ExtractionBacklogAuditTests(unittest.TestCase):
    def test_parse_supabase_timestamp_accepts_short_fractional_seconds(self):
        parsed = audit.parse_supabase_timestamp("2026-04-15T21:39:49.73+00:00")

        self.assertEqual(parsed, datetime(2026, 4, 15, 21, 39, 49, 730000, tzinfo=timezone.utc))

    def test_summary_counts_formats_and_high_enrollment_pending(self):
        client = FakeClient()
        now = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
        rows = audit.fetch_pending_documents(client)
        metadata = audit.fetch_directory_metadata(client, ["large-state", "small-college"])
        summary = audit.summarize_pending_backlog(rows, metadata, now=now)

        self.assertEqual(summary["pending_count"], 2)
        self.assertEqual(summary["by_source_format"], {"pdf_flat": 1, "unknown": 1})
        self.assertEqual(summary["high_enrollment_pending"][0]["school_id"], "large-state")
        self.assertAlmostEqual(summary["oldest_pending_age_hours"], 24.0, places=1)

    def test_gate_flags_old_pending_count_and_growth(self):
        failures = audit.evaluate_gates(
            {
                "pending_count": 11,
                "oldest_pending_age_hours": 25.5,
                "github_actions": {"available": True, "last_success_age_hours": 31.0},
            },
            audit.AuditThresholds(
                max_pending_age_hours=24.0,
                max_pending_count=10,
                max_github_success_age_hours=30.0,
                fail_on_pending_growth=True,
            ),
            previous_pending_count=9,
        )

        self.assertTrue(any("pending_count 11 exceeds" in failure for failure in failures))
        self.assertTrue(any("oldest pending row" in failure for failure in failures))
        self.assertTrue(any("pending_count grew" in failure for failure in failures))
        self.assertTrue(any("GitHub workflow last success" in failure for failure in failures))

    def test_github_summary_uses_last_success(self):
        summary = audit.summarize_github_runs(
            {
                "available": True,
                "runs": [
                    {
                        "databaseId": 2,
                        "status": "completed",
                        "conclusion": "failure",
                        "createdAt": "2026-05-01T09:00:00Z",
                        "updatedAt": "2026-05-01T09:01:00Z",
                    },
                    {
                        "databaseId": 1,
                        "status": "completed",
                        "conclusion": "success",
                        "createdAt": "2026-05-01T08:00:00Z",
                        "updatedAt": "2026-05-01T08:30:00Z",
                    },
                ],
            },
            now=datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(summary["latest_run"]["databaseId"], 2)
        self.assertEqual(summary["last_success"]["databaseId"], 1)
        self.assertEqual(summary["last_success_age_hours"], 2.0)


if __name__ == "__main__":
    unittest.main()
