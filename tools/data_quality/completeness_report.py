#!/usr/bin/env python3
"""Top-to-bottom data completeness pivot for the past N CDS years.

Funnel stages, per CDS year:
  corpus       — schools we are targeting (from tools/finder/schools.yaml)
  discovered   — cds_documents row exists (URL or sub_institutional placeholder)
  archived     — source file archived to Storage (source_sha256 not null)
  pending      — extraction_status = 'extraction_pending'
  extracted    — extraction_status = 'extracted'
  failed       — extraction_status = 'failed'
  canonical    — has at least one canonical artifact
  high_quality — canonical artifact with >= 5 schema fields populated
  low_quality  — canonical artifact with 1-4 fields (low_coverage)
  blank        — canonical artifact with 0 fields (blank_template)

Usage:
    python tools/data_quality/completeness_report.py
    python tools/data_quality/completeness_report.py --years 2020-21,2021-22,2022-23,2023-24,2024-25
    python tools/data_quality/completeness_report.py --json-output report.json
    python tools/data_quality/completeness_report.py --scrape-policy active   # narrow corpus
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
DEFAULT_YEARS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
LOW_FIELD_THRESHOLD = 5


def load_corpus(scrape_policy_filter: set[str] | None) -> list[dict]:
    with open(SCHOOLS_YAML) as fp:
        data = yaml.safe_load(fp)
    schools = data.get("schools", [])
    if scrape_policy_filter:
        schools = [s for s in schools if s.get("scrape_policy") in scrape_policy_filter]
    targets = []
    for s in schools:
        subs = s.get("sub_institutions") or [None]
        for sub in subs:
            targets.append({
                "school_id": s["id"],
                "sub_institutional": sub["id"] if sub else None,
            })
    return targets


def fetch_documents(sb, years: list[str]) -> list[dict]:
    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        batch = sb.table("cds_documents").select(
            "id, school_id, sub_institutional, cds_year, detected_year, "
            "participation_status, extraction_status, source_sha256, "
            "source_format, data_quality_flag"
        ).in_("cds_year", years).range(offset, offset + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def fetch_canonical_quality(sb, doc_ids: set[str]) -> dict[str, dict]:
    """Return {document_id: {producer, fields_populated}} for the most recent canonical."""
    quality: dict[str, dict] = {}
    if not doc_ids:
        return quality
    page_size = 200
    offset = 0
    while True:
        batch = sb.table("cds_artifacts").select(
            "document_id, producer, notes, created_at"
        ).eq("kind", "canonical").order("created_at", desc=True).range(
            offset, offset + page_size - 1
        ).execute().data or []
        for row in batch:
            doc_id = row["document_id"]
            if doc_id in quality or doc_id not in doc_ids:
                continue
            notes = row.get("notes") or {}
            stats = notes.get("stats") or {}
            values = notes.get("values") or {}
            fields = stats.get("schema_fields_populated", len(values))
            quality[doc_id] = {
                "producer": row.get("producer"),
                "fields_populated": fields,
            }
        if len(batch) < page_size:
            break
        offset += page_size
    return quality


def main() -> int:
    parser = argparse.ArgumentParser(description="CDS data completeness pivot report")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_YEARS),
        help=f"Comma-separated cds_year values (default: {','.join(DEFAULT_YEARS)})",
    )
    parser.add_argument(
        "--scrape-policy",
        default=None,
        help="Filter corpus to scrape_policy values (comma-separated, e.g. 'active,unknown')",
    )
    parser.add_argument("--json-output", default=None, help="Write JSON report to path")
    args = parser.parse_args()

    years = [y.strip() for y in args.years.split(",") if y.strip()]
    policy_filter = (
        {p.strip() for p in args.scrape_policy.split(",")} if args.scrape_policy else None
    )

    load_dotenv(args.env)
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    sb = create_client(url, key)

    corpus = load_corpus(policy_filter)
    corpus_size = len(corpus)
    unique_schools = len({c["school_id"] for c in corpus})

    print(f"Corpus: {corpus_size} school×variant rows ({unique_schools} unique schools)")
    if policy_filter:
        print(f"  scrape_policy filter: {sorted(policy_filter)}")
    print(f"Years: {years}\n")

    docs = fetch_documents(sb, years)
    print(f"Fetched {len(docs)} cds_documents rows across {len(years)} years")

    doc_ids = {d["id"] for d in docs}
    quality = fetch_canonical_quality(sb, doc_ids)
    print(f"Fetched {len(quality)} canonical artifacts\n")

    # Build pivot. Stages are cumulative-ish but we report raw counts so the
    # reader can see drop-off at each step.
    stages = [
        "corpus", "discovered", "published", "verified_absent",
        "archived", "pending", "extracted", "failed",
        "canonical", "high_quality", "low_quality", "blank",
    ]
    pivot: dict[str, dict[str, int]] = {y: {s: 0 for s in stages} for y in years}
    producer_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for y in years:
        pivot[y]["corpus"] = corpus_size

    for d in docs:
        y = d["cds_year"]
        if y not in pivot:
            continue
        pivot[y]["discovered"] += 1
        if d.get("participation_status") == "published":
            pivot[y]["published"] += 1
        if d.get("participation_status") == "verified_absent":
            pivot[y]["verified_absent"] += 1
        if d.get("source_sha256"):
            pivot[y]["archived"] += 1
        es = d.get("extraction_status")
        if es == "extraction_pending":
            pivot[y]["pending"] += 1
        elif es == "extracted":
            pivot[y]["extracted"] += 1
        elif es == "failed":
            pivot[y]["failed"] += 1

        q = quality.get(d["id"])
        if q:
            pivot[y]["canonical"] += 1
            fields = q["fields_populated"] or 0
            if fields >= LOW_FIELD_THRESHOLD:
                pivot[y]["high_quality"] += 1
            elif fields == 0:
                pivot[y]["blank"] += 1
            else:
                pivot[y]["low_quality"] += 1
            producer_counts[y][q["producer"] or "unknown"] += 1

    # Print pivot table
    col_w = 13
    header = f"{'stage':<22}" + "".join(f"{y:>{col_w}}" for y in years) + f"{'TOTAL':>{col_w}}"
    print(header)
    print("-" * len(header))
    for stage in stages:
        row_total = sum(pivot[y][stage] for y in years)
        if stage == "corpus":
            # "TOTAL" column for corpus is misleading (same value × N years); show '-'
            row = f"{stage:<22}" + "".join(f"{pivot[y][stage]:>{col_w}}" for y in years) + f"{'—':>{col_w}}"
        else:
            row = f"{stage:<22}" + "".join(f"{pivot[y][stage]:>{col_w}}" for y in years) + f"{row_total:>{col_w}}"
        print(row)

    # Coverage percentages relative to corpus
    print()
    print(f"{'% of corpus':<22}" + "".join(f"{'':>{col_w}}" for _ in years))
    for stage in ["discovered", "archived", "extracted", "high_quality"]:
        cells = []
        for y in years:
            pct = (pivot[y][stage] / corpus_size * 100) if corpus_size else 0
            cells.append(f"{pct:>{col_w-1}.1f}%")
        print(f"  {stage:<20}" + "".join(cells))

    # Producer breakdown
    if producer_counts:
        print("\nCanonical artifact producers (per year):")
        for y in years:
            if not producer_counts[y]:
                continue
            parts = ", ".join(
                f"{p}={c}" for p, c in sorted(producer_counts[y].items(), key=lambda kv: -kv[1])
            )
            print(f"  {y}: {parts}")

    if args.json_output:
        report = {
            "corpus_size": corpus_size,
            "unique_schools": unique_schools,
            "scrape_policy_filter": sorted(policy_filter) if policy_filter else None,
            "years": years,
            "pivot": pivot,
            "producers": {y: dict(producer_counts[y]) for y in years},
        }
        with open(args.json_output, "w") as fp:
            json.dump(report, fp, indent=2)
        print(f"\nReport written to {args.json_output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
