#!/usr/bin/env python3
"""Expand schools.yaml from ~84 hand-curated entries to ~2,000+ using IPEDS data.

Downloads the IPEDS Institutional Characteristics (HD) file from NCES,
filters to four-year degree-granting US institutions (excluding for-profits),
and merges with the existing schools.yaml — preserving all hand-entered
overrides (discovery_seed_url, browse_url, notes, scrape_policy, sub_institutions).

Dependencies: pyyaml (pip install pyyaml). Everything else is stdlib.

Usage:
    python build_school_list.py

    # Preview without overwriting:
    python build_school_list.py --dry-run

    # Use a specific IPEDS year (default: 2023, the most recent final release):
    python build_school_list.py --year 2022

Output: overwrites tools/finder/schools.yaml with the merged result.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

import yaml


ROOT = Path(__file__).parent
SCHOOLS_YAML = ROOT / "schools.yaml"

# IPEDS download URL pattern — the HD (Header/Directory) file
# contains institution-level characteristics.
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"

# Columns we care about (upper-cased)
WANT_COLS = {"UNITID", "INSTNM", "WEBADDR", "STABBR", "CONTROL",
             "ICLEVEL", "DEGGRANT", "FIPS"}

# US states + DC FIPS codes (exclude territories for V1)
US_FIPS = set(range(1, 57)) - {3, 7, 14, 43, 52}  # exclude AS, GU, MH, PW, VI


def download_ipeds(year: int) -> list[dict]:
    """Download and parse the IPEDS HD file for a given year.

    Returns a list of dicts, one per institution, with upper-cased column keys.
    """
    url = IPEDS_URL.format(year=year)
    print(f"Downloading IPEDS HD{year} from {url} ...")
    req = Request(url, headers={"User-Agent": "collegedata-fyi-builder/0.1"})
    resp = urlopen(req, timeout=60)
    data = resp.read()
    print(f"  Downloaded {len(data):,} bytes")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV found in {url}")
        csv_name = csv_names[0]
        raw = zf.read(csv_name)
        print(f"  Extracting {csv_name} ({len(raw):,} bytes)")

    # IPEDS CSVs are Latin-1 encoded but may have a UTF-8 BOM prefix.
    # Strip BOM bytes before decoding so the first column name stays clean.
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        # Normalize keys: upper-case, strip whitespace and stray non-ASCII
        normed = {k.strip().upper(): v for k, v in row.items()}
        rows.append(normed)

    # Sanity check: verify UNITID is present
    if rows:
        sample_keys = list(rows[0].keys())
        if "UNITID" not in sample_keys:
            print(f"  WARNING: UNITID not found in columns. Available: {sample_keys[:10]}")
        else:
            sample_id = rows[0].get("UNITID", "")
            print(f"  Columns OK. Sample UNITID={sample_id}, INSTNM={rows[0].get('INSTNM', '?')}")

    return rows


def safe_int(val: str) -> int | None:
    """Convert a string to int, returning None on failure."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def extract_domain(url: str) -> str:
    """Extract bare domain from a full URL."""
    if not url:
        return ""
    url = url.strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    url = url.split("/")[0]
    return url


def slugify(name: str) -> str:
    """Convert institution name to a kebab-case slug."""
    s = name.lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    s = re.sub(r"-+", "-", s)
    if len(s) > 60:
        s = s[:60].rsplit("-", 1)[0]
    return s


def filter_ipeds(rows: list[dict]) -> list[dict]:
    """Filter to four-year, degree-granting, non-profit US institutions."""
    n0 = len(rows)

    # Four-year
    rows = [r for r in rows if safe_int(r.get("ICLEVEL", "")) == 1]
    print(f"  After ICLEVEL=1 (four-year): {len(rows):,} (dropped {n0 - len(rows):,})")

    n1 = len(rows)
    # Degree-granting
    rows = [r for r in rows if safe_int(r.get("DEGGRANT", "")) == 1]
    print(f"  After DEGGRANT=1: {len(rows):,} (dropped {n1 - len(rows):,})")

    n2 = len(rows)
    # Exclude for-profit (CONTROL=3)
    rows = [r for r in rows if safe_int(r.get("CONTROL", "")) in (1, 2)]
    print(f"  After excluding for-profit: {len(rows):,} (dropped {n2 - len(rows):,})")

    n3 = len(rows)
    # US states + DC only
    rows = [r for r in rows if safe_int(r.get("FIPS", "")) in US_FIPS]
    print(f"  After US states+DC only: {len(rows):,} (dropped {n3 - len(rows):,})")

    return rows


