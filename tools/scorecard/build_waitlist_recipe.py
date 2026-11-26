#!/usr/bin/env python3
"""Build the checked-in dataset for /recipes/waitlist-odds.

Reads the public views only (anon key): school_browser_rows (C1/C2 values),
institution_directory (state, control, undergraduate enrollment) and
scorecard_summary (Carnegie class, enrollment fallback). Nothing is written to
a database.

Selection rules (docs/recipes/waitlist-odds.md, "The demo" and "How to
reproduce"):

* A school-year row is kept when it exposes at least one of the three C2
  wait-list counts (offered, accepted, admitted). Rows that only say "we have a
  wait list" with no count are not kept: the page calls the non-complete rows
  "partial", meaning some values are present.
* Sub-institutional rows (a school_browser_rows row carrying a
  sub_institutional label) are skipped. They share the parent's IPEDS id and
  would pick up the parent's federal facts.
* The canonical_year must be a well-formed consecutive pair such as "2024-25"
  that agrees with year_start. Malformed labels (for example "2025-03") are
  skipped.
* Rows whose published counts cannot all be true are excluded and reported:
  more accepting than offered, more admitted than accepting, more admitted
  than offered, or a negative count. A row is never silently repaired.
* Federal facts are attached only by IPEDS id. A row with no IPEDS id gets
  "Unknown control" / "Unknown Carnegie" and null state; there is no slug
  fallback.
* A row is "complete" when all three counts are present. The page excludes
  rows with zero accepted spots, collapses duplicate school-year rows and
  flags near-total high-volume admits in web/src/lib/waitlist-recipe-analysis.ts;
  this builder keeps those rows so the page logic stays the single place that
  decides.

Regenerate (the anon key is read from SUPABASE_ANON_KEY or
NEXT_PUBLIC_SUPABASE_ANON_KEY in the environment, the repo-root .env, or
web/.env.local):

    cd <repo root>
    python tools/scorecard/build_waitlist_recipe.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.common.site import API_ORIGIN, runtime_api_origin
from tools.finder.identity_guard import (
    canonicalize_school_url,
    resolve_canonical_school_id,
    validated_canonical_alias_slug_map,
    validated_unique_school_claim_slug_map,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "web/src/lib/waitlist-recipe-data.ts"
SOURCE_API_URL = API_ORIGIN  # display: recorded in generated data
GENERATED_FROM = "school_browser_rows joined to institution_directory and scorecard_summary"
PAGE_SIZE = 1000
USER_AGENT = "quadfile-pipeline/waitlist-recipe"
MIN_ROWS = 100

# Hand-picked (school_id, canonical_year) pairs for the page's "Case studies
# from the corpus" grid. Kept as an explicit list because the original choice
# was editorial. Pairs that no longer resolve to a kept row are reported and
# left out, never replaced.
CASE_STUDY_PAIRS: tuple[tuple[str, str], ...] = (
    ("baylor-university", "2024-25"),
    ("boston-university", "2025-26"),
    ("case-western-reserve-university", "2025-26"),
    ("stony-brook-university", "2025-26"),
    ("the-university-of-tennessee-knoxville", "2025-26"),
    ("uc-berkeley", "2025-26"),
    ("georgia-tech", "2024-25"),
)

SELECTIVITY_LABELS = (
    "Under 10% admit rate",
    "10-20% admit rate",
    "20-40% admit rate",
    "40%+ admit rate",
    "No admit rate",
)
CONTROL_LABELS = ("Public", "Private nonprofit", "Unknown control")
SIZE_LABELS = (
    "Small (<2.5k undergrads)",
    "Midsize (2.5k-10k)",
    "Large (10k-25k)",
    "Very large (25k+)",
    "Unknown size",
)
CARNEGIE_LABELS = (
    "Doctoral universities",
    "Master's colleges",
    "Baccalaureate colleges",
    "Unknown Carnegie",
)

BROWSER_SELECT = ",".join(
    [
        "document_id",
        "ipeds_id",
        "school_id",
        "school_name",
        "sub_institutional",
        "canonical_year",
        "year_start",
        "applied",
        "admitted",
        "enrolled_first_year",
        "acceptance_rate",
        "yield_rate",
        "archive_url",
        "wait_list_policy",
        "wait_list_offered",
        "wait_list_accepted",
        "wait_list_admitted",
        "admission_strategy_card_quality",
    ]
)

TYPES_BLOCK = """export type WaitlistRecipeRow = {
  documentId: string;
  ipedsId?: string;
  schoolId: string;
  schoolName: string;
  year: string;
  yearStart: number;
  state: string | null;
  control: string;
  carnegie: string;
  size: string;
  selectivity: string;
  applied: number | null;
  admitted: number | null;
  enrolledFirstYear: number | null;
  acceptanceRate: number | null;
  yieldRate: number | null;
  undergradEnrollment: number | null;
  waitListPolicy: boolean | null;
  waitListOffered: number | null;
  waitListAccepted: number | null;
  waitListAdmitted: number | null;
  quality: string | null;
  schoolUrl: string;
  archiveUrl: string | null;
  complete: boolean;
  waitListOptInRate: number | null;
  waitListSuccessRate: number | null;
  waitListOfferSuccessRate: number | null;
  relativeToRegularAdmitRate: number | null;
};

