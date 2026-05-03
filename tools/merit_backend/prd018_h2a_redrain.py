#!/usr/bin/env python3
"""Plan or queue the PRD 018 H2A Tier 4 redrain.

The Section H audit showed the public merit profile is blocked mainly by
H2A coverage. This helper finds latest 2024+ Tier 4 rows where `H.2A02` is
missing in the current projection, reruns the current checkout's Tier 4
cleaner against stored Docling markdown, and selects only documents where the
patched cleaner recovers `H.2A02`.

Default mode is read-only and writes a candidate JSON/Markdown report.
Use `--apply` to mark candidates `extraction_pending`; then run the normal
extraction worker so fresh `tier4_docling` artifacts and browser projections
are written through the standard path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "extraction_worker"))

from tier4_cleaner import clean  # noqa: E402
from prd018_section_h_audit import (  # noqa: E402
    fetch_latest_browser_rows,
    fetch_target_fields,
    is_answerable,
)


def load_env(env_path: Path | None) -> None:
    if not env_path:
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def supabase_client(env_path: Path | None, require_service_role: bool):
    load_env(env_path)
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key_name = "SUPABASE_SERVICE_ROLE_KEY"
    key = os.environ.get(key_name)
    if not key and not require_service_role:
        key_name = "SUPABASE_ANON_KEY"
        key = os.environ.get(key_name) or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not key:
        raise SystemExit(f"{'SUPABASE_URL and ' if not url else ''}{key_name} required")
    return create_client(url, key)


def fetch_latest_artifacts(client: Any, document_ids: list[str]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for start in range(0, len(document_ids), 20):
        chunk = document_ids[start : start + 20]
        rows = (
            client.table("cds_artifacts")
            .select("id,document_id,producer_version,schema_version,created_at,notes")
            .eq("producer", "tier4_docling")
            .eq("kind", "canonical")
            .in_("document_id", chunk)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        for row in rows:
            latest.setdefault(str(row["document_id"]), row)
    return latest


def plan_candidates(client: Any, limit: int | None) -> list[dict[str, Any]]:
    rows = [
        row
        for row in fetch_latest_browser_rows(client)
        if row.get("producer") == "tier4_docling"
    ]
    rows = sorted(rows, key=lambda row: row.get("applied") or 0, reverse=True)
    if limit:
        rows = rows[:limit]

    fields = fetch_target_fields(client, [str(row["document_id"]) for row in rows])
    misses = [
        row
        for row in rows
        if not is_answerable(fields.get(str(row["document_id"]), {}).get("H.2A02"))
    ]
    artifacts = fetch_latest_artifacts(client, [str(row["document_id"]) for row in misses])

    candidates: list[dict[str, Any]] = []
    for row in misses:
        document_id = str(row["document_id"])
        artifact = artifacts.get(document_id)
        if not artifact:
            continue
        notes = artifact.get("notes") or {}
        markdown = notes.get("markdown") if isinstance(notes, dict) else None
        if not isinstance(markdown, str) or not markdown.strip():
            continue
        values = clean(markdown)
        if "H.2A02" not in values:
            continue
        candidates.append(
            {
                "document_id": document_id,
                "school_id": row["school_id"],
                "school_name": row["school_name"],
                "canonical_year": row["canonical_year"],
                "applied": row.get("applied"),
                "previous_artifact_id": artifact.get("id"),
                "previous_producer_version": artifact.get("producer_version"),
                "recovered_h2a01": values.get("H.2A01", {}).get("value"),
                "recovered_h2a02": values["H.2A02"]["value"],
                "recovered_h2a05": values.get("H.2A05", {}).get("value"),
                "recovered_h2a06": values.get("H.2A06", {}).get("value"),
            }
        )
    return candidates


def apply_requeue(client: Any, candidates: list[dict[str, Any]]) -> int:
    changed = 0
    for candidate in candidates:
        result = (
            client.table("cds_documents")
            .update({"extraction_status": "extraction_pending"})
            .eq("id", candidate["document_id"])
            .execute()
        )
        rows = result.data or []
        if rows:
            changed += 1
    return changed


def write_report(out_dir: Path, candidates: list[dict[str, Any]], applied: bool, changed: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": generated_at,
        "applied": applied,
        "requeued_count": changed,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    (out_dir / "h2a-redrain-candidates.json").write_text(json.dumps(payload, indent=2, default=str))

    lines = [
        "# PRD 018 H2A Redrain Candidates",
        "",
        f"Generated: `{generated_at}`",
        f"Candidates: `{len(candidates)}`",
        f"Applied: `{applied}`",
        f"Requeued: `{changed}`",
        "",
        "| Applied | School | Year | H.2A01 | H.2A02 | H.2A05 | H.2A06 |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in candidates:
        lines.append(
            "| {applied} | `{school_id}` | {year} | {h2a01} | {h2a02} | {h2a05} | {h2a06} |".format(
                applied=row.get("applied") or "",
                school_id=row["school_id"],
                year=row["canonical_year"],
                h2a01=row.get("recovered_h2a01") or "",
                h2a02=row.get("recovered_h2a02") or "",
                h2a05=row.get("recovered_h2a05") or "",
                h2a06=row.get("recovered_h2a06") or "",
            )
        )
    (out_dir / "h2a-redrain-candidates.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--env", type=Path)
    parser.add_argument("--limit", type=int, help="Optional top-applied Tier 4 row cap")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "scratch" / "prd018")
    parser.add_argument("--apply", action="store_true", help="Mark candidate documents extraction_pending")
    args = parser.parse_args()

    client = supabase_client(args.env, require_service_role=args.apply)
    candidates = plan_candidates(client, args.limit)
    changed = apply_requeue(client, candidates) if args.apply else 0
    write_report(args.output_dir, candidates, args.apply, changed)

    print(f"Candidates: {len(candidates)}")
    if args.apply:
        print(f"Requeued: {changed}")
    print(f"Wrote {args.output_dir / 'h2a-redrain-candidates.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
