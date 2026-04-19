#!/usr/bin/env python3
"""Spot-check College Transitions' re-hosted CDS PDFs against our own archive.

For a small sample of (school, year) pairs present in both sources, download
CT's Google Drive file, hash it, and compare the sha256 to our stored
cds_artifacts.source_sha256.

Identical hashes → CT re-hosted the exact file the school published.
Different hashes → CT has a different version (different year of data
snapshotted, re-saved by PDF viewer, or edited).

Usage:
    python tools/data_quality/ct_spot_check.py                   # default 10 pairs
    python tools/data_quality/ct_spot_check.py --sample 20
    python tools/data_quality/ct_spot_check.py --school yale     # just one school (all overlap years)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from difflib import SequenceMatcher
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
CT_JSON = REPO_ROOT / ".playwright-mcp" / "ct-repository-full.json"
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"

# Google Drive direct-download rewrite. Mirrors rewriteGoogleDriveUrl
# in supabase/functions/_shared/resolve.ts.
def drive_download_url(share_url: str) -> str | None:
    """https://drive.google.com/file/d/<ID>/view → https://drive.google.com/uc?export=download&id=<ID>"""
    import re
    m = re.search(r"/file/d/([a-zA-Z0-9_-]{10,})", share_url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return None


def load_ct() -> list[dict]:
    with open(CT_JSON) as f:
        wrapper = json.load(f)
    return wrapper["data"] if "data" in wrapper else wrapper


def load_active_schools() -> dict[str, dict]:
    with open(SCHOOLS_YAML) as f:
        corpus = yaml.safe_load(f)
    return {
        s["name"].lower(): s
        for s in corpus["schools"]
        if s.get("scrape_policy") == "active"
    }


def match_school(ct_name: str, our_by_name: dict[str, dict]) -> dict | None:
    """Fuzzy-match CT school name → our school entry."""
    low = ct_name.lower()
    # Direct hits + common variants
    if low in our_by_name:
        return our_by_name[low]
    # Strip "University of " prefixes, "The", etc.
    variants = [
        low,
        low.replace("college of william and mary", "william & mary"),
        low.replace("the ", ""),
        low.replace("university of ", "").strip(),
    ]
    for v in variants:
        if v in our_by_name:
            return our_by_name[v]
    # Fuzzy
    best, best_score = None, 0.0
    for our_name, our_s in our_by_name.items():
        r = SequenceMatcher(None, low, our_name).ratio()
        if r > best_score:
            best_score = r
            best = our_s
    return best if best_score >= 0.88 else None


def fetch_our_sha(sb, school_id: str, cds_year: str) -> tuple[str | None, str | None]:
    """Return (source_sha256, source_url) from cds_documents/cds_artifacts."""
    doc = sb.table("cds_documents").select("id, source_sha256, source_url").eq(
        "school_id", school_id
    ).eq("cds_year", cds_year).execute().data
    if not doc:
        # Try detected_year instead
        doc = sb.table("cds_documents").select("id, source_sha256, source_url, cds_year").eq(
            "school_id", school_id
        ).eq("detected_year", cds_year).execute().data
    if not doc:
        return None, None
    return doc[0].get("source_sha256"), doc[0].get("source_url")


def download_and_hash(url: str, timeout: int = 45) -> tuple[str | None, int, str]:
    """Return (sha256_hex, byte_count, content_type)."""
    try:
        r = requests.get(url, allow_redirects=True, timeout=timeout)
    except Exception as e:
        return None, 0, f"exception: {e}"
    if r.status_code >= 400:
        return None, 0, f"http {r.status_code}"
    content_type = r.headers.get("content-type", "")
    if "text/html" in content_type.lower() and len(r.content) < 100_000:
        # Drive sometimes serves an HTML interstitial for large files
        return None, len(r.content), f"html interstitial ({content_type})"
    return hashlib.sha256(r.content).hexdigest(), len(r.content), content_type


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare CT Drive-hosted PDFs to our archive")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sample", type=int, default=10, help="Number of (school, year) pairs to check")
    parser.add_argument("--school", default=None, help="Filter to one school_id (all overlap years)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    args = parser.parse_args()

    load_dotenv(args.env)
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    ct = load_ct()
    our_by_name = load_active_schools()

    # Build candidate pairs: CT rows matched to our schools, where CT has a URL.
    candidates: list[dict] = []
    for ct_row in ct:
        our = match_school(ct_row["school"], our_by_name)
        if not our:
            continue
        if args.school and our["id"] != args.school:
            continue
        for year, drive_url in ct_row["years"].items():
            candidates.append({
                "ct_school": ct_row["school"],
                "our_school_id": our["id"],
                "our_school_name": our["name"],
                "year": year,
                "drive_share_url": drive_url,
            })

    print(f"Candidate CT (school, year) pairs matched to our corpus: {len(candidates)}")

    random.seed(args.seed)
    sample = candidates if args.school else random.sample(candidates, min(args.sample, len(candidates)))
    print(f"Spot-checking {len(sample)} pairs\n")

    results = []
    for i, c in enumerate(sample, 1):
        our_sha, our_src_url = fetch_our_sha(sb, c["our_school_id"], c["year"])

        direct = drive_download_url(c["drive_share_url"])
        if not direct:
            print(f"[{i}/{len(sample)}] {c['our_school_id']} {c['year']}: could not parse Drive URL, skipping")
            continue

        ct_sha, ct_bytes, ct_ct = download_and_hash(direct)
        matched = (
            "MATCH" if (ct_sha and our_sha and ct_sha == our_sha)
            else "MISMATCH" if (ct_sha and our_sha)
            else "WE_DONT_HAVE" if not our_sha
            else "CT_DOWNLOAD_FAILED"
        )
        result = {
            **c,
            "our_sha256": our_sha,
            "our_source_url": our_src_url,
            "ct_sha256": ct_sha,
            "ct_bytes": ct_bytes,
            "ct_content_type": ct_ct,
            "outcome": matched,
        }
        results.append(result)

        short_our = (our_sha or "—")[:12]
        short_ct = (ct_sha or "—")[:12]
        print(f"[{i}/{len(sample)}] {c['our_school_id']:<30} {c['year']}  "
              f"ours={short_our}  ct={short_ct}  {matched}")
        if matched == "MISMATCH":
            # For mismatches: print the filenames from both URLs to help diagnose
            print(f"           our source: {our_src_url}")
            print(f"           ct drive:   {c['drive_share_url']}")

    # Summary
    print("\n=== Summary ===")
    from collections import Counter
    outcomes = Counter(r["outcome"] for r in results)
    for o, n in outcomes.most_common():
        print(f"  {o:<22} {n}")

    # Save raw results for follow-up analysis
    out_path = REPO_ROOT / "tools" / "data_quality" / "ct-spot-check-results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
