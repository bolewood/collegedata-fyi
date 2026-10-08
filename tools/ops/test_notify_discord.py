"""Tests for Discord ops notifications."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from tools.ops import notify_discord as nd


NOW = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
WEBHOOK = "https://discord.com/api/webhooks/123/super-secret-token"
REPO = "bolewood/collegedata-fyi"


def gh_result(stdout: str = "[]", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout, stderr="")


def workflow_event(
    *,
    name: str = "CI",
    conclusion: str = "failure",
    branch: str = "main",
    event: str = "push",
    run_id: int = 99,
    sha: str = "abcdef1234567890",
) -> dict:
    return {
        "workflow_run": {
            "name": name,
            "conclusion": conclusion,
            "head_branch": branch,
            "head_sha": sha,
            "event": event,
            "id": run_id,
            "html_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        }
    }


def deployment_event(
    *,
    state: str = "success",
    environment: str = "Production",
    production: bool = True,
    sha: str = "abcdef1234567890",
    ref: str = "refs/heads/main",
) -> dict:
    return {
        "deployment": {
            "sha": sha,
            "ref": ref,
            "environment": environment,
            "production_environment": production,
        },
        "deployment_status": {
            "state": state,
            "environment": environment,
            "log_url": "https://github.com/bolewood/collegedata-fyi/deployments/1",
            "environment_url": "https://collegedata.fyi",
        },
    }


class NotifyDiscordTests(unittest.TestCase):
    def test_watched_workflows_match_checked_in_names(self) -> None:
        root = Path(__file__).resolve().parents[2]
        workflows = root / ".github" / "workflows"
        names: dict[str, str] = {}
        for path in workflows.glob("*.yml"):
            first_name = None
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("name:"):
                    first_name = line.split(":", 1)[1].strip().strip('"')
                    break
            self.assertIsNotNone(first_name, path.name)
            names[path.name] = first_name or ""

        notify = (workflows / nd.SELF_WORKFLOW_FILE).read_text(encoding="utf-8")
        self.assertIn("secrets.DISCORD_ALERTS_WEBHOOK_URL", notify)
        self.assertIn("secrets.DISCORD_DEPLOYS_WEBHOOK_URL", notify)
        self.assertNotIn("echo \"$DISCORD_", notify)
        self.assertIn("github.event_name != 'deployment_status'", notify)
        self.assertIn("production_environment == true", notify)
        for display, filename in nd.WATCHED_WORKFLOWS.items():
            self.assertEqual(names[filename], display, filename)
            self.assertTrue((workflows / filename).is_file())
            self.assertIn(f"- {display}", notify)

        for path in workflows.glob("*.yml"):
            if path.name == nd.SELF_WORKFLOW_FILE:
                continue
            if path.name.startswith("ops-") or path.name in {
                "ci.yml",
                "deploy-edge-functions.yml",
                "ipeds-release-probe.yml",
            }:
                self.assertIn(path.name, nd.WATCHED_WORKFLOWS.values(), path.name)

    def test_workflow_run_failure_on_main_posts_alert(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(),
            repo=REPO,
            token=None,
            previous="success",
            jobs="Python unit tests",
        )
        self.assertEqual(len(messages), 1)
        channel, body = messages[0]
        self.assertEqual(channel, "alerts")
        self.assertEqual(body["title"], "CI failed")
        self.assertEqual(body["color"], nd.COLOR_FAILURE)
        self.assertEqual(body["author"]["name"], "CollegeData.fyi")
        names = {field["name"]: field["value"] for field in body["fields"]}
        self.assertEqual(names["Workflow"], "CI")
        self.assertEqual(names["Job"], "Python unit tests")
        self.assertEqual(names["Branch"], "main")
        self.assertEqual(names["Commit"], "`abcdef1`")
        self.assertIn("/actions/runs/99", body["url"])

    def test_workflow_run_repeat_failure_is_quiet(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(),
            repo=REPO,
            token=None,
            previous="failure",
            jobs="Python unit tests",
        )
        self.assertEqual(messages, [])

    def test_workflow_run_recovery_posts_green_alert(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(conclusion="success"),
            repo=REPO,
            token=None,
            previous="failure",
            jobs="",
        )
        channels = [channel for channel, _ in messages]
        self.assertIn("alerts", channels)
        self.assertIn("deploys", channels)
        alert = next(body for channel, body in messages if channel == "alerts")
        self.assertEqual(alert["title"], "CI recovered")
        self.assertEqual(alert["color"], nd.COLOR_SUCCESS)

    def test_workflow_run_ci_success_on_main_posts_deploys(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(conclusion="success"),
            repo=REPO,
            token=None,
            previous="success",
            jobs="",
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], "deploys")
        self.assertEqual(messages[0][1]["title"], "CI succeeded")
        self.assertEqual(messages[0][1]["color"], nd.COLOR_SUCCESS)

    def test_workflow_run_edge_deploy_success_uses_deploy_copy(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(name="Deploy Edge Functions", conclusion="success"),
            repo=REPO,
            token=None,
            previous="success",
            jobs="",
        )
        self.assertEqual(messages[0][1]["title"], "Edge functions deployed")

    def test_scheduled_ops_success_does_not_spam_deploys(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(
                name="Ops headless archive",
                conclusion="success",
                event="schedule",
            ),
            repo=REPO,
            token=None,
            previous="success",
            jobs="",
        )
        self.assertEqual(messages, [])

    def test_pull_request_ci_is_ignored(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(branch="cursor/discord-ops-alerts-6f0a", event="pull_request"),
            repo=REPO,
            token=None,
            previous="success",
            jobs="Python unit tests",
        )
        self.assertEqual(messages, [])

    def test_timed_out_run_is_a_failure(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(conclusion="timed_out"),
            repo=REPO,
            token=None,
            previous="success",
            jobs="Drain pending extraction rows",
        )
        self.assertEqual(messages[0][0], "alerts")
        self.assertEqual(messages[0][1]["title"], "CI failed")

    def test_cancelled_run_is_ignored(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(conclusion="cancelled"),
            repo=REPO,
            token=None,
            previous="success",
            jobs="",
        )
        self.assertEqual(messages, [])

    def test_scheduled_failure_on_default_branch_alerts(self) -> None:
        messages = nd.workflow_run_messages(
            workflow_event(name="API usage ingest", event="schedule"),
            repo=REPO,
            token=None,
            previous=None,
            jobs="Ingest gateway logs",
        )
        self.assertEqual(messages[0][0], "alerts")
        self.assertEqual(messages[0][1]["title"], "API usage ingest failed")

    def test_preview_deployment_is_ignored(self) -> None:
        messages = nd.deployment_status_messages(
            deployment_event(environment="Preview", production=False, state="failure")
        )
        self.assertEqual(messages, [])

    def test_production_deploy_success_goes_to_deploys(self) -> None:
        messages = nd.deployment_status_messages(deployment_event())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], "deploys")
        self.assertEqual(messages[0][1]["title"], "Vercel production deploy succeeded")
        self.assertEqual(messages[0][1]["color"], nd.COLOR_SUCCESS)

    def test_production_deploy_failure_goes_to_alerts(self) -> None:
        messages = nd.deployment_status_messages(deployment_event(state="failure"))
        self.assertEqual(messages[0][0], "alerts")
        self.assertEqual(messages[0][1]["title"], "Vercel production deploy failed")
        self.assertEqual(messages[0][1]["color"], nd.COLOR_FAILURE)

    def test_pipeline_observation_baselines_without_spamming(self) -> None:
        snapshot = {
            "strip": {"lamp": "down"},
            "stations": [
                {
                    "station_id": "archive_process",
                    "label": "Process",
                    "lamp": "down",
                    "last_scheduled_finished_at": "2026-10-08T10:00:00Z",
                    "last_scheduled_status": "error",
                    "error_code": "job_failed",
                }
            ],
        }
        state: dict = {"stations": {}}
        self.assertEqual(nd.pipeline_observation_messages(snapshot, state, NOW), [])
        self.assertEqual(state["stations"]["archive_process"], "down")

    def test_pipeline_observation_posts_first_down_and_skips_repeat(self) -> None:
        snapshot = {
            "strip": {"lamp": "down"},
            "stations": [
                {
                    "station_id": "archive_process",
                    "label": "Process",
                    "lamp": "down",
                    "last_scheduled_finished_at": "2026-10-08T10:00:00Z",
                    "last_scheduled_status": "error",
                    "error_code": "job_failed",
                }
            ],
        }
        state: dict = {"stations": {"archive_process": "ok", "_board": "ok"}}
        first = nd.pipeline_observation_messages(snapshot, state, NOW)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0][1]["title"], "Scheduled pipeline heartbeat missed")
        names = {field["name"]: field["value"] for field in first[0][1]["fields"]}
        self.assertEqual(names["Station"], "Process")
        self.assertIn("2h", names["Age vs limit"])
        repeat = nd.pipeline_observation_messages(snapshot, state, NOW)
        self.assertEqual(repeat, [])
        snapshot["stations"][0]["lamp"] = "ok"
        recovered = nd.pipeline_observation_messages(snapshot, state, NOW)
        self.assertEqual(recovered[0][1]["title"], "Scheduled pipeline heartbeat recovered")
        self.assertEqual(recovered[0][1]["color"], nd.COLOR_SUCCESS)

    def test_api_usage_staleness_baselines_without_posting(self) -> None:
        state: dict = {"stations": {}}
        stale_run = {
            "createdAt": (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z"),
            "url": "https://github.com/bolewood/collegedata-fyi/actions/runs/1",
            "headSha": "fff1111",
        }
        self.assertEqual(nd.api_usage_staleness_messages(stale_run, state, NOW), [])
        self.assertEqual(state["api_usage_ingest"], "down")

    def test_api_usage_staleness_first_miss_and_recovery(self) -> None:
        state: dict = {"stations": {}, "api_usage_ingest": "ok"}
        stale_run = {
            "createdAt": (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z"),
            "url": "https://github.com/bolewood/collegedata-fyi/actions/runs/1",
            "headSha": "fff1111",
        }
        missed = nd.api_usage_staleness_messages(stale_run, state, NOW)
        self.assertEqual(missed[0][1]["title"], "Scheduled pipeline heartbeat missed")
        self.assertEqual(nd.api_usage_staleness_messages(stale_run, state, NOW), [])
        fresh = {
            "createdAt": (NOW - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
            "url": "https://github.com/bolewood/collegedata-fyi/actions/runs/2",
            "headSha": "abc2222",
        }
        recovered = nd.api_usage_staleness_messages(fresh, state, NOW)
        self.assertEqual(recovered[0][1]["title"], "Scheduled pipeline heartbeat recovered")

    def test_missing_webhook_skips_without_failing_or_logging_url(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(nd.sys, "stdout", stdout),
            patch.object(nd.sys, "stderr", stderr),
            tempfile.TemporaryDirectory() as tmp,
        ):
            event_path = Path(tmp) / "event.json"
            event_path.write_text(json.dumps(workflow_event()), encoding="utf-8")
            code = nd.main(
                [
                    "--event-name",
                    "workflow_run",
                    "--event-path",
                    str(event_path),
                    "--repo",
                    REPO,
                ],
                runner=lambda *_args, **_kwargs: gh_result(
                    '[{"databaseId": 1, "conclusion": "success", "status": "completed"}]'
                ),
            )
        self.assertEqual(code, 0)
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertIn("webhook unset", combined)
        self.assertNotIn("discord.com/api/webhooks", combined)
        self.assertNotIn("super-secret-token", combined)

    def test_http_error_does_not_log_webhook_url(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.dict(
                "os.environ",
                {"DISCORD_ALERTS_WEBHOOK_URL": WEBHOOK, "DISCORD_DEPLOYS_WEBHOOK_URL": ""},
                clear=True,
            ),
            patch.object(nd, "post_webhook", side_effect=nd.DiscordPostError("HTTP 500")),
            patch.object(nd.sys, "stdout", stdout),
            patch.object(nd.sys, "stderr", stderr),
            tempfile.TemporaryDirectory() as tmp,
        ):
            event_path = Path(tmp) / "event.json"
            event_path.write_text(json.dumps(workflow_event()), encoding="utf-8")
            code = nd.main(
                [
                    "--event-name",
                    "workflow_run",
                    "--event-path",
                    str(event_path),
                    "--repo",
                    REPO,
                ],
                runner=lambda *_args, **_kwargs: gh_result(
                    '[{"databaseId": 1, "conclusion": "success", "status": "completed"}]'
                ),
            )
        self.assertEqual(code, 0)
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertIn("discord post failed", combined)
        self.assertNotIn(WEBHOOK, combined)
        self.assertNotIn("super-secret-token", combined)

    def test_post_webhook_swallows_url_from_http_error(self) -> None:
        error = HTTPError(WEBHOOK, 429, "rate limited", hdrs=None, fp=None)
        with patch.object(nd.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(nd.DiscordPostError) as raised:
                nd.post_webhook(WEBHOOK, {"embeds": []})
        self.assertEqual(str(raised.exception), "HTTP 429")
        self.assertNotIn("super-secret-token", str(raised.exception))

    def test_previous_run_lookup_skips_current_and_cancelled(self) -> None:
        rows = [
            {"databaseId": 99, "conclusion": "failure", "status": "completed"},
            {"databaseId": 98, "conclusion": "cancelled", "status": "completed"},
            {"databaseId": 97, "conclusion": "success", "status": "completed"},
        ]
        conclusion = nd.previous_meaningful_conclusion(
            repo=REPO,
            workflow="CI",
            branch="main",
            current_run_id=99,
            token="t",
            runner=lambda *_args, **_kwargs: gh_result(json.dumps(rows)),
        )
        self.assertEqual(conclusion, "success")


if __name__ == "__main__":
    unittest.main()
