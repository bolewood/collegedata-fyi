#!/usr/bin/env python3
"""Find CDS artifacts likely to benefit from the visual OCR supplement.

This audits canonical Tier 4 artifacts for the Arizona failure mode:
section labels are present in the extracted text, but high-value admissions
numbers are absent because the PDF rendered filled-in cells visually rather
than in the embedded text layer.

Usage:
    python tools/data_quality/audit_visual_ocr_candidates.py \
      --env /path/to/.env \
      --csv-output .context/reports/visual-ocr-candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client


C1_KEYS = {"C.101", "C.102", "C.105", "C.106", "C.117", "C.118", "C.119"}
C9_KEYS = {"C.901", "C.902", "C.903", "C.904", "C.905", "C.906", "C.907", "C.914", "C.915", "C.916"}
OCR_PRODUCER_VERSION = "0.3.6"


def parse_year_start(year: str | None) -> int | None:
    if not year:
        return None
    match = re.match(r"^((?:19|20)\d{2})-\d{2}$", year)
    return int(match.group(1)) if match else None


def version_tuple(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    parts: list[int] = []
    for part in str(version).split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    return tuple(parts)


def fetch_all(client: Any, table: str, select: str, page_size: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch: list[dict[str, Any]] = []
        for attempt in range(4):
            try:
                batch = (
                    client.table(table)
                    .select(select)
                    .range(offset, offset + page_size - 1)
                    .execute()
                    .data
                    or []
                )
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def latest_canonical_artifacts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True):
        if row.get("kind") != "canonical":
            continue
        doc_id = str(row.get("document_id") or "")
        if doc_id and doc_id not in latest:
            latest[doc_id] = row
    return latest


def fetch_artifacts_for_documents(client: Any, document_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chunk_size = 40
    select = "id,document_id,kind,producer,producer_version,schema_version,created_at,notes"
    for start in range(0, len(document_ids), chunk_size):
        chunk = document_ids[start:start + chunk_size]
        for attempt in range(4):
            try:
                batch = (
                    client.table("cds_artifacts")
                    .select(select)
                    .eq("kind", "canonical")
                    .in_("document_id", chunk)
                    .execute()
                    .data
                    or []
                )
                rows.extend(batch)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    return rows


def has_c1_anchor(markdown: str) -> bool:
    lowered = markdown.lower()
    return (
        "c1. first-time" in lowered
        or "first-time, first-year student applicants" in lowered
        or "first-time, first-year admission" in lowered
    )


def has_c9_anchor(markdown: str) -> bool:
    lowered = markdown.lower()
    return "submitting sat scores" in lowered or "c9. percent and number" in lowered


def classify(doc: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any] | None:
    notes = artifact.get("notes") or {}
    if not isinstance(notes, dict):
        return None
    markdown = str(notes.get("markdown") or "")
    values = notes.get("values") or {}
    if not isinstance(values, dict):
        values = {}
    stats = notes.get("stats") or {}
    if not isinstance(stats, dict):
        stats = {}

    visual_pages = stats.get("visual_ocr_pages") or []
    if not isinstance(visual_pages, list):
        visual_pages = []
    field_count = int(stats.get("schema_fields_populated") or len(values) or 0)
    producer_version = str(artifact.get("producer_version") or "")

    c1_anchor = has_c1_anchor(markdown)
    c9_anchor = has_c9_anchor(markdown)
    missing_c1 = c1_anchor and not C1_KEYS.intersection(values)
    missing_c9 = c9_anchor and not C9_KEYS.intersection(values)
    recovered_c1 = c1_anchor and bool(C1_KEYS.intersection(values))
    recovered_c9 = c9_anchor and bool(C9_KEYS.intersection(values))

    if visual_pages:
        if missing_c1 or missing_c9:
            status = "ocr_attempt_still_missing"
        else:
            status = "visual_ocr_recovered"
    elif (missing_c1 or missing_c9) and field_count < 150:
        status = (
            "needs_redrain_visual_ocr"
            if version_tuple(producer_version) < version_tuple(OCR_PRODUCER_VERSION)
            else "candidate_without_ocr_pages"
        )
    else:
        return None

    return {
        "status": status,
        "document_id": doc["id"],
        "school_id": doc["school_id"],
        "school_name": doc.get("school_name") or "",
        "cds_year": doc.get("detected_year") or doc.get("cds_year") or "",
        "source_format": doc.get("source_format") or "",
        "producer": artifact.get("producer") or "",
        "producer_version": producer_version,
        "schema_version": artifact.get("schema_version") or "",
        "schema_fallback_used": bool(notes.get("schema_fallback_used")),
        "field_count": field_count,
        "visual_ocr_pages": ",".join(str(p) for p in visual_pages),
        "missing_c1": int(missing_c1),
        "missing_c9": int(missing_c9),
        "recovered_c1": int(recovered_c1),
        "recovered_c9": int(recovered_c9),
        "source_url": doc.get("source_url") or "",
        "created_at": artifact.get("created_at") or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit visual-OCR extraction candidates")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--school", help="Restrict to one school_id")
    parser.add_argument("--min-year-start", type=int, default=2024)
    parser.add_argument("--include-all-years", action="store_true")
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    load_dotenv(args.env)
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    docs = fetch_all(
        client,
        "cds_documents",
        "id,school_id,school_name,cds_year,detected_year,source_format,source_url",
        page_size=1000,
    )
    docs = [
        doc
        for doc in docs
        if (not args.school or doc.get("school_id") == args.school)
        and doc.get("source_format") in {"pdf_flat", "pdf_scanned"}
        and (
            args.include_all_years
            or (
                (parse_year_start(doc.get("detected_year") or doc.get("cds_year")) or 0)
                >= args.min_year_start
            )
        )
    ]
    artifacts = latest_canonical_artifacts(
        fetch_artifacts_for_documents(client, [str(doc["id"]) for doc in docs])
    )

    rows: list[dict[str, Any]] = []
    for doc in docs:
        artifact = artifacts.get(str(doc["id"]))
        if not artifact or artifact.get("producer") != "tier4_docling":
            continue
        row = classify(doc, artifact)
        if row:
            rows.append(row)

    status_order = {
        "needs_redrain_visual_ocr": 0,
        "candidate_without_ocr_pages": 1,
        "ocr_attempt_still_missing": 2,
        "visual_ocr_recovered": 3,
    }
    rows.sort(key=lambda r: (status_order.get(r["status"], 9), r["school_id"], r["cds_year"]))

    fieldnames = [
        "status",
        "document_id",
        "school_id",
        "school_name",
        "cds_year",
        "source_format",
        "producer",
        "producer_version",
        "schema_version",
        "schema_fallback_used",
        "field_count",
        "visual_ocr_pages",
        "missing_c1",
        "missing_c9",
        "recovered_c1",
        "recovered_c9",
        "source_url",
        "created_at",
    ]
    if args.csv_output:
        args.csv_output.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_output.open("w", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")

    summary: dict[str, int] = {"total": len(rows)}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    for row in rows[:25]:
        print(
            f"{row['status']:27s} {row['school_id']:45s} "
            f"{row['cds_year']:7s} fields={row['field_count']:3d} "
            f"pages={row['visual_ocr_pages'] or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
