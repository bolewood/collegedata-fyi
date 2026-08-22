import sys
import unittest
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKER_DIR))

from worker import infer_stopped_reason, with_heartbeat_fields


class ExtractionHeartbeatFieldsTests(unittest.TestCase):
    def test_cap_when_limit_hit_and_pending_remain(self) -> None:
        self.assertEqual(
            infer_stopped_reason(
                stopped_early=False,
                hit_error=False,
                limit=5,
                processed_count=5,
                pending_remaining=84,
            ),
            "cap",
        )

    def test_deadline_wins_over_cap(self) -> None:
        self.assertEqual(
            infer_stopped_reason(
                stopped_early=True,
                hit_error=False,
                limit=5,
                processed_count=3,
                pending_remaining=80,
            ),
            "deadline",
        )

    def test_empty_drain_is_complete(self) -> None:
        self.assertEqual(
            infer_stopped_reason(
                stopped_early=False,
                hit_error=False,
                limit=5,
                processed_count=0,
                pending_remaining=0,
            ),
            "complete",
        )

    def test_summary_contains_required_heartbeat_keys(self) -> None:
        payload = with_heartbeat_fields(
            {"processed_count": 5, "failure_count": 1},
            stopped_reason="cap",
            extracted=4,
            failed=1,
            pending_remaining=84,
        )
        self.assertEqual(payload["stopped_reason"], "cap")
        self.assertEqual(payload["extracted"], 4)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["pending_remaining"], 84)


if __name__ == "__main__":
    unittest.main()
