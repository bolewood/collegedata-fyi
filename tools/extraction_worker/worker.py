"""
M2 extraction worker (MVP skeleton).

Polls cds_documents WHERE extraction_status = 'extraction_pending',
downloads the archived source from Storage, routes by source_format,
and writes a canonical artifact back to cds_artifacts. The primary
goal of this tool is to close the loop from discovery → archive →
extract so end-to-end data flows for at least the fillable-PDF tier
(Tier 2), with cleanly stubbed failure reasons for tiers that are
not yet implemented.

Routing (driven by cds_documents.source_format):

    pdf_fillable    → Tier 2: tier2_extractor.extract (deterministic
                      AcroForm read via pypdf.get_fields)
    pdf_flat        → not yet implemented (Tier 4; Docling or Reducto
                      bake-off pending)
    pdf_scanned     → not yet implemented (Tier 5; OCR pipeline)
    xlsx            → not yet implemented (Tier 1; openpyxl read of
                      the CDS filled template)
    docx            → not yet implemented (Tier 3; python-docx read of
                      the Word template)
    (null)          → sniff via pypdf at run time and backfill

On success (Tier 2 path):
    1. Insert cds_artifacts(kind='canonical', producer=tier2_acroform,
       producer_version=..., storage_path=placeholder, notes=<canonical>)
       where `notes` is the full canonical JSON dict emitted by the
       tier2 extractor. For MVP this is stored inline in jsonb rather
       than uploaded to Storage because (a) the extracted JSON is
       small (HMC's is ~5KB) and (b) the sources bucket's MIME
       allowlist doesn't include application/json, so an upload path
       would need its own bucket or a MIME-filter migration. Real
       Storage upload is a follow-up for when extracts grow.
    2. Update cds_documents.extraction_status = 'extracted' and
       backfill source_format if it was null.

On failure (any tier stub or Tier 2 runtime error):
    Update cds_documents.extraction_status = 'failed' and leave a
    notes.reason in the stub case. The row sits at 'failed' until
    the operator force-reprocesses or the tier gets implemented.

Usage:
    python tools/extraction_worker/worker.py                 # drain everything
    python tools/extraction_worker/worker.py --limit 10      # test subset
    python tools/extraction_worker/worker.py --school yale   # one school
    python tools/extraction_worker/worker.py --dry-run       # no writes
    python tools/extraction_worker/worker.py --schema schemas/cds_schema_2024_25.json

Setup (one-time):
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r tools/extraction_worker/requirements.txt

Env: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY loaded from .env (read
literally, no shell sourcing — see load_env docstring).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Optional

import pypdf
from supabase import Client, create_client


# Import the tier2 extractor's extract() + schema loader directly. Both
# are pure functions: extract(pdf_path: Path, schema: dict) -> dict,
# load_schema(path: Path) -> dict. Adds the project tools root to
# sys.path so the sibling module is importable regardless of how the
# worker is invoked.
_TOOLS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLS_ROOT))
from tier2_extractor.extract import extract as tier2_extract  # noqa: E402
from tier2_extractor.extract import load_schema  # noqa: E402


def load_env(env_path: Path) -> dict[str, str]:
    """Read .env literally — shell sourcing collapses values with '$q'
    prefixes and similar shell-special characters. See the tier_probe
    comment for the gotcha."""
    env: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def fetch_latest_source_path(client: Client, document_id: str) -> Optional[str]:
    result = (
        client.table("cds_artifacts")
        .select("storage_path")
        .eq("document_id", document_id)
        .eq("kind", "source")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["storage_path"] if rows else None


def download_source(client: Client, storage_path: str) -> bytes:
    return client.storage.from_("sources").download(storage_path)


def sniff_format_from_bytes(data: bytes) -> str:
    """Best-effort format detection when cds_documents.source_format is null.
    Returns one of the extraction_status enum values the migration allows
    (pdf_fillable / pdf_flat / pdf_scanned / xlsx / docx / other)."""
    if len(data) >= 4 and data[:4] == b"%PDF":
        try:
            reader = pypdf.PdfReader(BytesIO(data))
            fields = reader.get_fields()
            if fields:
                return "pdf_fillable"
            # no fields → text-sniff first few pages
            total = 0
            for i in range(min(3, len(reader.pages))):
                try:
                    total += len(reader.pages[i].extract_text() or "")
                except Exception:
                    pass
            return "pdf_flat" if total >= 100 else "pdf_scanned"
        except Exception:
            return "other"
    if len(data) >= 4 and data[:4] == b"PK\x03\x04":
        return "xlsx"  # or docx; tier probe distinguishes via filename
    return "other"


def artifact_already_extracted(
    client: Client, document_id: str, producer: str, producer_version: str
) -> bool:
    """Idempotency: if an artifact with the same (document, kind, producer,
    version) tuple already exists, skip writing a duplicate."""
    result = (
        client.table("cds_artifacts")
        .select("id")
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .eq("producer", producer)
        .eq("producer_version", producer_version)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def run_tier2(pdf_bytes: bytes, schema: dict) -> dict:
    """Run tier2_extractor.extract against in-memory bytes. The extractor
    expects a Path, so we materialize to a NamedTemporaryFile briefly.
    Returns the canonical dict."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        return tier2_extract(Path(tmp.name), schema)


