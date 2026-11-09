import unittest
from tools.api_usage import aggregate


class UsageExclusionTests(unittest.TestCase):
    def test_private_queue_writes_reads_and_worker_calls_do_not_change_usage(self):
        for route in [
            "community_submit",
            "community_claim_notification",
            "community_finish_notification",
            "community_notification_health",
            "community_expire",
            "community_submissions",
            "community_rate_limits",
            "community_notification_batches",
        ]:
            row = {
                "h": 1794171600,
                "svc": "rest",
                "seg4": "rpc"
                if route
                not in [
                    "community_submissions",
                    "community_rate_limits",
                    "community_notification_batches",
                ]
                else route,
                "seg5": route,
                "method": "POST",
                "n": 1,
                "school_raw": "mit",
            }
            self.assertEqual(aggregate.edge_rollups([row], None), [])
            self.assertEqual(aggregate.edge_schools([row], None), [])
            self.assertEqual(
                aggregate.edge_clients([row], None, lambda _: "isolated-salt"), []
            )
