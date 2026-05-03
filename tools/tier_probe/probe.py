"""
Tier probe: detect CDS source format for every archived document.

Walks cds_documents, looks up each document's most recent kind='source'
artifact, downloads the bytes from the 'sources' Storage bucket, and
classifies the file into one of the enum values the extractor pipeline
cares about:

    pdf_fillable   — PDF with an AcroForm, some fields populated → Tier 2
    pdf_flat       — PDF with no AcroForm but extractable text → Tier 4
    pdf_scanned    — PDF with no AcroForm and no extractable text → Tier 5
    xlsx           — filled XLSX template → Tier 1
    docx           — filled DOCX template → Tier 3
    other          — parse error or unexpected content type

Backfills cds_documents.source_format so the M2 extraction worker can
route on it without re-downloading the file. Prints a per-row log and
a final distribution histogram.

Usage:
    python tools/tier_probe/probe.py                    # probe all null rows
    python tools/tier_probe/probe.py --limit 20         # test against 20 rows
    python tools/tier_probe/probe.py --school yale      # target one school
    python tools/tier_probe/probe.py --dry-run          # detect but don't write
    python tools/tier_probe/probe.py --refresh          # re-probe rows that
                                                          already have source_format

Setup (one-time, matching tools/tier2_extractor):
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r tools/tier_probe/requirements.txt

Run:
    python tools/tier_probe/probe.py --limit 5

SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are loaded from .env at the repo
root. The service role key is required to bypass RLS and read the
Storage bucket with service-level permissions.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path

import pypdf
from supabase import Client, create_client


PRODUCER_NAME = "tier_probe"
PRODUCER_VERSION = "0.1.0"

# Heuristic: below this total character count across the first few pages,
# treat the PDF as image-only (scanned). Set deliberately low so a mostly
# empty flat template still counts as pdf_flat — we only want to bucket
# the genuinely image-only ones into pdf_scanned so OCR can route them
# separately.
TEXT_SCANNED_THRESHOLD = 100

# Only sniff the first N pages for text. Full-document text extraction
# is expensive and we're making a routing decision, not extracting.
PAGES_TO_SAMPLE = 3


def load_env(env_path: Path) -> dict[str, str]:
    """Parse .env without shell interpretation.

    The Supabase DB password and DATABASE_URL can contain a leading '$'
    that bash's `set -a && source .env` would collapse to empty. Reading
    the file ourselves avoids the gotcha and means this script runs
    regardless of whether the caller sourced .env first.
    """
    env: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        # Strip matched surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def detect_format(storage_path: str, data: bytes) -> tuple[str, dict]:
    """Classify a downloaded source file. Returns (format, diagnostics)."""
    ext = ""
    if "." in storage_path:
        ext = storage_path.rsplit(".", 1)[-1].lower()

    byte_format = sniff_format_from_bytes(data)
    if byte_format == "html":
        return "other", {
            "reason": f"html bytes archived at .{ext or 'unknown'} path",
            "bytes": len(data),
        }
    if byte_format in {"xlsx", "docx"}:
        return byte_format, {"bytes": len(data)}
    if byte_format == "other":
        return "other", {
            "reason": f"unknown bytes for extension '{ext or 'none'}'",
            "bytes": len(data),
        }

    try:
        reader = pypdf.PdfReader(BytesIO(data))
    except Exception as e:
        return "other", {"reason": f"pypdf parse failed: {e}", "bytes": len(data)}

    try:
        page_count = len(reader.pages)
    except Exception as e:
        return "other", {"reason": f"page count failed: {e}", "bytes": len(data)}

    # AcroForm check: a populated fillable CDS is the Tier 2 happy path.
    # pypdf.get_fields() returns None when the PDF has no form; otherwise
    # a dict keyed by field name. Some flattened PDFs retain the form
    # structure but have all-empty values — still classify those as
    # fillable because the extractor downgrade path is cheap.
    fields = None
    try:
        fields = reader.get_fields()
    except Exception:
        fields = None

    if fields:
        populated = 0
        for field in fields.values():
            value = getattr(field, "value", None) if not isinstance(field, dict) else field.get("/V")
            if value not in (None, ""):
                populated += 1
        return "pdf_fillable", {
            "page_count": page_count,
            "field_count": len(fields),
            "populated_field_count": populated,
            "bytes": len(data),
        }

    # No AcroForm. Sniff text on the first few pages to decide flat vs scanned.
    total_text = 0
    sampled_pages = min(PAGES_TO_SAMPLE, page_count)
    for i in range(sampled_pages):
        try:
            text = reader.pages[i].extract_text() or ""
            total_text += len(text)
        except Exception:
            pass

    diag = {
        "page_count": page_count,
        "sampled_text_chars": total_text,
        "bytes": len(data),
    }
    if total_text >= TEXT_SCANNED_THRESHOLD:
        return "pdf_flat", diag
    return "pdf_scanned", diag


def sniff_format_from_bytes(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            names = zipfile.ZipFile(BytesIO(data)).namelist()
        except (zipfile.BadZipFile, ValueError, EOFError):
            return "other"
        has_word = any(n.startswith("word/") for n in names)
        has_xl = any(n.startswith("xl/") for n in names)
        if has_word and not has_xl:
            return "docx"
        if has_xl and not has_word:
            return "xlsx"
        return "other"
    head = data[:512].decode("utf-8", errors="ignore").lower().lstrip()
    if (
        head.startswith("<!doctype html")
        or head.startswith("<html")
        or head.startswith("<head")
        or (head.startswith("<?xml") and "<html" in head)
    ):
        return "html"
    return "other"


def fetch_latest_source_artifact(client: Client, document_id: str) -> dict | None:
    """Return the storage_path + sha256 of the most recent source artifact
    for a document, or None if the document has no source artifact.
    """
    result = (
        client.table("cds_artifacts")
        .select("storage_path, sha256")
        .eq("document_id", document_id)
        .eq("kind", "source")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def probe_documents(
    client: Client,
    docs: list[dict],
    dry_run: bool,
) -> tuple[Counter, list[dict]]:
    counts: Counter = Counter()
    details: list[dict] = []
    total = len(docs)

    for i, doc in enumerate(docs, 1):
        school = doc["school_id"]
        prefix = f"[{i:4d}/{total}] {school}"

        artifact = fetch_latest_source_artifact(client, doc["id"])
        if not artifact:
            print(f"{prefix}: no source artifact", flush=True)
            counts["no_artifact"] += 1
            continue

        storage_path = artifact["storage_path"]
        try:
            data = client.storage.from_("sources").download(storage_path)
        except Exception as e:
            print(f"{prefix}: storage download failed: {e}", flush=True)
            counts["download_error"] += 1
            continue

        fmt, diag = detect_format(storage_path, data)
        counts[fmt] += 1
        details.append({
            "school_id": school,
            "cds_year": doc.get("cds_year"),
            "format": fmt,
            "storage_path": storage_path,
            **diag,
        })
        print(f"{prefix}: {fmt} ({diag.get('bytes', 0)} bytes)", flush=True)

        if dry_run:
            continue

        try:
            (
                client.table("cds_documents")
                .update({"source_format": fmt})
                .eq("id", doc["id"])
                .execute()
            )
        except Exception as e:
            print(f"{prefix}: update failed: {e}", flush=True)

    return counts, details


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect CDS source format and backfill cds_documents.source_format",
    )
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N rows")
    parser.add_argument("--school", default=None, help="Probe only this school_id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify but do not write source_format",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-probe rows that already have source_format set (default: skip them)",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="Write per-row details to this JSON file",
    )
    args = parser.parse_args()

    env = load_env(Path(args.env))
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY in env file",
            file=sys.stderr,
        )
        return 2

    client: Client = create_client(url, key)

    # Fetch documents to probe
    query = client.table("cds_documents").select("id, school_id, cds_year, source_format")
    if not args.refresh:
        query = query.is_("source_format", "null")
    if args.school:
        query = query.eq("school_id", args.school)
    query = query.order("school_id")
    if args.limit:
        query = query.limit(args.limit)

    result = query.execute()
    docs = result.data or []

    if not docs:
        print(
            "No documents to probe. Use --refresh to re-probe rows that already have source_format set.",
        )
        return 0

    print(f"Probing {len(docs)} document(s){' (dry run)' if args.dry_run else ''}...", flush=True)
    counts, details = probe_documents(client, docs, args.dry_run)

    print()
    print("=== Tier distribution ===")
    for fmt, n in counts.most_common():
        print(f"  {fmt:18s} {n:5d}")
    total = sum(counts.values())
    print(f"  {'total':18s} {total:5d}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(details, indent=2))
        print(f"\nPer-row details → {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
