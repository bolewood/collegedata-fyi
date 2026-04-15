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
import re
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


# Year detection on archived PDFs. The canonical CDS template prints
# "Common Data Set 2024-2025" (or a compressed variant) on page 1. This
# gives us a content-derived year that's more trustworthy than whatever
# the resolver parsed out of the URL, and it unblocks the upcoming
# "keep every CDS-ish anchor from a landing page" resolver change where
# many candidate URLs won't carry a year at all. The y2=y1+1 span
# validation rejects compressed formats like "20242025" and spurious
# Drupal upload dates like "2020-04" that might otherwise masquerade
# as academic spans. This is a narrower detector than
# supabase/functions/_shared/year.ts — that module recovers
# no-separator variants like `cds9900`, which this one intentionally
# does not, since we only scan extracted-text output where separators
# are preserved and corruption risk outweighs recall.
#
# Deliberately strict: only spans that appear adjacent to a "Common
# Data Set" or "CDS" prefix count. A bare year-range fallback was
# tested against American University's flattened 47-page PDF and
# found `2006-07` on page 20 (a reference year from section J) as the
# only valid span anywhere in the document — detecting that would
# have silently mis-dated the school by 18 years. Missing a few docs
# is strictly preferable to corrupting a few.
#
# The dash character class covers ASCII hyphen, en dash (U+2013), em
# dash (U+2014), figure dash (U+2012), Unicode hyphen (U+2010),
# non-breaking hyphen (U+2011), and minus sign (U+2212). pypdf can
# emit any of these depending on how a PDF's font maps the hyphen
# glyph; non-breaking hyphen in particular shows up in CDS templates
# that don't want the year to line-break.
_DASH_CLASS = r"[-\u2010\u2011\u2012\u2013\u2014\u2212/]"
_YEAR_PATTERNS = [
    re.compile(
        r"Common\s+Data\s+Set\s*[,:]?\s*(20\d{2})\s*" + _DASH_CLASS + r"\s*(20\d{2}|\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bCDS\s*[,:]?\s*(20\d{2})\s*" + _DASH_CLASS + r"\s*(20\d{2}|\d{2})\b",
        re.IGNORECASE,
    ),
]


def _normalize_year_span(y1_raw: str, y2_raw: str) -> Optional[str]:
    y1 = int(y1_raw)
    y2 = int(y2_raw) % 100 if len(y2_raw) == 4 else int(y2_raw)
    if (y1 + 1) % 100 != y2:
        return None
    # y1 is structurally constrained to 20xx by the regex; the upper
    # bound is the real check. Cap at 2035 — nine years of headroom
    # past the current corpus, far enough out that a match beyond it
    # is almost certainly a parser artifact.
    if y1 > 2035:
        return None
    return f"{y1}-{y2:02d}"


