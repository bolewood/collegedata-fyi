#!/usr/bin/env python3
"""CSV of active schools and which recent CDS years we're missing for them.

Output columns:
  school_id, school_name, domain, cds_url_hint, missing_count,
  has_2022_23, has_2023_24, has_2024_25, has_2025_26, notes

A "Y" means we have a published cds_documents row for that year. Empty means
no row exists yet. Kids open the cds_url_hint in a browser, look for the
missing year, and report any URL they find.

Usage:
    python tools/data_quality/active_schools_missing_recent.py
    python tools/data_quality/active_schools_missing_recent.py --output kids-worklist.csv
    python tools/data_quality/active_schools_missing_recent.py --years 2023-24,2024-25,2025-26
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_YEARS = ["2022-23", "2023-24", "2024-25", "2025-26"]


def load_active_schools() -> list[dict]:
    with open(SCHOOLS_YAML) as fp:
        data = yaml.safe_load(fp)
    return [s for s in data.get("schools", []) if s.get("scrape_policy") == "active"]


def fetch_published_years(sb, school_ids: list[str], years: list[str]) -> dict[str, set[str]]:
    """Return {school_id: {years_present}} for published documents."""
    have: dict[str, set[str]] = {sid: set() for sid in school_ids}
    page_size = 1000
    offset = 0
    while True:
        batch = sb.table("cds_documents").select(
            "school_id, cds_year, participation_status"
        ).in_("cds_year", years).range(offset, offset + page_size - 1).execute().data or []
        for row in batch:
            sid = row["school_id"]
            if sid in have and row.get("participation_status") == "published":
                have[sid].add(row["cds_year"])
        if len(batch) < page_size:
            break
        offset += page_size
    return have


def main() -> int:
    parser = argparse.ArgumentParser(description="Worklist of active schools missing recent CDS years")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--years", default=",".join(DEFAULT_YEARS),
                        help=f"Comma-separated cds_year values (default: {','.join(DEFAULT_YEARS)})")
    parser.add_argument("--output", default="tools/data_quality/active-schools-missing-recent.csv")
    parser.add_argument("--only-incomplete", action="store_true",
                        help="Skip schools that already have all target years")
    args = parser.parse_args()

    years = [y.strip() for y in args.years.split(",") if y.strip()]

    load_dotenv(args.env)
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    schools = load_active_schools()
    school_ids = [s["id"] for s in schools]
    print(f"Active schools in corpus: {len(schools)}")

    have = fetch_published_years(sb, school_ids, years)

    # Expand schools with sub-institutions into one row per variant for clarity
    rows = []
    for s in schools:
        sid = s["id"]
        present = have.get(sid, set())
        missing = [y for y in years if y not in present]
        if args.only_incomplete and not missing:
            continue
        row = {
            "school_id": sid,
            "school_name": s.get("name", ""),
            "domain": s.get("domain", ""),
            "cds_url_hint": s.get("cds_url_hint", ""),
            "missing_count": len(missing),
        }
        for y in years:
            row[f"has_{y.replace('-', '_')}"] = "Y" if y in present else ""
        row["notes"] = s.get("notes", "") or ""
        rows.append(row)

    # Sort: most-missing first, then by name. Kids tackle the biggest gaps first.
    rows.sort(key=lambda r: (-r["missing_count"], r["school_name"].lower()))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        ["school_id", "school_name", "domain", "cds_url_hint", "missing_count"]
        + [f"has_{y.replace('-', '_')}" for y in years]
        + ["notes"]
    )
    with open(output_path, "w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    by_missing: dict[int, int] = {}
    for r in rows:
        by_missing[r["missing_count"]] = by_missing.get(r["missing_count"], 0) + 1
    total = len(rows)
    print(f"\nWrote {total} rows to {output_path}")
    print(f"\nGap distribution (of {total} schools):")
    for n in sorted(by_missing.keys(), reverse=True):
        bar = "█" * min(60, by_missing[n] // 10)
        print(f"  missing {n}/{len(years)} years: {by_missing[n]:>4}  {bar}")

    fully_missing = by_missing.get(len(years), 0)
    fully_complete = by_missing.get(0, 0)
    print(f"\n  {fully_missing} schools have NONE of the target years (highest yield)")
    print(f"  {fully_complete} schools already have ALL target years")
    return 0


if __name__ == "__main__":
    sys.exit(main())
