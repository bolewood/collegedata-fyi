#!/usr/bin/env python3
"""Post CollegeData.fyi ops events to Bolewood Discord webhooks.

Never fails the calling job. Missing webhook secrets skip the post.
Webhook URLs are never written to stdout/stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_NAME = "CollegeData.fyi"
PIPELINE_BOARD_URL = "https://www.collegedata.fyi/pipeline-observation"
PIPELINE_JSON_URL = "https://www.collegedata.fyi/pipeline-observation.json"
COLOR_FAILURE = 0xD7263D
COLOR_SUCCESS = 0x1F7A4D

WATCHED_WORKFLOWS = {
    "CI": "ci.yml",
    "Deploy Edge Functions": "deploy-edge-functions.yml",
    "IPEDS release probe": "ipeds-release-probe.yml",
    "Ops finder probe": "ops-finder-probe.yml",
    "API usage ingest": "ops-api-usage-ingest.yml",
    "Ops extraction worker": "ops-extraction-worker.yml",
    "Ops archive seed catchup": "ops-archive-seed-catchup.yml",
    "Ops headless archive": "ops-headless-archive.yml",
}
DEPLOY_SUCCESS_WORKFLOWS = frozenset({"CI", "Deploy Edge Functions"})
SELF_WORKFLOW_FILE = "ops-discord-notify.yml"

# Public board lamps that mean "broke". late/capped stay on the board only.
ALERT_LAMPS = frozenset({"down"})

STATION_SLA: dict[str, tuple[str, int]] = {
    "finder_brave": ("40d", 40 * 24 * 3600),
    "finder_stuck_pdf": ("40d", 40 * 24 * 3600),
    "finder_landing_hints": ("40d", 40 * 24 * 3600),
    "archive_enqueue": ("36h", 36 * 3600),
    "archive_process": ("2h", 2 * 3600),
    "headless_archive": ("36h", 36 * 3600),
    "extraction_worker": ("36h", 36 * 3600),
    "coverage_refresh": ("3h", 3 * 3600),
    "serving_cache_refresh": ("3h", 3 * 3600),
    "ipeds_release_probe": ("40d", 40 * 24 * 3600),
    "schema_build": ("18mo", 18 * 30 * 24 * 3600),
    "scorecard_load": ("18mo", 18 * 30 * 24 * 3600),
    "api_usage_ingest": ("8h", 8 * 3600),
}

API_USAGE_WORKFLOW = "API usage ingest"
API_USAGE_MAX_AGE_HOURS = 8
PRODUCTION_ENV_NAMES = frozenset({"production", "prod"})


class DiscordPostError(RuntimeError):
    """Raised when Discord rejects a post. Must not include the webhook URL."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_label(iso: str | None, now: datetime) -> str:
    parsed = parse_time(iso)
    if parsed is None:
        return "never"
    seconds = max(0, int((now - parsed).total_seconds()))
    if seconds < 90:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def short_sha(sha: str | None) -> str:
    if not sha:
        return "unknown"
    return sha[:7]


def branch_name(ref: str | None) -> str:
    if not ref:
        return "unknown"
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/") :]
    return ref


def is_production_environment(event: dict[str, Any]) -> bool:
    deployment = event.get("deployment") or {}
    status = event.get("deployment_status") or {}
    if deployment.get("production_environment") is True:
        return True
    names = {
        str(status.get("environment") or "").lower(),
        str(deployment.get("environment") or "").lower(),
        str(deployment.get("original_environment") or "").lower(),
    }
    return bool(names & PRODUCTION_ENV_NAMES)


