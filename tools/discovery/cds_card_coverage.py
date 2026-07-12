#!/usr/bin/env python3
"""Per-card CDS field extraction coverage (PRD 026 Milestone 0).

Regenerates the coverage numbers cited in
docs/plans/prd-026-data-spike-findings.md finding 5: for each E1/F1 field
backing a card in data/discovery/cards/v1.json, how many schools have the
field extracted for the given canonical year.

Usage:
  python3 tools/discovery/cds_card_coverage.py [--year 2024-25]

Reads the anon key from web/.env.local (NEXT_PUBLIC_SUPABASE_ANON_KEY) or the
environment. Writes scratch/discovery-spike/cds-card-coverage.json.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.collegedata.fyi/rest/v1"

# CDS field id -> card_id(s) the field backs (2024-25 schema ids; see
# web/src/lib/labels-2024-25.ts for labels).
FIELD_CARDS = {
    "E.101": "accelerated-degree",
    "E.103": "cross-registration",
    "E.105": "combine-interests (double major)",
    "E.110": "honors-path",
    "E.111": "independent-study",
    "E.112": "internship-credit",
    "E.114": "combine-interests (student-designed major)",
    "E.115": "study-abroad-normal",
    "E.116": "teacher-certification",
    "E.117": "early-research",
    "F.101": "geographic-mix (out-of-state, all UG)",
    "F.102": "greek-scene (fraternity)",
    "F.103": "greek-scene (sorority)",
    "F.104": "residential-campus (all UG)",
    "F.109": "geographic-mix (out-of-state, first-year)",
    "F.112": "residential-campus (first-year)",
}


def anon_key():
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if key:
        return key
    env = ROOT / "web" / ".env.local"
    if env.exists():
        m = re.search(r"NEXT_PUBLIC_SUPABASE_ANON_KEY=(.+)", env.read_text())
        if m:
            return m.group(1).strip()
    sys.exit("No anon key: set NEXT_PUBLIC_SUPABASE_ANON_KEY or create web/.env.local")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2024-25")
    args = parser.parse_args()
    key = anon_key()

    ids = ",".join(FIELD_CARDS)
    rows, offset = [], 0
    while True:
        url = (f"{API}/cds_fields?select=school_id,field_id"
               f"&canonical_year=eq.{args.year}&field_id=in.({ids})"
               f"&limit=1000&offset={offset}")
        req = urllib.request.Request(url, headers={"apikey": key})
        batch = json.load(urllib.request.urlopen(req))
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    per_field = defaultdict(set)
    for r in rows:
        per_field[r["field_id"]].add(r["school_id"])
    schools_with_any = set().union(*per_field.values()) if per_field else set()

    out = {
        "canonical_year": args.year,
        "schools_with_any_tracked_field": len(schools_with_any),
        "fields": {
            f: {"card": card, "schools": len(per_field.get(f, set()))}
            for f, card in sorted(FIELD_CARDS.items())
        },
    }
    dest = ROOT / "scratch" / "discovery-spike" / "cds-card-coverage.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"schools with any tracked field ({args.year}): {len(schools_with_any)}")
    for f, card in sorted(FIELD_CARDS.items()):
        print(f"{f:8} {card:44} {len(per_field.get(f, set()))}")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
