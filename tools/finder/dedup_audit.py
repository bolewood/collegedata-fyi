#!/usr/bin/env python3
"""Audit duplicate-name entries in schools.yaml against authoritative IPEDS HD data.

The corpus has 12 known duplicate-name pairs (24 rows) where two
schools.yaml entries share a name but carry different IPEDS UNITIDs.
This is the same bug class as the Reed/Oregon-State story in
finder/README.md, just inverted: instead of one wrong ID overlaying
another school in the merger, we have an old hand-curated entry with
a wrong IPEDS ID coexisting with a new IPEDS-merger entry that has
the correct ID.

This script:
  1. Downloads the IPEDS HD CSV (one we already trust per
     build_school_list.py) for the most recent year we can fetch.
  2. For every duplicate-name pair in schools.yaml, looks up both
     UNITIDs in the IPEDS data and prints what NCES says about each
     (institution name, state, web address, sector).
  3. Marks which pair-half matches the schools.yaml display name —
     that's the canonical entry. The other half is the corpus bug.

Usage:
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_audit.py
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_audit.py --year 2023
    tools/extraction_worker/.venv/bin/python tools/finder/dedup_audit.py --json out.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"
IPEDS_CACHE = REPO_ROOT / "tools" / "finder" / ".ipeds-cache"


def download_ipeds_hd(year: int) -> dict[str, dict]:
    """Return {UNITID(str): row}. Caches the zip locally to avoid repeated NCES hits."""
    IPEDS_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = IPEDS_CACHE / f"HD{year}.zip"
    if cache_path.exists():
        print(f"  using cached IPEDS HD{year} at {cache_path}", file=sys.stderr)
        data = cache_path.read_bytes()
    else:
        url = IPEDS_URL.format(year=year)
        print(f"  downloading IPEDS HD{year} from {url}", file=sys.stderr)
        req = Request(url, headers={"User-Agent": "collegedata-fyi-builder/0.1"})
        data = urlopen(req, timeout=60).read()
        cache_path.write_bytes(data)
        print(f"  cached {len(data):,} bytes → {cache_path}", file=sys.stderr)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise FileNotFoundError(f"No CSV in HD{year}.zip")
        raw = zf.read(csv_name)

    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    by_id: dict[str, dict] = {}
    for row in reader:
        normed = {k.strip().upper(): (v or "").strip() for k, v in row.items()}
        unitid = normed.get("UNITID")
        if unitid:
            by_id[unitid.lstrip("0") or "0"] = normed
            by_id[unitid] = normed  # also keyed with leading-zero form
    return by_id


def find_duplicates(corpus: dict) -> list[dict]:
    """Group active schools by lowercase name; return pairs/groups with > 1 row."""
    by_name = defaultdict(list)
    for s in corpus.get("schools", []):
        if s.get("scrape_policy") == "active":
            by_name[s["name"].lower().strip()].append(s)
    return [
        {"name": name, "rows": rows}
        for name, rows in sorted(by_name.items())
        if len(rows) > 1
    ]


def name_match(yaml_name: str, ipeds_name: str) -> str:
    """Return EXACT/PARTIAL/MISMATCH for a name comparison."""
    if not ipeds_name:
        return "MISMATCH"
    a = yaml_name.lower().strip()
    b = ipeds_name.lower().strip()
    if a == b:
        return "EXACT"
    # IPEDS uses "-" or "," to add campus suffixes; strip and re-compare
    b_simple = b.split(",")[0].split("-")[0].strip()
    if a == b_simple:
        return "EXACT (suffix-stripped)"
    if a in b or b in a:
        return "PARTIAL"
    return "MISMATCH"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit schools.yaml duplicates against IPEDS HD")
    parser.add_argument("--year", type=int, default=2024,
                        help="IPEDS HD year to use (default: 2024)")
    parser.add_argument("--json", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    print(f"Loading schools.yaml from {SCHOOLS_YAML}", file=sys.stderr)
    with open(SCHOOLS_YAML) as f:
        corpus = yaml.safe_load(f)

    print(f"Loading IPEDS HD{args.year}", file=sys.stderr)
    ipeds = download_ipeds_hd(args.year)
    print(f"  {len(ipeds):,} IPEDS rows indexed", file=sys.stderr)

    dupes = find_duplicates(corpus)
    print(f"\nDuplicate-name groups in active corpus: {len(dupes)}\n", file=sys.stderr)

    audit: list[dict] = []
    for group in dupes:
        name = group["name"]
        rows = group["rows"]
        print(f"\n━━━ {name} ━━━")
        group_audit = {"yaml_name": name, "candidates": []}
        for r in rows:
            sid = r["id"]
            ipeds_id = str(r.get("ipeds_id", "")).strip().strip('"')
            ipeds_row = ipeds.get(ipeds_id)
            domain_yaml = r.get("domain", "")
            if ipeds_row:
                ipeds_name = ipeds_row.get("INSTNM", "")
                ipeds_state = ipeds_row.get("STABBR", "")
                ipeds_web = ipeds_row.get("WEBADDR", "")
                cyactive = ipeds_row.get("CYACTIVE", "")
                control = ipeds_row.get("CONTROL", "")
                iclevel = ipeds_row.get("ICLEVEL", "")
                match = name_match(name, ipeds_name)
            else:
                ipeds_name = "(IPEDS row not found)"
                ipeds_state = ipeds_web = cyactive = control = iclevel = ""
                match = "NOT_IN_IPEDS"
            print(f"  slug={sid!r}")
            print(f"    yaml: ipeds_id={ipeds_id}  domain={domain_yaml!r}")
            print(f"    NCES: INSTNM={ipeds_name!r}  state={ipeds_state}  web={ipeds_web}  active={cyactive}")
            print(f"    name match: {match}")
            group_audit["candidates"].append({
                "slug": sid,
                "yaml_ipeds_id": ipeds_id,
                "yaml_domain": domain_yaml,
                "ipeds_instnm": ipeds_name,
                "ipeds_state": ipeds_state,
                "ipeds_web": ipeds_web,
                "ipeds_active": cyactive,
                "ipeds_control": control,
                "ipeds_iclevel": iclevel,
                "name_match": match,
            })

        # Recommend a canonical
        exact_matches = [c for c in group_audit["candidates"] if c["name_match"].startswith("EXACT")]
        if len(exact_matches) == 1:
            print(f"  → CANONICAL: {exact_matches[0]['slug']} (only EXACT match)")
            group_audit["recommended_canonical"] = exact_matches[0]["slug"]
            group_audit["recommendation"] = "delete-other"
        elif len(exact_matches) > 1:
            # Both match → maybe genuinely two institutions sharing a name
            print(f"  → BOTH MATCH — possible legitimate name collision (e.g., Lincoln University in PA + MO).")
            print(f"     Compare states / web addresses to decide whether to keep both with disambiguated names.")
            group_audit["recommended_canonical"] = None
            group_audit["recommendation"] = "manual-review-both-match"
        else:
            print(f"  → NEITHER matches IPEDS exactly. Manual review needed.")
            group_audit["recommended_canonical"] = None
            group_audit["recommendation"] = "manual-review-no-match"

        audit.append(group_audit)

    # Summary
    print("\n\n=== SUMMARY ===")
    counts: dict[str, int] = defaultdict(int)
    for a in audit:
        counts[a["recommendation"]] += 1
    for k, v in counts.items():
        print(f"  {k}: {v}")

    if args.json:
        Path(args.json).write_text(json.dumps(audit, indent=2))
        print(f"\nWrote {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