export type WaitlistBucketSummary = {
  label: string;
  rows: number;
  schools: number;
  medianSuccessRate: number | null;
  weightedSuccessRate: number | null;
  medianOfferSuccessRate: number | null;
  zeroishShare: number;
  medianAccepted: number;
};
"""

_YEAR_RE = re.compile(r"^(\d{4})-(\d{2})$")


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def postgrest_get_all(
    base_url: str,
    api_key: str,
    table: str,
    params: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_params = dict(params)
        page_params.update({"limit": str(PAGE_SIZE), "offset": str(offset)})
        query = urllib.parse.urlencode(page_params, safe="(),.")
        url = f"{base_url.rstrip('/')}/rest/v1/{table}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                page = json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"PostgREST {table} failed with HTTP {exc.code}") from None
        if not isinstance(page, list):
            raise ValueError(f"PostgREST {table} returned a non-row response")
        if not page:
            return rows
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += len(page)


# ---------------------------------------------------------------- pure logic


def round4(value: float | None) -> float | None:
    """Round half up to four places, matching the page's JS round4."""
    if value is None or not math.isfinite(value):
        return None
    return math.floor(value * 10000 + 0.5) / 10000


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number != int(number):
        return None
    return int(number)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def valid_year_label(label: Any, year_start: Any) -> bool:
    """True for a consecutive "YYYY-YY" pair that agrees with year_start."""
    if not isinstance(label, str):
        return False
    match = _YEAR_RE.match(label)
    if not match:
        return False
    start = int(match.group(1))
    if int(match.group(2)) != (start + 1) % 100:
        return False
    return year_start is None or _count(year_start) == start


def impossible_counts_reason(
    offered: int | None, accepted: int | None, admitted: int | None
) -> str | None:
    """Why the published counts cannot all be true, or None.

    Only comparisons between counts that are present are made, so a partial row
    is judged on what it does publish.
    """
    for name, value in (("offered", offered), ("accepted", accepted), ("admitted", admitted)):
        if value is not None and value < 0:
            return f"negative {name} count"
    if offered is not None and accepted is not None and accepted > offered:
        return "more accepted a spot than were offered one"
    if accepted is not None and admitted is not None and admitted > accepted:
        return "more admitted from the wait list than accepted a spot"
    if offered is not None and admitted is not None and admitted > offered:
        return "more admitted from the wait list than were offered a spot"
    return None


def selectivity_label(acceptance_rate: float | None) -> str:
    if acceptance_rate is None:
        return "No admit rate"
    if acceptance_rate < 0.10:
        return "Under 10% admit rate"
    if acceptance_rate < 0.20:
        return "10-20% admit rate"
    if acceptance_rate < 0.40:
        return "20-40% admit rate"
    return "40%+ admit rate"


def size_label(undergrad: float | None) -> str:
    if undergrad is None:
        return "Unknown size"
    if undergrad < 2500:
        return "Small (<2.5k undergrads)"
    if undergrad < 10000:
        return "Midsize (2.5k-10k)"
    if undergrad < 25000:
        return "Large (10k-25k)"
    return "Very large (25k+)"


