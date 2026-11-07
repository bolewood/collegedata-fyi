"""Add missing data-quality flags to already-extracted documents.

Tier 1 and Tier 2 extraction never evaluated ``extraction_quality_flag``, and
the ``--reconcile-pending`` pass cleared flags without re-evaluating, so
near-empty and single-section documents were served unflagged.

This backfill applies only the two rules for that failure class: fewer than
25 populated fields (``blank_template`` / ``low_coverage``) and a
single-section source without Section C. The broader live-extraction
heuristics (sparse long documents, the H.1501 section-swallow check) are not
applied retroactively: on 2026-11-07 they would have hidden 600-field
current-year documents for one bad field, a separate policy call.

Add-only: it sets a flag on documents that have none and never clears or
overrides an existing flag (``wrong_file``, LLM-fallback or operator flags),
so it can only hide, never unhide.

Usage:
    python tools/extraction_worker/backfill_quality_flags.py --env .env
    python tools/extraction_worker/backfill_quality_flags.py --env .env --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from supabase import Client, create_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker import (  # noqa: E402
    is_single_section_source,
    load_env,
    low_field_quality_flag,
)

PAGE = 500
# `values` is large; bigger chunks hit the PostgREST statement timeout.
CANONICAL_CHUNK = 20


def plan_backfill(
    documents: list[dict],
    latest_canonical: dict[str, dict],
) -> list[dict]:
    """Return {document_id, school_id, cds_year, producer, fields, flag} rows to set."""
    planned: list[dict] = []
    for doc in documents:
        if doc.get("data_quality_flag"):
            continue
        canonical = latest_canonical.get(doc["id"])
        if not canonical:
            continue
        fields = int((canonical.get("stats") or {}).get("schema_fields_populated") or 0)
        flag = low_field_quality_flag(fields)
        if not flag and is_single_section_source(canonical.get("values") or {}, fields):
            flag = "low_coverage"
        if not flag:
            continue
        planned.append({
            "document_id": doc["id"],
            "school_id": doc.get("school_id"),
            "cds_year": doc.get("cds_year"),
            "producer": canonical.get("producer"),
            "fields": fields,
            "flag": flag,
        })
    return planned


def fetch_unflagged_documents(client: Client) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        batch = (
            client.table("cds_documents")
            .select("id,school_id,cds_year,data_quality_flag")
            .is_("removed_at", "null")
            .is_("data_quality_flag", "null")
            .eq("extraction_status", "extracted")
            .order("id")
            .range(start, start + PAGE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        start += PAGE


def fetch_latest_canonical(client: Client, document_ids: list[str]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for i in range(0, len(document_ids), CANONICAL_CHUNK):
        chunk = document_ids[i : i + CANONICAL_CHUNK]
        batch = (
            client.table("cds_artifacts")
            .select("document_id,producer,created_at,stats:notes->stats,values:notes->values")
            .eq("kind", "canonical")
            .in_("document_id", chunk)
            .execute()
            .data
            or []
        )
        for row in batch:
            prior = latest.get(row["document_id"])
            if prior is None or row["created_at"] > prior["created_at"]:
                latest[row["document_id"]] = row
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--env", default=".env")
    parser.add_argument("--apply", action="store_true", help="write flags (default: dry run)")
    parser.add_argument(
        "--out-jsonl",
        default="scratch/quality-flag-backfill/planned.jsonl",
        help="where to write the planned rows",
    )
    args = parser.parse_args()

    env = load_env(Path(args.env))
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in env file", file=sys.stderr)
        return 2
    client = create_client(url, key)

    documents = fetch_unflagged_documents(client)
    canonical = fetch_latest_canonical(client, [d["id"] for d in documents])
    planned = plan_backfill(documents, canonical)

    out = Path(args.out_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row) + "\n" for row in planned))

    print(f"unflagged extracted documents: {len(documents)}")
    print(f"with a canonical artifact:     {len(canonical)}")
    print(f"flags to add:                  {len(planned)}  ({'APPLY' if args.apply else 'dry run'})")
    for (flag, producer), n in sorted(Counter((r["flag"], r["producer"]) for r in planned).items()):
        print(f"  {flag:15s} {producer or '?':16s} {n:5d}")
    print(f"planned rows: {out}")

    if not args.apply:
        return 0
    written = 0
    for row in planned:
        # Guard on null so a flag set since the read is never overwritten.
        client.table("cds_documents").update({"data_quality_flag": row["flag"]}).eq(
            "id", row["document_id"]
        ).is_("data_quality_flag", "null").execute()
        written += 1
    print(f"written: {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
