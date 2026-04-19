#!/usr/bin/env python3
"""Kid-friendly batched CSVs of active schools missing recent CDS years.

Generates one CSV per batch of 50 schools, sorted highest-yield first.
Each CSV is ready to drop into Google Sheets (File → Import → Upload).

Output layout:
    tools/data_quality/kids-worklist/
        README.txt              — one-page instructions for kids
        batch-001.csv           — schools 1-50
        batch-002.csv           — schools 51-100
        ...

Per-row columns:
    row, school_name, landing_page,
    need_2022_23, need_2023_24, need_2024_25, need_2025_26,
    url_2022_23, url_2023_24, url_2024_25, url_2025_26,
    notes_from_kid

The "need_*" columns show "FIND IT" if we don't have that year yet, or "have"
if we already have it (so kids skip ones we already have). The "url_*" columns
are blank for kids to fill in. "notes_from_kid" is a free-text column.

Usage:
    python tools/data_quality/kids_worklist.py
    python tools/data_quality/kids_worklist.py --batch-size 25
    python tools/data_quality/kids_worklist.py --max-missing 4   # only fully-missing schools
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
DEFAULT_OUTDIR = REPO_ROOT / "tools" / "data_quality" / "kids-worklist"

README_TEMPLATE = """\
Kids' CDS Worklist — instructions
==================================

Each batch CSV has 50 schools. Open one in Google Sheets:
  1. Open Google Sheets → File → Import → Upload → pick batch-001.csv
  2. Choose "Replace spreadsheet" and "Detect automatically" for separator
  3. Work through the rows top to bottom

For each row:
  1. Click the "landing_page" link — that's the school's CDS page.
  2. Look for any year listed in the "need_*" columns (those are the years we
     don't have yet). Years marked "have" are already in our database.
  3. When you find a downloadable CDS file (PDF, Excel, or Word), copy its
     URL into the matching "url_YYYY_YY" column.
  4. If a year isn't on the page at all, leave its url column blank.
  5. Use "notes_from_kid" for anything weird — broken page, school changed
     URL, multiple files for one year, etc.

Tip: ignore years before {first_year} and after {last_year} — we already
have the older ones, and the newer ones may not be published yet.

When a batch is done, save it as CSV and hand it back to the maintainer.
The URLs you collect will be batch-archived automatically — see
tools/finder/manual_urls.yaml for the format.

Years we are filling in: {years_str}
Generated: {timestamp}
"""


def load_active_schools() -> list[dict]:
    with open(SCHOOLS_YAML) as fp:
        data = yaml.safe_load(fp)
    return [s for s in data.get("schools", []) if s.get("scrape_policy") == "active"]


def fetch_published_years(sb, school_ids: list[str], years: list[str]) -> dict[str, set[str]]:
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
    parser = argparse.ArgumentParser(description="Kid-friendly batched worklist CSVs")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--years", default=",".join(DEFAULT_YEARS),
                        help=f"Comma-separated CDS years (default: {','.join(DEFAULT_YEARS)})")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--max-missing", type=int, default=None,
                        help="Only include schools missing exactly this many years (e.g. 4 for fully-missing)")
    parser.add_argument("--min-missing", type=int, default=1,
                        help="Skip schools missing fewer than this many years (default 1)")
    args = parser.parse_args()

    years = [y.strip() for y in args.years.split(",") if y.strip()]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    load_dotenv(args.env)
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    schools = load_active_schools()
    print(f"Active schools in corpus: {len(schools)}")

    have = fetch_published_years(sb, [s["id"] for s in schools], years)

    rows: list[dict] = []
    for s in schools:
        sid = s["id"]
        present = have.get(sid, set())
        missing = [y for y in years if y not in present]
        if len(missing) < args.min_missing:
            continue
        if args.max_missing is not None and len(missing) != args.max_missing:
            continue
        if not s.get("cds_url_hint"):
            continue
        row = {
            "school_name": s.get("name", ""),
            "landing_page": s.get("cds_url_hint", ""),
            "_missing_count": len(missing),
            "_school_id": sid,
        }
        for y in years:
            key = y.replace("-", "_")
            row[f"need_{key}"] = "have" if y in present else "FIND IT"
            row[f"url_{key}"] = ""
        row["notes_from_kid"] = ""
        rows.append(row)

    rows.sort(key=lambda r: (-r["_missing_count"], r["school_name"].lower()))
    print(f"Eligible rows: {len(rows)}")

    fieldnames = ["row", "school_name", "landing_page"]
    fieldnames += [f"need_{y.replace('-', '_')}" for y in years]
    fieldnames += [f"url_{y.replace('-', '_')}" for y in years]
    fieldnames += ["notes_from_kid"]

    # Wipe any prior batches so the directory always reflects this run
    for old in outdir.glob("batch-*.csv"):
        old.unlink()

    batch_size = args.batch_size
    total_batches = (len(rows) + batch_size - 1) // batch_size
    for i in range(total_batches):
        chunk = rows[i * batch_size : (i + 1) * batch_size]
        path = outdir / f"batch-{i+1:03d}.csv"
        with open(path, "w", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for j, r in enumerate(chunk, start=1):
                r["row"] = i * batch_size + j
                writer.writerow(r)

    # README
    from datetime import date
    readme = outdir / "README.txt"
    readme.write_text(README_TEMPLATE.format(
        first_year=years[0],
        last_year=years[-1],
        years_str=", ".join(years),
        timestamp=date.today().isoformat(),
    ))

    print(f"\nWrote {total_batches} batches of up to {batch_size} schools each to {outdir}/")
    print(f"  {outdir}/README.txt")
    for i in range(min(3, total_batches)):
        print(f"  {outdir}/batch-{i+1:03d}.csv")
    if total_batches > 3:
        print(f"  ... through batch-{total_batches:03d}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
