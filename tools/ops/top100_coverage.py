#!/usr/bin/env python3
"""Score the operator priority-100 cohort against the two-year byte bar.

Coverage is finder/archive, not extraction. A school is in_bar only when
it has an HTML listing seed and archived source bytes (sha256 + source
artifact) for the current and prior CDS year.

Suggested routes are advisory. Residential fetch happens only for ids on
the sticky allowlist. This script never heartbeats a top100_coverage station.

Usage:
    python tools/ops/top100_coverage.py --json-out coverage.json
    python tools/ops/top100_coverage.py --resolve-residential-only --dispatch-only nyu
    python tools/ops/top100_coverage.py --hosted-gap-ids --from-json coverage.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COHORT = REPO_ROOT / "data" / "watchlists" / "priority_coverage.yaml"
DEFAULT_ALLOWLIST = REPO_ROOT / "data" / "watchlists" / "residential_allowlist.yaml"
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
WAF_YAML = REPO_ROOT / "tools" / "finder" / "waf_blocked_urls.yaml"
DEFAULT_YEARS = ["2025-26", "2024-25"]
RESIDENTIAL_CAP = 5
SSO_HOST_MARKERS = ("tableau.com", "powerbi.com", "okta.com", "login.microsoftonline.com")
DRIVE_HOST_MARKERS = (
    "drive.google.com",
    "docs.google.com",
    "box.com",
    "dropbox.com",
    "sharepoint.com",
)

sys.path.insert(0, str(REPO_ROOT))

from tools.finder.stuck_pdf_seeds import is_direct_doc_seed  # noqa: E402
from tools.finder.waf_school_ids import (  # noqa: E402
    canonical_waf_school_id,
    parse_only_ids,
)


def coverage_bar_years(today: date | None = None) -> list[str]:
    """Current and prior CDS year until an operator bumps DEFAULT_YEARS.

    August 2026 → 2025-26 + 2024-25. Do not auto-roll to 2026-27 in
    September; wait until that cycle is actually publishing.
    """
    today = today or date.today()
    if today >= date(2027, 9, 1):
        return ["2026-27", "2025-26"]
    return list(DEFAULT_YEARS)


def load_yaml_map(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_cohort_ids(path: Path = DEFAULT_COHORT) -> list[str]:
    doc = load_yaml_map(path)
    ids: list[str] = []
    seen: set[str] = set()
    for row in doc.get("schools") or []:
        sid = (row or {}).get("school_id")
        if not sid:
            raise SystemExit(f"{path} has a school row without school_id")
        if sid in seen:
            raise SystemExit(f"{path} duplicates school_id {sid}")
        seen.add(sid)
        ids.append(sid)
    return ids


def load_allowlist(path: Path = DEFAULT_ALLOWLIST) -> dict[str, dict[str, Any]]:
    doc = load_yaml_map(path)
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("schools") or []:
        sid = canonical_waf_school_id((row or {}).get("school_id") or "")
        if not sid:
            continue
        out[sid] = dict(row)
    return out


def load_schools_by_id(path: Path = SCHOOLS_YAML) -> dict[str, dict[str, Any]]:
    doc = load_yaml_map(path)
    return {row["id"]: row for row in doc.get("schools") or [] if row.get("id")}


def listing_url_for(school: dict[str, Any], starting_urls: dict[str, str]) -> str | None:
    sid = school.get("id")
    candidates = [
        school.get("browse_url"),
        school.get("discovery_seed_url") or school.get("cds_url_hint"),
        starting_urls.get(sid) if sid else None,
    ]
    html: list[str] = []
    for raw in candidates:
        if not raw:
            continue
        if is_direct_doc_seed(raw):
            continue
        html.append(raw)
    return html[0] if html else None


def seed_is_listing(school: dict[str, Any], starting_urls: dict[str, str]) -> bool:
    return listing_url_for(school, starting_urls) is not None


def host_looks_like(url: str | None, markers: tuple[str, ...]) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return any(marker in host for marker in markers)


def suggested_route(
    *,
    school_id: str,
    listing: bool,
    listing_url: str | None,
    in_waf_yaml: bool,
    allowlisted: bool,
    allowlist_error: str | None,
    queue_outcome: str | None,
) -> str:
    """Advisory only. Residential requires the sticky allowlist."""
    if host_looks_like(listing_url, SSO_HOST_MARKERS):
        return "human"
    if allowlisted:
        return "residential"
    if not listing or in_waf_yaml or host_looks_like(listing_url, DRIVE_HOST_MARKERS):
        return "hosted"
    return "static_html"


def year_status(slot: dict[str, Any] | None) -> str:
    if not slot:
        return "missing"
    if slot.get("has_bytes"):
        return "bytes"
    if slot.get("published") and not slot.get("sha256"):
        return "missing_bytes"
    if slot.get("published") and not slot.get("has_source_artifact"):
        return "missing_bytes"
    if slot.get("published"):
        return "missing_bytes"
    return "missing"


def score_school(
    school_id: str,
    school: dict[str, Any],
    years: list[str],
    coverage: dict[str, dict[str, Any]],
    *,
    starting_urls: dict[str, str],
    waf_ids: set[str],
    allowlist: dict[str, dict[str, Any]],
    queue_outcome: str | None = None,
) -> dict[str, Any]:
    listing_url = listing_url_for(school, starting_urls)
    listing = listing_url is not None
    allow_row = allowlist.get(school_id)
    route = suggested_route(
        school_id=school_id,
        listing=listing,
        listing_url=listing_url,
        in_waf_yaml=school_id in waf_ids,
        allowlisted=allow_row is not None,
        allowlist_error=(allow_row or {}).get("last_hosted_error"),
        queue_outcome=queue_outcome,
    )
    year_map = {}
    missing_years: list[str] = []
    for year in years:
        status = year_status(coverage.get(year))
        year_map[year] = status
        if status != "bytes":
            missing_years.append(year)
    in_bar = listing and not missing_years
    gap_reason = None
    if not listing:
        gap_reason = "pdf_seed"
    elif missing_years:
        gap_reason = "missing_bytes"
    return {
        "school_id": school_id,
        "in_bar": in_bar,
        "listing": listing,
        "listing_url": listing_url,
        "route": route,
        "years": year_map,
        "missing_years": missing_years,
        "gap_reason": gap_reason,
    }


def load_starting_urls() -> dict[str, str]:
    try:
        from tools.finder.playwright_collect import STARTING_URLS
    except ImportError:
        return {}
    return dict(STARTING_URLS)


def load_waf_ids(path: Path = WAF_YAML) -> set[str]:
    doc = load_yaml_map(path)
    from tools.finder.headless_archive import merge_waf_school_entries

    merged = merge_waf_school_entries(doc.get("schools") or {})
    return set(merged)


def score_cohort(
    *,
    cohort_ids: list[str],
    schools: dict[str, dict[str, Any]],
    years: list[str],
    byte_coverage: dict[str, dict[str, dict[str, Any]]],
    starting_urls: dict[str, str],
    waf_ids: set[str],
    allowlist: dict[str, dict[str, Any]],
    queue_outcomes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for sid in cohort_ids:
        school = schools.get(sid) or {"id": sid}
        if not school.get("id"):
            school = {**school, "id": sid}
        rows.append(
            score_school(
                sid,
                school,
                years,
                byte_coverage.get(sid) or {},
                starting_urls=starting_urls,
                waf_ids=waf_ids,
                allowlist=allowlist,
                queue_outcome=(queue_outcomes or {}).get(sid),
            )
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    in_bar = sum(1 for r in rows if r["in_bar"])
    by_route: dict[str, int] = {}
    for row in rows:
        if row["in_bar"]:
            continue
        by_route[row["route"]] = by_route.get(row["route"], 0) + 1
    return {
        "cohort_size": len(rows),
        "in_bar": in_bar,
        "gaps": len(rows) - in_bar,
        "routed_hosted": by_route.get("hosted", 0),
        "routed_residential": by_route.get("residential", 0),
        "routed_static": by_route.get("static_html", 0),
        "human": by_route.get("human", 0),
    }


def resolve_residential_only(
    *,
    dispatch_only: str | None,
    allowlist: dict[str, dict[str, Any]],
    cap: int = RESIDENTIAL_CAP,
) -> list[str]:
    requested = parse_only_ids(dispatch_only) or ["nyu"]
    allowed = []
    unknown = []
    for sid in requested:
        if sid in allowlist:
            allowed.append(sid)
        else:
            unknown.append(sid)
    if unknown:
        raise SystemExit(
            "residential --only includes ids not on the allowlist: "
            + ", ".join(unknown)
        )
    if not allowed:
        raise SystemExit("residential --only is empty after allowlist intersection")
    if len(allowed) > cap:
        raise SystemExit(
            f"residential --only has {len(allowed)} ids; cap is {cap}"
        )
    return allowed


def hosted_gap_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [
        row["school_id"]
        for row in rows
        if not row["in_bar"] and row["route"] == "hosted"
    ]


def fetch_queue_outcomes(sb, school_ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        result = (
            sb.table("archive_queue")
            .select("school_id, last_outcome")
            .in_("school_id", school_ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        print(f"warn: archive_queue lookup failed: {exc}", file=sys.stderr)
        return out
    for row in result.data or []:
        sid = canonical_waf_school_id(row.get("school_id") or "")
        if sid:
            out[sid] = row.get("last_outcome") or ""
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--env", default=".env")
    parser.add_argument("--years", default=",".join(DEFAULT_YEARS))
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--resolve-residential-only", action="store_true")
    parser.add_argument("--dispatch-only", default="")
    parser.add_argument("--max", type=int, default=RESIDENTIAL_CAP)
    parser.add_argument("--hosted-gap-ids", action="store_true")
    parser.add_argument("--from-json", type=Path)
    args = parser.parse_args(argv)

    if args.resolve_residential_only:
        allowlist = load_allowlist(args.allowlist)
        ids = resolve_residential_only(
            dispatch_only=args.dispatch_only,
            allowlist=allowlist,
            cap=args.max,
        )
        print(",".join(ids))
        return 0

    if args.hosted_gap_ids:
        if args.from_json is None or not args.from_json.exists():
            raise SystemExit("--hosted-gap-ids requires --from-json")
        payload = json.loads(args.from_json.read_text())
        print(",".join(hosted_gap_ids(payload.get("schools") or [])))
        return 0

    years = [y.strip() for y in args.years.split(",") if y.strip()]
    cohort_ids = load_cohort_ids(args.cohort)
    schools = load_schools_by_id()
    missing = [sid for sid in cohort_ids if sid not in schools]
    if missing:
        raise SystemExit("cohort ids missing from schools.yaml: " + ", ".join(missing))

    from dotenv import load_dotenv
    from supabase import create_client

    from tools.data_quality.published_years import fetch_year_byte_coverage

    env_path = Path(args.env)
    if env_path.exists():
        load_dotenv(env_path)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SUPABASE_ANON_KEY"
    )
    if not url or not key:
        raise SystemExit("SUPABASE_URL and a Supabase key are required to score")
    sb = create_client(url, key)
    byte_coverage = fetch_year_byte_coverage(sb, cohort_ids, years)
    allowlist = load_allowlist(args.allowlist)
    starting_urls = load_starting_urls()
    waf_ids = load_waf_ids()
    queue_outcomes = fetch_queue_outcomes(sb, cohort_ids)
    rows = score_cohort(
        cohort_ids=cohort_ids,
        schools=schools,
        years=years,
        byte_coverage=byte_coverage,
        starting_urls=starting_urls,
        waf_ids=waf_ids,
        allowlist=allowlist,
        queue_outcomes=queue_outcomes,
    )
    summary = summarize(rows)
    payload = {
        "years": years,
        "summary": summary,
        "schools": rows,
    }
    text = json.dumps(payload, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text)
    print(json.dumps(summary, indent=2), file=sys.stderr)
    if not args.json_out:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
