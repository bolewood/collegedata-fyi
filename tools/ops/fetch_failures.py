#!/usr/bin/env python3
"""Fetch failures: one list of schools whose listing is known but whose
current-year file is not archived, grouped by cause (issue #468).

Population: schools whose listing is known (seed is a listing page, not one
file, or the school is in `tools/finder/waf_blocked_urls.yaml`) that have no
live published document filed under the current CDS year
(`cds_freshness_floor()`).

Cause, from evidence, first match wins:

  blocked             in waf_blocked_urls, or the newest archive attempt was a
                      bot challenge / HTTP 403, 405, 429, 451
  viewer              SharePoint, Box, Dropbox, Google Docs/Drive, OneDrive or
                      an SSO wall in the seed or in the newest archive error
  section_files       a URL in the seed or the newest archive error is one CDS
                      section file. The archive does not record "saw only
                      section files" as such, so this only catches failures
                      that name a section file. A school whose archived
                      current-year document is a section file already has a
                      document and is not in this list (see docs, #452).
  dead_link           dead_url outcome, HTTP 404/410, DNS failure
  other               any other recorded error. The raw string is kept.
  no_failure_recorded the newest archive attempt finished without an error, or
                      there is none in the window. The school may simply not
                      have posted yet. Not counted as a fetch failure.

Evidence is the newest `archive_queue` row per school over the last 45 days
(service role, read only). Without the service role key nothing is classified
and no summary keys are written: a missing number is never reported as 0.

Fails loudly: an empty queue read, a short page of rows, or a count that
changes while paging is an error and exits nonzero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

# One copy of the mechanism: these come from the renewal module (PR #474).
# This module imports only after #474 is on main.
from tools.common.site import runtime_api_origin  # noqa: E402
from tools.ops.discovery_renewal import (  # noqa: E402
    DEFAULT_SCHOOLS_YAML,
    PAGE_SIZE,
    SCHOOL_PAGE_URL,
    RenewalError,
    _headers,
    cds_freshness_floor,
    fetch_live_manifest,
    format_year,
    http_json,
    load_schools,
    parse_content_range_total,
    parse_year,
    school_years,
    seed_for,
)
from tools.finder.stuck_pdf_seeds import is_section_seed  # noqa: E402

DEFAULT_WAF_YAML = REPO_ROOT / "tools" / "finder" / "waf_blocked_urls.yaml"
WINDOW_DAYS = 45
LARGE_POPULATION = 100
QUEUE_SELECT = "school_id,status,last_outcome,last_error,enqueued_at,processed_at"

BLOCKED = "blocked"
VIEWER = "viewer"
SECTION_FILES = "section_files"
DEAD_LINK = "dead_link"
OTHER = "other"
NO_FAILURE = "no_failure_recorded"

FAILURE_CAUSES = (BLOCKED, VIEWER, SECTION_FILES, DEAD_LINK, OTHER)
CAUSE_ORDER = FAILURE_CAUSES + (NO_FAILURE,)
# The flat summary keys this module writes: the contract with the heartbeat
# station summary and the registry test.
SUMMARY_KEYS = ("fetch_failures",) + tuple(f"fetch_failures_{c}" for c in FAILURE_CAUSES)
CAUSE_HEADINGS = {
    BLOCKED: "Blocked (WAF, bot challenge, 403/405/429): needs the headless job or a manual file",
    VIEWER: "Behind a viewer or login (SharePoint, Box, Dropbox, Google, SSO)",
    SECTION_FILES: "Posted as separate section files",
    DEAD_LINK: "Dead link (404/410/DNS)",
    OTHER: "Other error (raw archive error shown)",
    NO_FAILURE: "No failure recorded (the school may not have posted yet)",
}

# Outcomes of an attempt that reached the school's files without a problem.
CLEAN_OUTCOMES = {"inserted", "refreshed", "unchanged_verified", "unchanged_repaired", "marked_removed"}
BLOCKED_OUTCOMES = {"bot_challenge"}
VIEWER_OUTCOMES = {"auth_walled_microsoft", "auth_walled_okta", "auth_walled_google"}
DEAD_OUTCOMES = {"dead_url"}

BLOCKED_ERROR_RE = re.compile(
    r"\bHTTP (?:403|405|429|451)\b|bot[ _-]?challenge|cloudflare|captcha|\bwaf\b|access denied",
    re.I,
)
DEAD_ERROR_RE = re.compile(
    r"\bHTTP (?:404|410)\b|dns error|failed to lookup|name or service not known|"
    r"no such host|nxdomain|enotfound|dead[ _]url",
    re.I,
)
VIEWER_HOST_RE = re.compile(
    r"sharepoint\.com|box\.com|dropbox\.com|docs\.google\.com|drive\.google\.com|"
    r"onedrive|1drv\.ms|microsoftonline\.com|\.okta\.com|auth-walled",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s\"'<>)]+")


# ---------------------------------------------------------------- classification


@dataclass
class Case:
    school_id: str
    name: str
    seed_url: str
    seed_kind: str
    newest_year: str | None
    in_waf: bool
    attempt: dict[str, Any] | None  # newest archive_queue row, or None
    cause: str = NO_FAILURE
    evidence: str = ""
    raw_error: str = ""
    outcome: str = ""
    attempted_at: str = ""


def _urls(text: str) -> list[str]:
    return [u.rstrip(".,;:") for u in URL_RE.findall(text or "")]


def classify(
    *, in_waf: bool, seed_url: str, attempt: dict[str, Any] | None
) -> tuple[str, str]:
    """(cause, short evidence) from the evidence, first match wins."""
    error = str((attempt or {}).get("last_error") or "")
    outcome = str((attempt or {}).get("last_outcome") or "")

    if in_waf:
        return BLOCKED, "listed in waf_blocked_urls.yaml"
    if outcome in BLOCKED_OUTCOMES:
        return BLOCKED, f"archive outcome {outcome}"
    if error and BLOCKED_ERROR_RE.search(error):
        return BLOCKED, "archive error looks like a block (403/405/429/challenge)"

    if outcome in VIEWER_OUTCOMES:
        return VIEWER, f"archive outcome {outcome}"
    if VIEWER_HOST_RE.search(seed_url or ""):
        return VIEWER, "seed is a viewer or login host"
    if error and VIEWER_HOST_RE.search(error):
        return VIEWER, "archive error names a viewer or login host"

    for url in [seed_url, *_urls(error)]:
        if url and is_section_seed(url):
            return SECTION_FILES, f"a section file is named: {url}"

    if outcome in DEAD_OUTCOMES:
        return DEAD_LINK, f"archive outcome {outcome}"
    if error and DEAD_ERROR_RE.search(error):
        return DEAD_LINK, "archive error is 404/410/DNS"

    if error:
        return OTHER, f"archive outcome {outcome or 'none'}"
    status = str((attempt or {}).get("status") or "")
    # A failure with no error text is still a failure. Anything not on the
    # clean allowlist counts, so a new failure outcome cannot read as success.
    if attempt is not None and (
        status.startswith("failed") or (outcome and outcome not in CLEAN_OUTCOMES)
    ):
        return OTHER, f"archive status {status or 'none'}, outcome {outcome or 'none'}, no error text"
    if attempt is None:
        return NO_FAILURE, "no archive attempt in the window"
    return NO_FAILURE, f"newest archive attempt {attempt.get('status')} ({outcome or 'no outcome'}), no error"


def other_reason(outcome: str, error: str) -> str:
    """Short label for an `other` case, so the long tail is readable.

    The raw error is always kept next to it.
    """
    low = error.lower()
    if "none carry a year signal" in low:
        return "several CDS-looking files, none with a year (often section files)"
    if outcome == "no_pdfs_found" or "no cds found" in low:
        return "no document links found on the page"
    if outcome == "wrong_content_type" or "unknown content type" in low:
        return "link returned a web page or the wrong file type"
    if outcome in ("transient", "") or "transient" in low or "timed out" in low:
        return "timeout, connection or server error (retries used up)"
    return "other"


# ---------------------------------------------------------------- population


def load_waf_ids(path: Path) -> dict[str, str]:
    """{school_id: school_name} from waf_blocked_urls.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("schools") if isinstance(data, dict) else None
    if not entries:
        raise RenewalError(f"no schools found in {path}")
    return {sid: str((v or {}).get("school_name") or sid) for sid, v in entries.items()}


