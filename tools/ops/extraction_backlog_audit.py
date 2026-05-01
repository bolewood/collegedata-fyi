#!/usr/bin/env python3
"""Audit extraction backlog after archive/directory drains.

This is an operator check, not CI. It reads live Supabase state, reports the
current `cds_documents.extraction_status='extraction_pending'` backlog, and
optionally checks the GitHub Actions extraction worker's last successful run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ops import directory_enqueue_batches as batches


DEFAULT_OUT_DIR = Path("scratch/extraction-backlog-audits")
DEFAULT_GITHUB_REPO = "bolewood/collegedata-fyi"
DEFAULT_GITHUB_WORKFLOW = "Ops extraction worker"
HIGH_ENROLLMENT_THRESHOLD = 10_000


@dataclass(frozen=True)
class AuditThresholds:
    max_pending_age_hours: float
    max_pending_count: int | None
    max_github_success_age_hours: float | None
    fail_on_pending_growth: bool


def parse_supabase_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.replace("Z", "+00:00")
    match = re.match(r"(.*\.)(\d+)([+-]\d\d:\d\d)$", value)
    if match:
        value = match.group(1) + match.group(2).ljust(6, "0")[:6] + match.group(3)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hours_between(start: datetime | None, end: datetime) -> float | None:
    if start is None:
        return None
    return max(0.0, (end - start).total_seconds() / 3600)


def fetch_pending_documents(client: Any) -> list[dict[str, Any]]:
    return batches.paged_rest_get(
        client,
        "cds_documents",
        {
            "select": (
                "id,school_id,cds_year,detected_year,source_format,"
                "source_provenance,extraction_status,discovered_at,"
                "created_at,updated_at,source_url,ipeds_id"
            ),
            "extraction_status": "eq.extraction_pending",
            "order": "created_at.asc",
        },
    )


def fetch_directory_metadata(client: Any, school_ids: list[str]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    unique_ids = sorted({school_id for school_id in school_ids if school_id})
    for index in range(0, len(unique_ids), 100):
        chunk = unique_ids[index:index + 100]
        rows = client.rest_get(
            "institution_directory",
            {
                "select": "school_id,school_name,state,undergraduate_enrollment,website_url",
                "school_id": f"in.({','.join(chunk)})",
                "order": "school_id.asc",
            },
        )
        metadata.update({str(row.get("school_id")): row for row in rows if row.get("school_id")})
    return metadata


def pending_document_key(row: dict[str, Any]) -> datetime:
    return parse_supabase_timestamp(str(row.get("created_at") or "")) or datetime.max.replace(tzinfo=timezone.utc)


def enriched_pending_rows(
    rows: list[dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        created_at = parse_supabase_timestamp(str(row.get("created_at") or ""))
        school = metadata.get(str(row.get("school_id") or ""), {})
        enrollment = school.get("undergraduate_enrollment")
        try:
            enrollment_int = int(enrollment)
        except (TypeError, ValueError):
            enrollment_int = 0
        enriched.append({
            "id": row.get("id"),
            "school_id": row.get("school_id"),
            "school_name": school.get("school_name"),
            "state": school.get("state"),
            "undergraduate_enrollment": enrollment_int or None,
            "cds_year": row.get("cds_year"),
            "detected_year": row.get("detected_year"),
            "source_format": row.get("source_format") or "unknown",
            "source_provenance": row.get("source_provenance"),
            "created_at": row.get("created_at"),
            "age_hours": hours_between(created_at, now),
            "source_url": row.get("source_url"),
        })
    return enriched


def summarize_pending_backlog(
    rows: list[dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    *,
    now: datetime | None = None,
    sample_limit: int = 15,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    enriched = enriched_pending_rows(rows, metadata, now=current_time)
    oldest = sorted(enriched, key=lambda row: row.get("age_hours") or -1, reverse=True)
    high_signal = sorted(
        (
            row for row in enriched
            if (row.get("undergraduate_enrollment") or 0) >= HIGH_ENROLLMENT_THRESHOLD
        ),
        key=lambda row: (row.get("undergraduate_enrollment") or 0, row.get("age_hours") or 0),
        reverse=True,
    )
    by_format = Counter(row.get("source_format") or "unknown" for row in enriched)
    by_provenance = Counter(row.get("source_provenance") or "unknown" for row in enriched)
    by_school = Counter(str(row.get("school_id") or "") for row in enriched)
    oldest_age = oldest[0].get("age_hours") if oldest else 0.0
    oldest_created = oldest[0].get("created_at") if oldest else None

    return {
        "generated_at": current_time.isoformat().replace("+00:00", "Z"),
        "pending_count": len(enriched),
        "oldest_pending_age_hours": round(float(oldest_age or 0.0), 2),
        "oldest_pending_created_at": oldest_created,
        "by_source_format": dict(sorted(by_format.items())),
        "by_source_provenance": dict(sorted(by_provenance.items())),
        "top_schools_by_pending_count": [
            {"school_id": school_id, "pending_count": count}
            for school_id, count in by_school.most_common(10)
            if school_id
        ],
        "oldest_pending": oldest[:sample_limit],
        "high_enrollment_pending": high_signal[:sample_limit],
    }


def fetch_github_workflow_runs(
    *,
    repo: str,
    workflow: str,
    limit: int,
    gh_bin: str = "gh",
) -> dict[str, Any]:
    if not shutil.which(gh_bin):
        return {"available": False, "error": f"{gh_bin} not found"}

    command = [
        gh_bin,
        "run",
        "list",
        "--repo",
        repo,
        "--workflow",
        workflow,
        "--limit",
        str(limit),
        "--json",
        "databaseId,status,conclusion,createdAt,updatedAt,event,headBranch,url",
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    if completed.returncode != 0:
        return {"available": False, "error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        runs = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {"available": False, "error": f"gh returned non-JSON output: {exc}"}
    return {"available": True, "runs": runs}


def summarize_github_runs(raw: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    if not raw.get("available"):
        return {
            "available": False,
            "error": raw.get("error") or "unavailable",
            "last_success": None,
            "last_success_age_hours": None,
            "latest_run": None,
        }

    runs = raw.get("runs") or []
    latest = runs[0] if runs else None
    successful = next((run for run in runs if run.get("conclusion") == "success"), None)
    success_at = parse_supabase_timestamp(str(successful.get("updatedAt") or successful.get("createdAt") or "")) if successful else None
    age = hours_between(success_at, current_time)
    return {
        "available": True,
        "last_success": successful,
        "last_success_age_hours": round(age, 2) if age is not None else None,
        "latest_run": latest,
    }


def evaluate_gates(
    audit: dict[str, Any],
    thresholds: AuditThresholds,
    *,
    previous_pending_count: int | None = None,
) -> list[str]:
    failures: list[str] = []
    pending_count = int(audit.get("pending_count") or 0)
    oldest_age = float(audit.get("oldest_pending_age_hours") or 0.0)

    if thresholds.max_pending_count is not None and pending_count > thresholds.max_pending_count:
        failures.append(
            f"pending_count {pending_count} exceeds max {thresholds.max_pending_count}"
        )
    if pending_count and oldest_age > thresholds.max_pending_age_hours:
        failures.append(
            f"oldest pending row is {oldest_age:.1f}h old; max is {thresholds.max_pending_age_hours:.1f}h"
        )
    if thresholds.fail_on_pending_growth and previous_pending_count is not None and pending_count > previous_pending_count:
        failures.append(
            f"pending_count grew from {previous_pending_count} to {pending_count}"
        )

    github = audit.get("github_actions") or {}
    github_max = thresholds.max_github_success_age_hours
    if github_max is not None:
        if not github.get("available"):
            failures.append(f"GitHub workflow status unavailable: {github.get('error') or 'unknown error'}")
        elif github.get("last_success_age_hours") is None:
            failures.append("GitHub workflow has no successful runs in the inspected window")
        elif float(github["last_success_age_hours"]) > github_max:
            failures.append(
                f"GitHub workflow last success is {float(github['last_success_age_hours']):.1f}h old; "
                f"max is {github_max:.1f}h"
            )
    return failures


def build_audit(
    client: Any,
    *,
    sample_limit: int,
    include_github: bool,
    github_repo: str,
    github_workflow: str,
    github_limit: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    pending = fetch_pending_documents(client)
    metadata = fetch_directory_metadata(client, [str(row.get("school_id") or "") for row in pending])
    audit = summarize_pending_backlog(pending, metadata, now=current_time, sample_limit=sample_limit)
    if include_github:
        github_raw = fetch_github_workflow_runs(repo=github_repo, workflow=github_workflow, limit=github_limit)
        audit["github_actions"] = summarize_github_runs(github_raw, now=current_time)
    return audit


def write_audit(out_dir: Path, audit: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = str(audit.get("generated_at") or datetime.now(timezone.utc).isoformat())
    safe_stamp = stamp.replace(":", "").replace("-", "").replace("+0000", "Z")
    path = out_dir / f"extraction-backlog-{safe_stamp}.json"
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def print_audit(audit: dict[str, Any], failures: list[str], path: Path | None = None) -> None:
    print("\nExtraction backlog audit")
    print(f"  pending_count: {audit.get('pending_count')}")
    print(f"  oldest_pending_age_hours: {audit.get('oldest_pending_age_hours')}")
    print(f"  by_source_format: {json.dumps(audit.get('by_source_format') or {}, sort_keys=True)}")
    print(f"  high_enrollment_pending: {len(audit.get('high_enrollment_pending') or [])} sampled")

    github = audit.get("github_actions")
    if github:
        if github.get("available"):
            latest = github.get("latest_run") or {}
            print(
                "  github_last_success_age_hours: "
                f"{github.get('last_success_age_hours')} "
                f"(latest={latest.get('conclusion') or latest.get('status')})"
            )
        else:
            print(f"  github_status: unavailable ({github.get('error')})")

    if audit.get("oldest_pending"):
        print("\nOldest pending rows")
        for row in audit["oldest_pending"][:10]:
            name = row.get("school_name") or row.get("school_id")
            print(
                f"  {row.get('age_hours'):.1f}h  {name}  "
                f"{row.get('cds_year')}  {row.get('source_format')}"
            )

    if audit.get("high_enrollment_pending"):
        print("\nHigh-enrollment pending rows")
        for row in audit["high_enrollment_pending"][:10]:
            name = row.get("school_name") or row.get("school_id")
            print(
                f"  {row.get('undergraduate_enrollment') or 0:>6}  "
                f"{row.get('age_hours'):.1f}h  {name}  {row.get('cds_year')}"
            )

    if failures:
        print("\nGate failures")
        for failure in failures:
            print(f"  - {failure}")
    if path:
        print(f"\nWrote JSON audit: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env", help="Path to .env containing Supabase credentials")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directory for JSON audit reports")
    parser.add_argument("--sample-limit", type=int, default=15)
    parser.add_argument("--max-pending-age-hours", type=float, default=24.0)
    parser.add_argument("--max-pending-count", type=int)
    parser.add_argument("--previous-pending-count", type=int)
    parser.add_argument("--fail-on-pending-growth", action="store_true")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--github-repo", default=DEFAULT_GITHUB_REPO)
    parser.add_argument("--github-workflow", default=DEFAULT_GITHUB_WORKFLOW)
    parser.add_argument("--github-limit", type=int, default=20)
    parser.add_argument("--max-github-success-age-hours", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Print the full audit JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write the JSON report to scratch/")
    return parser


def main(argv: list[str] | None = None) -> int:
    batches.configure_output_buffering()
    args = build_parser().parse_args(argv)
    try:
        supabase_url, service_key = batches.require_supabase_credentials(Path(args.env))
        client = batches.SupabaseClient(supabase_url, service_key)
        audit = build_audit(
            client,
            sample_limit=args.sample_limit,
            include_github=not args.skip_github,
            github_repo=args.github_repo,
            github_workflow=args.github_workflow,
            github_limit=args.github_limit,
        )
        github_threshold = None if args.skip_github else args.max_github_success_age_hours
        failures = evaluate_gates(
            audit,
            AuditThresholds(
                max_pending_age_hours=args.max_pending_age_hours,
                max_pending_count=args.max_pending_count,
                max_github_success_age_hours=github_threshold,
                fail_on_pending_growth=args.fail_on_pending_growth,
            ),
            previous_pending_count=args.previous_pending_count,
        )
        path = None if args.no_write else write_audit(Path(args.out_dir), audit)
        if args.json:
            print(json.dumps({"audit": audit, "gate_failures": failures}, indent=2, sort_keys=True))
        else:
            print_audit(audit, failures, path)
        return 1 if failures else 0
    except (batches.OpsError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