def mark_extraction_status(
    client: Client,
    document_id: str,
    status: str,
    source_format: Optional[str] = None,
) -> None:
    update: dict = {"extraction_status": status}
    if source_format is not None:
        update["source_format"] = source_format
    client.table("cds_documents").update(update).eq("id", document_id).execute()


def insert_canonical_artifact(
    client: Client,
    document_id: str,
    canonical: dict,
) -> None:
    """Write a cds_artifacts(kind='canonical') row with the extracted JSON
    inline in notes (jsonb). storage_path gets a placeholder path that
    documents where the bytes WOULD live if we uploaded them; this keeps
    downstream consumers that expect the column populated working without
    an actual Storage object. See the module docstring for the MVP
    tradeoff."""
    producer = canonical["producer"]
    producer_version = canonical["producer_version"]
    placeholder_path = (
        f"canonical-inline/{document_id}/{producer}-{producer_version}.json"
    )
    client.table("cds_artifacts").insert({
        "document_id": document_id,
        "kind": "canonical",
        "producer": producer,
        "producer_version": producer_version,
        "schema_version": canonical.get("schema_version"),
        "storage_path": placeholder_path,
        "notes": canonical,
    }).execute()


def extract_one(
    client: Client,
    doc: dict,
    schema: dict,
    dry_run: bool,
) -> str:
    """Process a single cds_documents row. Returns a short action string
    for logging. Does NOT raise — every failure is caught and recorded
    as extraction_status='failed' with a category for the summary."""
    document_id = doc["id"]
    school_id = doc["school_id"]

    storage_path = fetch_latest_source_path(client, document_id)
    if not storage_path:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return "no_source_artifact"

    try:
        pdf_bytes = download_source(client, storage_path)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return f"download_error: {e}"

    source_format = doc.get("source_format") or sniff_format_from_bytes(pdf_bytes)

    if source_format != "pdf_fillable":
        # All non-Tier-2 paths are stubs for now. Mark failed so the row
        # leaves the extraction_pending queue and the operator can see
        # which tiers still need work via a simple GROUP BY source_format.
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return f"stub_{source_format}"

    # Tier 2 path.
    try:
        canonical = run_tier2(pdf_bytes, schema)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return f"tier2_error: {e}"

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]

    if not dry_run:
        if artifact_already_extracted(client, document_id, producer, producer_version):
            # Idempotent re-run: the row was already extracted with this
            # producer version at some earlier point. Mark extracted and
            # move on without writing a duplicate.
            mark_extraction_status(client, document_id, "extracted", source_format)
            return "already_extracted"

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return f"artifact_insert_error: {e}"

        mark_extraction_status(client, document_id, "extracted", source_format)

    # Log a few headline stats from the canonical output for visibility.
    stats = canonical.get("stats") or {}
    _populated = stats.get("schema_fields_populated", 0)
    _total = stats.get("schema_fields_total", 0)
    _unmapped = stats.get("unmapped_acroform_fields", 0)
    return f"extracted ({_populated}/{_total} fields, {_unmapped} unmapped)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll extraction_pending and route docs to tier extractors",
    )
    parser.add_argument("--env", default=".env")
    parser.add_argument(
        "--schema",
        default="schemas/cds_schema_2025_26.json",
        help="CDS schema JSON used by tier2_extractor. MVP uses 2025-26 "
        "for all years; real fix is multi-schema loading once more "
        "years exist.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--school", default=None, help="Only process this school_id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Also process rows with extraction_status='failed' (for retry runs)",
    )
    args = parser.parse_args()

    env = load_env(Path(args.env))
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in env file",
            file=sys.stderr,
        )
        return 2

    client: Client = create_client(url, key)
    schema = load_schema(Path(args.schema))

    query = client.table("cds_documents").select(
        "id, school_id, cds_year, source_format, extraction_status",
    )
    if args.include_failed:
        query = query.in_("extraction_status", ["extraction_pending", "failed"])
    else:
        query = query.eq("extraction_status", "extraction_pending")
    if args.school:
        query = query.eq("school_id", args.school)
    query = query.order("school_id")
    if args.limit:
        query = query.limit(args.limit)

    docs = query.execute().data or []
    if not docs:
        print(
            "No rows to process. Try --include-failed to re-process earlier failures.",
        )
        return 0

    print(
        f"Processing {len(docs)} document(s){' (dry run)' if args.dry_run else ''}...",
        flush=True,
    )

    counts: Counter = Counter()
    for i, doc in enumerate(docs, 1):
        action = extract_one(client, doc, schema, args.dry_run)
        bucket = action.split(":")[0].split(" ")[0]
        counts[bucket] += 1
        print(f"[{i:4d}/{len(docs)}] {doc['school_id']}: {action}", flush=True)

    print()
    print("=== extraction results ===")
    for bucket, n in counts.most_common():
        print(f"  {bucket:30s} {n:5d}")
    print(f"  {'total':30s} {sum(counts.values()):5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