def population(
    *,
    schools: dict[str, dict[str, Any]],
    waf: dict[str, str],
    years_by_school: dict[str, set[int]],
    current_year: int,
) -> list[Case]:
    """Schools with a known listing and no live current-year document."""
    cases: list[Case] = []
    # waf_blocked_urls keys must be canonical schools.yaml ids; a key that is
    # not one (an alias) is not a school here.
    for sid in sorted(schools):
        school = schools[sid]
        if school.get("scrape_policy") == "verified_absent":
            continue
        url, kind = seed_for(school)
        in_waf = sid in waf
        if kind != "listing_page" and not in_waf:
            continue
        years = years_by_school.get(sid, set())
        if current_year in years:
            continue
        newest = max(years) if years else None
        cases.append(
            Case(
                school_id=sid,
                name=str(school.get("name") or waf.get(sid) or sid),
                seed_url=url,
                seed_kind=kind,
                newest_year=format_year(newest) if newest is not None else None,
                in_waf=in_waf,
                attempt=None,
            )
        )
    return cases


def _recency(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("enqueued_at") or ""), str(row.get("processed_at") or ""))


def _unattempted(row: dict[str, Any]) -> bool:
    return (
        str(row.get("status") or "") in ("ready", "processing")
        and not row.get("last_error")
        and not row.get("last_outcome")
    )