def detect_year_from_pdf_bytes(data: bytes, max_pages: int = 10) -> Optional[str]:
    """Extract a canonical CDS academic-year string (e.g. '2024-25') from
    the first ~10 pages of a PDF. Returns None if no valid prefix-adjacent
    span is found OR if multiple distinct valid spans are found (the
    ambiguous case is conservatively treated as undetected — "strict
    may miss but must never corrupt").

    Collects every valid span across all scanned pages under both
    patterns rather than returning on the first hit. A page-1 footer
    referencing a prior year (e.g. "Common Data Set 2015-16 data for
    comparison") would otherwise beat a real title on page 8 under a
    first-match-wins loop, since y2=y1+1 validates that 2015-16 is a
    structurally sound span. Collecting first and requiring
    uniqueness closes that latent reference-trap without reducing
    recall on the observed corpus: every mismatched school in the
    Stage A harness had exactly one unique valid span across pages
    1-10 (TCNJ had 10 hits all of "2024-25", Dominican 10 hits all
    "2024-25", etc.), so the mismatches this function produces are
    unchanged while the safety invariant gets tighter.

    Broad except blocks log to stderr so that pypdf regressions or
    corrupt-PDF failures can be distinguished from genuine
    no-prefix-present misses in the harness output.

    STAGE B TODO (timeout/hang protection): pypdf parsing and
    `extract_text()` are pure Python and can loop indefinitely on
    malformed PDFs. The harness processes documents serially, so one
    pathological file wedges the whole run. Stage A is manual and
    operator-supervised — Ctrl-C is the current answer — but when
    extraction becomes write-authoritative under a cron, this
    function needs a real watchdog. Candidates: multiprocessing.Pool
    with apply_async + get(timeout=30) to isolate parsing per PDF,
    or signal.alarm on Unix. Out of scope for Stage A; tracked as a
    Stage B blocker.
    """
    # STAGE B TODO (leading-junk PDF gate): rare PDFs ship with a BOM
    # or preamble before the `%PDF-` header; pypdf tolerates them but
    # this magic-byte check rejects them outright and they end up in
    # the `non_pdf` bucket. Estimated <1% of the corpus. Backlogged
    # for Stage B where the format-sniff story can be reworked
    # alongside xlsx/docx detection.
    if len(data) < 4 or data[:4] != b"%PDF":
        return None
    try:
        reader = pypdf.PdfReader(BytesIO(data))
    except Exception as e:
        print(
            f"    pdf_error: PdfReader init failed: {type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return None
    try:
        page_count = min(max_pages, len(reader.pages))
    except Exception as e:
        print(
            f"    pdf_error: reader.pages enumeration failed: {type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return None
    spans: set[str] = set()
    for page_idx in range(page_count):
        try:
            text = reader.pages[page_idx].extract_text() or ""
        except Exception as e:
            print(
                f"    pdf_error: page {page_idx} extract_text failed: {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
            continue
        for pattern in _YEAR_PATTERNS:
            for m in pattern.finditer(text):
                span = _normalize_year_span(m.group(1), m.group(2))
                if span:
                    spans.add(span)
    if len(spans) == 1:
        return next(iter(spans))
    # Zero hits → undetected. Multiple distinct hits → ambiguous →
    # treat as undetected per the strict invariant. Both cases return
    # None; they're bucketed identically in the harness summary.
    return None


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

    # Side-channel year detection. Observation-only until we trust the
    # signal across the whole corpus — no DB writes here, just a print.
    # The real load-bearing use is the upcoming resolver change that will
    # emit multiple CDS candidates per landing page without year info in
    # the URL; this proves detection is reliable first.
    #
    # Stage B TODO: the `stored_year and` guard below must come out when
    # extraction becomes write-authoritative. At that point nullable /
    # placeholder `cds_year` values need to surface as mismatches so
    # extraction can populate them, not be silently skipped.
    detected_year = detect_year_from_pdf_bytes(pdf_bytes)
    stored_year = doc.get("cds_year")
    if detected_year and stored_year and detected_year != stored_year:
        print(
            f"    year_mismatch: school={school_id} document={document_id} "
            f"stored={stored_year} detected={detected_year}",
            flush=True,
        )

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


def run_detect_year_only(
    client: Client,
    school_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> int:
    """Year-detection harness. Queries every cds_documents row that has
    an archived source (any extraction_status) and runs
    detect_year_from_pdf_bytes on each. Writes nothing. Reports
    confirmed / mismatch / undetected counts plus a sample of mismatches
    and undetecteds for manual inspection. This is the gate we clear
    before making year detection load-bearing."""
    # Explicit row cap to close PostgREST's silent-truncation risk.
    # The default cap (often 1000 at project settings) would otherwise
    # silently drop rows once Stage B's multi-candidate archiver
    # pushes the corpus past the default. 5000 is sized for the
    # projected post-Stage-B corpus (~1900 historical + 535 current
    # + headroom) and the code warns if the result actually fills
    # the cap, which is the signal to paginate properly.
    # STAGE B TODO: replace with explicit .range() pagination when
    # the corpus can predictably exceed the cap.
    HARNESS_ROW_CAP = 5000
    query = (
        client.table("cds_documents")
        .select("id, school_id, cds_year, source_format, extraction_status")
        .order("school_id")
        .limit(HARNESS_ROW_CAP)
    )
    if school_filter:
        query = query.eq("school_id", school_filter)
    if limit and limit < HARNESS_ROW_CAP:
        query = query.limit(limit)
    docs = query.execute().data or []
    if not docs:
        print("No cds_documents rows matched the filter.")
        return 0
    if not school_filter and not limit and len(docs) >= HARNESS_ROW_CAP:
        print(
            f"WARNING: harness hit the {HARNESS_ROW_CAP}-row cap — results are "
            f"truncated. Add .range() pagination before trusting these numbers.",
            file=sys.stderr,
            flush=True,
        )

    print(f"Running year detection against {len(docs)} document(s)...", flush=True)

    counts: Counter = Counter()
    mismatches: list[tuple[str, str, str]] = []
    undetecteds: list[tuple[str, str]] = []
    non_pdf: list[tuple[str, str]] = []
    download_errors: list[tuple[str, str]] = []

    for i, doc in enumerate(docs, 1):
        school_id = doc["school_id"]
        stored_year = doc.get("cds_year")
        storage_path = fetch_latest_source_path(client, doc["id"])
        if not storage_path:
            counts["no_source"] += 1
            print(f"[{i:4d}/{len(docs)}] {school_id}: no_source", flush=True)
            continue
        try:
            pdf_bytes = download_source(client, storage_path)
        except Exception as e:
            counts["download_error"] += 1
            download_errors.append((school_id, str(e)[:80]))
            print(f"[{i:4d}/{len(docs)}] {school_id}: download_error", flush=True)
            continue
        if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
            counts["non_pdf"] += 1
            non_pdf.append((school_id, doc.get("source_format") or "?"))
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: non_pdf ({doc.get('source_format')})",
                flush=True,
            )
            continue
        detected = detect_year_from_pdf_bytes(pdf_bytes)
        if detected is None:
            counts["undetected"] += 1
            undetecteds.append((school_id, stored_year or ""))
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: undetected (stored={stored_year})",
                flush=True,
            )
        elif detected == stored_year:
            counts["confirmed"] += 1
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: confirmed {detected}", flush=True
            )
        else:
            counts["mismatch"] += 1
            mismatches.append((school_id, stored_year or "", detected))
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: MISMATCH stored={stored_year} detected={detected}",
                flush=True,
            )

    print()
    print("=== year detection summary ===")
    for bucket in ("confirmed", "mismatch", "undetected", "non_pdf", "download_error", "no_source"):
        if counts[bucket]:
            print(f"  {bucket:18s} {counts[bucket]:5d}")
    print(f"  {'total':18s} {sum(counts.values()):5d}")

    if mismatches:
        print()
        print(f"=== first {min(20, len(mismatches))} mismatches ===")
        for sid, stored, detected in mismatches[:20]:
            print(f"  {sid:45s} stored={stored:10s} detected={detected}")
    if undetecteds:
        print()
        print(f"=== first {min(20, len(undetecteds))} undetecteds ===")
        for sid, stored in undetecteds[:20]:
            print(f"  {sid:45s} stored={stored}")
    if non_pdf:
        print()
        print(f"=== first {min(10, len(non_pdf))} non-PDF formats ===")
        for sid, fmt in non_pdf[:10]:
            print(f"  {sid:45s} format={fmt}")

    return 0


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
    parser.add_argument(
        "--detect-year-only",
        action="store_true",
        help=(
            "Run only the PDF year-detection harness across every archived "
            "document regardless of extraction_status. Writes nothing; "
            "prints a confirmed/mismatch/undetected summary. Used to "
            "validate detection reliability before the resolver change "
            "that emits multiple CDS candidates per landing page."
        ),
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

    if args.detect_year_only:
        return run_detect_year_only(
            client,
            school_filter=args.school,
            limit=args.limit,
        )

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