def load_existing() -> dict[str, dict]:
    """Load existing schools.yaml and return a dict keyed by ipeds_id (string)."""
    if not SCHOOLS_YAML.exists():
        return {}
    data = yaml.safe_load(SCHOOLS_YAML.read_text())
    schools = data.get("schools", []) if data else []
    by_ipeds: dict[str, dict] = {}
    for s in schools:
        iid = str(s.get("ipeds_id", "")).strip('"').strip()
        if iid:
            by_ipeds[iid] = s
    return by_ipeds


def merge(ipeds_rows: list[dict], existing: dict[str, dict]) -> list[dict]:
    """Merge IPEDS data with existing hand-curated entries."""
    result = []
    seen_ipeds: set[str] = set()

    for row in ipeds_rows:
        iid = str(safe_int(row.get("UNITID", "")))
        if iid in seen_ipeds or iid == "None":
            continue
        seen_ipeds.add(iid)

        domain = extract_domain(row.get("WEBADDR", ""))
        name = row.get("INSTNM", "").strip()
        slug = slugify(name)

        entry: dict = {
            "id": slug,
            "name": name,
            "domain": domain,
            "ipeds_id": iid,
            "scrape_policy": "unknown",
        }

        # If we have a hand-curated entry, overlay it (hand data wins).
        # PR 5 of the URL hint refactor renamed cds_url_hint →
        # discovery_seed_url and added browse_url; both are preserved
        # alongside the legacy field so older YAML rows keep working
        # until they're rewritten.
        if iid in existing:
            hand = existing[iid]
            for key in [
                "id", "name",
                "discovery_seed_url", "browse_url",
                "cds_url_hint",  # legacy; kept for back-compat
                "scrape_policy", "notes", "sub_institutions",
                "probe_state",
            ]:
                if key in hand and hand[key] is not None:
                    entry[key] = hand[key]
            if "domain" in hand and hand["domain"]:
                entry["domain"] = hand["domain"]

        result.append(entry)

    # Include any hand-curated entries not found in IPEDS (safety net)
    for iid, hand in existing.items():
        if iid not in seen_ipeds:
            result.append(hand)
            seen_ipeds.add(iid)

    return result


