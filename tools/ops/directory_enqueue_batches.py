#!/usr/bin/env python3
"""Operator workflow for controlled directory-enqueue batches.

The script intentionally wraps existing Edge Functions instead of adding any
new automatic discovery path. By default it only performs dry-runs; pass
--apply to enqueue and drain staged batches.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


ACTIVE_QUEUE_STATUSES = {"ready", "processing"}
TRANSIENT_OUTCOME = "transient"
PERMANENT_OTHER_OUTCOME = "permanent_other"
WATCH_STATUSES = [
    "not_checked",
    "no_public_cds_found",
    "source_not_automatically_accessible",
    "cds_available_current",
    "extract_failed",
]
DEFAULT_BATCHES = [25, 75, 150, 250]


class OpsError(RuntimeError):
    """Raised for operator-visible failures that should stop the rollout."""


def configure_output_buffering() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True)


@dataclass(frozen=True)
class DirectoryEnqueueOptions:
    min_enrollment: int | None = None
    state: str | None = None
    force_recheck: bool = False
    uniform_cooldown_days: int | None = None


class SupabaseClient:
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    def rest_get(self, table: str, params: dict[str, str], *, page: tuple[int, int] | None = None) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(params)
        url = f"{self.supabase_url}/rest/v1/{table}?{query}"
        headers = self._headers()
        if page is not None:
            headers["Range"] = f"{page[0]}-{page[1]}"
            headers["Prefer"] = "count=exact"
        return self._request_json("GET", url, headers=headers)

    def post_function(self, name: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"{self.supabase_url}/functions/v1/{name}"
        if query:
            url = f"{url}?{query}"
        return self._request_json("POST", url, headers=self._headers())

    def post_function_json(self, name: str, body: dict[str, Any], params: dict[str, str] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.supabase_url}/functions/v1/{name}"
        if query:
            url = f"{url}?{query}"
        return self._request_json("POST", url, headers=self._headers(), body=json.dumps(body).encode("utf-8"))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
            "Content-Type": "application/json",
        }

    def _request_json(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None) -> Any:
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OpsError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise OpsError(f"{method} {url} failed: {exc.reason}") from exc
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise OpsError(f"{method} {url} returned non-JSON response: {body[:500]}") from exc


class JsonlLogger:
    def __init__(self, out_dir: Path, started_at: datetime | None = None) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = (started_at or utc_now()).strftime("%Y%m%dT%H%M%SZ")
        self.path = out_dir / f"directory-enqueue-{stamp}.jsonl"

    def write(self, event: str, **payload: Any) -> None:
        record = {
            "ts": utc_now().isoformat().replace("+00:00", "Z"),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def require_supabase_credentials(env_path: Path) -> tuple[str, str]:
    file_env = load_env_file(env_path)
    supabase_url = file_env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    service_key = file_env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise OpsError(
            f"Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. Add them to {env_path} or export them."
        )
    return supabase_url, service_key


def directory_enqueue_params(limit: int, options: DirectoryEnqueueOptions, *, dry_run: bool) -> dict[str, str]:
    params = {"limit": str(limit)}
    if dry_run:
        params["dry_run"] = "true"
    if options.min_enrollment is not None:
        params["min_enrollment"] = str(options.min_enrollment)
    if options.state:
        params["state"] = options.state
    if options.force_recheck:
        params["force_recheck"] = "true"
    if options.uniform_cooldown_days is not None:
        params["cooldown_days"] = str(options.uniform_cooldown_days)
    return params


def call_directory_enqueue(
    client: Any,
    limit: int,
    options: DirectoryEnqueueOptions,
    *,
    dry_run: bool,
    run_id: str | None = None,
) -> dict[str, Any]:
    params = directory_enqueue_params(limit, options, dry_run=dry_run)
    if run_id:
        params["run_id"] = run_id
    return client.post_function("directory-enqueue", params)


def refresh_coverage(client: Any) -> dict[str, Any]:
    return client.post_function("refresh-coverage", {})


def fetch_coverage_histogram(client: Any) -> dict[str, int]:
    rows = paged_rest_get(
        client,
        "institution_cds_coverage",
        {
            "select": "coverage_status",
            "order": "ipeds_id.asc",
        },
    )
    return dict(Counter(row.get("coverage_status") for row in rows if row.get("coverage_status")))


def fetch_top_not_checked(client: Any, limit: int) -> list[dict[str, Any]]:
    return client.rest_get(
        "institution_cds_coverage",
        {
            "select": "ipeds_id,school_id,school_name,state,undergraduate_enrollment",
            "coverage_status": "eq.not_checked",
            "order": "undergraduate_enrollment.desc.nullslast,school_name.asc",
            "limit": str(limit),
        },
    )


def fetch_in_flight_directory_rows(client: Any) -> list[dict[str, Any]]:
    return client.rest_get(
        "archive_queue",
        {
            "select": "school_id,school_name,status,enqueued_run_id,enqueued_at,claimed_at",
            "source": "eq.institution_directory",
            "status": "in.(ready,processing)",
            "order": "enqueued_at.asc",
        },
    )


def fetch_queue_rows(client: Any, run_id: str) -> list[dict[str, Any]]:
    return paged_rest_get(
        client,
        "archive_queue",
        {
            "select": "school_id,school_name,cds_url_hint,status,last_outcome,processed_at,attempts,last_error",
            "source": "eq.institution_directory",
            "enqueued_run_id": f"eq.{run_id}",
            "order": "school_name.asc",
        },
    )


def fetch_sample_schools(client: Any, school_ids: Iterable[str]) -> list[dict[str, Any]]:
    ids = [school_id for school_id in school_ids if school_id]
    if not ids:
        return []
    return client.rest_get(
        "institution_directory",
        {
            "select": "school_id,school_name,state,undergraduate_enrollment",
            "school_id": f"in.({','.join(ids)})",
            "order": "undergraduate_enrollment.desc.nullslast,school_name.asc",
        },
    )


def paged_rest_get(client: Any, table: str, params: dict[str, str], *, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for start in range(0, 50_000, page_size):
        page = client.rest_get(table, params, page=(start, start + page_size - 1))
        rows.extend(page)
        if len(page) < page_size:
            return rows
    raise OpsError(f"Refusing to read more than 50,000 rows from {table}")


def summarize_queue_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(row.get("status") for row in rows if row.get("status"))
    outcomes = Counter(row.get("last_outcome") for row in rows if row.get("last_outcome"))
    active = sum(statuses.get(status, 0) for status in ACTIVE_QUEUE_STATUSES)
    terminal = len(rows) - active
    transient = outcomes.get(TRANSIENT_OUTCOME, 0)
    permanent_other = outcomes.get(PERMANENT_OTHER_OUTCOME, 0)
    return {
        "total": len(rows),
        "active": active,
        "terminal": terminal,
        "statuses": dict(statuses),
        "last_outcomes": dict(outcomes),
        "transient_outcomes": transient,
        "transient_outcome_rate": transient / len(rows) if rows else 0.0,
        "permanent_other_outcomes": permanent_other,
        "permanent_other_outcome_rate": permanent_other / len(rows) if rows else 0.0,
        "unexpected_outcomes": transient + permanent_other,
        "unexpected_outcome_rate": (transient + permanent_other) / len(rows) if rows else 0.0,
    }


def poll_until_drained(
    client: Any,
    run_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
    stall_timeout_seconds: int,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    logger: JsonlLogger | None = None,
) -> dict[str, Any]:
    started = now()
    last_progress_at = started
    last_terminal = -1

    while True:
        try:
            rows = fetch_queue_rows(client, run_id)
        except OpsError as exc:
            if logger:
                logger.write("poll_error", run_id=run_id, error=str(exc))
            elapsed = now() - started
            stalled = now() - last_progress_at
            if elapsed >= timeout_seconds:
                raise TimeoutError(f"Timed out waiting for run_id={run_id} after poll errors") from exc
            if stalled >= stall_timeout_seconds:
                raise TimeoutError(f"Queue polling stalled for run_id={run_id} after {int(stalled)} seconds") from exc
            print(f"Polling read failed for run_id={run_id}; retrying: {exc}")
            sleep(poll_interval_seconds)
            continue

        summary = summarize_queue_rows(rows)
        if logger:
            logger.write("poll", run_id=run_id, queue=summary)

        if summary["active"] == 0:
            return {"rows": rows, "summary": summary}

        terminal = int(summary["terminal"])
        if terminal > last_terminal:
            last_terminal = terminal
            last_progress_at = now()

        elapsed = now() - started
        stalled = now() - last_progress_at
        if elapsed >= timeout_seconds:
            raise TimeoutError(f"Timed out waiting for run_id={run_id} after {int(elapsed)} seconds")
        if stalled >= stall_timeout_seconds:
            raise TimeoutError(f"Queue stalled for run_id={run_id} after {int(stalled)} seconds without progress")

        print_queue_progress(run_id, summary)
        sleep(poll_interval_seconds)


def histogram_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    statuses = sorted(set(before) | set(after))
    return {status: after.get(status, 0) - before.get(status, 0) for status in statuses}


def watched_histogram_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    delta = histogram_delta(before, after)
    return {status: delta.get(status, 0) for status in WATCH_STATUSES}


def assert_histogram_plausible(before: dict[str, int], after: dict[str, int]) -> None:
    before_total = sum(before.values())
    after_total = sum(after.values())
    if before_total and after_total and abs(after_total - before_total) > 5:
        raise OpsError(f"Coverage row count changed implausibly: before={before_total}, after={after_total}")
    if before.get("cds_available_current", 0) > 0 and after.get("cds_available_current", 0) == 0:
        raise OpsError("Coverage histogram lost all cds_available_current rows")
    if before.get("not_checked", 0) > 0 and after.get("not_checked", 0) == 0:
        raise OpsError("Coverage histogram lost all not_checked rows")


def enforce_outcome_gates(
    summary: dict[str, Any],
    *,
    max_transient_rate: float,
    max_permanent_other_rate: float,
    stop_on_transient_gate: bool,
) -> None:
    total = int(summary.get("total", 0))
    if not total:
        return

    permanent_other_rate = float(summary.get("permanent_other_outcome_rate", 0.0))
    if permanent_other_rate > max_permanent_other_rate:
        raise OpsError(
            f"permanent_other outcomes exceeded gate: {permanent_other_rate:.1%} > "
            f"{max_permanent_other_rate:.1%} "
            f"({summary.get('permanent_other_outcomes', 0)} of {total})"
        )

    transient_rate = float(summary.get("transient_outcome_rate", 0.0))
    if transient_rate > max_transient_rate:
        message = (
            f"transient outcomes exceeded warning gate: {transient_rate:.1%} > "
            f"{max_transient_rate:.1%} ({summary.get('transient_outcomes', 0)} of {total})"
        )
        if stop_on_transient_gate:
            raise OpsError(message)
        print(f"WARNING: {message}")


def run_batch(
    client: Any,
    *,
    limit: int,
    apply: bool,
    options: DirectoryEnqueueOptions,
    logger: JsonlLogger,
    timeout_seconds: int,
    poll_interval_seconds: int,
    stall_timeout_seconds: int,
    max_transient_rate: float,
    max_permanent_other_rate: float,
    stop_on_transient_gate: bool,
) -> dict[str, Any]:
    print(f"\n== Batch limit={limit} ==")
    before = fetch_coverage_histogram(client)
    logger.write("coverage_before", limit=limit, histogram=before)
    print_histogram("Coverage before", before)

    dry_run = call_directory_enqueue(client, limit, options, dry_run=True)
    sample_ids = dry_run.get("sample_school_ids") or []
    sample = fetch_sample_schools(client, sample_ids[:10])
    dry_run_report = {
        "limit": limit,
        "mode": dry_run.get("mode"),
        "run_id": dry_run.get("run_id"),
        "would_enqueue": dry_run.get("would_enqueue", 0),
        "considered": dry_run.get("considered"),
        "skipped": dry_run.get("skipped", {}),
        "sample_schools": sample,
    }
    logger.write("dry_run", **dry_run_report)
    print_json("Dry-run", dry_run_report)

    if not apply:
        print("Dry-run only. Pass --apply to enqueue and drain this batch.")
        return {"dry_run": dry_run_report, "applied": False}

    if int(dry_run.get("would_enqueue") or 0) == 0:
        print("No selected schools passed the dry-run filters; skipping real enqueue.")
        return {"dry_run": dry_run_report, "applied": False, "reason": "empty_dry_run"}

    enqueue = call_directory_enqueue(
        client,
        limit,
        options,
        dry_run=False,
        run_id=str(dry_run.get("run_id") or ""),
    )
    run_id = str(enqueue.get("run_id") or "")
    if not run_id:
        raise OpsError(f"directory-enqueue did not return run_id: {enqueue}")

    enqueue_report = {
        "limit": limit,
        "run_id": run_id,
        "enqueued": enqueue.get("enqueued", 0),
        "considered": enqueue.get("considered"),
        "skipped_existing": enqueue.get("skipped_existing", 0),
        "skipped": enqueue.get("skipped", {}),
    }
    logger.write("enqueue", **enqueue_report)
    print_json("Enqueue", enqueue_report)

    drained = poll_until_drained(
        client,
        run_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        stall_timeout_seconds=stall_timeout_seconds,
        logger=logger,
    )
    queue_summary = drained["summary"]
    logger.write("drained", run_id=run_id, queue=queue_summary)
    print_json("Queue drained", queue_summary)

    refresh = refresh_coverage(client)
    after = refresh.get("coverage_status_histogram") or fetch_coverage_histogram(client)
    assert_histogram_plausible(before, after)
    delta = watched_histogram_delta(before, after)
    refresh_report = {
        "run_id": run_id,
        "rows_written": refresh.get("rows_written"),
        "refresh_duration_ms": refresh.get("refresh_duration_ms"),
        "total_duration_ms": refresh.get("total_duration_ms"),
        "coverage_after": after,
        "watched_delta": delta,
    }
    logger.write("refresh", **refresh_report)
    print_histogram("Coverage after", after)
    print_json("Watched status delta", delta)
    enforce_outcome_gates(
        queue_summary,
        max_transient_rate=max_transient_rate,
        max_permanent_other_rate=max_permanent_other_rate,
        stop_on_transient_gate=stop_on_transient_gate,
    )

    return {
        "dry_run": dry_run_report,
        "enqueue": enqueue_report,
        "queue": queue_summary,
        "refresh": refresh_report,
        "applied": True,
    }


def resume_run(
    client: Any,
    *,
    run_id: str,
    logger: JsonlLogger,
    timeout_seconds: int,
    poll_interval_seconds: int,
    stall_timeout_seconds: int,
    max_transient_rate: float,
    max_permanent_other_rate: float,
    stop_on_transient_gate: bool,
) -> dict[str, Any]:
    print(f"\n== Resume run_id={run_id} ==")
    before = fetch_coverage_histogram(client)
    logger.write("resume_coverage_before", run_id=run_id, histogram=before)
    print_histogram("Coverage before resume refresh", before)

    drained = poll_until_drained(
        client,
        run_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        stall_timeout_seconds=stall_timeout_seconds,
        logger=logger,
    )
    queue_summary = drained["summary"]
    logger.write("resume_drained", run_id=run_id, queue=queue_summary)
    print_json("Queue drained", queue_summary)

    refresh = refresh_coverage(client)
    after = refresh.get("coverage_status_histogram") or fetch_coverage_histogram(client)
    assert_histogram_plausible(before, after)
    delta = watched_histogram_delta(before, after)
    refresh_report = {
        "run_id": run_id,
        "rows_written": refresh.get("rows_written"),
        "refresh_duration_ms": refresh.get("refresh_duration_ms"),
        "total_duration_ms": refresh.get("total_duration_ms"),
        "coverage_after": after,
        "watched_delta": delta,
    }
    logger.write("resume_refresh", **refresh_report)
    print_histogram("Coverage after", after)
    print_json("Watched status delta", delta)
    enforce_outcome_gates(
        queue_summary,
        max_transient_rate=max_transient_rate,
        max_permanent_other_rate=max_permanent_other_rate,
        stop_on_transient_gate=stop_on_transient_gate,
    )

    return {"run_id": run_id, "queue": queue_summary, "refresh": refresh_report}


def print_queue_progress(run_id: str, summary: dict[str, Any]) -> None:
    statuses = summary.get("statuses", {})
    print(
        f"Waiting for run_id={run_id}: "
        f"active={summary.get('active', 0)} terminal={summary.get('terminal', 0)} statuses={statuses}"
    )


def print_histogram(label: str, histogram: dict[str, int]) -> None:
    print(f"\n{label}")
    for status, count in sorted(histogram.items()):
        print(f"  {status}: {count}")


def print_json(label: str, payload: Any) -> None:
    print(f"\n{label}")
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_batches(raw: str | None, single_limit: int | None) -> list[int]:
    if single_limit is not None:
        if single_limit < 0:
            raise ValueError("limit must be a non-negative integer")
        return [single_limit]
    if not raw:
        return DEFAULT_BATCHES
    batches = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not batches or any(limit < 0 for limit in batches):
        raise ValueError("batches must be comma-separated non-negative integers")
    return batches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env", help="Path to .env containing Supabase credentials")
    parser.add_argument("--out-dir", default="scratch/directory-enqueue-runs", help="Directory for JSONL run logs")
    parser.add_argument("--limit", type=int, help="Run one batch with this explicit limit")
    parser.add_argument("--batches", help="Comma-separated staged limits; default: 25,75,150,250")
    parser.add_argument("--apply", action="store_true", help="Actually enqueue, poll, refresh, and gate each batch")
    parser.add_argument("--resume-run-id", help="Poll, refresh, and gate an already-enqueued directory run")
    parser.add_argument("--min-enrollment", type=int, help="Pass min_enrollment through to directory-enqueue")
    parser.add_argument("--state", help="Pass a two-letter state filter through to directory-enqueue")
    parser.add_argument("--force-recheck", action="store_true", help="Pass force_recheck=true; do not use for first top-500 pass")
    parser.add_argument("--uniform-cooldown-days", type=int, help="Override outcome cooldowns")
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--timeout-minutes", type=int, default=360)
    parser.add_argument("--stall-timeout-minutes", type=int, default=20)
    parser.add_argument("--max-transient-rate", type=float, default=0.25, help="Warn when terminal transient outcomes exceed this rate")
    parser.add_argument("--max-permanent-other-rate", type=float, default=0.05, help="Stop when terminal permanent_other outcomes exceed this rate")
    parser.add_argument("--stop-on-transient-gate", action="store_true", help="Treat --max-transient-rate as a stop gate instead of a warning")
    parser.add_argument("--baseline-sample-size", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_buffering()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.force_recheck:
            print("WARNING: --force-recheck bypasses cooldowns and is not for the first top-500 pass.", file=sys.stderr)

        batches = parse_batches(args.batches, args.limit)
        supabase_url, service_key = require_supabase_credentials(Path(args.env))
        client = SupabaseClient(supabase_url, service_key)
        logger = JsonlLogger(Path(args.out_dir))
        options = DirectoryEnqueueOptions(
            min_enrollment=args.min_enrollment,
            state=args.state,
            force_recheck=args.force_recheck,
            uniform_cooldown_days=args.uniform_cooldown_days,
        )

        if args.resume_run_id:
            report = resume_run(
                client,
                run_id=args.resume_run_id,
                logger=logger,
                timeout_seconds=args.timeout_minutes * 60,
                poll_interval_seconds=args.poll_interval_seconds,
                stall_timeout_seconds=args.stall_timeout_minutes * 60,
                max_transient_rate=args.max_transient_rate,
                max_permanent_other_rate=args.max_permanent_other_rate,
                stop_on_transient_gate=args.stop_on_transient_gate,
            )
            logger.write("completed", reports=[report])
            print(f"\nCompleted. JSONL log: {logger.path}")
            return 0

        baseline = {
            "coverage": fetch_coverage_histogram(client),
            "top_not_checked": fetch_top_not_checked(client, args.baseline_sample_size),
            "in_flight_directory_rows": fetch_in_flight_directory_rows(client),
            "batches": batches,
            "apply": args.apply,
            "options": {
                "min_enrollment": options.min_enrollment,
                "state": options.state,
                "force_recheck": options.force_recheck,
                "uniform_cooldown_days": options.uniform_cooldown_days,
            },
        }
        logger.write("baseline", **baseline)
        print(f"Writing JSONL log to {logger.path}")
        print_histogram("Baseline coverage", baseline["coverage"])
        print_json("Top not_checked sample", baseline["top_not_checked"])
        print_json("Current in-flight directory rows", baseline["in_flight_directory_rows"])

        reports = []
        for limit in batches:
            reports.append(
                run_batch(
                    client,
                    limit=limit,
                    apply=args.apply,
                    options=options,
                    logger=logger,
                    timeout_seconds=args.timeout_minutes * 60,
                    poll_interval_seconds=args.poll_interval_seconds,
                    stall_timeout_seconds=args.stall_timeout_minutes * 60,
                    max_transient_rate=args.max_transient_rate,
                    max_permanent_other_rate=args.max_permanent_other_rate,
                    stop_on_transient_gate=args.stop_on_transient_gate,
                )
            )

        logger.write("completed", reports=reports)
        print(f"\nCompleted. JSONL log: {logger.path}")
        return 0
    except (OpsError, TimeoutError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