def newest_attempts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Newest `archive_queue` row per school (by enqueue time).

    The newest row is the one that counts, even when it is still `ready` with
    a transient error left from an earlier attempt: that error is the current
    state of the school's fetch. A row nobody has attempted (ready or
    processing, no error, no outcome) says nothing and is ignored, so a stalled
    worker cannot overwrite yesterday's failure with a blank row.
    """
    newest: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = row.get("school_id")
        if not sid:
            continue
        if _unattempted(row):
            continue
        if sid not in newest or _recency(row) > _recency(newest[sid]):
            newest[sid] = row
    return newest


def build_cases(
    *,
    schools: dict[str, dict[str, Any]],
    waf: dict[str, str],
    manifest_rows: list[dict[str, Any]],
    queue_rows: list[dict[str, Any]],
    as_of: date,
) -> tuple[list[Case], int]:
    """Classified cases and the current CDS year (start year)."""
    current = parse_year(cds_freshness_floor(as_of))
    assert current is not None
    cases = population(
        schools=schools, waf=waf, years_by_school=school_years(manifest_rows), current_year=current
    )
    newest = newest_attempts(queue_rows)
    for case in cases:
        case.attempt = newest.get(case.school_id)
        case.cause, case.evidence = classify(
            in_waf=case.in_waf, seed_url=case.seed_url, attempt=case.attempt
        )
        if case.attempt:
            case.raw_error = str(case.attempt.get("last_error") or "")
            case.outcome = str(case.attempt.get("last_outcome") or "")
            case.attempted_at = str(case.attempt.get("enqueued_at") or "")[:10]
    return cases, current


# ---------------------------------------------------------------- summary / report


def summary_dict(cases: list[Case]) -> dict[str, Any]:
    """Flat heartbeat keys. `fetch_failures` is the five failure causes only."""
    counts = Counter(c.cause for c in cases)
    out: dict[str, Any] = {
        "fetch_failures": sum(counts[c] for c in FAILURE_CAUSES),
    }
    for cause in FAILURE_CAUSES:
        out[f"fetch_failures_{cause}"] = counts[cause]
    assert tuple(out) == SUMMARY_KEYS
    return out


def worklist(cases: list[Case]) -> list[dict[str, Any]]:
    return [
        {
            "school_id": c.school_id,
            "name": c.name,
            "cause": c.cause,
            "evidence": c.evidence,
            "other_reason": other_reason(c.outcome, c.raw_error) if c.cause == OTHER else "",
            "newest_year": c.newest_year,
            "seed_url": c.seed_url,
            "last_outcome": c.outcome,
            "last_error": c.raw_error,
            "last_attempt": c.attempted_at,
        }
        for c in sorted(cases, key=lambda c: (CAUSE_ORDER.index(c.cause), c.school_id))
    ]


def _cell(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _row(c: Case) -> str:
    link = f"[{_cell(c.name, 60)}]({SCHOOL_PAGE_URL.format(school_id=c.school_id)})"
    return (
        f"| {link} | {c.newest_year or 'none'} | {_cell(c.evidence, 80)} | "
        f"{_cell(c.raw_error or '(none)')} | {_cell(c.seed_url, 80) or '(none)'} |"
    )


def render_report(
    cases: list[Case],
    *,
    current_year: int,
    as_of: date,
    window_days: int = WINDOW_DAYS,
    heading_level: int = 2,
    max_chars: int = 60000,
    max_rows_per_cause: int | None = None,
) -> str:
    """`max_rows_per_cause` caps each cause's rows (and the no-failure name
    list); the full list is in the worklist artifact."""
    h = "#" * heading_level
    h2 = "#" * (heading_level + 1)
    summary = summary_dict(cases)
    by_cause: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        by_cause[case.cause].append(case)
    no_attempt = sum(1 for c in cases if c.attempt is None)
    cur = format_year(current_year)
    lines = [
        f"{h} Fetch failures, {as_of.isoformat()}",
        "",
        f"**{summary['fetch_failures']} schools** have a known listing and no live {cur} "
        f"document, and the archive recorded a problem fetching it. "
        f"{len(by_cause[NO_FAILURE])} more have no problem recorded (they may not have "
        f"posted {cur} yet; {no_attempt} of them had no archive attempt in the last "
        f"{window_days} days).",
        "",
        "| Cause | Schools |",
        "|---|---:|",
    ]
    for cause in CAUSE_ORDER:
        lines.append(f"| {cause} | {len(by_cause[cause])} |")
    lines += [
        "",
        f"Evidence: the newest archive attempt per school in the last {window_days} days "
        "(`archive_queue`), the seed in `schools.yaml`, and `waf_blocked_urls.yaml`. "
        "Order of checks: blocked, viewer, section_files, dead_link, other.",
        "",
    ]
    for cause in CAUSE_ORDER:
        group = sorted(by_cause[cause], key=lambda c: c.school_id)
        lines.append(f"{h2} {CAUSE_HEADINGS[cause]} ({len(group)})")
        lines.append("")
        if not group:
            lines += ["None.", ""]
            continue
        cap = max_rows_per_cause if max_rows_per_cause is not None else len(group)
        if cause == NO_FAILURE:
            shown = group[:cap]
            lines.append(
                ", ".join(f"[{_cell(c.name, 60)}]({SCHOOL_PAGE_URL.format(school_id=c.school_id)})" for c in shown)
            )
            if len(group) > len(shown):
                lines.append(f"and {len(group) - len(shown)} more (full list in the run artifact).")
            lines.append("")
            continue
        budget = cap
        subgroups: list[tuple[str | None, list[Case]]]
        if cause == OTHER:
            by_reason: dict[str, list[Case]] = defaultdict(list)
            for c in group:
                by_reason[other_reason(c.outcome, c.raw_error)].append(c)
            subgroups = [(r, by_reason[r]) for r in sorted(by_reason, key=lambda r: (-len(by_reason[r]), r))]
        else:
            subgroups = [(None, group)]
        for reason, members in subgroups:
            if reason:
                lines += [f"**{reason} ({len(members)})**", ""]
            if budget <= 0:
                lines += [f"{len(members)} more not shown (full list in the run artifact).", ""]
                continue
            shown = members[:budget]
            budget -= len(shown)
            lines += ["| School | Newest year | Evidence | Archive error | Seed |", "|---|---|---|---|---|"]
            lines += [_row(c) for c in shown]
            if len(members) > len(shown):
                lines += ["", f"{len(members) - len(shown)} more not shown (full list in the run artifact)."]
            lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    if len(text) > max_chars:
        text = text[: max_chars - 80].rstrip() + "\n\n(report truncated; the full list is in the worklist artifact)\n"
    return text


# ---------------------------------------------------------------- reading the queue


def fetch_queue_rows(
    api_url: str,
    service_key: str,
    *,
    since: datetime,
    get: Callable[..., tuple[Any, dict[str, str]]] = http_json,
) -> list[dict[str, Any]]:
    """Every `archive_queue` row enqueued since `since`, paged, read only.

    Raises unless every row counted by Content-Range arrived.
    """
    stamp = urllib.parse.quote(since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rows: list[dict[str, Any]] = []
    total: int | None = None
    while total is None or len(rows) < total:
        url = (
            f"{api_url.rstrip('/')}/rest/v1/archive_queue?select={QUEUE_SELECT}"
            f"&enqueued_at=gte.{stamp}&order=enqueued_at.desc,id.asc"
            f"&limit={PAGE_SIZE}&offset={len(rows)}"
        )
        page, headers = get(url, _headers(service_key, Prefer="count=exact"))
        page_total = parse_content_range_total(headers.get("content-range"))
        if total is None:
            total = page_total
            if total == 0:
                raise RenewalError(f"archive_queue has no rows in the last {WINDOW_DAYS} days")
        elif page_total != total:
            raise RenewalError(f"row count changed while paging ({total} -> {page_total})")
        if not isinstance(page, list):
            raise RenewalError("archive_queue page was not a list")
        if not page:
            break
        rows.extend(page)
    if total is None or len(rows) != total:
        raise RenewalError(f"short read: fetched {len(rows)} rows, Content-Range total {total}")
    return rows


# ---------------------------------------------------------------- CLI


def write_json(path: Path | None, data: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("CDS_API_URL") or runtime_api_origin())
    parser.add_argument("--anon-key", default=os.environ.get("SUPABASE_ANON_KEY", ""))
    parser.add_argument(
        "--supabase-url",
        default=os.environ.get("SUPABASE_URL", ""),
        help="project URL for the archive_queue read (service role); default $SUPABASE_URL",
    )
    parser.add_argument("--as-of", help="YYYY-MM-DD; default today (UTC)")
    parser.add_argument("--manifest-json", type=Path, help="local manifest snapshot, no network")
    parser.add_argument("--queue-json", type=Path, help="local archive_queue rows, no network")
    parser.add_argument("--schools-yaml", type=Path, default=DEFAULT_SCHOOLS_YAML)
    parser.add_argument("--waf-yaml", type=Path, default=DEFAULT_WAF_YAML)
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    parser.add_argument("--heading-level", type=int, default=2)
    parser.add_argument("--max-rows-per-cause", type=int, help="cap the report rows per cause (the worklist JSON is never capped)")
    parser.add_argument("--max-chars", type=int, default=60000, help="hard cap on the report length")
    parser.add_argument("--out-summary", type=Path)
    parser.add_argument(
        "--merge-summary",
        type=Path,
        help="add the fetch_failures keys to this existing summary JSON (renewal summary); "
        "left untouched when the run is skipped",
    )
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--out-worklist", type=Path)
    return parser


def run(args: argparse.Namespace) -> int:
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if args.queue_json:
        queue_rows = json.loads(args.queue_json.read_text(encoding="utf-8"))
        if not queue_rows:
            raise RenewalError(f"{args.queue_json} has no rows")
    elif not service_key or not args.supabase_url:
        # Say so, write no summary keys: a missing number is never 0.
        message = (
            "fetch failures SKIPPED: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_URL is not set, "
            "so the archive evidence cannot be read. No counts are reported."
        )
        print(f"::warning::{message}", file=sys.stderr)
        if args.out_summary and args.out_summary.exists():
            args.out_summary.unlink()
        if args.out_report:
            args.out_report.parent.mkdir(parents=True, exist_ok=True)
            args.out_report.write_text(f"{'#' * args.heading_level} Fetch failures\n\n{message}\n", encoding="utf-8")
        return 0
    else:
        since = datetime.now(timezone.utc) - timedelta(days=args.window_days)
        queue_rows = fetch_queue_rows(args.supabase_url, service_key, since=since)

    if args.manifest_json:
        manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
        manifest = [r for r in manifest if not r.get("removed_at")]
    else:
        if not args.anon_key:
            raise RenewalError("no anon key: set SUPABASE_ANON_KEY or pass --anon-key")
        manifest = fetch_live_manifest(args.api_url, args.anon_key)

    schools = load_schools(args.schools_yaml)
    waf = load_waf_ids(args.waf_yaml)
    cases, current = build_cases(
        schools=schools, waf=waf, manifest_rows=manifest, queue_rows=queue_rows, as_of=as_of
    )
    if not cases:
        raise RenewalError("no schools matched the population; the inputs do not look right")

    summary = summary_dict(cases)
    clean = sum(1 for c in cases if c.cause == NO_FAILURE)
    if len(cases) >= LARGE_POPULATION and clean == len(cases):
        print(
            f"::warning::fetch failures: all {len(cases)} schools read as no_failure_recorded; "
            "the archive_queue data is probably not what this check assumes",
            file=sys.stderr,
        )
    report = render_report(
        cases,
        current_year=current,
        as_of=as_of,
        window_days=args.window_days,
        heading_level=args.heading_level,
        max_rows_per_cause=args.max_rows_per_cause,
        max_chars=args.max_chars,
    )
    write_json(args.out_summary, summary)
    if args.merge_summary:
        merged = json.loads(args.merge_summary.read_text(encoding="utf-8"))
        if not isinstance(merged, dict):
            raise RenewalError(f"{args.merge_summary} is not a JSON object")
        merged.update(summary)
        write_json(args.merge_summary, merged)
    write_json(args.out_worklist, worklist(cases))
    if args.out_report:
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    counts = Counter(c.cause for c in cases)
    print("population by cause: " + ", ".join(f"{k}={counts[k]}" for k in CAUSE_ORDER))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except RenewalError as exc:
        print(f"::error::fetch failures: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
