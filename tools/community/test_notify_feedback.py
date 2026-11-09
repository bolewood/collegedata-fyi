from __future__ import annotations
import contextlib
import io
import unittest
from pathlib import Path
from tools.community import notify_feedback as worker
from tools.ops import notify_discord as ops
from datetime import datetime, timedelta, timezone

INBOX = "https://supabase.com/dashboard/project/abcdefghijklmnopqrst/editor/public.community_submissions"
ENV = {
    "GITHUB_REF": "refs/heads/main",
    "COMMUNITY_NOTIFICATIONS_ENABLED": "true",
    "SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "isolated-test-key",
    "RESEND_API_KEY": "mock-key",
    "COMMUNITY_NOTIFICATION_FROM": worker.SENDER,
    "COMMUNITY_INBOX_URL": INBOX,
}
BATCH = {
    "id": "batch-one",
    "token": "lease-one",
    "count": 2,
    "payload": {
        "from": worker.SENDER,
        "to": [worker.RECIPIENT],
        "subject": "CollegeData.fyi: 2 new feedback message(s)",
        "text": f"There are 2 new messages waiting for review.\n\nOpen the private feedback inbox: {INBOX}",
    },
}


class NotificationTests(unittest.TestCase):
    def run_worker(self, fail=None, overdue=0):
        calls = []

        def transport(url, payload, headers):
            calls.append((url, payload, headers))
            if url.endswith("community_notification_health"):
                return {"overdue": overdue, "pending": 1}
            if url.endswith("community_claim_notification"):
                return BATCH
            if url.endswith("community_finish_notification"):
                return True
            if fail:
                raise worker.WorkerError(fail)
            return {"id": "mock-provider-id"}

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            try:
                result = worker.run(ENV, transport)
            except worker.WorkerError as exc:
                result = str(exc)
        return result, calls, output.getvalue()

    def test_count_link_only_and_stable_retry_identity(self):
        result, calls, output = self.run_worker()
        self.assertEqual(result, 0)
        mail = calls[2]
        self.assertEqual(mail[1], BATCH["payload"])
        self.assertEqual(mail[2]["Idempotency-Key"], "community-feedback/batch-one")
        self.assertEqual(set(mail[1]), {"from", "to", "subject", "text"})
        self.assertEqual(output, "community_feedback sent_count=2\n")
        self.assertEqual(self.run_worker()[1][2], mail)

    def test_timeout_records_retry_without_dropping_receipts(self):
        result, calls, _ = self.run_worker("timeout")
        self.assertEqual(result, "timeout")
        self.assertEqual(
            calls[-1][1],
            {"p_id": "batch-one", "p_token": "lease-one", "p_error": "timeout"},
        )

    def test_provider_failure_and_overdue_fail_visibly(self):
        self.assertEqual(self.run_worker("provider")[0], "provider")
        self.assertEqual(self.run_worker(overdue=1)[0], "overdue")

    def test_backoff_does_not_report_false_recovery(self):
        def transport(url, *_):
            if url.endswith("community_notification_health"):
                return {"overdue": 0, "pending": 1}
            return None

        with self.assertRaisesRegex(worker.WorkerError, "retry_pending"):
            worker.run(ENV, transport)

    def test_unconfigured_and_non_main_never_send(self):
        for changes in [
            {"GITHUB_REF": "refs/heads/feature"},
            {"COMMUNITY_NOTIFICATIONS_ENABLED": ""},
            {"COMMUNITY_INBOX_URL": "https://evil.test"},
            {"COMMUNITY_NOTIFICATION_FROM": "attacker@example.com"},
        ]:
            with self.assertRaises(worker.WorkerError):
                worker.run({**ENV, **changes}, lambda *args: self.fail("network used"))

    def test_failure_allowlists_and_success_freshness(self):
        root = Path(__file__).resolve().parents[2]
        name = "Community feedback notifications"
        self.assertIn(name, ops.WATCHED_WORKFLOWS)
        self.assertIn(
            "- " + name, (root / ".github/workflows/ops-discord-notify.yml").read_text()
        )
        state = {}
        now = datetime.now(timezone.utc)
        messages = ops.api_usage_staleness_messages(
            None, state, now, workflow=name, state_key="community_feedback"
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(state["community_feedback"], "down")
        run = {"createdAt": (now - timedelta(hours=9)).isoformat()}
        self.assertEqual(
            ops.api_usage_staleness_messages(
                run, {}, now, workflow=name, state_key="community_feedback"
            )[0][0],
            "alerts",
        )
        self.assertEqual(
            len(
                ops.api_usage_staleness_messages(
                    {"createdAt": now.isoformat()},
                    state,
                    now,
                    workflow=name,
                    state_key="community_feedback",
                )
            ),
            1,
        )
