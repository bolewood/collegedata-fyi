from __future__ import annotations

import unittest

from worker import (
    extraction_no_project,
    extraction_success,
    is_failure_action,
    mean_or_none,
    parsed_field_count,
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
        self.assertTrue(is_failure_action("no_source_artifact"))

    def test_summary_mean_rounding(self):
        self.assertEqual(mean_or_none([1, 2, 4]), 2.33)
        self.assertIsNone(mean_or_none([]))


if __name__ == "__main__":
    unittest.main()
