#!/usr/bin/env python3
"""Select and optionally download failure-stratified Docling spike fixtures.

This is the operational Step 3 setup for PRD 0111A. It queries public
Supabase data for low-coverage Tier 4 Docling artifacts, joins the source
document metadata, and writes a manifest. With --download it also downloads
the archived source PDFs into a gitignored fixture directory.

Default output paths live under .context so fixture PDFs and manifests do not
become committed repo state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from supabase import create_client


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / ".context" / "docling-spike" / "fixtures"


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


def default_env_path() -> Path:
    if (REPO_ROOT / ".env").exists():
        return REPO_ROOT / ".env"
    return REPO_ROOT / ".env.local"


def supabase_config(env: dict[str, str]) -> tuple[str, str]:
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        env.get("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_ANON_KEY")
        or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise SystemExit(
            "Missing Supabase env. Need SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY "
            "or NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_ANON_KEY."
        )
    return url, key


def stat_count(notes: dict[str, Any]) -> int:
    stats = notes.get("stats") or {}
    raw = stats.get("schema_fields_populated")
    try:
        return int(raw)
    except Exception:
        return 0


def values_count(notes: dict[str, Any], prefix: str | None) -> int:
    values = notes.get("values") or {}
    if not isinstance(values, dict):
        return 0
    if not prefix:
        return len(values)
    return sum(1 for key in values if str(key).startswith(prefix))


def safe_name(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "unknown"


def year_start(year: str | None) -> int | None:
    if not year:
        return None
    m = re.match(r"^(20\d{2})", str(year))
    return int(m.group(1)) if m else None


def document_year(doc: dict[str, Any]) -> str | None:
    return doc.get("cds_year") or doc.get("detected_year")


def fetch_docs(client: Any, document_ids: list[str]) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for i in range(0, len(document_ids), 100):
        batch = document_ids[i : i + 100]
        rows = (
            client.table("cds_documents")
            .select("id,school_id,cds_year,detected_year,source_format,source_sha256")
            .in_("id", batch)
            .execute()
            .data
            or []
        )
        for row in rows:
            docs[row["id"]] = row
    return docs


def fetch_latest_source(client: Any, document_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("cds_artifacts")
        .select("id,storage_path,sha256,created_at")
        .eq("document_id", document_id)
        .eq("kind", "source")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def download_pdf(client: Any, storage_path: str, out_path: Path) -> None:
    data = client.storage.from_("sources").download(storage_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", type=Path, default=default_env_path())
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--candidate-limit", type=int, default=300)
    ap.add_argument("--source-format", default="pdf_flat")
    ap.add_argument("--min-fields", type=int, default=20,
                    help="Skip likely blank/wrong-file artifacts below this coverage")
    ap.add_argument("--min-year", default=None,
                    help="Minimum academic year start, e.g. 2024-25 or 2024")
    ap.add_argument("--max-per-school", type=int, default=1,
                    help="Diversify fixtures by limiting rows per school")
    ap.add_argument("--field-prefix", default="C.9",
                    help="Prefer docs missing this field prefix; use '' to disable")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir

    env = load_env(args.env)
    url, key = supabase_config(env)
    client = create_client(url, key)

    print(
        f"Fetching up to {args.candidate_limit} tier4_docling artifacts...",
        file=sys.stderr,
    )
    artifacts = (
        client.table("cds_artifacts")
        .select("id,document_id,notes,created_at")
        .eq("producer", "tier4_docling")
        .eq("kind", "canonical")
        .limit(args.candidate_limit)
        .execute()
        .data
        or []
    )
    docs = fetch_docs(client, [a["document_id"] for a in artifacts])

    prefix = args.field_prefix or None
    candidates: list[dict[str, Any]] = []
    for art in artifacts:
        doc = docs.get(art["document_id"])
        if not doc:
            continue
        if args.source_format != "any" and doc.get("source_format") != args.source_format:
            continue
        if args.min_year:
            min_year = year_start(args.min_year)
            doc_year = year_start(document_year(doc))
            if min_year is not None and (doc_year is None or doc_year < min_year):
                continue
        notes = art.get("notes") or {}
        field_count = stat_count(notes)
        if field_count < args.min_fields:
            continue
        source = fetch_latest_source(client, art["document_id"])
        if not source:
            continue
        prefix_count = values_count(notes, prefix)
        year = document_year(doc) or "unknown-year"
        stem = safe_name(f"{doc.get('school_id')}-{year}-{art['document_id'][:8]}")
        pdf_path = out_dir / f"{stem}.pdf"
        item = {
            "document_id": art["document_id"],
            "artifact_id": art["id"],
            "school_id": doc.get("school_id"),
            "cds_year": doc.get("cds_year"),
            "detected_year": doc.get("detected_year"),
            "source_format": doc.get("source_format"),
            "source_sha256": doc.get("source_sha256"),
            "source_storage_path": source.get("storage_path"),
            "source_artifact_id": source.get("id"),
            "schema_fields_populated": field_count,
            "prefix": prefix,
            "prefix_fields_populated": prefix_count,
            "pdf_path": str(pdf_path.relative_to(REPO_ROOT)),
        }
        candidates.append(item)

    candidates.sort(key=lambda x: (x["prefix_fields_populated"], x["schema_fields_populated"]))
    selected: list[dict[str, Any]] = []
    per_school: dict[str, int] = {}
    for item in candidates:
        school_id = str(item.get("school_id") or "")
        if args.max_per_school > 0 and per_school.get(school_id, 0) >= args.max_per_school:
            continue
        selected.append(item)
        per_school[school_id] = per_school.get(school_id, 0) + 1
        if len(selected) >= args.limit:
            break

    out_dir.mkdir(parents=True, exist_ok=True)
    if args.download:
        for item in selected:
            out_path = REPO_ROOT / item["pdf_path"]
            print(f"Downloading {item['school_id']} -> {out_path}", file=sys.stderr)
            download_pdf(client, item["source_storage_path"], out_path)

    manifest = {
        "selection": {
            "producer": "tier4_docling",
            "kind": "canonical",
            "source_format": args.source_format,
            "candidate_limit": args.candidate_limit,
            "limit": args.limit,
            "min_fields": args.min_fields,
            "min_year": args.min_year,
            "max_per_school": args.max_per_school,
            "field_prefix": prefix,
        },
        "fixtures": selected,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {manifest_path}")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
