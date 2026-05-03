from __future__ import annotations

import unittest

from worker import (
    extraction_no_project,
    extraction_success,
    is_failure_action,
    mean_or_none,
    parsed_field_count,
    pending_doc_priority_key,
)


class WorkerProjectionRefreshTests(unittest.TestCase):
    def test_projection_refresh_is_structured_not_action_prefix_based(self):
        self.assertTrue(extraction_success("tier3_extracted (123 fields)").refresh_projection)
        self.assertTrue(extraction_success("custom_success_name").refresh_projection)
        self.assertFalse(extraction_no_project("already_extracted").refresh_projection)
        self.assertFalse(extraction_no_project("tier4_error: boom").refresh_projection)

    def test_summary_field_count_parser_handles_worker_actions(self):
        self.assertEqual(parsed_field_count("tier4_extracted (289 fields, 48 pages)"), 289)
        self.assertEqual(parsed_field_count("extracted (576/812 fields, 156 unmapped)"), 576)
        self.assertIsNone(parsed_field_count("already_extracted"))

    def test_summary_failure_classifier_ignores_already_extracted(self):
        self.assertFalse(is_failure_action("already_extracted"))
        self.assertFalse(is_failure_action("tier4_extracted (289 fields, 48 pages)"))
        self.assertTrue(is_failure_action("tier4_error: boom"))
        self.assertTrue(is_failure_action("stub_docx"))
        self.assertTrue(is_failure_action("tier1_low_fields (0 fields)"))
        self.assertTrue(is_failure_action("no_source_artifact"))

    def test_summary_mean_rounding(self):
        self.assertEqual(mean_or_none([1, 2, 4]), 2.33)
        self.assertIsNone(mean_or_none([]))

    def test_pending_doc_priority_prefers_recent_cds_year(self):
        rows = [
            {"school_id": "aaa-old", "cds_year": "2019-20", "discovered_at": "2026-05-03T00:00:00Z"},
            {"school_id": "zzz-current", "cds_year": "2025-26", "discovered_at": "2026-04-01T00:00:00Z"},
            {"school_id": "mid-prior", "detected_year": "2024-25", "cds_year": "2023-24", "discovered_at": "2026-05-01T00:00:00Z"},
        ]

        ordered = sorted(rows, key=pending_doc_priority_key)

        self.assertEqual([row["school_id"] for row in ordered], [
            "zzz-current",
            "mid-prior",
            "aaa-old",
        ])

    def test_pending_doc_priority_prefers_newer_discovery_within_year(self):
        rows = [
            {"school_id": "yale", "cds_year": "2025-26", "discovered_at": "2026-05-01T02:11:14Z"},
            {"school_id": "brown", "cds_year": "2025-26", "discovered_at": "2026-05-01T02:14:44Z"},
            {"school_id": "uw", "cds_year": "2025-26", "discovered_at": "2026-04-15T00:34:39Z"},
        ]

        ordered = sorted(rows, key=pending_doc_priority_key)

        self.assertEqual([row["school_id"] for row in ordered], [
            "brown",
            "yale",
            "uw",
        ])


if __name__ == "__main__":
    unittest.main()