def assert_no_duplicates(schools: list[dict]) -> None:
    """Refuse to write schools.yaml if it contains duplicate-name entries.

    Prevents regression of the bug class cleaned up in 2026-04-19's dedup
    migration: short-slug hand-curated entries (`williams`, `davidson`, etc.)
    coexisting alongside the IPEDS-merger's `<name>-college` entries, with
    different IPEDS UNITIDs that often pointed at completely unrelated
    institutions (the `williams` slug had IPEDS 168148 = Tufts University).

    Two checks:
      1. Duplicate `id` (slug) — same key twice in the file.
      2. Duplicate `(name, state)` among active entries — two slugs claim
         the same school. State comes from the FIPS code in IPEDS data;
         hand-curated entries without a state are matched by name alone.

    On any duplicate, prints all involved entries with their IPEDS IDs and
    aborts with a non-zero exit. The build is broken; the operator must
    decide which entry is canonical (run tools/finder/dedup_audit.py for
    IPEDS-driven analysis) before re-running build_school_list.py.
    """
    active = [s for s in schools if s.get("scrape_policy") == "active"]

    # Slug uniqueness among ACTIVE schools is the load-bearing invariant
    # (active schools drive the resolver, archive_queue, and storage paths).
    # Inactive duplicates exist from a separate slugify-collision bug
    # (e.g., two real schools both named "Anderson University") and are
    # tracked as a backlog item — they don't affect runtime correctness.
    by_id: dict[str, list[dict]] = {}
    for s in active:
        by_id.setdefault(s.get("id", ""), []).append(s)
    id_dupes = {sid: rows for sid, rows in by_id.items() if len(rows) > 1}
    if id_dupes:
        print("\n✗ ERROR: schools.yaml has duplicate active-school slugs:", file=sys.stderr)
        for sid, rows in sorted(id_dupes.items()):
            print(f"  {sid!r} appears {len(rows)} times:", file=sys.stderr)
            for r in rows:
                print(f"    name={r.get('name')!r}  ipeds={r.get('ipeds_id')}",
                      file=sys.stderr)
        print("\nFix: run tools/finder/dedup_audit.py to identify which entry is canonical, "
              "then dedup_migrate.py to consolidate.", file=sys.stderr)
        raise SystemExit(2)

    # Inactive-cohort duplicate slugs: warn loudly (they break the next
    # IPEDS regeneration's merge dict — the slug collision causes one
    # entry to silently overwrite the other) but don't block this build.
    by_id_all: dict[str, list[dict]] = {}
    for s in schools:
        by_id_all.setdefault(s.get("id", ""), []).append(s)
    inactive_id_dupes = {
        sid: rows for sid, rows in by_id_all.items()
        if len(rows) > 1 and sid not in id_dupes
    }
    if inactive_id_dupes:
        print(f"\n⚠️  WARNING: schools.yaml has {len(inactive_id_dupes)} duplicate "
              f"slugs among non-active schools:", file=sys.stderr)
        for sid in sorted(inactive_id_dupes)[:5]:
            ipeds = [r.get("ipeds_id") for r in inactive_id_dupes[sid]]
            print(f"  {sid!r}  ipeds={ipeds}", file=sys.stderr)
        if len(inactive_id_dupes) > 5:
            print(f"  ... and {len(inactive_id_dupes) - 5} more", file=sys.stderr)
        print("This is a separate slugify-collision bug. See backlog: "
              "'Fix slugify state-suffix disambiguation'.", file=sys.stderr)

    by_name: dict[str, list[dict]] = {}
    for s in active:
        key = (s.get("name", "").lower().strip())
        by_name.setdefault(key, []).append(s)
    name_dupes = {n: rows for n, rows in by_name.items() if len(rows) > 1}
    if name_dupes:
        print("\n✗ ERROR: schools.yaml has duplicate active-school names:", file=sys.stderr)
        for name, rows in sorted(name_dupes.items()):
            print(f"  {name!r} appears {len(rows)} times:", file=sys.stderr)
            for r in rows:
                print(f"    id={r.get('id')!r}  ipeds={r.get('ipeds_id')}  "
                      f"domain={r.get('domain')!r}", file=sys.stderr)
        print("\nThis is the bug class cleaned up by the 2026-04-19 dedup migration.",
              file=sys.stderr)
        print("Fix: run tools/finder/dedup_audit.py for IPEDS-driven analysis, "
              "then dedup_migrate.py to consolidate.", file=sys.stderr)
        raise SystemExit(2)


