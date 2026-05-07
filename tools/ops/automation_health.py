#!/usr/bin/env python3
"""One-command health check for automated archive/extraction workers."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENV = Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/.env")
DEFAULT_POOLER_URL = Path("supabase/.temp/pooler-url")
DEFAULT_REPO = "bolewood/collegedata-fyi"
CRON_JOBS = (
    "archive-enqueue-daily",
    "archive-process-every-30s",
    "refresh-coverage-every-15min",
)


class HealthError(RuntimeError):
    """Raised when the health check cannot inspect production state."""


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hours_since(raw: str | None, now: datetime) -> float | None:
    parsed = parse_time(raw)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600)


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def pooler_dsn(env: dict[str, str], pooler_url_path: Path) -> str:
    database_url = env.get("DATABASE_URL")
    password = env.get("SUPABASE_DB_PASSWORD")
    if not password:
        raise HealthError("SUPABASE_DB_PASSWORD is required for cron/net health queries.")
    if pooler_url_path.exists():
        parsed = urllib.parse.urlparse(pooler_url_path.read_text(encoding="utf-8").strip())
    elif database_url:
        parsed = urllib.parse.urlparse(database_url)
    else:
        raise HealthError(f"Missing {pooler_url_path} and DATABASE_URL.")
    user = parsed.username or "postgres"
    encoded_password = urllib.parse.quote(password, safe="")
    port = parsed.port or 5432
    return f"{parsed.scheme}://{user}:{encoded_password}@{parsed.hostname}:{port}{parsed.path}?sslmode=require"


def http_content_category(content: str | None, status_code: int | None) -> str:
    body = content or ""
    if "RPC returned row with null claimed_at" in body:
        return "archive_process_null_claim"
    if "IDLE_TIMEOUT" in body or "Request idle timeout" in body:
        return "edge_idle_timeout"
    if "queue_drained" in body:
        return "archive_process_queue_drained"
    if "attempt_budget_exhausted_before_processing" in body:
        return "archive_process_attempt_budget_exhausted"
    if "rows_written" in body and "coverage_status_histogram" in body:
        return "refresh_coverage"
    if status_code and 200 <= status_code < 300:
        return "success_other"
    return "error_other"


def fetch_db_health(dsn: str, *, hours: int) -> dict[str, Any]:
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise HealthError("Install psycopg first: python3 -m pip install 'psycopg[binary]'") from exc

    queries: dict[str, tuple[str, tuple[Any, ...]]] = {
        "cron_jobs": (
            """
            select jobid, jobname, schedule, active
            from cron.job
            where jobname = any(%s)
            order by jobname
            """,
            (list(CRON_JOBS),),
        ),
        "cron_recent_summary": (
            """
            select j.jobname, r.status, count(*) as n,
                   max(r.start_time) as last_start, max(r.end_time) as last_end
            from cron.job_run_details r
            join cron.job j on j.jobid = r.jobid
            where r.start_time >= now() - (%s || ' hours')::interval
              and j.jobname = any(%s)
            group by j.jobname, r.status
            order by j.jobname, r.status
            """,
            (hours, list(CRON_JOBS)),
        ),
        "cron_recent_failures": (
            """
            select j.jobname, r.status, r.start_time, r.end_time,
                   left(coalesce(r.return_message, ''), 500) as message
            from cron.job_run_details r
            join cron.job j on j.jobid = r.jobid
            where r.start_time >= now() - (%s || ' hours')::interval
              and j.jobname = any(%s)
              and r.status <> 'succeeded'
            order by r.start_time desc
            limit 20
            """,
            (hours, list(CRON_JOBS)),
        ),
        "http_responses": (
            """
            select status_code, timed_out, left(coalesce(content, ''), 220) as content, count(*) as n,
                   min(created) as first_created, max(created) as last_created
            from net._http_response
            where created >= now() - (%s || ' hours')::interval
            group by status_code, timed_out, left(coalesce(content, ''), 220)
            order by n desc
            """,
            (hours,),
        ),
        "archive_queue_recent": (
            """
            select status, coalesce(last_outcome, '(null)') as last_outcome, source,
                   count(*) as n, max(processed_at) as last_processed
            from public.archive_queue
            where processed_at >= now() - (%s || ' hours')::interval
            group by status, coalesce(last_outcome, '(null)'), source
            order by n desc
            """,
            (hours,),
        ),
        "archive_queue_open": (
            """
            select id, school_id, school_name, status, attempts, source,
                   enqueued_at, claimed_at, left(coalesce(last_error, ''), 240) as last_error
            from public.archive_queue
            where status in ('ready', 'processing')
            order by coalesce(claimed_at, enqueued_at) asc
            limit 30
            """,
            (),
        ),
        "documents_recent": (
            """
            select extraction_status, count(*) as n, max(updated_at) as last_updated
            from public.cds_documents
            where updated_at >= now() - (%s || ' hours')::interval
            group by extraction_status
            order by n desc
            """,
            (hours,),
        ),
        "artifacts_recent": (
            """
            select kind, producer, producer_version, count(*) as n,
                   min(created_at) as first_created, max(created_at) as last_created
            from public.cds_artifacts
            where created_at >= now() - (%s || ' hours')::interval
            group by kind, producer, producer_version
            order by n desc
            """,
            (hours,),
        ),
        "coverage_refresh": (
            """
            select count(*) as rows, min(updated_at) as oldest_updated, max(updated_at) as newest_updated
            from public.institution_cds_coverage
            """,
            (),
        ),
        "coverage_histogram": (
            """
            select coverage_status, count(*) as n
            from public.institution_cds_coverage
            group by coverage_status
            order by n desc
            """,
            (),
        ),
        "pending_documents": (
            """
            select extraction_status, count(*) as n
            from public.cds_documents
            where extraction_status in ('extraction_pending', 'discovered', 'failed')
            group by extraction_status
            order by extraction_status
            """,
            (),
        ),
        "bot_challenged": (
            """
            select count(*) as n, max(last_challenge_at) as latest
            from public.bot_challenged_documents
            """,
            (),
        ),
    }

    out: dict[str, Any] = {}
    with psycopg.connect(dsn, connect_timeout=20) as conn:
        for name, (sql, params) in queries.items():
            with conn.cursor() as cur:
                cur.execute(sql, params)
                out[name] = rows_to_dicts(cur)

    category_counts: Counter[str] = Counter()
    for row in out["http_responses"]:
        category_counts[http_content_category(row.get("content"), row.get("status_code"))] += int(row["n"])
    out["http_response_categories"] = dict(sorted(category_counts.items()))
    return out


def fetch_github_actions(*, repo: str, hours: int, limit: int) -> dict[str, Any]:
    if not shutil.which("gh"):
        return {"available": False, "error": "gh not found"}
    command = [
        "gh",
        "run",
        "list",
        "--repo",
        repo,
        "--limit",
        str(limit),
        "--json",
        "databaseId,workflowName,event,status,conclusion,createdAt,updatedAt,headBranch,url,displayTitle",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=45)
    if completed.returncode != 0:
        return {"available": False, "error": completed.stderr.strip() or completed.stdout.strip()}
    runs = json.loads(completed.stdout or "[]")
    now = datetime.now(timezone.utc)
    cutoff_hours = float(hours)
    recent = [
        run for run in runs
        if (age := hours_since(run.get("createdAt"), now)) is not None and age <= cutoff_hours
    ]
    by_workflow: dict[str, Counter[str]] = {}
    for run in recent:
        workflow = run.get("workflowName") or "unknown"
        conclusion = run.get("conclusion") or run.get("status") or "unknown"
        by_workflow.setdefault(workflow, Counter())[conclusion] += 1
    latest_by_workflow: dict[str, dict[str, Any]] = {}
    for run in recent:
        workflow = run.get("workflowName") or "unknown"
        current = latest_by_workflow.get(workflow)
        if current is None or str(run.get("createdAt")) > str(current.get("createdAt")):
            latest_by_workflow[workflow] = run
    return {
        "available": True,
        "recent_runs": recent,
        "by_workflow": {k: dict(v) for k, v in sorted(by_workflow.items())},
        "latest_by_workflow": latest_by_workflow,
    }


def evaluate(report: dict[str, Any], now: datetime) -> list[str]:
    issues: list[str] = []
    db = report["database"]

    inactive = [row["jobname"] for row in db["cron_jobs"] if not row.get("active")]
    if inactive:
        issues.append(f"inactive cron jobs: {', '.join(inactive)}")

    if db["cron_recent_failures"]:
        issues.append(f"{len(db['cron_recent_failures'])} pg_cron failures in window")

    categories = db.get("http_response_categories", {})
    bad_http = {
        key: value
        for key, value in categories.items()
        if key not in {
            "refresh_coverage",
            "archive_process_queue_drained",
            "archive_process_attempt_budget_exhausted",
            "success_other",
        }
    }
    if bad_http:
        issues.append(f"edge HTTP errors: {bad_http}")

    open_rows = db["archive_queue_open"]
    poison = [
        row for row in open_rows
        if row.get("status") == "processing" and int(row.get("attempts") or 0) > 3
    ]
    if poison:
        schools = ", ".join(str(row.get("school_id")) for row in poison[:5])
        issues.append(f"archive queue poison rows over retry budget: {schools}")

    coverage = (db["coverage_refresh"] or [{}])[0]
    coverage_age = hours_since(json_default(coverage.get("newest_updated")), now)
    if coverage_age is None or coverage_age > 0.5:
        issues.append(f"coverage refresh stale: {coverage_age if coverage_age is not None else 'unknown'} hours")

    gha = report.get("github_actions") or {}
    if gha.get("available"):
        failed = [
            run for run in gha.get("recent_runs", [])
            if run.get("status") == "completed" and run.get("conclusion") not in ("success", "skipped")
        ]
        if failed:
            issues.append(f"{len(failed)} GitHub Actions runs failed in window")
    else:
        issues.append(f"GitHub Actions unavailable: {gha.get('error')}")

    return issues


def render_markdown(report: dict[str, Any], issues: list[str]) -> str:
    db = report["database"]
    gha = report.get("github_actions") or {}
    verdict = "ATTENTION" if issues else "HEALTHY"
    lines = [
        f"# Automation Health: {verdict}",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Window: `{report['hours']}h`",
    ]
    if issues:
        lines.append("- Issues:")
        lines.extend(f"  - {issue}" for issue in issues)
    lines.extend(["", "## GitHub Actions"])
    if gha.get("available"):
        for workflow, counts in gha.get("by_workflow", {}).items():
            latest = gha.get("latest_by_workflow", {}).get(workflow, {})
            lines.append(
                f"- `{workflow}`: {counts}; latest `{latest.get('conclusion') or latest.get('status')}` "
                f"at `{latest.get('createdAt')}`"
            )
    else:
        lines.append(f"- unavailable: {gha.get('error')}")

    lines.extend(["", "## Cron Jobs"])
    for row in db["cron_jobs"]:
        lines.append(f"- `{row['jobname']}`: active={row['active']} schedule=`{row['schedule']}`")
    lines.append("")
    lines.append("Recent cron summaries:")
    for row in db["cron_recent_summary"]:
        lines.append(f"- `{row['jobname']}` `{row['status']}`: {row['n']} latest `{json_default(row['last_end'])}`")

    lines.extend(["", "## Edge HTTP Responses"])
    for category, count in db.get("http_response_categories", {}).items():
        lines.append(f"- `{category}`: {count}")

    lines.extend(["", "## Archive Queue"])
    if db["archive_queue_open"]:
        for row in db["archive_queue_open"][:10]:
            lines.append(
                f"- `{row['school_id']}` `{row['status']}` attempts={row['attempts']} "
                f"claimed=`{json_default(row['claimed_at'])}`"
            )
    else:
        lines.append("- no ready/processing rows")
    lines.append("")
    lines.append("Recent terminal outcomes:")
    if db["archive_queue_recent"]:
        for row in db["archive_queue_recent"]:
            lines.append(f"- `{row['status']}` `{row['last_outcome']}` source=`{row['source']}`: {row['n']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Extraction And Coverage"])
    lines.append("- Recent document updates:")
    if db["documents_recent"]:
        for row in db["documents_recent"]:
            lines.append(
                f"  - `{row['extraction_status']}`: {row['n']} latest `{json_default(row['last_updated'])}`"
            )
    else:
        lines.append("  - none")
    lines.append("- Recent artifacts:")
    if db["artifacts_recent"]:
        for row in db["artifacts_recent"]:
            lines.append(
                f"  - `{row['kind']}` `{row['producer']}` `{row['producer_version']}`: "
                f"{row['n']} latest `{json_default(row['last_created'])}`"
            )
    else:
        lines.append("  - none")
    lines.append("- Pending/discovered/failed docs:")
    if db["pending_documents"]:
        for row in db["pending_documents"]:
            lines.append(f"  - `{row['extraction_status']}`: {row['n']}")
    else:
        lines.append("  - none")
    coverage = (db["coverage_refresh"] or [{}])[0]
    lines.append(
        f"- Coverage rows: `{coverage.get('rows')}`, refreshed `{json_default(coverage.get('newest_updated'))}`"
    )
    lines.append("- Coverage histogram:")
    for row in db["coverage_histogram"]:
        lines.append(f"  - `{row['coverage_status']}`: {row['n']}")
    bot = (db["bot_challenged"] or [{}])[0]
    lines.append(f"- Bot-challenged docs: `{bot.get('n', 0)}` latest `{json_default(bot.get('latest'))}`")
    return "\n".join(lines) + "\n"


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    now = datetime.now(timezone.utc)
    env = load_env_file(args.env)
    db = fetch_db_health(pooler_dsn(env, args.pooler_url), hours=args.hours)
    gha = fetch_github_actions(repo=args.github_repo, hours=args.hours, limit=args.github_limit)
    report = {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "hours": args.hours,
        "database": db,
        "github_actions": gha,
    }
    return report, evaluate(report, now)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--pooler-url", type=Path, default=DEFAULT_POOLER_URL)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--github-repo", default=DEFAULT_REPO)
    parser.add_argument("--github-limit", type=int, default=50)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--fail-on-unhealthy", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        report, issues = build_report(args)
    except HealthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    markdown = render_markdown(report, issues)
    print(markdown)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, default=json_default, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    return 1 if issues and args.fail_on_unhealthy else 0


if __name__ == "__main__":
    raise SystemExit(main())
