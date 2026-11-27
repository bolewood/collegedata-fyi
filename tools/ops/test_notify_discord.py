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
REPO = "bolewood/quadfile"


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
        self.assertEqual(body["author"]["name"], "Quadfile")
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
            "as_of": NOW.isoformat().replace("+00:00", "Z"),
            "activity_load_error": False,
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

    def test_stale_seed_does_not_baseline_or_alert_stations(self) -> None:
        snapshot = {
            "as_of": "2026-10-06T16:24:30.330Z",
            "activity_load_error": True,
            "strip": {"lamp": "down", "text": "10 stations overdue · Finder no heartbeat"},
            "stations": [
                {
                    "station_id": "archive_process",
                    "label": "Process",
                    "lamp": "down",
                    "last_scheduled_status": "never",
                    "last_scheduled_finished_at": None,
                }
            ],
        }
        state: dict = {"stations": {}}
        self.assertEqual(nd.pipeline_observation_messages(snapshot, state, NOW), [])
        self.assertNotIn("archive_process", state["stations"])
        self.assertEqual(state["board_unhealthy_streak"], 1)
        self.assertNotEqual(state.get("board"), "down")

    def test_board_health_alerts_on_second_unhealthy_poll_and_recovers(self) -> None:
        stale = {
            "as_of": "2026-10-06T16:24:30.330Z",
            "activity_load_error": True,
            "stations": [],
        }
        state: dict = {"stations": {}}
        self.assertEqual(nd.pipeline_observation_messages(stale, state, NOW), [])
        second = nd.pipeline_observation_messages(stale, state, NOW)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0][1]["title"], "Pipeline observation board is stale")
        self.assertEqual(second[0][1]["color"], nd.COLOR_FAILURE)
        self.assertEqual(state["board"], "down")
        self.assertEqual(nd.pipeline_observation_messages(stale, state, NOW), [])
        fresh = {
            "as_of": NOW.isoformat().replace("+00:00", "Z"),
            "activity_load_error": False,
            "stations": [],
        }
        recovered = nd.pipeline_observation_messages(fresh, state, NOW)
        self.assertEqual(recovered[0][1]["title"], "Pipeline observation board recovered")
        self.assertEqual(state["board"], "ok")
        self.assertEqual(state["board_unhealthy_streak"], 0)

    def test_retry_then_fresh_does_not_alert(self) -> None:
        stale = {
            "as_of": "2026-10-06T16:24:30.330Z",
            "activity_load_error": True,
            "stations": [
                {
                    "station_id": "archive_process",
                    "label": "Process",
                    "lamp": "down",
                    "last_scheduled_status": "never",
                }
            ],
        }
        fresh = {
            "as_of": NOW.isoformat().replace("+00:00", "Z"),
            "activity_load_error": False,
            "stations": [
                {
                    "station_id": "archive_process",
                    "label": "Process",
                    "lamp": "ok",
                    "last_scheduled_status": "ok",
                    "last_scheduled_finished_at": "2026-10-08T15:50:00Z",
                }
            ],
        }
        fetches = [stale, fresh]
        slept: list[float] = []

        def fetch(_url: str) -> dict:
            return fetches.pop(0)

        snapshot = nd.load_pipeline_snapshot(
            nd.PIPELINE_JSON_URL,
            now=NOW,
            fetch_snapshot=fetch,
            sleeper=slept.append,
        )
        self.assertEqual(slept, [nd.BOARD_RETRY_SLEEP_SEC])
        self.assertEqual(snapshot["as_of"], fresh["as_of"])
        state: dict = {"stations": {}}
        self.assertEqual(nd.pipeline_observation_messages(snapshot, state, NOW), [])
        self.assertEqual(state["stations"]["archive_process"], "ok")
        self.assertEqual(state.get("board_unhealthy_streak", 0), 0)

    def test_pipeline_observation_posts_first_down_and_skips_repeat(self) -> None:
        snapshot = {
            "as_of": NOW.isoformat().replace("+00:00", "Z"),
            "activity_load_error": False,
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

    def test_first_poll_alerts_on_a_stale_run_and_baselines_a_fresh_one(self) -> None:
        stale_run = {
            "createdAt": (NOW - timedelta(hours=10)).isoformat().replace("+00:00", "Z"),
            "url": "https://github.com/bolewood/collegedata-fyi/actions/runs/1",
            "headSha": "fff1111",
        }
        state: dict = {"stations": {}}
        first = nd.api_usage_staleness_messages(stale_run, state, NOW)
        self.assertEqual(first[0][1]["title"], "Scheduled pipeline heartbeat missed")
        self.assertEqual(state["api_usage_ingest"], "down")
        self.assertEqual(nd.api_usage_staleness_messages(stale_run, state, NOW), [])
        fresh = dict(stale_run, createdAt=(NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"))
        state = {"stations": {}}
        self.assertEqual(nd.api_usage_staleness_messages(fresh, state, NOW), [])
        self.assertEqual(state["api_usage_ingest"], "ok")

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

    def _station(self, station_id="discovery_renewal", lamp="down", status="ok",
                 finished=None, summary=None, **extra) -> dict:
        # Shaped like toPublicJson: station.summary holds the heartbeat figures.
        return {
            "station_id": station_id, "label": "Discovery renewal", "lamp": lamp,
            "last_scheduled_finished_at": (finished or NOW - timedelta(hours=2)).isoformat(),
            "last_scheduled_status": status,
            "summary": summary if summary is not None else {
                "renewed": 364, "prev_schools": 479, "renewal_pct": 76, "floor_pct": 82.5,
                "below_floor": True},
            **extra,
        }

    def _poll(self, station: dict, previous: str = "ok") -> list:
        snapshot = {"as_of": NOW.isoformat(), "strip": {}, "stations": [station]}
        state: dict = {"stations": {station["station_id"]: previous}}
        return nd.pipeline_observation_messages(snapshot, state, NOW)

    def test_down_to_late_is_not_a_recovery(self) -> None:
        state: dict = {"stations": {"finder_stuck_pdf": "down"}}

        def poll(lamp: str) -> list:
            station = self._station(station_id="finder_stuck_pdf", lamp=lamp, summary={"stuck": 78, "still_stuck": 70},
                                    finished=NOW - timedelta(days=3))
            snapshot = {"as_of": NOW.isoformat(), "strip": {}, "stations": [station]}
            return nd.pipeline_observation_messages(snapshot, state, NOW)

        self.assertEqual(poll("late"), [])  # not "recovered"
        self.assertEqual(poll("capped"), [])
        self.assertEqual(state["stations"]["finder_stuck_pdf"], "down")
        self.assertEqual(poll("down"), [])  # still the same outage: no second alert
        self.assertEqual(poll("run"), [])  # a restarted job may fail again: not recovered
        back = poll("ok")
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0][1]["color"], nd.COLOR_SUCCESS)
        self.assertEqual(poll("late"), [])  # a healthy station going late is not announced
        self.assertEqual(poll("run"), [])

    def _renewal_down(self, summary: dict) -> dict:
        out = self._poll(self._station(summary=summary))
        return {"title": out[0][1]["title"],
                "fields": {f["name"]: f["value"] for f in out[0][1]["fields"]}}

    def test_every_renewal_check_counts_as_a_result_failure_with_its_own_figures(self) -> None:
        healthy = {"below_floor": False, "two_year_below_floor": False, "next_below_floor": None,
                   "outstanding_below_floor": False}
        next_only = self._renewal_down({
            **healthy, "next_below_floor": True, "next_renewed": 40, "next_prev_schools": 417,
            "next_renewal_pct": 9.6, "next_floor_pct": 50.7})
        self.assertEqual(next_only["title"], "Discovery renewal below floor")
        self.assertEqual(next_only["fields"]["Result"], "next-year: 40 of 417 renewed (9.6%) · floor 50.7%")
        two_only = self._renewal_down({
            **healthy, "two_year_below_floor": True, "two_year_renewed": 377,
            "two_year_prev_schools": 536, "two_year_renewal_pct": 70.3, "two_year_floor_pct": 74.5,
            "renewed": 410, "prev_schools": 479})
        self.assertEqual(two_only["title"], "Discovery renewal below floor")
        self.assertEqual(two_only["fields"]["Result"], "two-year: 377 of 536 renewed (70.3%) · floor 74.5%")
        outstanding = self._renewal_down({
            **healthy, "outstanding_below_floor": True, "outstanding_years": "2025-26"})
        self.assertEqual(outstanding["title"], "Discovery renewal below floor")
        self.assertEqual(outstanding["fields"]["Result"], "still short: 2025-26")

    def test_the_first_failing_check_leads_and_healthy_summaries_show_the_headline(self) -> None:
        both = self._renewal_down({"below_floor": True, "renewed": 364, "prev_schools": 479,
                                   "two_year_below_floor": True, "two_year_renewed": 377,
                                   "two_year_prev_schools": 536})
        self.assertTrue(both["fields"]["Result"].startswith("one-year: 364 of 479"))
        self.assertFalse(nd.station_shows_failure(self._station(summary={"below_floor": False})))
        text = nd.station_result_text(self._station(summary={
            "below_floor": False, "renewed": 410, "prev_schools": 479, "renewal_pct": 85.6, "floor_pct": 82.5}))
        self.assertEqual(text, "one-year: 410 of 479 renewed (85.6%) · floor 82.5%")

    def test_down_to_ok_still_recovers(self) -> None:
        state: dict = {"stations": {"finder_brave": "down"}}
        station = self._station(station_id="finder_brave", lamp="ok")
        snapshot = {"as_of": NOW.isoformat(), "strip": {}, "stations": [station]}
        out = nd.pipeline_observation_messages(snapshot, state, NOW)
        self.assertEqual(out[0][1]["title"], "Scheduled pipeline heartbeat recovered")

    def test_result_title_with_text_derived_from_the_public_summary(self) -> None:
        down = self._poll(self._station())
        self.assertEqual(down[0][1]["title"], "Discovery renewal below floor")
        names = [f["name"] for f in down[0][1]["fields"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Last success", names)
        fields = {f["name"]: f["value"] for f in down[0][1]["fields"]}
        self.assertEqual(fields["Result"], "one-year: 364 of 479 renewed (76%) · floor 82.5%")
        self.assertIn("/ 36h", fields["Age vs limit"])
        self.assertEqual(names[:2], ["Station", "Result"])

    def test_result_line_wins_over_derived_text(self) -> None:
        down = self._poll(self._station(result_line="364 of 479 renewed (76%) · floor 82%"))
        fields = {f["name"]: f["value"] for f in down[0][1]["fields"]}
        self.assertEqual(fields["Result"], "364 of 479 renewed (76%) · floor 82%")

    def test_result_recovery_title(self) -> None:
        back = self._poll(self._station(lamp="ok", summary={"below_floor": False, "renewed": 410, "prev_schools": 479}),
                          previous="down")
        self.assertEqual(back[0][1]["title"], "Discovery renewal recovered")

    def test_fresh_error_run_is_a_failure_not_below_floor(self) -> None:
        down = self._poll(self._station(status="error", summary={}))
        self.assertEqual(down[0][1]["title"], "Discovery renewal failed")

    def test_missing_or_ambiguous_figures_stay_a_missed_heartbeat(self) -> None:
        for summary in ({}, {"below_floor": None}, {"below_floor": False}, {"renewed": 1}):
            down = self._poll(self._station(summary=summary))
            self.assertEqual(down[0][1]["title"], "Scheduled pipeline heartbeat missed", summary)
        stale = self._poll(self._station(finished=NOW - timedelta(hours=60)))
        self.assertEqual(stale[0][1]["title"], "Scheduled pipeline heartbeat missed")
        other = self._poll(self._station(station_id="finder_brave"))
        self.assertEqual(other[0][1]["title"], "Scheduled pipeline heartbeat missed")

    def test_stuck_pdf_title_needs_the_share_from_the_summary(self) -> None:
        def stuck(summary):
            return self._poll(self._station(station_id="finder_stuck_pdf", summary=summary,
                                            finished=NOW - timedelta(days=3)))
        self.assertEqual(stuck({"stuck": 78, "still_stuck": 71})[0][1]["title"], "Stuck PDFs mostly still stuck")
        self.assertEqual(stuck({"stuck": 78, "still_stuck": 30})[0][1]["title"], "Scheduled pipeline heartbeat missed")
        self.assertEqual(stuck({"stuck": 0, "still_stuck": 0})[0][1]["title"], "Scheduled pipeline heartbeat missed")

    def test_discovery_renewal_staleness_alerts_once_then_recovers(self) -> None:
        state: dict = {"stations": {}, "discovery_renewal": "ok"}
        kwargs = {
            "workflow": nd.DISCOVERY_RENEWAL_WORKFLOW,
            "state_key": "discovery_renewal",
            "max_age_hours": nd.DISCOVERY_RENEWAL_MAX_AGE_HOURS,
        }
        # 30h old is fine for a daily job; 40h is a miss.
        ok_run = {"createdAt": (NOW - timedelta(hours=30)).isoformat().replace("+00:00", "Z"), "url": "u", "headSha": "abc1234"}
        self.assertEqual(nd.api_usage_staleness_messages(ok_run, state, NOW, **kwargs), [])
        stale_run = {"createdAt": (NOW - timedelta(hours=40)).isoformat().replace("+00:00", "Z"), "url": "u", "headSha": "abc1234"}
        missed = nd.api_usage_staleness_messages(stale_run, state, NOW, **kwargs)
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0][1]["title"], "Scheduled pipeline heartbeat missed")
        fields = {f["name"]: f["value"] for f in missed[0][1]["fields"]}
        self.assertEqual(fields["Workflow"], "Ops discovery renewal")
        self.assertIn("/ 36h", fields["Age vs limit"])
        # Still stale: no repeat.
        self.assertEqual(nd.api_usage_staleness_messages(stale_run, state, NOW, **kwargs), [])
        # A fresh run: one recovery.
        fresh = {"createdAt": (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z"), "url": "u", "headSha": "abc1234"}
        recovered = nd.api_usage_staleness_messages(fresh, state, NOW, **kwargs)
        self.assertEqual(recovered[0][1]["title"], "Scheduled pipeline heartbeat recovered")
        self.assertEqual(state["discovery_renewal"], "ok")

    def test_discovery_renewal_never_run_is_not_announced_as_a_recovery_later(self) -> None:
        state: dict = {"stations": {}}
        kwargs = {"workflow": nd.DISCOVERY_RENEWAL_WORKFLOW, "state_key": "discovery_renewal",
                  "max_age_hours": 36}
        self.assertEqual(nd.api_usage_staleness_messages(None, state, NOW, **kwargs), [])
        self.assertNotIn("discovery_renewal", state)
        first = {"createdAt": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "url": "u", "headSha": "abc1234"}
        self.assertEqual(nd.api_usage_staleness_messages(first, state, NOW, **kwargs), [])
        self.assertEqual(state["discovery_renewal"], "ok")

    def test_deleted_workflow_that_was_ok_alerts(self) -> None:
        state: dict = {"stations": {}, "discovery_renewal": "ok"}
        out = nd.api_usage_staleness_messages(
            None, state, NOW, workflow=nd.DISCOVERY_RENEWAL_WORKFLOW,
            state_key="discovery_renewal", max_age_hours=36)
        self.assertEqual(len(out), 1)

    def test_state_round_trip_keeps_every_watched_workflow_key(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            path.write_text(json.dumps({"stations": {}, "api_usage_ingest": "down", "discovery_renewal": "ok"}))
            loaded = nd.load_state(path)
            self.assertEqual(loaded["api_usage_ingest"], "down")
            self.assertEqual(loaded["discovery_renewal"], "ok")

    def test_hourly_poll_checks_every_watched_workflow(self) -> None:
        seen: list[str] = []

        def runner(args, token):
            if args[:2] == ["run", "list"] and "--event" in args:
                seen.append(args[args.index("--workflow") + 1])
            return subprocess.CompletedProcess(args, 0, "[]", "")

        with tempfile.TemporaryDirectory() as d:
            nd.main(
                ["--event-name", "schedule", "--state-path", str(Path(d) / "s.json"), "--dry-run"],
                fetch_snapshot=lambda url: {"as_of": NOW.isoformat(), "stations": [], "strip": {}},
                runner=runner, now=NOW, sleeper=lambda s: None,
            )
        self.assertEqual(seen, ["API usage ingest", "Ops discovery renewal", "Ops monthly hand check"])

    def test_the_monthly_hand_check_is_watched_with_a_35_day_limit(self) -> None:
        watch = {w: (key, hours) for w, key, hours in nd.SCHEDULED_RUN_WATCHES}
        self.assertEqual(watch["Ops monthly hand check"], ("hand_check", 35 * 24))
        kwargs = {"workflow": "Ops monthly hand check", "state_key": "hand_check",
                  "max_age_hours": 35 * 24}
        state: dict = {"stations": {}, "hand_check": "ok"}

        def run_at(days: float) -> dict:
            created = (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")
            return {"createdAt": created, "url": "u", "headSha": "abc1234"}

        self.assertEqual(nd.api_usage_staleness_messages(run_at(31), state, NOW, **kwargs), [])
        missed = nd.api_usage_staleness_messages(run_at(36), state, NOW, **kwargs)
        self.assertEqual(len(missed), 1)
        self.assertIn("/ 840h", {f["name"]: f["value"] for f in missed[0][1]["fields"]}["Age vs limit"])
        self.assertEqual(nd.api_usage_staleness_messages(run_at(40), state, NOW, **kwargs), [])
        back = nd.api_usage_staleness_messages(run_at(2), state, NOW, **kwargs)
        self.assertEqual(back[0][1]["title"], "Scheduled pipeline heartbeat recovered")
        # The state file keeps the new key between hourly polls.
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            path.write_text(json.dumps({"stations": {}, "hand_check": "down"}))
            self.assertEqual(nd.load_state(path)["hand_check"], "down")

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