def write_yaml(schools: list[dict], dry_run: bool = False) -> None:
    """Write the merged school list to schools.yaml."""

    # Refuse to write a corrupted corpus.
    assert_no_duplicates(schools)

    # discovery_seed_url is the post-PR-5 field; cds_url_hint is the
    # legacy alias preserved during the migration window.
    def _seed(s: dict) -> str | None:
        return s.get("discovery_seed_url") or s.get("cds_url_hint")

    active_hand = [s for s in schools if s.get("scrape_policy") == "active"
                   and _seed(s)]
    active_no_hint = [s for s in schools if s.get("scrape_policy") == "active"
                      and not _seed(s)]
    absent = [s for s in schools if s.get("scrape_policy") == "verified_absent"]
    partial = [s for s in schools if s.get("scrape_policy") == "verified_partial"]
    unknown = [s for s in schools if s.get("scrape_policy") in ("unknown", None)]

    for group in [active_hand, active_no_hint, absent, partial, unknown]:
        group.sort(key=lambda s: s.get("name", "").lower())

    total = len(schools)
    n_active = len(active_hand) + len(active_no_hint)
    n_unknown = len(unknown)
    n_absent = len(absent)

    header = f"""\
# schools.yaml — canonical school list for the CDS Finder
#
# Generated by build_school_list.py from IPEDS institutional characteristics data,
# merged with hand-curated overrides. DO NOT edit the IPEDS-sourced entries by hand —
# edit the merge logic in build_school_list.py or add overrides to the "hand-curated"
# sections at the top. Hand-curated entries (with discovery_seed_url, browse_url,
# notes, etc.) are preserved across regeneration runs.
#
# Fields:
#   id:                  kebab-case slug, used as the Storage path key
#   name:                display name
#   domain:              primary .edu domain (no protocol, no trailing slash)
#   ipeds_id:            IPEDS Unit ID (6 digits) — stable join key
#   discovery_seed_url:  URL the resolver fetches first (parent-walk + well-known
#                        paths run from here). May be a direct PDF or a landing page.
#   browse_url:          (optional) human-friendly URL surfaced by the kids worklist.
#                        Distinct from discovery_seed_url when the seed is a direct
#                        PDF that no one wants to send a contributor to.
#   scrape_policy:       active | verified_absent | verified_partial | unknown
#   sub_institutions:    optional list if the school publishes >1 CDS per year
#   notes:               optional free-text
#
# School-specific operator overrides (manually-supplied direct PDF lists,
# hosting fingerprints, etc.) live in school_overrides.yaml — kept out of
# this file because schools.yaml is regenerated from IPEDS and would lose
# nested override data on the next build_school_list.py run.
#
# Stats: {total} total, {n_active} active, {n_unknown} unknown, {n_absent} absent
"""

    output_path = SCHOOLS_YAML if not dry_run else SCHOOLS_YAML.with_suffix(".preview.yaml")

    with output_path.open("w") as f:
        f.write(header + "\nschools:\n")

        def write_section(label: str, items: list[dict]) -> None:
            if not items:
                return
            f.write(f"\n  # ── {label} ({len(items)}) ──\n\n")
            for s in items:
                f.write(f"  - id: {s['id']}\n")
                # Escape names that contain special YAML chars
                name = s.get("name", "")
                if any(c in name for c in ":&'\"[]{}#"):
                    f.write(f'    name: "{name}"\n')
                else:
                    f.write(f"    name: {name}\n")
                f.write(f"    domain: {s.get('domain', '')}\n")
                iid = str(s.get("ipeds_id", "")).strip('"')
                f.write(f'    ipeds_id: "{iid}"\n')
                # Prefer discovery_seed_url; carry legacy cds_url_hint forward
                # if that's all the row has (PR 5 migration window).
                seed = s.get("discovery_seed_url") or s.get("cds_url_hint")
                if seed:
                    f.write(f"    discovery_seed_url: {seed}\n")
                if s.get("browse_url"):
                    f.write(f"    browse_url: {s['browse_url']}\n")
                policy = s.get("scrape_policy", "unknown")
                f.write(f"    scrape_policy: {policy}\n")
                if s.get("sub_institutions"):
                    f.write("    sub_institutions:\n")
                    for sub in s["sub_institutions"]:
                        f.write(f'      - id: {sub.get("id", "")}\n')
                        f.write(f'        label: "{sub.get("label", "")}"\n')
                if s.get("notes"):
                    notes = s["notes"].replace('"', '\\"')
                    f.write(f'    notes: "{notes}"\n')
                f.write("\n")

        write_section("Hand-curated active (with URL hints)", active_hand)
        write_section("Hand-curated active (discovery needed)", active_no_hint)
        write_section("Known non-publishers", absent)
        write_section("Known partial publishers", partial)
        write_section("IPEDS candidates — discovery needed", unknown)

    print(f"\nWrote {total} schools to {output_path}")
    print(f"  Active (hand-curated): {n_active}")
    print(f"  Unknown (IPEDS, needs discovery): {n_unknown}")
    print(f"  Verified absent: {n_absent}")


def main():
    ap = argparse.ArgumentParser(description="Expand schools.yaml from IPEDS data")
    ap.add_argument("--year", type=int, default=2023,
                    help="IPEDS data year (default: 2023)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Write to schools.preview.yaml instead of overwriting")
    args = ap.parse_args()

    rows = download_ipeds(args.year)
    print(f"Raw IPEDS rows: {len(rows):,}")

    rows = filter_ipeds(rows)
    print(f"Filtered to {len(rows):,} candidate institutions")

    existing = load_existing()
    print(f"Existing hand-curated entries: {len(existing)}")

    schools = merge(rows, existing)
    print(f"Merged total: {len(schools)}")

    write_yaml(schools, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
