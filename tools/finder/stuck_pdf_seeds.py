"""Flag schools whose discovery seed is a one-file PDF (or xlsx/docx).

A direct-document seed whose newest archived year is older than the current
CDS cycle is the OU failure class: weekly archive refresh re-verifies that
one file and never looks for a listing. How many older years are archived
does not matter: an earlier cap of two archived years kept 90 such schools
out of the monthly re-probe (75 flagged with the cap, 165 without it, on
2026-11-24). Many of them hold several years from the College Transitions
mirror, which ends at 2024-25, behind a seed that is one old file. Counting
only dated documents as years (see classify_school) flags 25 more: 190.

This is the coverage job for that class. It reads schools.yaml and public
cds_documents year counts, then emits JSON / markdown / id lists the monthly
finder workflow and probe_urls.py consume.

Usage:
    python tools/finder/stuck_pdf_seeds.py
    python tools/finder/stuck_pdf_seeds.py --ids-only
    python tools/finder/stuck_pdf_seeds.py --out-json stuck.json --out-md stuck.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import unquote, urlparse
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DOCUMENT_EXT_RE = re.compile(r"\.(pdf|xlsx|docx)(\?|#|$)", re.I)
DEFAULT_API = "https://api.collegedata.fyi"
YEAR_RE = re.compile(r"^\d{4}-\d{2}$")


def default_min_fresh_year(today: date | None = None) -> str:
    """Freshness floor: the CDS year that should already be on a listing.

    Before September, last complete cycle is year-2/year-1 (Aug 2026 →
    2024-25). From September, expect the previous academic year (Sep 2026
    → 2025-26).

    One rule, several copies: SQL cds_freshness_floor(), web/src/lib/freshness.ts
    cdsFreshnessFloor, and tools/ops/discovery_renewal.py once it lands. All are
    tested against tests/fixtures/freshness_floor_cases.json.
    """
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start - 1}-{str(start)[2:]}"


def is_direct_doc_seed(url: str | None) -> bool:
    if not url:
        return False
    return bool(DOCUMENT_EXT_RE.search(url))


# Mirrors the section-file patterns in supabase/functions/_shared/resolve.ts
# (sectionLetterFromFilename), minus the bare single-letter filename shape,
# which is too ambiguous for a seed URL on its own.
SECTION_SEED_RES = (
    re.compile(r"(?:^|[-_ .])section[-_ ]?([a-j])(?:[-_ .]|$)", re.I),
    re.compile(r"(?<![a-z])cds[-_ ]?\d{4}(?:[-_ ]?(?:\d{4}|\d{2}))?[-_ ]?([a-j])(?:[-_ .]|\d|$)", re.I),
    re.compile(r"(?<![a-z])cds[-_ ]?([a-j])(?:[-_ .]|\d|$)", re.I),
)


def is_section_seed(url: str | None) -> bool:
    """True when the seed is one CDS section file (Section D, CDS_2022-2023-D.pdf).

    Archive refresh re-verifies the seed itself, so a section seed can only
    ever yield that one section, however many other years are archived.
    """
    if not is_direct_doc_seed(url):
        return False
    filename = unquote(urlparse(url or "").path.rsplit("/", 1)[-1])
    return any(rx.search(filename) for rx in SECTION_SEED_RES)


SATELLITE_MARKERS = (
    "online",
    "professional-programs",
    "continuing",
    "digital-immersion",
    "regional",
    "system-office",
    "system-administration",
    "center-for-online",
    "institute-of-international",
    "hamilton",
    "middletown",
    "florham",
)
MAIN_MARKERS = (
    "main-campus",
    "main campus",
    "-at-kent",
    "campus-immersion",
)


def choose_canonical_school(schools: list[dict]) -> dict:
    """Prefer a main-campus row when several UNITIDs share one seed URL."""

    def score(school: dict) -> tuple[int, int, str]:
        sid = school.get("id") or ""
        name = (school.get("name") or "").lower()
        blob = f"{sid} {name}"
        points = 0
        if any(m in sid or m in name for m in MAIN_MARKERS):
            points += 100
        if any(m in blob for m in SATELLITE_MARKERS):
            points -= 80
        return (points, -len(sid), sid)

    return max(schools, key=score)


SKIP_REASONS = {
    "listing_seed": (
        "the seed is a listing page, not a document. The re-probe can never "
        "replace a listing page (probe_urls.should_replace_seed), so these are "
        "not fed to it. Listing seeds behind the cycle are counted by seed_age "
        "and listed in the discovery renewal report (#462)"
    ),
    "no_seed": "the school has no discovery seed, so there is nothing to go stale",
}


def year_start(year: str | None) -> int | None:
    """Start year of a real CDS year (``2025-26`` -> 2025), else None.

    ``unknown`` and anything else that is not ``YYYY-YY`` is None. Never
    compare year strings directly: ``unknown`` sorts above every real year.
    """
    if not year or not YEAR_RE.match(year):
        return None
    return int(year[:4])


def classify_school(
    school: dict,
    years: list[str],
    *,
    min_fresh_year: str,
) -> dict[str, Any]:
    """Put one school in exactly one bucket: flagged, fresh or skipped."""
    floor = year_start(min_fresh_year)
    if floor is None:
        raise ValueError(f"min_fresh_year is not a CDS year: {min_fresh_year!r}")
    seed = school.get("discovery_seed_url") or school.get("cds_url_hint") or ""
    if not seed:
        return {"bucket": "skipped", "reason": "no_seed", "id": school.get("id")}
    if not is_direct_doc_seed(seed):
        return {"bucket": "skipped", "reason": "listing_seed", "id": school.get("id")}
    # Real years only: the archive files a document it cannot date under
    # "unknown", and as a string that sorts above every year, which made a
    # school holding one such document look fresh forever.
    unique_years = sorted({y for y in years if year_start(y) is not None})
    latest = unique_years[-1] if unique_years else None
    n_years = len(unique_years)
    if is_section_seed(seed):
        reason = "section_seed"
    else:
        if latest and year_start(latest) >= floor:
            return {"bucket": "fresh", "reason": "fresh", "id": school.get("id")}
        reason = "stale_single_document"
    return {
        "bucket": "flagged",
        "reason": reason,
        "id": school.get("id"),
        "name": school.get("name"),
        "domain": school.get("domain"),
        "seed": seed,
        "years": unique_years,
        "n_years": n_years,
        "latest": latest,
        "min_fresh_year": min_fresh_year,
    }


def check_accounting(counts: dict[str, int]) -> None:
    """Raise unless flagged + fresh + skipped == total and skips add up."""
    accounted = counts["flagged"] + counts["fresh"] + counts["skipped"]
    by_reason = sum(counts[f"skipped_{r}"] for r in SKIP_REASONS)
    if accounted != counts["total"] or by_reason != counts["skipped"]:
        raise RuntimeError(
            "school accounting does not add up: "
            f"flagged {counts['flagged']} + fresh {counts['fresh']} + "
            f"skipped {counts['skipped']} != total {counts['total']} "
            f"(skip reasons sum to {by_reason})"
        )


def classify_all(
    schools: list[dict],
    years_by_school: dict[str, list[str]],
    *,
    min_fresh_year: str,
) -> tuple[list[dict], dict[str, int]]:
    """Classify every school; return (flagged rows, counts).

    Raises if a school fell out of every bucket: a sweep that reports only
    what it caught looks the same whether it found every case or a third.
    """
    flagged: list[dict] = []
    counts: dict[str, int] = {
        "total": len(schools),
        "flagged": 0,
        "fresh": 0,
        "skipped": 0,
    }
    for reason in SKIP_REASONS:
        counts[f"skipped_{reason}"] = 0
    for school in schools:
        row = classify_school(
            school,
            years_by_school.get(school.get("id") or "", []),
            min_fresh_year=min_fresh_year,
        )
        bucket = row["bucket"]
        counts[bucket] += 1
        if bucket == "flagged":
            flagged.append(row)
        elif bucket == "skipped":
            counts[f"skipped_{row['reason']}"] += 1
    check_accounting(counts)
    return flagged, counts


def parse_content_range_total(value: str | None) -> int | None:
    """Total from a PostgREST ``Content-Range: 0-999/6048`` header."""
    m = re.match(r"^(?:\d+-\d+|\*)/(\d+)$", (value or "").strip())
    return int(m.group(1)) if m else None


def fetch_years_by_school(
    api_url: str,
    anon_key: str | None,
    *,
    page: int = 1000,
    opener=urllib.request.urlopen,
) -> dict[str, list[str]]:
    """Filed years per school: ``canonical_year`` of live published documents.

    Reads ``cds_manifest``, the view the postmortem defines "filed year"
    against (``cds_documents.cds_year`` is the raw detected year, not the
    canonical one). Fails loudly: no key, an HTTP error, an empty result or
    a short page raises, because "0 years found" would flag every school.
    """
    if not anon_key:
        raise SystemExit(
            "NEXT_PUBLIC_SUPABASE_ANON_KEY (or --anon-key) is required: "
            "without it every school looks like it has no archived years"
        )
    headers = {
        "Accept": "application/json",
        "User-Agent": "collegedata-pipeline/stuck-pdf-seeds",
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Prefer": "count=exact",
    }
    by_school: dict[str, list[str]] = defaultdict(list)
    fetched = 0
    total: int | None = None
    while total is None or fetched < total:
        path = (
            "/rest/v1/cds_manifest"
            "?select=school_id,canonical_year"
            "&removed_at=is.null"
            "&participation_status=eq.published"
            "&order=document_id.asc"
        )
        req = urllib.request.Request(
            api_url.rstrip("/") + path,
            headers={**headers, "Range-Unit": "items", "Range": f"{fetched}-{fetched + page - 1}"},
        )
        try:
            with opener(req, timeout=60) as resp:
                content_range = resp.headers.get("Content-Range")
                chunk = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"cds_manifest fetch failed: HTTP {exc.code}") from exc
        page_total = parse_content_range_total(content_range)
        if page_total is None:
            raise SystemExit(f"cds_manifest fetch: no usable Content-Range ({content_range!r})")
        if total is None:
            total = page_total
            if total == 0:
                raise SystemExit("cds_manifest returned zero rows; refusing to continue")
        elif page_total != total:
            raise SystemExit(f"cds_manifest changed size mid-fetch ({total} -> {page_total})")
        if not chunk:
            raise SystemExit(
                f"cds_manifest short read: got {fetched} of {total} rows and an empty page"
            )
        fetched += len(chunk)
        for row in chunk:
            sid = row.get("school_id")
            year = row.get("canonical_year")
            if sid and year:
                by_school[sid].append(year)
    if fetched != total:
        raise SystemExit(f"cds_manifest fetched {fetched} rows, expected {total}")
    return by_school


def load_schools(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("schools") or []


def shared_seed_groups(schools: list[dict]) -> list[dict[str, Any]]:
    by_url: dict[str, list[dict]] = defaultdict(list)
    for school in schools:
        seed = school.get("discovery_seed_url") or ""
        if seed:
            by_url[seed].append(school)
    groups = []
    for seed, group in sorted(by_url.items()):
        if len(group) < 2:
            continue
        keeper = choose_canonical_school(group)
        groups.append({
            "seed": seed,
            "keeper_id": keeper.get("id"),
            "school_ids": [s.get("id") for s in group],
        })
    return groups


def render_counts(counts: dict[str, int]) -> list[str]:
    lines = [
        f"Schools checked: **{counts['total']}** = flagged {counts['flagged']} "
        f"+ fresh {counts['fresh']} + skipped {counts['skipped']}",
        "",
        "Skipped, by reason:",
        "",
    ]
    for reason, why in SKIP_REASONS.items():
        lines.append(f"- `{reason}`: {counts[f'skipped_{reason}']} ({why})")
    lines.append("")
    return lines


def render_markdown(
    stuck: list[dict],
    shared: list[dict],
    min_fresh_year: str,
    counts: dict[str, int],
) -> str:
    lines = [
        f"# Stuck PDF discovery seeds",
        "",
        *render_counts(counts),
        f"Freshness floor: `{min_fresh_year}`. `stale_single_document`: "
        f"direct-document seed, newest archived year older than the floor "
        f"(or none archived). `section_seed`: the seed is one CDS section file.",
        "",
        f"Stuck schools: **{len(stuck)}**",
        "",
        "| school_id | reason | latest | years | seed |",
        "|---|---|---|---|---|",
    ]
    for row in stuck:
        seed = (row.get("seed") or "").replace("|", "\\|")
        lines.append(
            f"| `{row['id']}` | {row.get('reason', '')} | {row.get('latest') or 'none'} | "
            f"{row.get('n_years', 0)} | `{seed}` |"
        )
    if shared:
        lines += [
            "",
            "## Identical seeds shared across UNITIDs",
            "",
            "| keeper | also assigned to | seed |",
            "|---|---|---|",
        ]
        for group in shared:
            others = [s for s in group["school_ids"] if s != group["keeper_id"]]
            seed = group["seed"].replace("|", "\\|")
            lines.append(
                f"| `{group['keeper_id']}` | "
                f"{', '.join(f'`{s}`' for s in others)} | `{seed}` |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--schools-yaml", type=Path, default=ROOT / "schools.yaml")
    ap.add_argument("--api-url", default=os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or DEFAULT_API)
    ap.add_argument(
        "--anon-key",
        default=os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "",
    )
    ap.add_argument("--min-fresh-year", default=default_min_fresh_year())
    ap.add_argument("--ids-only", action="store_true")
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    ap.add_argument("--out-ids", type=Path)
    args = ap.parse_args()

    schools = load_schools(args.schools_yaml)
    years_by_school = fetch_years_by_school(args.api_url, args.anon_key)
    stuck, counts = classify_all(
        schools, years_by_school, min_fresh_year=args.min_fresh_year
    )
    stuck.sort(key=lambda r: ((year_start(r.get("latest")) or 0), r["id"] or ""))
    shared = shared_seed_groups(schools)

    skipped_by = ", ".join(f"{r} {counts['skipped_' + r]}" for r in SKIP_REASONS)
    print(
        f"stuck_pdf_seeds flagged {counts['flagged']}  "
        f"fresh {counts['fresh']}  skipped {counts['skipped']} ({skipped_by})  "
        f"total {counts['total']}  "
        f"shared_url_groups {len(shared)}  "
        f"min_fresh_year {args.min_fresh_year}",
        file=sys.stderr,
    )
    if args.ids_only:
        sys.stdout.write("\n".join(r["id"] for r in stuck if r.get("id")) + "\n")

    payload = {
        "min_fresh_year": args.min_fresh_year,
        "counts": counts,
        "skip_reasons": SKIP_REASONS,
        "stuck": stuck,
        "shared_seed_groups": shared,
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(stuck, shared, args.min_fresh_year, counts))
    if args.out_ids:
        args.out_ids.parent.mkdir(parents=True, exist_ok=True)
        args.out_ids.write_text(
            "\n".join(r["id"] for r in stuck if r.get("id")) + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
