#!/usr/bin/env python3
"""PRD 014 M5 staged requeue and rollback helper.

The extraction worker only processes `extraction_pending` rows. M5 needs to
re-extract already-extracted documents so they pick up year-aware schema
dispatch. This helper identifies documents that do not yet have a canonical
artifact for their resolved schema version, snapshots their current selected
artifact, and optionally requeues them.

Rollback mode plans or deletes canonical artifacts created after the snapshot
timestamp, allowing `cds_manifest`/projection selection to fall back to the
previous artifact.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / ".context" / "prd-014-m5"

PRODUCER_BY_FORMAT = {
    "xlsx": ("tier1_xlsx", "0.1.0"),
    "pdf_fillable": ("tier2_acroform", "0.2.0"),
    "pdf_flat": ("tier4_docling", "0.3.1"),
    "pdf_scanned": ("tier4_docling", "0.3.1"),
    "html": ("tier6_html", "0.1.0"),
}


@dataclass(frozen=True)
class Candidate:
    document_id: str
    school_id: str
    canonical_year: str
    source_format: str
    producer: str
    producer_version: str
    previous_artifact_id: str | None
    previous_artifact_created_at: str | None
    previous_artifact_schema_version: str | None
    reason: str


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def supabase_config(env: dict[str, str]) -> tuple[str, str]:
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        env.get("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_ANON_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise SystemExit("missing Supabase URL/key in env file")
    return url, key


def is_service_role_key(key: str) -> bool:
    parts = key.split(".")
    if len(parts) < 2:
        return False
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return False
    return claims.get("role") == "service_role"


def canonical_year(doc: dict[str, Any]) -> str | None:
    return doc.get("detected_year") or doc.get("cds_year")


def year_start(year: str | None) -> int | None:
    match = re.match(r"^((?:19|20)\d{2})-\d{2}$", str(year or ""))
    return int(match.group(1)) if match else None


def schema_path_for_year(year: str | None) -> Path:
    if not year:
        return REPO_ROOT / "schemas" / "cds_schema_2025_26.json"
    candidate = REPO_ROOT / "schemas" / f"cds_schema_{year.replace('-', '_')}.json"
    if candidate.exists():
        return candidate
    return REPO_ROOT / "schemas" / "cds_schema_2025_26.json"


def schema_version_for_year(year: str | None) -> str:
    path = schema_path_for_year(year)
    data = json.loads(path.read_text())
    return str(data.get("schema_version") or "2025-26")


def fetch_docs(client: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    offset = 0
    page_size = min(1000, max(1, args.candidate_limit))
    while len(docs) < args.candidate_limit:
        query = (
            client.table("cds_documents")
            .select("id,school_id,cds_year,detected_year,source_format,extraction_status,data_quality_flag")
            .eq("extraction_status", "extracted")
            .order("school_id")
            .order("id")
        )
        if args.school:
            query = query.eq("school_id", args.school)
        if args.source_format:
            query = query.eq("source_format", args.source_format)
        # Pull a bounded candidate set and filter canonical-year locally because
        # PostgREST OR filters become awkward with detected_year precedence.
        rows = query.range(offset, offset + page_size - 1).execute().data or []
        if not rows:
            break
        docs.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    docs = docs[:args.candidate_limit]
    out = []
    for doc in docs:
        year = canonical_year(doc)
        if args.year and year != args.year:
            continue
        start = year_start(year)
        if start is None or start < args.min_year_start:
            continue
        if doc.get("source_format") not in PRODUCER_BY_FORMAT:
            continue
        if doc.get("data_quality_flag") in {"blank_template", "wrong_file"}:
            continue
        out.append(doc)
    return out


def latest_canonical_artifact(client: Any, document_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("cds_artifacts")
        .select("id,producer,producer_version,schema_version,created_at,notes")
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def has_target_artifact(
    client: Any,
    *,
    document_id: str,
    producer: str,
    producer_version: str,
    schema_version: str,
) -> bool:
    rows = (
        client.table("cds_artifacts")
        .select("id")
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .eq("producer", producer)
        .eq("producer_version", producer_version)
        .eq("schema_version", schema_version)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def select_candidates(client: Any, args: argparse.Namespace) -> list[Candidate]:
    candidates: list[Candidate] = []
    for doc in fetch_docs(client, args):
        year = canonical_year(doc)
        schema_version = schema_version_for_year(year)
        producer, producer_version = PRODUCER_BY_FORMAT[str(doc["source_format"])]
        if has_target_artifact(
            client,
            document_id=doc["id"],
            producer=producer,
            producer_version=producer_version,
            schema_version=schema_version,
        ):
            continue
        previous = latest_canonical_artifact(client, doc["id"])
        candidates.append(Candidate(
            document_id=str(doc["id"]),
            school_id=str(doc["school_id"]),
            canonical_year=str(year),
            source_format=str(doc["source_format"]),
            producer=producer,
            producer_version=producer_version,
            previous_artifact_id=(str(previous["id"]) if previous else None),
            previous_artifact_created_at=(str(previous["created_at"]) if previous else None),
            previous_artifact_schema_version=(
                str(previous.get("schema_version")) if previous and previous.get("schema_version") else None
            ),
            reason=f"missing {producer}@{producer_version} schema_version={schema_version}",
        ))
        if args.limit and len(candidates) >= args.limit:
            break
    return candidates


def write_snapshot(candidates: list[Candidate], args: argparse.Namespace) -> Path:
    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"snapshot-{run_id}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "year": args.year,
            "source_format": args.source_format,
            "school": args.school,
            "limit": args.limit,
            "candidate_limit": args.candidate_limit,
        },
        "candidates": [candidate.__dict__ for candidate in candidates],
    }
    path.write_text(json.dumps(payload, indent=2))
    latest = out_dir / "latest-snapshot.json"
    latest.write_text(json.dumps(payload, indent=2))
    return path


def print_summary(candidates: list[Candidate]) -> None:
    by_format: dict[str, int] = {}
    by_year: dict[str, int] = {}
    for candidate in candidates:
        by_format[candidate.source_format] = by_format.get(candidate.source_format, 0) + 1
        by_year[candidate.canonical_year] = by_year.get(candidate.canonical_year, 0) + 1
    print(f"Candidates: {len(candidates)}")
    print("By year:", json.dumps(by_year, sort_keys=True))
    print("By source_format:", json.dumps(by_format, sort_keys=True))
    for candidate in candidates[:20]:
        print(
            f"  {candidate.school_id:45s} {candidate.canonical_year:7s} "
            f"{candidate.source_format:12s} {candidate.reason}"
        )


def requeue(client: Any, candidates: list[Candidate]) -> int:
    changed = 0
    for candidate in candidates:
        client.table("cds_documents").update({
            "extraction_status": "extraction_pending",
        }).eq("id", candidate.document_id).execute()
        rows = (
            client.table("cds_documents")
            .select("id,extraction_status")
            .eq("id", candidate.document_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows or rows[0].get("extraction_status") != "extraction_pending":
            raise RuntimeError(
                f"failed to requeue document {candidate.document_id}; "
                "check Supabase credentials/RLS"
            )
        changed += 1
    return changed


def rollback_plan(client: Any, snapshot_path: Path) -> list[dict[str, Any]]:
    snapshot = json.loads(snapshot_path.read_text())
    rows: list[dict[str, Any]] = []
    for candidate in snapshot.get("candidates", []):
        cutoff = candidate.get("previous_artifact_created_at")
        if not cutoff:
            continue
        artifacts = (
            client.table("cds_artifacts")
            .select("id,document_id,producer,producer_version,schema_version,created_at")
            .eq("document_id", candidate["document_id"])
            .eq("kind", "canonical")
            .gt("created_at", cutoff)
            .execute()
            .data
            or []
        )
        rows.extend(artifacts)
    return rows


def rollback(client: Any, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        client.table("cds_artifacts").delete().eq("id", row["id"]).execute()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("mode", choices=["plan", "requeue", "rollback-plan", "rollback"])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env.local")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_OUT_DIR / "latest-snapshot.json")
    parser.add_argument("--year", default=None)
    parser.add_argument("--source-format", choices=sorted(PRODUCER_BY_FORMAT), default=None)
    parser.add_argument("--school", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--candidate-limit", type=int, default=1000)
    parser.add_argument("--min-year-start", type=int, default=2024)
    args = parser.parse_args()

    url, key = supabase_config(load_env(args.env))
    if args.mode in {"requeue", "rollback"} and not is_service_role_key(key):
        raise SystemExit("mutating modes require a Supabase service_role key")
    client = create_client(url, key)

    if args.mode in {"plan", "requeue"}:
        candidates = select_candidates(client, args)
        print_summary(candidates)
        snapshot = write_snapshot(candidates, args)
        print(f"Snapshot: {snapshot}")
        if args.mode == "requeue":
            changed = requeue(client, candidates)
            print(f"Requeued {changed} document(s).")
        return 0

    snapshot = args.snapshot if args.snapshot.is_absolute() else REPO_ROOT / args.snapshot
    rows = rollback_plan(client, snapshot)
    print(f"Rollback would delete {len(rows)} canonical artifact(s).")
    for row in rows[:20]:
        print(
            f"  {row['id']} {row['producer']} {row.get('schema_version')} {row['created_at']}"
        )
    if args.mode == "rollback":
        rollback(client, rows)
        print(f"Deleted {len(rows)} canonical artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
