"""Flag schools whose discovery seed is a one-file PDF (or xlsx/docx).

A direct-document seed plus fewer than a few archived years, with the latest
year older than the current CDS cycle, is the OU failure class: weekly
archive refresh re-verifies that one file and never looks for a listing.

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
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DOCUMENT_EXT_RE = re.compile(r"\.(pdf|xlsx|docx)(\?|#|$)", re.I)
DEFAULT_API = "https://api.collegedata.fyi"


def default_min_fresh_year(today: date | None = None) -> str:
    """Freshness floor: the CDS year that should already be on a listing.

    Before September, last complete cycle is year-2/year-1 (Aug 2026 →
    2024-25). From September, expect the previous academic year (Sep 2026
    → 2025-26).
    """
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start - 1}-{str(start)[2:]}"


def is_direct_doc_seed(url: str | None) -> bool:
    if not url:
        return False
    return bool(DOCUMENT_EXT_RE.search(url))


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


def classify_school(
    school: dict,
    years: list[str],
    *,
    min_fresh_year: str,
    max_years: int,
) -> dict[str, Any] | None:
    seed = school.get("discovery_seed_url") or school.get("cds_url_hint") or ""
    if not is_direct_doc_seed(seed):
        return None
    unique_years = sorted({y for y in years if y})
    latest = unique_years[-1] if unique_years else None
    n_years = len(unique_years)
    if n_years > max_years:
        return None
    if latest and latest >= min_fresh_year:
        return None
    return {
        "id": school.get("id"),
        "name": school.get("name"),
        "domain": school.get("domain"),
        "seed": seed,
        "years": unique_years,
        "n_years": n_years,
        "latest": latest,
        "min_fresh_year": min_fresh_year,
    }


def fetch_years_by_school(
    api_url: str,
    anon_key: str | None,
) -> dict[str, list[str]]:
    headers = {"Accept": "application/json"}
    if anon_key:
        headers["apikey"] = anon_key
        headers["Authorization"] = f"Bearer {anon_key}"
    by_school: dict[str, list[str]] = defaultdict(list)
    start = 0
    page = 1000
    while True:
        path = (
            "/rest/v1/cds_documents"
            "?select=school_id,cds_year"
            "&removed_at=is.null"
        )
        req = urllib.request.Request(
            api_url.rstrip("/") + path,
            headers={**headers, "Range": f"{start}-{start + page - 1}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                chunk = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"cds_documents fetch failed: HTTP {exc.code}") from exc
        for row in chunk:
            sid = row.get("school_id")
            year = row.get("cds_year")
            if sid and year:
                by_school[sid].append(year)
        if len(chunk) < page:
            break
        start += page
        if start > 50_000:
            break
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


def render_markdown(stuck: list[dict], shared: list[dict], min_fresh_year: str) -> str:
    lines = [
        f"# Stuck PDF discovery seeds",
        "",
        f"Freshness floor: `{min_fresh_year}`. Direct-document seed, "
        f"≤2 archived years, latest older than the floor (or none).",
        "",
        f"Stuck schools: **{len(stuck)}**",
        "",
        "| school_id | latest | years | seed |",
        "|---|---|---|---|",
    ]
    for row in stuck:
        seed = (row.get("seed") or "").replace("|", "\\|")
        lines.append(
            f"| `{row['id']}` | {row.get('latest') or 'none'} | "
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
    ap.add_argument("--max-years", type=int, default=2)
    ap.add_argument("--ids-only", action="store_true")
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    ap.add_argument("--out-ids", type=Path)
    args = ap.parse_args()

    schools = load_schools(args.schools_yaml)
    years_by_school: dict[str, list[str]] = {}
    if args.anon_key:
        years_by_school = fetch_years_by_school(args.api_url, args.anon_key)
    else:
        print("warn: no anon key; year counts will be empty", file=sys.stderr)

    stuck = []
    for school in schools:
        row = classify_school(
            school,
            years_by_school.get(school.get("id") or "", []),
            min_fresh_year=args.min_fresh_year,
            max_years=args.max_years,
        )
        if row:
            stuck.append(row)
    stuck.sort(key=lambda r: ((r.get("latest") or ""), r["id"] or ""))
    shared = shared_seed_groups(schools)

    if args.ids_only:
        sys.stdout.write("\n".join(r["id"] for r in stuck if r.get("id")) + "\n")
    else:
        print(
            f"stuck_pdf_seeds {len(stuck)}  "
            f"shared_url_groups {len(shared)}  "
            f"min_fresh_year {args.min_fresh_year}",
            file=sys.stderr,
        )

    payload = {
        "min_fresh_year": args.min_fresh_year,
        "max_years": args.max_years,
        "stuck": stuck,
        "shared_seed_groups": shared,
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(stuck, shared, args.min_fresh_year))
    if args.out_ids:
        args.out_ids.parent.mkdir(parents=True, exist_ok=True)
        args.out_ids.write_text(
            "\n".join(r["id"] for r in stuck if r.get("id")) + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
