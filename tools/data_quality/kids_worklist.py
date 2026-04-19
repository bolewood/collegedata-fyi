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
    row, school_name, landing_page, hosting_note,
    need_2022_23, need_2023_24, need_2024_25, need_2025_26,
    url_2022_23, url_2023_24, url_2024_25, url_2025_26,
    notes_from_kid

The "need_*" columns show "FIND IT" if we don't have that year yet, or "have"
if we already have it (so kids skip ones we already have). The "url_*" columns
are blank for kids to fill in. "notes_from_kid" is a free-text column.

PR 6 of the URL hint refactor plan added two protections:
  - Schools whose latest_school_hosting row reports auth_required != none
    are SKIPPED entirely. No point sending kids to a school behind SSO.
  - The landing_page column prefers browse_url (operator-supplied human URL)
    over discovery_seed_url (resolver seed). When the seed is a direct PDF
    and there's no browse_url, the row gets a "needs landing page" prompt
    instead of the stale PDF link.

Usage:
    python tools/data_quality/kids_worklist.py
    python tools/data_quality/kids_worklist.py --batch-size 25
    python tools/data_quality/kids_worklist.py --max-missing 4   # only fully-missing schools
    python tools/data_quality/kids_worklist.py --include-walled  # don't skip auth-walled
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
SCHOOL_OVERRIDES_YAML = REPO_ROOT / "tools" / "finder" / "school_overrides.yaml"
DEFAULT_YEARS = ["2022-23", "2023-24", "2024-25", "2025-26"]
DEFAULT_OUTDIR = REPO_ROOT / "tools" / "data_quality" / "kids-worklist"

# Document extensions that signal "this is a direct file, not a landing
# page." Used by the heuristic that flags a school as "needs a landing
# page" when discovery_seed_url is a direct PDF and no browse_url is
# set. Mirrors DOCUMENT_EXT_RE in supabase/functions/_shared/resolve.ts.
DOCUMENT_EXT = (".pdf", ".xlsx", ".xls", ".docx", ".doc")