def control_label(code: Any) -> str:
    """IPEDS CONTROL: 1 public, 2 private nonprofit. Anything else is unknown."""
    number = _count(code)
    if number == 1:
        return "Public"
    if number == 2:
        return "Private nonprofit"
    return "Unknown control"


def carnegie_label(code: Any) -> str:
    """Carnegie basic classification (2021): 15-17 doctoral, 18-20 master's, 21-22 baccalaureate."""
    number = _count(code)
    if number is not None and 15 <= number <= 17:
        return "Doctoral universities"
    if number is not None and 18 <= number <= 20:
        return "Master's colleges"
    if number is not None and 21 <= number <= 22:
        return "Baccalaureate colleges"
    return "Unknown Carnegie"


def derive_rates(
    offered: int | None,
    accepted: int | None,
    admitted: int | None,
    acceptance_rate: float | None,
) -> dict[str, float | None]:
    opt_in = round4(accepted / offered) if offered and accepted is not None else None
    success = round4(admitted / accepted) if accepted and admitted is not None else None
    offer_success = round4(admitted / offered) if offered and admitted is not None else None
    relative = None
    if success is not None and acceptance_rate:
        relative = round(success / acceptance_rate + 1e-12, 2)
    return {
        "waitListOptInRate": opt_in,
        "waitListSuccessRate": success,
        "waitListOfferSuccessRate": offer_success,
        "relativeToRegularAdmitRate": relative,
    }


def build_row(
    browser: Mapping[str, Any],
    directory: Mapping[str, Any] | None,
    scorecard: Mapping[str, Any] | None,
    *,
    school_id: str,
) -> dict[str, Any]:
    offered = _count(browser.get("wait_list_offered"))
    accepted = _count(browser.get("wait_list_accepted"))
    admitted = _count(browser.get("wait_list_admitted"))
    acceptance_rate = round4(_float(browser.get("acceptance_rate")))
    undergrad = None
    if directory is not None:
        undergrad = _float(directory.get("undergraduate_enrollment"))
    if not undergrad and scorecard is not None:
        undergrad = _float(scorecard.get("enrollment"))
    undergrad = undergrad if undergrad and undergrad > 0 else None
    year = browser["canonical_year"]
    row: dict[str, Any] = {
        "documentId": browser["document_id"],
    }
    ipeds_id = browser.get("ipeds_id")
    if isinstance(ipeds_id, str) and ipeds_id:
        row["ipedsId"] = ipeds_id
    state = directory.get("state") if directory is not None else None
    row.update(
        {
            "schoolId": school_id,
            "schoolName": browser["school_name"],
            "year": year,
            "yearStart": int(browser["year_start"]),
            "state": state if isinstance(state, str) and state else None,
            "control": control_label(directory.get("control") if directory is not None else None),
            "carnegie": carnegie_label(scorecard.get("carnegie_basic") if scorecard is not None else None),
            "size": size_label(undergrad),
            "selectivity": selectivity_label(acceptance_rate),
            "applied": _count(browser.get("applied")),
            "admitted": _count(browser.get("admitted")),
            "enrolledFirstYear": _count(browser.get("enrolled_first_year")),
            "acceptanceRate": acceptance_rate,
            "yieldRate": round4(_float(browser.get("yield_rate"))),
            "undergradEnrollment": int(undergrad) if undergrad else None,
            "waitListPolicy": browser.get("wait_list_policy")
            if isinstance(browser.get("wait_list_policy"), bool)
            else None,
            "waitListOffered": offered,
            "waitListAccepted": accepted,
            "waitListAdmitted": admitted,
            "quality": browser.get("admission_strategy_card_quality"),
            "schoolUrl": f"/schools/{school_id}/{year}",
            "archiveUrl": browser.get("archive_url") or None,
            "complete": offered is not None and accepted is not None and admitted is not None,
        }
    )
    row.update(derive_rates(offered, accepted, admitted, acceptance_rate))
    return row


