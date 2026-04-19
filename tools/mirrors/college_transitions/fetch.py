#!/usr/bin/env python3
"""Fetch the College Transitions CDS repository into catalog.json.

The target page renders its table client-side via jQuery FooTable, so
a plain curl + HTML parse won't work. This script uses playwright-python
to load the page, pull the FooTable's in-memory row data (which has
ALL rows, not just the currently paginated slice), and cross-reference
each school against tools/finder/schools.yaml to resolve our slug.

Runs occasionally (monthly-ish), not in a tight loop. Output diffs
against the committed catalog.json are human-reviewable — when CT
adds a school or year, the PR shows what changed.

Setup (one-time):
    pip install playwright pyyaml
    playwright install chromium

Usage:
    python tools/mirrors/college_transitions/fetch.py
    python tools/mirrors/college_transitions/fetch.py --out catalog.json
    python tools/mirrors/college_transitions/fetch.py --dry-run   # show stats, don't write
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import yaml

SOURCE_URL = "https://www.collegetransitions.com/dataverse/common-data-set-repository/"
PROVENANCE_TAG = "mirror_college_transitions"

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_OUT = Path(__file__).resolve().parent / "catalog.json"

# Hand-maintained aliases for schools whose CT name doesn't fuzzy-match
# our schools.yaml name above the 0.88 threshold. Add entries here when
# a new CT refresh surfaces a mismatch; keys are lowercased CT names,
# values are lowercased schools.yaml names.
ALIAS_MAP = {
    "college of william and mary": "william & mary",
    "cuny brooklyn college": "brooklyn college",
    "cuny hunter college": "hunter college",
    "cuny queens college": "queens college",
    "rensselaer polytechnic institute": "rpi",
    "pennsylvania state university": "penn state",
    "university of massachusetts amherst": "university of massachusetts-amherst",
}


def fetch_via_playwright() -> list[dict]:
    """Return [{school, years: {year: drive_share_url}}] from CT's page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium",
              file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(SOURCE_URL, wait_until="networkidle", timeout=60_000)

        # FooTable stores all rows in its in-memory state (rows.all),
        # independent of the currently paginated DOM. Extract directly
        # from that rather than paginating through the UI.
        data = page.evaluate(
            """
            () => {
              const table = document.querySelector('table.foo-table');
              if (!table || !window.jQuery) return { error: 'table or jQuery missing' };
              const ft = window.jQuery(table).data('__FooTable__');
              if (!ft || !ft.rows) return { error: 'FooTable state missing' };
              const headers = ft.columns.array.map(c => c.title || c.name);
              const decode = (href) => {
                const m = href.match(/[?&]q=([^&]+)/);
                return m ? decodeURIComponent(m[1]).split('?')[0] : href;
              };
              return ft.rows.all.map(row => {
                const school = (row.cells[0].$el[0].textContent || '').trim();
                const years = {};
                for (let i = 1; i < row.cells.length && i < headers.length; i++) {
                  const a = row.cells[i].$el[0].querySelector('a');
                  if (a) years[headers[i]] = decode(a.href);
                }
                return { school, years };
              });
            }
            """
        )
        browser.close()

    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"playwright extract failed: {data['error']}")
    return data


def build_matcher():
    with open(SCHOOLS_YAML) as f:
        corpus = yaml.safe_load(f)
    active = [s for s in corpus["schools"] if s.get("scrape_policy") == "active"]
    by_name = {s["name"].lower(): s for s in active}

    def match(ct_name: str):
        low = ct_name.lower().strip()
        if low in by_name:
            return by_name[low], 1.0
        if low in ALIAS_MAP and ALIAS_MAP[low] in by_name:
            return by_name[ALIAS_MAP[low]], 0.99
        # Fuzzy
        best, score = None, 0.0
        for name, s in by_name.items():
            r = SequenceMatcher(None, low, name).ratio()
            if r > score:
                best, score = s, r
        return (best, score) if score >= 0.88 else (None, score)

    return match


def build_catalog(rows: list[dict], match) -> dict:
    matched, unmatched = [], []
    for row in rows:
        s, score = match(row["school"])
        record = {
            "school_name_ct": row["school"],
            "match_score": round(score, 3),
            "years": row["years"],
        }
        if s:
            record["school_id"] = s["id"]
            record["school_name"] = s["name"]
            matched.append(record)
        else:
            unmatched.append(record)

    return {
        "source": "college_transitions",
        "source_url": SOURCE_URL,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provenance_tag": PROVENANCE_TAG,
        "school_count_total": len(rows),
        "school_count_matched": len(matched),
        "school_count_unmatched": len(unmatched),
        "file_count": sum(len(r["years"]) for r in rows),
        "entries": sorted(matched, key=lambda r: r["school_id"]),
        "unmatched": sorted(unmatched, key=lambda r: r["school_name_ct"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch College Transitions CDS repository")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Fetching {SOURCE_URL} via Playwright...")
    rows = fetch_via_playwright()
    print(f"  Got {len(rows)} schools, {sum(len(r['years']) for r in rows)} files")

    match = build_matcher()
    catalog = build_catalog(rows, match)

    print(f"\nMatched to our corpus: {catalog['school_count_matched']}")
    print(f"Unmatched:             {catalog['school_count_unmatched']}")
    if catalog["unmatched"]:
        print("\nSample unmatched (add to ALIAS_MAP if they should match):")
        for u in catalog["unmatched"][:10]:
            print(f"  {u['school_name_ct']!r} (best fuzzy score: {u['match_score']})")

    if args.dry_run:
        print("\n(dry-run; not writing catalog.json)")
        return 0

    out_path = Path(args.out)
    out_path.write_text(json.dumps(catalog, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