README_TEMPLATE = """\
Kids' CDS Worklist — instructions
==================================

Each batch CSV has 50 schools. Open one in Google Sheets:
  1. Open Google Sheets → File → Import → Upload → pick batch-001.csv
  2. Choose "Replace spreadsheet" and "Detect automatically" for separator
  3. Work through the rows top to bottom

For each row:
  1. Read the "hosting_note" — it tells you what kind of page to expect
     (Box folder, IR landing page, "needs landing page", etc.). If it
     says "needs landing page", the URL we have is a direct PDF — please
     find the school's actual IR page (search Google for "<school name>
     common data set") and put the IR page URL in notes_from_kid.
  2. Click the "landing_page" link.
  3. Look for any year listed in the "need_*" columns (those are the
     years we don't have yet). Years marked "have" are already in our
     database.
  4. When you find a downloadable CDS file (PDF, Excel, or Word), copy
     its URL into the matching "url_YYYY_YY" column.
  5. If a year isn't on the page at all, leave its url column blank.
  6. Use "notes_from_kid" for anything weird — broken page, school
     changed URL, multiple files for one year, etc.

What we already filtered out for you:
  - Schools whose CDS files are behind a login (Microsoft 365 / Okta /
    Google SSO). Those aren't recoverable via browsing.
  - Schools with no usable URL at all.

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


def load_overrides() -> dict[str, dict]:
    """Read school_overrides.yaml, return {school_id: override_dict}."""
    if not SCHOOL_OVERRIDES_YAML.exists():
        return {}
    with open(SCHOOL_OVERRIDES_YAML) as fp:
        data = yaml.safe_load(fp) or {}
    return {o["school_id"]: o for o in (data.get("overrides") or []) if o.get("school_id")}


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


def fetch_latest_hosting(sb, school_ids: list[str]) -> dict[str, dict]:
    """Return {school_id: latest_hosting_row} from latest_school_hosting view.

    Empty dict if the view doesn't exist yet (PR 3 ships the schema; older
    deploys won't have it). Best-effort — any error is logged and ignored.
    """
    out: dict[str, dict] = {}
    if not school_ids:
        return out
    try:
        # Page through to handle large school sets (the view's WHERE
        # filter happens in Postgres; we just chunk the IN list).
        for chunk_start in range(0, len(school_ids), 500):
            chunk = school_ids[chunk_start:chunk_start + 500]
            rows = sb.table("latest_school_hosting").select(
                "school_id, auth_required, file_storage, cms, rendering, "
                "outcome, notes"
            ).in_("school_id", chunk).execute().data or []
            for r in rows:
                out[r["school_id"]] = r
    except Exception as e:
        print(f"warn: latest_school_hosting query failed ({e}); proceeding "
              f"without hosting filter", file=sys.stderr)
    return out


def is_direct_doc(url: str) -> bool:
    if not url:
        return False
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return any(path.endswith(ext) for ext in DOCUMENT_EXT)


def hosting_note_for(
    school: dict,
    override: dict | None,
    hosting: dict | None,
    landing: str | None,
) -> str:
    """One-line human-readable hint about what the kid will encounter.

    Sources, in priority order:
      1. operator-supplied hosting_override.notes (school_overrides.yaml)
      2. inferred file_storage from latest_school_hosting (Box / Drive / etc.)
      3. heuristic on the landing URL itself ("needs landing page" if direct PDF)
      4. default: "browse and look for the years listed below"
    """
    if override and override.get("hosting_override", {}).get("notes"):
        return override["hosting_override"]["notes"][:140]

    storage = (hosting or {}).get("file_storage")
    if storage == "box":
        return "Hosted on Box. Files may need individual downloads."
    if storage == "google_drive":
        return "Hosted on Google Drive."
    if storage == "sharepoint":
        return "Hosted on SharePoint."
    if storage == "dropbox":
        return "Hosted on Dropbox."

    rendering = (hosting or {}).get("rendering")
    if rendering == "js_required":
        return "Page is JavaScript-rendered. Wait for it to load fully."

    if is_direct_doc(landing or ""):
        return ("NEEDS LANDING PAGE. The URL above is just one PDF. "
                "Please find the school's IR landing page.")

    return "Browse the page and look for the years listed below."


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
    parser.add_argument("--include-walled", action="store_true",
                        help="Don't skip schools with auth_required != none. Useful for "
                             "auditing the auth-walled cohort; default behavior is to skip them.")
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
    overrides = load_overrides()
    print(f"Active schools in corpus: {len(schools)}")
    print(f"Operator overrides: {len(overrides)}")

    have = fetch_published_years(sb, [s["id"] for s in schools], years)
    hosting = fetch_latest_hosting(sb, [s["id"] for s in schools])
    print(f"Latest hosting observations: {len(hosting)}")

    rows: list[dict] = []
    skipped_walled = 0
    skipped_no_url = 0
    for s in schools:
        sid = s["id"]
        present = have.get(sid, set())
        missing = [y for y in years if y not in present]
        if len(missing) < args.min_missing:
            continue
        if args.max_missing is not None and len(missing) != args.max_missing:
            continue

        # Auth-wall filter. Operator override wins over DB observation;
        # DB wins over the default. --include-walled disables both.
        override = overrides.get(sid)
        ovr_auth = (override or {}).get("hosting_override", {}).get("auth_required")
        host_row = hosting.get(sid)
        host_auth = (host_row or {}).get("auth_required")
        effective_auth = ovr_auth or host_auth or "none"
        if not args.include_walled and effective_auth not in (None, "none", "unknown"):
            skipped_walled += 1
            continue

        # Landing URL: browse_url > schools.yaml.discovery_seed_url
        # > legacy cds_url_hint. Override file's browse_url is overlaid
        # at the YAML loader (PR 6); when it lands here it shows up on
        # the school dict already. We re-check the override map for
        # belt-and-suspenders since this Python tool doesn't go through
        # the Deno loader.
        landing = (
            (override or {}).get("browse_url")
            or s.get("browse_url")
            or s.get("discovery_seed_url")
            or s.get("cds_url_hint")
        )
        if not landing:
            skipped_no_url += 1
            continue

        row = {
            "school_name": s.get("name", ""),
            "landing_page": landing,
            "hosting_note": hosting_note_for(s, override, host_row, landing),
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
    print(f"  Skipped (auth-walled):  {skipped_walled}")
    print(f"  Skipped (no usable URL): {skipped_no_url}")

    fieldnames = ["row", "school_name", "landing_page", "hosting_note"]
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
