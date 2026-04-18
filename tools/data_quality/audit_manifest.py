#!/usr/bin/env python3
"""Flag documents with data-quality issues that aren't extraction bugs.

Queries cds_artifacts for canonical artifacts and flags documents where:
  - schema_fields_populated < 5 (blank template or wrong file)
  - All field values are empty/zero (boilerplate document)

Outputs a JSON report and optionally writes data_quality_flag to cds_documents.

Usage:
    python tools/data_quality/audit_manifest.py                 # report only
    python tools/data_quality/audit_manifest.py --write          # report + persist flags
    python tools/data_quality/audit_manifest.py --school yale    # single school
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

LOW_FIELD_THRESHOLD = 5


def main():
    parser = argparse.ArgumentParser(description="Audit manifest for data-quality issues")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--write", action="store_true", help="Persist flags to cds_documents")
    parser.add_argument("--school", default=None, help="Filter to a single school_id")
    parser.add_argument("--json-output", default=None, help="Write JSON report to file")
    args = parser.parse_args()

    load_dotenv(args.env)
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    sb = create_client(url, key)

    # Fetch canonical artifacts in small batches to avoid statement timeout.
    # The notes JSONB is large, so we fetch in pages of 200.
    data = []
    page_size = 200
    offset = 0
    while True:
        batch = sb.table("cds_artifacts").select(
            "id, document_id, notes, producer"
        ).eq("kind", "canonical").order(
            "created_at", desc=True
        ).range(offset, offset + page_size - 1).execute().data or []
        data.extend(batch)
        print(f"  fetched {len(data)} artifacts...", end="\r")
        if len(batch) < page_size:
            break
        offset += page_size
    print(f"Found {len(data)} canonical artifacts        ")

    # Build a map of document_id -> artifact
    doc_artifacts: dict[str, dict] = {}
    for row in data:
        doc_id = row["document_id"]
        # Keep the most recent artifact per document (data is unordered)
        if doc_id not in doc_artifacts:
            doc_artifacts[doc_id] = row

    # Fetch document metadata
    doc_query = sb.table("cds_documents").select(
        "id, school_id, school_name, cds_year, extraction_status, detected_year"
    )
    if args.school:
        doc_query = doc_query.eq("school_id", args.school)
    docs = doc_query.execute().data or []

    flagged = []
    for doc in docs:
        doc_id = doc["id"]
        artifact = doc_artifacts.get(doc_id)
        if not artifact:
            continue

        notes = artifact.get("notes") or {}
        stats = notes.get("stats") or {}
        values = notes.get("values") or {}
        fields_populated = stats.get("schema_fields_populated", len(values))

        reason = None
        if fields_populated < LOW_FIELD_THRESHOLD:
            # Check if it's a blank template vs wrong file
            if fields_populated == 0:
                reason = "blank_template"
            else:
                reason = "low_coverage"

        if reason:
            flagged.append({
                "document_id": doc_id,
                "school_id": doc["school_id"],
                "school_name": doc["school_name"],
                "year": doc.get("detected_year") or doc.get("cds_year"),
                "fields_populated": fields_populated,
                "producer": artifact.get("producer"),
                "reason": reason,
            })

    # Report
    print(f"\nFlagged: {len(flagged)} documents")
    for f in flagged:
        print(f"  {f['school_name']} ({f['year']}): {f['reason']} ({f['fields_populated']} fields)")

    # Write JSON report
    if args.json_output:
        with open(args.json_output, "w") as fp:
            json.dump(flagged, fp, indent=2)
        print(f"\nReport written to {args.json_output}")

    # Persist flags
    if args.write and flagged:
        print(f"\nWriting data_quality_flag to {len(flagged)} documents...")
        for f in flagged:
            sb.table("cds_documents").update(
                {"data_quality_flag": f["reason"]}
            ).eq("id", f["document_id"]).execute()
        print("Done.")
    elif args.write and not flagged:
        print("\nNo documents to flag.")

    # Summary
    print(f"\nSummary: {len(flagged)} flagged out of {len(doc_artifacts)} artifacts checked")
    if flagged:
        by_reason = {}
        for f in flagged:
            by_reason[f["reason"]] = by_reason.get(f["reason"], 0) + 1
        for reason, count in sorted(by_reason.items()):
            print(f"  {reason}: {count}")

    return 0 if not flagged else 1


if __name__ == "__main__":
    sys.exit(main())
