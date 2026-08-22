from __future__ import annotations

import io
import json
import unittest
from unittest import mock
from urllib.error import URLError

from tools.ops import record_heartbeat as hb


class RecordHeartbeatTests(unittest.TestCase):
    def test_unknown_station_exits_zero_with_warning(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(hb.sys, "stderr", stderr):
            code = hb.main([
                "--station", "not_a_station",
                "--status", "ok",
                "--trigger", "schedule",
            ])
        self.assertEqual(code, 0)
        self.assertIn("::warning::pipeline heartbeat failed for not_a_station", stderr.getvalue())

    def test_post_failure_exits_zero_with_warning(self) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role",
            },
            clear=False,
        ), mock.patch.object(
            hb.urllib.request,
            "urlopen",
            side_effect=URLError("connection refused"),
        ), mock.patch.object(hb.sys, "stderr", stderr):
            code = hb.main([
                "--station", "finder_brave",
                "--status", "ok",
                "--trigger", "schedule",
                "--summary", json.dumps({
                    "probed": 1,
                    "found": 0,
                    "replaced": 0,
                    "budget_remaining": 10,
                }),
            ])
        self.assertEqual(code, 0)
        self.assertIn("::warning::pipeline heartbeat failed for finder_brave", stderr.getvalue())

    def test_missing_secrets_exits_zero_with_warning(self) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(
            "os.environ",
            {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""},
            clear=False,
        ), mock.patch.object(hb, "load_env", return_value={}), mock.patch.object(hb.sys, "stderr", stderr):
            code = hb.main([
                "--station", "finder_brave",
                "--status", "running",
                "--trigger", "schedule",
            ])
        self.assertEqual(code, 0)
        self.assertIn("::warning::pipeline heartbeat failed for finder_brave", stderr.getvalue())

    def test_post_payload_uses_rpc_argument_names(self) -> None:
        captured: dict[str, object] = {}

        class FakeResponse:
            def read(self) -> bytes:
                return b""

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

        def fake_urlopen(request, timeout=20):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        with mock.patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role",
            },
            clear=False,
        ), mock.patch.object(hb.urllib.request, "urlopen", side_effect=fake_urlopen):
            code = hb.main([
                "--station", "ipeds_release_probe",
                "--status", "ok",
                "--trigger", "schedule",
                "--summary", json.dumps({"new_release": False, "issue_opened": False}),
                "--run-url", "https://github.com/bolewood/collegedata-fyi/actions/runs/99",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(
            captured["url"],
            "https://example.supabase.co/rest/v1/rpc/record_pipeline_heartbeat",
        )
        body = captured["body"]
        assert isinstance(body, dict)
        self.assertEqual(body["p_station_id"], "ipeds_release_probe")
        self.assertEqual(body["p_status"], "ok")
        self.assertEqual(body["p_trigger"], "schedule")
        self.assertEqual(body["p_error_code"], "none")
        self.assertEqual(body["p_summary"]["new_release"], False)
        self.assertEqual(
            body["p_summary"]["run_url"],
            "https://github.com/bolewood/collegedata-fyi/actions/runs/99",
        )


if __name__ == "__main__":
    unittest.main()