def select_rows(
    browser_rows: Iterable[Mapping[str, Any]],
    directory_by_ipeds: Mapping[str, Mapping[str, Any]],
    scorecard_by_ipeds: Mapping[str, Mapping[str, Any]],
    *,
    canonical_by_ipeds: Mapping[str, str] | None = None,
    canonical_by_alias: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply the selection rules. Returns (rows, exclusion report)."""
    canonical_by_ipeds = canonical_by_ipeds or {}
    canonical_by_alias = canonical_by_alias or {}
    report: dict[str, Any] = {
        "inspected": 0,
        "noWaitListCounts": 0,
        "subInstitutional": 0,
        "malformedYear": [],
        "impossible": [],
    }
    kept: list[dict[str, Any]] = []
    for browser in browser_rows:
        report["inspected"] += 1
        counts = [_count(browser.get(k)) for k in ("wait_list_offered", "wait_list_accepted", "wait_list_admitted")]
        if all(value is None for value in counts):
            report["noWaitListCounts"] += 1
            continue
        if browser.get("sub_institutional"):
            report["subInstitutional"] += 1
            continue
        if not valid_year_label(browser.get("canonical_year"), browser.get("year_start")):
            report["malformedYear"].append(
                {
                    "documentId": browser.get("document_id"),
                    "schoolId": browser.get("school_id"),
                    "year": browser.get("canonical_year"),
                }
            )
            continue
        reason = impossible_counts_reason(*counts)
        if reason:
            report["impossible"].append(
                {
                    "documentId": browser.get("document_id"),
                    "schoolId": browser.get("school_id"),
                    "year": browser.get("canonical_year"),
                    "offered": counts[0],
                    "accepted": counts[1],
                    "admitted": counts[2],
                    "reason": reason,
                }
            )
            continue
        ipeds_id = browser.get("ipeds_id") if isinstance(browser.get("ipeds_id"), str) else None
        school_id = resolve_canonical_school_id(
            browser.get("school_id"),
            ipeds_id=ipeds_id,
            canonical_by_ipeds=dict(canonical_by_ipeds),
            canonical_by_alias=dict(canonical_by_alias),
        )
        row = build_row(
            browser,
            directory_by_ipeds.get(ipeds_id) if ipeds_id else None,
            scorecard_by_ipeds.get(ipeds_id) if ipeds_id else None,
            school_id=school_id,
        )
        if row["archiveUrl"]:
            row["archiveUrl"] = canonicalize_school_url(
                row["archiveUrl"],
                canonical_school_id=school_id,
                canonical_by_alias=dict(canonical_by_alias),
            )
        kept.append(row)
    # Newest year first, then school name descending (the order the page's
    # first-wins duplicate collapse has always seen); document id breaks ties.
    kept.sort(key=lambda r: r["documentId"])
    kept.sort(key=lambda r: r["schoolName"], reverse=True)
    kept.sort(key=lambda r: r["yearStart"], reverse=True)
    report["malformedYear"].sort(key=lambda r: str(r["documentId"]))
    report["impossible"].sort(key=lambda r: (str(r["schoolId"]), str(r["year"]), str(r["documentId"])))
    return kept, report


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    success = [r["waitListSuccessRate"] for r in rows if r["waitListSuccessRate"] is not None]
    offer_success = [r["waitListOfferSuccessRate"] for r in rows if r["waitListOfferSuccessRate"] is not None]
    accepted = sum(r["waitListAccepted"] or 0 for r in rows)
    admitted = sum(r["waitListAdmitted"] or 0 for r in rows)
    zeroish = sum(1 for r in rows if r["waitListSuccessRate"] is not None and r["waitListSuccessRate"] < 0.02)
    return {
        "medianSuccessRate": round4(_median(success)),
        "weightedSuccessRate": round4(admitted / accepted) if accepted > 0 else None,
        "medianOfferSuccessRate": round4(_median(offer_success)),
        "zeroishRows": zeroish,
        "zeroishShare": round4(zeroish / len(rows)) if rows else 0,
    }


def rate_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Complete rows with at least one accepted spot (what "completeRows" counts)."""
    return [r for r in rows if r["complete"] and (r["waitListAccepted"] or 0) > 0]


def build_summary(rows: list[Mapping[str, Any]], generated_at: str) -> dict[str, Any]:
    complete = rate_rows(rows)
    stats = summarize_rows(list(complete))
    accepted = [r["waitListAccepted"] for r in complete]
    schools = len({r["schoolId"] for r in complete})
    return {
        "allVisibleRows": len(rows),
        "completeRows": len(complete),
        "completeSchools": schools,
        "latestCompleteSchools": schools,
        "partialRows": len(rows) - len(complete),
        "medianSuccessRate": stats["medianSuccessRate"],
        "weightedSuccessRate": stats["weightedSuccessRate"],
        "medianOfferSuccessRate": stats["medianOfferSuccessRate"],
        "zeroishRows": stats["zeroishRows"],
        "zeroishShare": stats["zeroishShare"],
        "medianAcceptedWaitList": int(_median(accepted)) if accepted else 0,
        "largestAcceptedWaitList": max(accepted) if accepted else 0,
        "generatedFrom": GENERATED_FROM,
        "generatedAt": generated_at,
    }


def build_buckets(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    complete = rate_rows(rows)
    out: dict[str, list[dict[str, Any]]] = {}
    for key, labels in (
        ("selectivity", SELECTIVITY_LABELS),
        ("control", CONTROL_LABELS),
        ("size", SIZE_LABELS),
        ("carnegie", CARNEGIE_LABELS),
    ):
        buckets = []
        for label in labels:
            members = [r for r in complete if r[key] == label]
            if not members:
                # An empty bucket (for example "Unknown control" once every row
                # joins on IPEDS id) would render as a blank chart band.
                continue
            stats = summarize_rows(members)
            accepted = [r["waitListAccepted"] for r in members]
            buckets.append(
                {
                    "label": label,
                    "rows": len(members),
                    "schools": len({r["schoolId"] for r in members}),
                    "medianSuccessRate": stats["medianSuccessRate"],
                    "weightedSuccessRate": stats["weightedSuccessRate"],
                    "medianOfferSuccessRate": stats["medianOfferSuccessRate"],
                    "zeroishShare": stats["zeroishShare"],
                    "medianAccepted": int(_median(accepted)) if accepted else 0,
                }
            )
        out[key] = buckets
    return out


def pick_cases(
    rows: list[Mapping[str, Any]],
    pairs: Iterable[tuple[str, str]] = CASE_STUDY_PAIRS,
) -> tuple[list[Mapping[str, Any]], list[tuple[str, str]]]:
    """Case-study rows for the listed pairs, plus the pairs with no kept row."""
    cases: list[Mapping[str, Any]] = []
    missing: list[tuple[str, str]] = []
    for school_id, year in pairs:
        matches = sorted(
            (r for r in rows if r["schoolId"] == school_id and r["year"] == year),
            key=lambda r: r["documentId"],
        )
        if matches:
            cases.append(matches[0])
        else:
            missing.append((school_id, year))
    return cases, missing


def render_typescript(
    rows: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
    buckets: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
    report: Mapping[str, Any],
) -> str:
    def dump(value: Any) -> str:
        return json.dumps(value, indent=2, ensure_ascii=False)

    header = [
        "// Generated by tools/scorecard/build_waitlist_recipe.py. Do not edit by hand.",
        "// Regenerate: python tools/scorecard/build_waitlist_recipe.py",
        f"// Source: {GENERATED_FROM} ({SOURCE_API_URL}).",
        f"// Generated at {summary['generatedAt']}.",
        f"// Excluded as internally impossible: {len(report['impossible'])} row(s).",
    ]
    for item in report["impossible"]:
        header.append(
            f"//   {item['schoolId']} {item['year']}: offered {item['offered']}, "
            f"accepted {item['accepted']}, admitted {item['admitted']} ({item['reason']})"
        )
    return (
        "\n".join(header)
        + "\n\n"
        + TYPES_BLOCK
        + "\nexport const WAITLIST_RECIPE_SUMMARY = "
        + dump(summary)
        + " as const;\n\n"
        + "export const WAITLIST_BUCKETS = "
        + dump(buckets)
        + " as const satisfies Record<string, readonly WaitlistBucketSummary[]>;\n\n"
        + "export const WAITLIST_CASES = "
        + dump(cases)
        + " as const satisfies readonly WaitlistRecipeRow[];\n\n"
        + "export const WAITLIST_ROWS = "
        + dump(rows)
        + " as const satisfies readonly WaitlistRecipeRow[];\n"
    )


# ------------------------------------------------------------------ fetching


def fetch_inputs(base_url: str, api_key: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "browser": postgrest_get_all(
            base_url,
            api_key,
            "school_browser_rows",
            {"select": BROWSER_SELECT, "order": "document_id.asc"},
        ),
        "directory": postgrest_get_all(
            base_url,
            api_key,
            "institution_directory",
            {"select": "ipeds_id,state,control,undergraduate_enrollment", "order": "ipeds_id.asc"},
        ),
        "scorecard": postgrest_get_all(
            base_url,
            api_key,
            "scorecard_summary",
            {"select": "ipeds_id,carnegie_basic,enrollment", "order": "ipeds_id.asc"},
        ),
    }


def _index_by_ipeds(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        ipeds_id = row.get("ipeds_id")
        if isinstance(ipeds_id, str) and ipeds_id:
            indexed[ipeds_id] = row
    return indexed


def build_artifact(
    inputs: Mapping[str, list[dict[str, Any]]],
    *,
    generated_at: str,
    canonical_school_ids: Mapping[str, str] | None = None,
    alias_school_ids: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    rows, report = select_rows(
        inputs["browser"],
        _index_by_ipeds(inputs["directory"]),
        _index_by_ipeds(inputs["scorecard"]),
        canonical_by_ipeds=canonical_school_ids,
        canonical_by_alias=alias_school_ids,
    )
    if len(rows) < MIN_ROWS:
        raise ValueError(f"waitlist recipe selected only {len(rows)} rows")
    cases, missing_cases = pick_cases(rows)
    report["missingCases"] = missing_cases
    return {
        "rows": rows,
        "summary": build_summary(rows, generated_at),
        "buckets": build_buckets(rows),
        "cases": cases,
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--schools-yaml",
        type=Path,
        default=REPO_ROOT / "tools/finder/schools.yaml",
        help="Identity-guarded canonical school slugs keyed by IPEDS UNITID",
    )
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args()
    try:
        date.fromisoformat(args.generated_at)
    except ValueError:
        parser.error("--generated-at must be an ISO date (YYYY-MM-DD)")

    # Only the public anon key is read from these files; nothing else is used.
    for env_path in (REPO_ROOT / ".env", REPO_ROOT / "web/.env.local"):
        load_env(env_path)
    supabase_url = runtime_api_origin()
    api_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    )
    if not api_key:
        print("error: SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY is required", file=sys.stderr)
        return 2

    try:
        canonical_school_ids = validated_unique_school_claim_slug_map(schools_path=args.schools_yaml)
        alias_school_ids = validated_canonical_alias_slug_map(schools_path=args.schools_yaml)
        artifact = build_artifact(
            fetch_inputs(supabase_url, api_key),
            generated_at=args.generated_at,
            canonical_school_ids=canonical_school_ids,
            alias_school_ids=alias_school_ids,
        )
    except (OSError, ValueError) as exc:
        print(f"error: waitlist build failed: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        render_typescript(
            artifact["rows"],
            artifact["summary"],
            artifact["buckets"],
            artifact["cases"],
            artifact["report"],
        ),
        encoding="utf-8",
    )
    report = artifact["report"]
    summary = artifact["summary"]
    print(
        f"wrote {args.out} ({summary['allVisibleRows']} rows, {summary['completeRows']} complete "
        f"across {summary['completeSchools']} schools, {summary['partialRows']} partial)"
    )
    print(
        f"skipped: {report['noWaitListCounts']} without counts, {report['subInstitutional']} "
        f"sub-institutional, {len(report['malformedYear'])} malformed year, "
        f"{len(report['impossible'])} impossible"
    )
    for item in report["impossible"]:
        print(f"  impossible: {item}")
    for item in report["malformedYear"]:
        print(f"  malformed year: {item}")
    for school_id, year in report["missingCases"]:
        print(f"  case study not found: {school_id} {year}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
