from __future__ import annotations

import unittest

from worker import extraction_no_project, extraction_success


class WorkerProjectionRefreshTests(unittest.TestCase):
    def test_projection_refresh_is_structured_not_action_prefix_based(self):
        self.assertTrue(extraction_success("tier3_extracted (123 fields)").refresh_projection)
        self.assertTrue(extraction_success("custom_success_name").refresh_projection)
        self.assertFalse(extraction_no_project("already_extracted").refresh_projection)
        self.assertFalse(extraction_no_project("tier4_error: boom").refresh_projection)


if __name__ == "__main__":
    unittest.main()
