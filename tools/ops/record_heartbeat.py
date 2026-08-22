#!/usr/bin/env python3
"""Write a pipeline observation heartbeat via record_pipeline_heartbeat.

Never fails the calling job. A POST/RPC error prints
`::warning::pipeline heartbeat failed for <station>` and exits 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


VALID_STATUSES = {"running", "ok", "error"}
VALID_TRIGGERS = {"schedule", "dispatch", "operator", "cron"}
VALID_ERROR_CODES = {
    "search_provider_rejected",
    "missing_required_secret",
    "heartbeat_summary_malformed",
    "worker_timeout",
    "job_failed",
    "none",
}

# Mirrors public.pipeline_stations. CI asserts workflow --station values
# are a subset of this list.
REGISTRY_STATIONS = (
    "finder_brave",
    "finder_stuck_pdf",
    "finder_landing_hints",
    "archive_enqueue",
    "archive_process",
    "extraction_worker",
    "coverage_refresh",
    "serving_cache_refresh",
    "ipeds_release_probe",
    "schema_build",
    "scorecard_load",
    "directory_enqueue",
    "mirror_ingest",
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def warning_and_ok(station: str, detail: str) -> int:
    print(f"::warning::pipeline heartbeat failed for {station}", file=sys.stderr)
    print(detail, file=sys.stderr)
    return 0


def post_heartbeat(
    *,
    supabase_url: str,
    service_role_key: str,
    station_id: str,
    status: str,
    trigger: str,
    summary: dict[str, Any],
    error_code: str,
    timeout_sec: float = 20,
) -> None:
    endpoint = supabase_url.rstrip("/") + "/rest/v1/rpc/record_pipeline_heartbeat"
    payload = json.dumps({
        "p_station_id": station_id,
        "p_status": status,
        "p_trigger": trigger,
        "p_summary": summary,
        "p_error_code": error_code,
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Prefer": "return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        response.read()


def load_summary(args: argparse.Namespace) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if args.summary:
        parsed = json.loads(args.summary)
        if not isinstance(parsed, dict):
            raise ValueError("--summary must be a JSON object")
        summary.update(parsed)
    if args.summary_json:
        parsed = json.loads(args.summary_json.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("--summary-json must contain a JSON object")
        summary.update(parsed)
    if args.run_url:
        summary["run_url"] = args.run_url
    if args.pr_url:
        summary["pr_url"] = args.pr_url
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", required=True)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--trigger", required=True, choices=sorted(VALID_TRIGGERS))
    parser.add_argument("--summary", default="", help="JSON object string")
    parser.add_argument("--summary-json", type=Path, help="Path to a JSON object")
    parser.add_argument("--error-code", default="none", choices=sorted(VALID_ERROR_CODES))
    parser.add_argument("--run-url")
    parser.add_argument("--pr-url")
    parser.add_argument("--env", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)

    station = args.station
    if station not in REGISTRY_STATIONS:
        return warning_and_ok(station, f"unknown station_id {station}")

    env = load_env(args.env)
    supabase_url = os.environ.get("SUPABASE_URL") or env.get("SUPABASE_URL") or ""
    service_role_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )
    if not supabase_url or not service_role_key:
        return warning_and_ok(station, "missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")

    try:
        summary = load_summary(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return warning_and_ok(station, f"invalid summary: {exc}")

    try:
        post_heartbeat(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            station_id=station,
            status=args.status,
            trigger=args.trigger,
            summary=summary,
            error_code=args.error_code,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        return warning_and_ok(station, str(exc))
    except Exception as exc:  # noqa: BLE001 — heartbeat must never fail the job
        return warning_and_ok(station, f"{type(exc).__name__}: {exc}")

    print(f"pipeline heartbeat wrote {station} status={args.status} trigger={args.trigger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