def redact(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return out


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"stations": {}, "api_usage_ingest": "ok"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"stations": {}, "api_usage_ingest": "ok"}
    if not isinstance(data, dict):
        return {"stations": {}, "api_usage_ingest": "ok"}
    stations = data.get("stations")
    if not isinstance(stations, dict):
        stations = {}
    return {
        "stations": {str(key): str(value) for key, value in stations.items()},
        "api_usage_ingest": str(data.get("api_usage_ingest") or "ok"),
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def embed(
    *,
    title: str,
    color: int,
    url: str | None = None,
    fields: list[tuple[str, str]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title[:256],
        "color": color,
        "author": {"name": PROJECT_NAME},
        "footer": {"text": PROJECT_NAME},
    }
    if url:
        payload["url"] = url
        payload["author"]["url"] = url
    payload["fields"] = [
        {"name": name, "value": (value or "—")[:1024], "inline": True}
        for name, value in fields
        if name
    ]
    return payload


def post_webhook(url: str, payload: dict[str, Any], timeout_sec: float = 20) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "collegedata-fyi-ops-discord",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            if response.status not in (200, 204):
                raise DiscordPostError(f"HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise DiscordPostError(f"HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise DiscordPostError("network error") from None


def fetch_json(url: str, timeout_sec: float = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "collegedata-fyi-ops-discord", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def run_gh(args: list[str], token: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token
        env.setdefault("GITHUB_TOKEN", token)
    return subprocess.run(
        ["gh", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=45,
    )


def previous_meaningful_conclusion(
    *,
    repo: str,
    workflow: str,
    branch: str,
    current_run_id: int | None,
    token: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_gh,
) -> str | None:
    listed = runner(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--branch",
            branch,
            "--limit",
            "20",
            "--json",
            "databaseId,conclusion,status",
        ],
        token,
    )
    if listed.returncode != 0:
        print("::warning::could not list previous workflow runs", file=sys.stderr)
        return None
    try:
        rows = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        return None
    for row in rows:
        if current_run_id is not None and int(row.get("databaseId") or 0) == int(current_run_id):
            continue
        if row.get("status") not in (None, "completed"):
            continue
        conclusion = row.get("conclusion")
        if conclusion in {"cancelled", "skipped", None, ""}:
            continue
        return str(conclusion)
    return None


def failed_job_names(
    *,
    repo: str,
    run_id: int,
    token: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_gh,
) -> str:
    listed = runner(
        [
            "api",
            f"repos/{repo}/actions/runs/{run_id}/jobs",
            "--jq",
            '[.jobs[] | select(.conclusion=="failure") | .name] | join(", ")',
        ],
        token,
    )
    if listed.returncode != 0:
        return ""
    return (listed.stdout or "").strip()


def latest_scheduled_run(
    *,
    repo: str,
    workflow: str,
    token: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_gh,
) -> dict[str, Any] | None:
    listed = runner(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--event",
            "schedule",
            "--limit",
            "1",
            "--json",
            "conclusion,createdAt,url,displayTitle,headSha,headBranch",
        ],
        token,
    )
    if listed.returncode != 0:
        print("::warning::could not list API usage ingest runs", file=sys.stderr)
        return None
    try:
        rows = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        return None
    return rows[0] if rows else None


def should_watch_workflow_run(event_name: str, branch: str) -> bool:
    if event_name == "schedule":
        return True
    return branch == "main"


def as_outcome(conclusion: str | None) -> str | None:
    """Collapse GitHub conclusions to success / failure / ignore."""
    if conclusion in {None, "", "cancelled", "skipped"}:
        return None
    if conclusion == "success":
        return "success"
    return "failure"


def transition(previous: str | None, current: str | None) -> str | None:
    """Return 'failure', 'recovery', or None for an ongoing/quiet state."""
    previous_outcome = as_outcome(previous)
    current_outcome = as_outcome(current)
    if current_outcome is None:
        return None
    if current_outcome == "failure" and previous_outcome != "failure":
        return "failure"
    if current_outcome == "success" and previous_outcome == "failure":
        return "recovery"
    return None


def workflow_run_messages(
    event: dict[str, Any],
    *,
    repo: str,
    token: str | None,
    previous: str | None | object = ...,
    jobs: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_gh,
) -> list[tuple[str, dict[str, Any]]]:
    run = event.get("workflow_run") or {}
    workflow = str(run.get("name") or event.get("workflow", {}).get("name") or "")
    if workflow not in WATCHED_WORKFLOWS:
        return []
    conclusion = str(run.get("conclusion") or "")
    outcome = as_outcome(conclusion)
    if outcome is None:
        return []
    branch = branch_name(str(run.get("head_branch") or ""))
    triggering_event = str(run.get("event") or "")
    if not should_watch_workflow_run(triggering_event, branch):
        return []

    run_id = run.get("id")
    sha = short_sha(str(run.get("head_sha") or ""))
    url = str(run.get("html_url") or "")
    if previous is ...:
        previous = previous_meaningful_conclusion(
            repo=repo,
            workflow=workflow,
            branch=branch,
            current_run_id=int(run_id) if run_id is not None else None,
            token=token,
            runner=runner,
        )
    if jobs is None and outcome != "success" and run_id is not None:
        jobs = failed_job_names(repo=repo, run_id=int(run_id), token=token, runner=runner)

    fields = [
        ("Workflow", workflow),
        ("Job", jobs or "—"),
        ("Branch", branch),
        ("Commit", f"`{sha}`"),
        ("Event", triggering_event or "—"),
    ]
    messages: list[tuple[str, dict[str, Any]]] = []
    kind = transition(
        previous if isinstance(previous, str) or previous is None else None,
        conclusion,
    )
    if kind == "failure":
        messages.append(
            (
                "alerts",
                embed(
                    title=f"{workflow} failed",
                    color=COLOR_FAILURE,
                    url=url or None,
                    fields=fields,
                ),
            )
        )
    elif kind == "recovery":
        messages.append(
            (
                "alerts",
                embed(
                    title=f"{workflow} recovered",
                    color=COLOR_SUCCESS,
                    url=url or None,
                    fields=fields,
                ),
            )
        )
    if outcome == "success" and workflow in DEPLOY_SUCCESS_WORKFLOWS and branch == "main":
        title = (
            "Edge functions deployed"
            if workflow == "Deploy Edge Functions"
            else f"{workflow} succeeded"
        )
        messages.append(
            (
                "deploys",
                embed(title=title, color=COLOR_SUCCESS, url=url or None, fields=fields),
            )
        )
    return messages


def deployment_status_messages(event: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    status = event.get("deployment_status") or {}
    deployment = event.get("deployment") or {}
    state = str(status.get("state") or "")
    if state not in {"success", "failure", "error"}:
        return []
    if not is_production_environment(event):
        return []
    env_name = str(status.get("environment") or deployment.get("environment") or "Production")
    sha = short_sha(str(deployment.get("sha") or ""))
    ref = branch_name(str(deployment.get("ref") or ""))
    url = str(
        status.get("log_url")
        or status.get("target_url")
        or deployment.get("url")
        or ""
    )
    environment_url = str(status.get("environment_url") or "")
    fields = [
        ("Environment", env_name),
        ("Branch", ref),
        ("Commit", f"`{sha}`"),
    ]
    if environment_url:
        fields.append(("URL", environment_url))
    failed = state in {"failure", "error"}
    title = (
        "Vercel production deploy failed"
        if failed
        else "Vercel production deploy succeeded"
    )
    channel = "alerts" if failed else "deploys"
    color = COLOR_FAILURE if failed else COLOR_SUCCESS
    return [(channel, embed(title=title, color=color, url=url or environment_url or None, fields=fields))]


def station_alert_fields(station: dict[str, Any], now: datetime) -> list[tuple[str, str]]:
    station_id = str(station.get("station_id") or "")
    label, limit_sec = STATION_SLA.get(station_id, ("unknown", 0))
    last = station.get("last_scheduled_finished_at") or station.get("last_finished_at")
    fields = [
        ("Station", str(station.get("label") or station_id or "unknown")),
        ("Last success", age_label(str(last) if last else None, now)),
        ("Age vs limit", label),
        ("Status", str(station.get("last_scheduled_status") or station.get("lamp") or "—")),
    ]
    error = str(station.get("error_code") or "")
    if error and error != "none":
        fields.append(("Error", error))
    if limit_sec:
        parsed = parse_time(str(last) if last else None)
        if parsed is not None:
            age = max(0, int((now - parsed).total_seconds()))
            fields[2] = ("Age vs limit", f"{age_label(str(last), now)} / {label}")
        else:
            fields[2] = ("Age vs limit", f"never / {label}")
    return fields


def pipeline_observation_messages(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    now: datetime,
) -> list[tuple[str, dict[str, Any]]]:
    messages: list[tuple[str, dict[str, Any]]] = []
    stations_state: dict[str, str] = state.setdefault("stations", {})
    strip = snapshot.get("strip") or {}
    if snapshot.get("load_error") or strip.get("lamp") == "down" and not snapshot.get("stations"):
        previous = stations_state.get("_board")
        if previous != "down":
            messages.append(
                (
                    "alerts",
                    embed(
                        title="Pipeline observation board failed to load",
                        color=COLOR_FAILURE,
                        url=PIPELINE_BOARD_URL,
                        fields=[("Board", PIPELINE_BOARD_URL)],
                    ),
                )
            )
        stations_state["_board"] = "down"
    else:
        if stations_state.get("_board") == "down":
            messages.append(
                (
                    "alerts",
                    embed(
                        title="Pipeline observation board recovered",
                        color=COLOR_SUCCESS,
                        url=PIPELINE_BOARD_URL,
                        fields=[("Board", PIPELINE_BOARD_URL)],
                    ),
                )
            )
        stations_state["_board"] = "ok"

    for station in snapshot.get("stations") or []:
        station_id = str(station.get("station_id") or "")
        if not station_id:
            continue
        lamp = str(station.get("lamp") or "")
        previous = stations_state.get(station_id)
        current = "down" if lamp in ALERT_LAMPS else "ok"
        if current == "down" and previous != "down":
            messages.append(
                (
                    "alerts",
                    embed(
                        title="Scheduled pipeline heartbeat missed",
                        color=COLOR_FAILURE,
                        url=PIPELINE_BOARD_URL,
                        fields=station_alert_fields(station, now),
                    ),
                )
            )
        elif current == "ok" and previous == "down":
            messages.append(
                (
                    "alerts",
                    embed(
                        title="Scheduled pipeline heartbeat recovered",
                        color=COLOR_SUCCESS,
                        url=PIPELINE_BOARD_URL,
                        fields=station_alert_fields(station, now),
                    ),
                )
            )
        stations_state[station_id] = current
    return messages


def api_usage_staleness_messages(
    run: dict[str, Any] | None,
    state: dict[str, Any],
    now: datetime,
) -> list[tuple[str, dict[str, Any]]]:
    created = parse_time(str((run or {}).get("createdAt") or ""))
    age_hours = None if created is None else (now - created).total_seconds() / 3600
    stale = age_hours is None or age_hours > API_USAGE_MAX_AGE_HOURS
    previous = state.get("api_usage_ingest") or "ok"
    current = "down" if stale else "ok"
    state["api_usage_ingest"] = current
    if current == previous:
        return []
    last = "never" if created is None else age_label(str(run.get("createdAt")), now)
    url = str((run or {}).get("url") or PIPELINE_BOARD_URL)
    sha = short_sha(str((run or {}).get("headSha") or ""))
    fields = [
        ("Workflow", API_USAGE_WORKFLOW),
        ("Last run", last),
        ("Age vs limit", f"{last} / {API_USAGE_MAX_AGE_HOURS}h"),
        ("Commit", f"`{sha}`"),
    ]
    if current == "down":
        return [
            (
                "alerts",
                embed(
                    title="Scheduled pipeline heartbeat missed",
                    color=COLOR_FAILURE,
                    url=url,
                    fields=fields,
                ),
            )
        ]
    return [
        (
            "alerts",
            embed(
                title="Scheduled pipeline heartbeat recovered",
                color=COLOR_SUCCESS,
                url=url,
                fields=fields,
            )
        )
    ]


def deliver(
    messages: list[tuple[str, dict[str, Any]]],
    *,
    alerts_url: str,
    deploys_url: str,
    dry_run: bool,
) -> int:
    posted = 0
    for channel, body in messages:
        webhook = alerts_url if channel == "alerts" else deploys_url
        label = f"#{channel}"
        if dry_run:
            print(json.dumps({"channel": channel, "embed": body}, sort_keys=True))
            posted += 1
            continue
        if not webhook:
            print(f"discord notify skipped: {label} webhook unset")
            continue
        try:
            post_webhook(webhook, {"embeds": [body]})
        except DiscordPostError as exc:
            print(f"::warning::discord post failed ({label}): {exc}", file=sys.stderr)
            continue
        print(f"discord notify posted {label}: {body.get('title')}")
        posted += 1
    if not messages:
        print("discord notify: nothing to post")
    return posted


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", type=Path)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "bolewood/collegedata-fyi"))
    parser.add_argument("--state-path", type=Path, default=Path(".discord-notify-state.json"))
    parser.add_argument("--pipeline-url", default=PIPELINE_JSON_URL)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    fetch_snapshot: Callable[[str], dict[str, Any]] = fetch_json,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_gh,
    now: datetime | None = None,
) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    alerts_url = (os.environ.get("DISCORD_ALERTS_WEBHOOK_URL") or "").strip()
    deploys_url = (os.environ.get("DISCORD_DEPLOYS_WEBHOOK_URL") or "").strip()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    clock = now or utc_now()
    secrets = [value for value in (alerts_url, deploys_url) if value]

    try:
        messages: list[tuple[str, dict[str, Any]]] = []
        event: dict[str, Any] = {}
        if args.event_path and args.event_path.exists():
            event = load_json(args.event_path)

        if args.event_name == "workflow_run":
            messages = workflow_run_messages(event, repo=args.repo, token=token, runner=runner)
        elif args.event_name == "deployment_status":
            messages = deployment_status_messages(event)
        elif args.event_name in {"schedule", "workflow_dispatch"}:
            state = load_state(args.state_path)
            try:
                snapshot = fetch_snapshot(args.pipeline_url)
            except Exception as exc:  # noqa: BLE001 — never fail the job
                print(
                    f"::warning::pipeline observation fetch failed: {type(exc).__name__}",
                    file=sys.stderr,
                )
                snapshot = {"load_error": True, "strip": {"lamp": "down"}, "stations": []}
            messages.extend(pipeline_observation_messages(snapshot, state, clock))
            latest = latest_scheduled_run(
                repo=args.repo,
                workflow=API_USAGE_WORKFLOW,
                token=token,
                runner=runner,
            )
            messages.extend(api_usage_staleness_messages(latest, state, clock))
            save_state(args.state_path, state)
        else:
            print(f"discord notify skipped: unsupported event {args.event_name}")
            return 0

        deliver(messages, alerts_url=alerts_url, deploys_url=deploys_url, dry_run=args.dry_run)
        return 0
    except Exception as exc:  # noqa: BLE001 — notifier must never fail the job
        detail = redact(f"{type(exc).__name__}", secrets)
        print(f"::warning::discord notify failed: {detail}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
