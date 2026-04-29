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

    xlsx            → Tier 1: tier1_extractor.extract (deterministic
                      cell-position read via openpyxl, mapped from the
                      CDS template's hidden lookup columns)
    pdf_fillable    → Tier 2: tier2_extractor.extract (deterministic
                      AcroForm read via pypdf.get_fields)
    pdf_flat        → Tier 4: tier4_extractor.extract (Docling baseline
                      config — markdown output, not yet schema-mapped)
    pdf_scanned     → Tier 4 with lazy OCR: same Docling pipeline. do_ocr=True
                      triggers EasyOCR on pages with no extractable text,
                      which is exactly the pdf_scanned case.
    docx            → not yet implemented. PRD 007 originally proposed a
                      direct OOXML SDT reader (Tier 3 Lane A); on
                      benchmarking against the only SDT-preserving
                      publisher (Kent State, 1 file shared by 8 campus
                      rows), Tier 4 on a Word-rendered PDF produced 450
                      mapped fields vs Lane A's 492, a 9% gap that did
                      not justify the new tier and dependency. Deferred
                      pending a second SDT-preserving DOCX publisher.
                      Inner-ZIP sniff still ships so DOCX vs XLSX is now
                      content-based — JMU and Stanford reroute correctly
                      and a future docx→pdf headless-conversion path can
                      slot in without revisiting routing.
    html            → Tier 6 (PRD 008): html_to_markdown() normalizes the
                      bytes to the markdown shape that tier4_cleaner
                      already consumes. No bespoke parser — reuses the
                      cleaner's table parser, row-label normalizer, and
                      SchemaIndex filter. producer='tier6_html'.
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
    python tools/extraction_worker/worker.py --skip-projection-refresh
    python tools/extraction_worker/worker.py --seed-projection-metadata
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
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import pypdf
from supabase import Client, create_client


# Import the tier2 extractor's extract() + schema loader directly. Both
# are pure functions: extract(pdf_path: Path, schema: dict) -> dict,
# load_schema(path: Path) -> dict. Adds the project tools root to
# sys.path so the sibling module is importable regardless of how the
# worker is invoked.
_TOOLS_ROOT = Path(__file__).resolve().parent.parent
_WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS_ROOT))
sys.path.insert(0, str(_WORKER_DIR))
from tier1_extractor.extract import build_cell_map, extract_from_bytes as tier1_extract  # noqa: E402
from tier2_extractor.extract import extract as tier2_extract  # noqa: E402
from tier2_extractor.extract import load_schema  # noqa: E402
from html_to_markdown import html_to_markdown  # noqa: E402 (PRD 008 Tier 6)


@dataclass(frozen=True)
class ExtractionOutcome:
    action: str
    refresh_projection: bool = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parsed_field_count(action: str) -> int | None:
    match = re.search(r"\((\d+)(?:/\d+)? fields\b", action)
    return int(match.group(1)) if match else None


def is_failure_action(action: str) -> bool:
    if action == "already_extracted":
        return False
    if action == "no_source_artifact" or action.startswith("stub_"):
        return True
    if "_error" in action or action.endswith("_no_tables"):
        return True
    return False


def mean_or_none(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def write_run_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def extraction_success(action: str) -> ExtractionOutcome:
    return ExtractionOutcome(action, refresh_projection=True)


def extraction_no_project(action: str) -> ExtractionOutcome:
    return ExtractionOutcome(action, refresh_projection=False)


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


_DOCX_TAG_STRIPPER = re.compile(r"<[^>]+>")


def _docx_collect_year_spans(xml: str) -> set[str]:
    """Strip OOXML tags and run the canonical year regex against the
    resulting plain text. Word splits text into many ``<w:t>`` runs, so
    tag stripping flattens runs to whitespace before regex matching.

    Headers commonly carry the ``Common Data Set 2024-2025`` title (and
    sometimes only the headers carry it — JMU's body has no title at
    all). Caller is expected to feed each XML part separately or as a
    concatenation."""
    text = _DOCX_TAG_STRIPPER.sub(" ", xml)
    spans: set[str] = set()
    for pattern in _YEAR_PATTERNS:
        for m in pattern.finditer(text):
            span = _normalize_year_span(m.group(1), m.group(2))
            if span:
                spans.add(span)
    return spans


def detect_year_from_docx_bytes(data: bytes) -> Optional[str]:
    """Extract the canonical CDS academic-year string from a DOCX. Reads
    ``word/document.xml`` plus every ``word/header*.xml`` part, strips
    OOXML tags, and runs the same year patterns used for PDFs.

    Strict invariant matches PDF detection: zero hits OR multiple
    distinct valid spans → None. Conservative by design — corrupting a
    school's year is worse than missing detection."""
    if len(data) < 4 or data[:4] != b"PK\x03\x04":
        return None
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except (zipfile.BadZipFile, ValueError, EOFError) as e:
        print(
            f"    docx_error: ZipFile init failed: {type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return None

    spans: set[str] = set()
    targets = ["word/document.xml"]
    targets.extend(
        sorted(
            n for n in zf.namelist()
            if n.startswith("word/header") and n.endswith(".xml")
        )
    )
    for name in targets:
        try:
            xml = zf.read(name).decode("utf-8", "replace")
        except KeyError:
            continue
        except Exception as e:
            print(
                f"    docx_error: read {name} failed: {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
            continue
        spans |= _docx_collect_year_spans(xml)

    if len(spans) == 1:
        return next(iter(spans))
    return None


def detect_year_from_bytes(data: bytes) -> Optional[str]:
    """Format-aware year detection. Dispatches by magic bytes so callers
    can run year detection before knowing the source_format. Returns
    None for unsupported formats (HTML, OCR-only PDF without text,
    etc.) — the caller treats None as "undetected"."""
    if len(data) >= 4 and data[:4] == b"%PDF":
        return detect_year_from_pdf_bytes(data)
    if len(data) >= 4 and data[:4] == b"PK\x03\x04":
        # Only DOCX has a meaningful CDS title; XLSX year detection is
        # not implemented and the original path was PDF-only anyway.
        if sniff_zip_inner_format(data) == "docx":
            return detect_year_from_docx_bytes(data)
    return None


def sniff_zip_inner_format(data: bytes) -> str:
    """Distinguish DOCX from XLSX (and other ZIPs) by inspecting inner
    entries. Both formats share the PK\\x03\\x04 magic, so magic alone is
    insufficient. Per PRD 007: ``word/document.xml`` → docx,
    ``xl/workbook.xml`` → xlsx, otherwise → other.

    Returns "docx", "xlsx", or "other". Returns "other" on malformed ZIPs.
    """
    try:
        zf = zipfile.ZipFile(BytesIO(data))
        names = zf.namelist()
    except (zipfile.BadZipFile, ValueError, EOFError):
        return "other"
    has_word = any(n.startswith("word/") for n in names)
    has_xl = any(n.startswith("xl/") for n in names)
    if has_word and not has_xl:
        return "docx"
    if has_xl and not has_word:
        return "xlsx"
    # Both or neither: ambiguous container, treat as other rather than
    # guessing. Real CDS files have not been observed with both prefixes.
    return "other"


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
        # Inspect inner ZIP entries to distinguish DOCX from XLSX. PRD 007
        # M1: prior logic returned "xlsx" for any ZIP and relied on the
        # tier probe's filename heuristic, which silently misroutes any
        # extensionless URL (e.g. Kent State's ``TU CDS_2025-2026-Final``).
        return sniff_zip_inner_format(data)
    # HTML sniff (PRD 008). Runs after binary magic so a PDF/ZIP with a
    # stray "<html" byte sequence doesn't mis-route. Matches the
    # storage.ts sniffBytesForExt logic on the discovery side.
    try:
        head = data[:512].decode("utf-8", errors="ignore").lower().lstrip()
    except Exception:
        head = ""
    if (
        head.startswith("<!doctype html")
        or head.startswith("<html")
        or head.startswith("<head")
        or (head.startswith("<?xml") and "<html" in head)
    ):
        return "html"
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


def _run_tier1(
    client: Client,
    document_id: str,
    school_id: str,
    xlsx_bytes: bytes,
    source_format: str,
    schema: dict,
    cell_map: dict,
    dry_run: bool,
) -> ExtractionOutcome:
    """Tier 1 path: read filled CDS XLSX via template cell-position map."""
    try:
        canonical = tier1_extract(xlsx_bytes, schema, cell_map)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier1_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]

    if not dry_run:
        if artifact_already_extracted(client, document_id, producer, producer_version):
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)

    fields = canonical.get("stats", {}).get("schema_fields_populated", 0)
    return extraction_success(f"tier1_extracted ({fields} fields)")


def _run_tier6(
    client: Client,
    document_id: str,
    school_id: str,
    html_bytes: bytes,
    source_format: str,
    dry_run: bool,
) -> ExtractionOutcome:
    """Tier 6 path (PRD 008): HTML → markdown → tier4_cleaner.

    The normalizer (html_to_markdown) emits the same pipe-delimited markdown
    shape tier4_cleaner already handles, so this is a thin orchestration
    layer: normalize, call the cleaner, wrap the canonical artifact shape.

    Failure modes: if the normalized markdown yields fewer than
    MIN_HTML_FIELDS populated fields, mark the row failed with reason
    html_no_tables — this is the silent-success trap (login-wall stub,
    empty redirect page, etc.). Genuine low-coverage HTML is still flagged
    so an operator can investigate.
    """
    MIN_HTML_FIELDS = 5
    from tier4_cleaner import clean as tier4_clean

    try:
        markdown = html_to_markdown(html_bytes)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier6_html_error: {e}")

    try:
        values = tier4_clean(markdown)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier6_clean_error: {e}")

    if len(values) < MIN_HTML_FIELDS:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"html_no_tables ({len(values)} fields)")

    canonical: dict = {
        "producer": "tier6_html",
        "producer_version": "0.1.0",
        "source_html": f"{document_id}.html",
        "extracted_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {
            "markdown_length": len(markdown),
            "schema_fields_populated": len(values),
        },
        "markdown": markdown,
        "values": values,
    }

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]

    if not dry_run:
        if artifact_already_extracted(client, document_id, producer, producer_version):
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)

    return extraction_success(f"tier6_extracted ({len(values)} fields, {len(markdown)} md chars)")


def _run_tier4(
    client: Client,
    document_id: str,
    school_id: str,
    pdf_bytes: bytes,
    source_format: str,
    dry_run: bool,
) -> ExtractionOutcome:
    """Tier 4 path: Docling baseline → markdown artifact.

    For pdf_scanned, forces full-page EasyOCR since Docling's auto OCR
    heuristic doesn't reliably trigger on scanned documents.
    """
    from tier4_extractor import extract_from_bytes as tier4_extract

    force_ocr = source_format == "pdf_scanned"
    try:
        canonical = tier4_extract(pdf_bytes, force_ocr=force_ocr)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier4_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]

    if not dry_run:
        if artifact_already_extracted(client, document_id, producer, producer_version):
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)

    stats = canonical.get("stats", {})
    md_len = stats.get("markdown_length", 0)
    pages = stats.get("page_count", 0)
    fields = stats.get("schema_fields_populated", 0)
    return extraction_success(f"tier4_extracted ({fields} fields, {md_len} chars, {pages} pages)")


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


def write_detected_year(
    client: Client,
    document_id: str,
    detected_year: str,
) -> None:
    """Persist a content-derived year to cds_documents.detected_year.

    Per ADR 0007 Stage B, extraction is the authoritative source for a
    document's academic year. cds_year stays as the archive-time guess;
    detected_year supersedes it. cds_manifest's canonical_year
    expression returns detected_year when set, so consumers see the
    corrected value without needing to chase the column change.

    This function never touches cds_year and never rekeys the source
    Storage object. Storage paths are {school_id}/{cds_year}/{sha}.ext
    and consumers look the path up via cds_manifest.source_storage_path
    rather than reconstructing it from year — so a mismatched path is
    aesthetic, not load-bearing. Rekey is tracked as a Stage C
    follow-up if the aesthetic bothers us later.
    """
    client.table("cds_documents").update(
        {"detected_year": detected_year},
    ).eq("id", document_id).execute()


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
    # Strip \u0000 null bytes that Postgres JSONB rejects (22P05).
    # Docling occasionally produces these from malformed PDF text streams.
    # Check both raw null bytes and JSON-escaped \u0000 sequences.
    import json
    notes_json = json.dumps(canonical)
    if "\x00" in notes_json or "\\u0000" in notes_json:
        notes_json = notes_json.replace("\x00", "").replace("\\u0000", "")
        canonical = json.loads(notes_json)

    client.table("cds_artifacts").insert({
        "document_id": document_id,
        "kind": "canonical",
        "producer": producer,
        "producer_version": producer_version,
        "schema_version": canonical.get("schema_version"),
        "storage_path": placeholder_path,
        "notes": canonical,
    }).execute()


def load_projection_definitions() -> dict:
    from browser_backend.project_browser_data import load_schema_definitions

    definitions = load_schema_definitions()
    if not definitions:
        raise RuntimeError("no browser projection schema definitions found")
    return definitions


def seed_projection_metadata(client: Client, definitions: dict) -> None:
    from browser_backend.project_browser_data import seed_metadata

    seed_metadata(client, definitions, True)


def refresh_browser_projection(
    client: Client,
    document_id: str,
    definitions: dict,
) -> tuple[int, bool]:
    from browser_backend.project_browser_data import project_document_id

    return project_document_id(client, document_id, definitions, apply=True)


def extract_one(
    client: Client,
    doc: dict,
    schema: dict,
    dry_run: bool,
    cell_map: dict | None = None,
) -> ExtractionOutcome:
    """Process a single cds_documents row. Returns a short action string
    for logging. Does NOT raise — every failure is caught and recorded
    as extraction_status='failed' with a category for the summary."""
    document_id = doc["id"]
    school_id = doc["school_id"]

    storage_path = fetch_latest_source_path(client, document_id)
    if not storage_path:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return extraction_no_project("no_source_artifact")

    try:
        pdf_bytes = download_source(client, storage_path)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return extraction_no_project(f"download_error: {e}")

    # Year detection. ADR 0007 Stage B: extraction is write-authoritative
    # for academic year. Writes detected_year when a valid span is found
    # on the archived PDF; leaves detected_year null when detection
    # couldn't resolve a unique span (the collect-all-spans rule
    # deliberately fails rather than corrupts). cds_year is never
    # touched — it stays as the resolver's archive-time guess and keeps
    # its role in the unique constraint. Consumer queries read
    # cds_manifest.canonical_year which COALESCEs detected_year over
    # cds_year.
    detected_year = detect_year_from_bytes(pdf_bytes)
    stored_year = doc.get("cds_year")
    stored_detected = doc.get("detected_year")
    if detected_year and detected_year != stored_detected:
        if not dry_run:
            try:
                write_detected_year(client, document_id, detected_year)
            except Exception as e:
                print(
                    f"    year_write_error: school={school_id} document={document_id} "
                    f"{type(e).__name__}: {e}",
                    file=sys.stderr,
                    flush=True,
                )
        if stored_year and stored_year != detected_year:
            print(
                f"    year_correction: school={school_id} document={document_id} "
                f"stored={stored_year} detected={detected_year}",
                flush=True,
            )
        else:
            print(
                f"    year_confirmed: school={school_id} document={document_id} "
                f"year={detected_year}",
                flush=True,
            )

    source_format = doc.get("source_format") or sniff_format_from_bytes(pdf_bytes)

    if source_format == "xlsx" and cell_map:
        return _run_tier1(
            client, document_id, school_id, pdf_bytes,
            source_format, schema, cell_map, dry_run,
        )

    # Tier 6 (PRD 008): HTML → markdown → tier4_cleaner. Must run before
    # the "pdf_*" and "pdf_fillable" branches since the variable name
    # `pdf_bytes` is reused for raw source bytes regardless of format.
    if source_format == "html":
        return _run_tier6(
            client, document_id, school_id, pdf_bytes,
            source_format, dry_run,
        )

    # pdf_scanned routes to Tier 4 too — Docling's do_ocr=True lazily runs
    # OCR (default engine: EasyOCR) on pages with no extractable text, which
    # is exactly the pdf_scanned case. If OCR quality is insufficient, a
    # follow-up can add a dedicated Tier 5 path with force_full_page_ocr=True.
    if source_format in ("pdf_flat", "pdf_scanned"):
        return _run_tier4(
            client, document_id, school_id, pdf_bytes,
            source_format, dry_run,
        )

    if source_format != "pdf_fillable":
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"stub_{source_format}")

    # Tier 2 path.
    try:
        canonical = run_tier2(pdf_bytes, schema)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier2_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]

    if not dry_run:
        if artifact_already_extracted(client, document_id, producer, producer_version):
            # Idempotent re-run: the row was already extracted with this
            # producer version at some earlier point. Mark extracted and
            # move on without writing a duplicate.
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)

    # Log a few headline stats from the canonical output for visibility.
    stats = canonical.get("stats") or {}
    _populated = stats.get("schema_fields_populated", 0)
    _total = stats.get("schema_fields_total", 0)
    _unmapped = stats.get("unmapped_acroform_fields", 0)
    return extraction_success(f"extracted ({_populated}/{_total} fields, {_unmapped} unmapped)")


def run_detect_year_only(
    client: Client,
    school_filter: Optional[str] = None,
    limit: Optional[int] = None,
    write: bool = False,
) -> int:
    """Year-detection harness. Queries every cds_documents row that has
    an archived source (any extraction_status) and runs
    detect_year_from_pdf_bytes on each. Reports confirmed / mismatch /
    undetected counts plus a sample of mismatches and undetecteds for
    manual inspection.

    With write=False (default), this is the Stage A read-only gate we
    clear before making detection load-bearing. With write=True, this
    is the Stage B backfill tool: every confirmed or corrected hit is
    persisted via write_detected_year. Use the --write CLI flag to
    opt in.
    """
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
        .select(
            "id, school_id, cds_year, detected_year, source_format, extraction_status",
        )
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
        stored_detected = doc.get("detected_year")
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
        is_pdf = len(pdf_bytes) >= 4 and pdf_bytes[:4] == b"%PDF"
        is_zip = len(pdf_bytes) >= 4 and pdf_bytes[:4] == b"PK\x03\x04"
        is_docx = is_zip and sniff_zip_inner_format(pdf_bytes) == "docx"
        if not (is_pdf or is_docx):
            counts["non_pdf"] += 1
            non_pdf.append((school_id, doc.get("source_format") or "?"))
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: non_pdf ({doc.get('source_format')})",
                flush=True,
            )
            continue
        detected = detect_year_from_bytes(pdf_bytes)
        if detected is None:
            counts["undetected"] += 1
            undetecteds.append((school_id, stored_year or ""))
            print(
                f"[{i:4d}/{len(docs)}] {school_id}: undetected (stored={stored_year})",
                flush=True,
            )
            continue
        if detected == stored_year:
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
        # Backfill detected_year when --write is set, skipping rows that
        # already carry the right value. Backfill is idempotent; re-runs
        # are cheap.
        if write and detected != stored_detected:
            try:
                write_detected_year(client, doc["id"], detected)
                counts["written"] += 1
            except Exception as e:
                counts["write_error"] += 1
                print(
                    f"    write_error: {school_id} {type(e).__name__}: {e}",
                    file=sys.stderr,
                    flush=True,
                )

    print()
    print("=== year detection summary ===")
    for bucket in (
        "confirmed",
        "mismatch",
        "undetected",
        "non_pdf",
        "download_error",
        "no_source",
    ):
        if counts[bucket]:
            print(f"  {bucket:18s} {counts[bucket]:5d}")
    # The detection-outcome bucket is what sums to the query cardinality.
    # written/write_error are side-effect counters from the --write path
    # and are not part of the row total.
    detection_total = (
        counts["confirmed"]
        + counts["mismatch"]
        + counts["undetected"]
        + counts["non_pdf"]
        + counts["download_error"]
        + counts["no_source"]
    )
    print(f"  {'total':18s} {detection_total:5d}")
    if write:
        print()
        print("=== write summary ===")
        print(f"  {'written':18s} {counts['written']:5d}")
        if counts["write_error"]:
            print(f"  {'write_error':18s} {counts['write_error']:5d}")

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
        "--skip-projection-refresh",
        action="store_true",
        help=(
            "Do not refresh cds_fields and school_browser_rows after each "
            "successful extraction. By default, non-dry-run drains keep the "
            "browser projection fresh document-by-document."
        ),
    )
    parser.add_argument(
        "--seed-projection-metadata",
        action="store_true",
        help=(
            "Before refreshing document projections, upsert "
            "cds_field_definitions and cds_metric_aliases. This is normally "
            "only needed after schema or alias changes; full rebuilds seed "
            "metadata through project_browser_data.py."
        ),
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help=(
            "Write a small machine-readable run summary for ops workflows. "
            "Includes processed count, failures, mean field count, low-field "
            "docs, and projection refresh counters."
        ),
    )
    parser.add_argument(
        "--low-field-threshold",
        type=int,
        default=25,
        help="Field-count threshold for low-field docs in --summary-json.",
    )
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
            "document regardless of extraction_status. Prints a "
            "confirmed/mismatch/undetected summary. Combine with --write "
            "to persist detected_year values (ADR 0007 Stage B backfill)."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "With --detect-year-only, persist each detected year to "
            "cds_documents.detected_year via write_detected_year. "
            "Default is read-only observation. Safe to re-run — backfill "
            "is idempotent and skips rows whose detected_year already "
            "matches the result."
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
            write=args.write,
        )

    schema = load_schema(Path(args.schema))

    # Build the Tier 1 cell map from the CDS template (once, reused for
    # all xlsx docs in the run). The template ships with the repo.
    _TEMPLATE_PATH = _TOOLS_ROOT.parent / "scratch" / "CDS-PDF-2025-2026-Excel_Template.xlsx"
    cell_map = None
    if _TEMPLATE_PATH.exists():
        try:
            cell_map = build_cell_map(_TEMPLATE_PATH)
            print(f"Tier 1 cell map loaded: {len(cell_map)} fields", flush=True)
        except Exception as e:
            print(f"Tier 1 cell map failed: {e} (xlsx will fall through to stub)", flush=True)

    query = client.table("cds_documents").select(
        "id, school_id, cds_year, detected_year, source_format, extraction_status",
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

    started_at = utc_now_iso()
    docs = query.execute().data or []
    if not docs:
        print(
            "No rows to process. Try --include-failed to re-process earlier failures.",
        )
        if args.summary_json:
            write_run_summary(args.summary_json, {
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "dry_run": args.dry_run,
                "limit": args.limit,
                "school": args.school,
                "include_failed": args.include_failed,
                "low_field_threshold": args.low_field_threshold,
                "processed_count": 0,
                "failure_count": 0,
                "mean_fields": None,
                "low_field_docs": [],
                "extraction_counts": {},
                "projection_counts": {},
                "documents": [],
            })
        return 0

    print(
        f"Processing {len(docs)} document(s){' (dry run)' if args.dry_run else ''}...",
        flush=True,
    )

    projection_definitions: dict | None = None
    projection_enabled = not args.dry_run and not args.skip_projection_refresh
    projection_counts: Counter = Counter()
    if projection_enabled:
        try:
            projection_definitions = load_projection_definitions()
            if args.seed_projection_metadata:
                seed_projection_metadata(client, projection_definitions)
        except Exception as e:
            projection_enabled = False
            projection_counts["setup_error"] += 1
            message = str(e).splitlines()[0][:200]
            print(
                "browser projection refresh disabled: "
                f"{type(e).__name__}: {message}",
                file=sys.stderr,
                flush=True,
            )

    counts: Counter = Counter()
    summary_docs: list[dict[str, Any]] = []
    field_counts: list[int] = []
    low_field_docs: list[dict[str, Any]] = []
    failure_count = 0
    for i, doc in enumerate(docs, 1):
        outcome = extract_one(client, doc, schema, args.dry_run, cell_map)
        bucket = outcome.action.split(":")[0].split(" ")[0]
        counts[bucket] += 1
        fields = parsed_field_count(outcome.action)
        if fields is not None:
            field_counts.append(fields)
            if fields < args.low_field_threshold:
                low_field_docs.append({
                    "document_id": str(doc["id"]),
                    "school_id": doc["school_id"],
                    "source_format": doc.get("source_format"),
                    "field_count": fields,
                    "action": outcome.action,
                })
        failed = is_failure_action(outcome.action)
        failure_count += int(failed)

        projection_note = ""
        projection_field_count: int | None = None
        projection_browser_row: bool | None = None
        if (
            projection_enabled
            and projection_definitions is not None
            and outcome.refresh_projection
        ):
            try:
                field_count, has_browser_row = refresh_browser_projection(
                    client,
                    str(doc["id"]),
                    projection_definitions,
                )
                projection_counts["documents"] += 1
                projection_counts["fields"] += field_count
                projection_counts["browser_rows"] += int(has_browser_row)
                projection_field_count = field_count
                projection_browser_row = has_browser_row
                projection_note = (
                    f"; projected {field_count} fields, "
                    f"browser_row={'yes' if has_browser_row else 'no'}"
                )
            except Exception as e:
                projection_counts["errors"] += 1
                message = str(e).splitlines()[0][:200]
                projection_note = f"; projection_error={type(e).__name__}: {message}"

        summary_docs.append({
            "document_id": str(doc["id"]),
            "school_id": doc["school_id"],
            "canonical_year": doc.get("detected_year") or doc.get("cds_year"),
            "source_format": doc.get("source_format"),
            "action": outcome.action,
            "field_count": fields,
            "failed": failed,
            "projection_field_count": projection_field_count,
            "projection_browser_row": projection_browser_row,
        })
        print(f"[{i:4d}/{len(docs)}] {doc['school_id']}: {outcome.action}{projection_note}", flush=True)

    print()
    print("=== extraction results ===")
    for bucket, n in counts.most_common():
        print(f"  {bucket:30s} {n:5d}")
    print(f"  {'total':30s} {sum(counts.values()):5d}")
    if projection_enabled or projection_counts:
        print()
        print("=== browser projection refresh ===")
        for bucket in ("documents", "fields", "browser_rows", "errors", "setup_error"):
            if projection_counts[bucket]:
                print(f"  {bucket:30s} {projection_counts[bucket]:5d}")
        if projection_counts["errors"] or projection_counts["setup_error"]:
            if args.summary_json:
                write_run_summary(args.summary_json, {
                    "started_at": started_at,
                    "finished_at": utc_now_iso(),
                    "dry_run": args.dry_run,
                    "limit": args.limit,
                    "school": args.school,
                    "include_failed": args.include_failed,
                    "low_field_threshold": args.low_field_threshold,
                    "processed_count": len(docs),
                    "failure_count": failure_count,
                    "mean_fields": mean_or_none(field_counts),
                    "low_field_docs": low_field_docs,
                    "extraction_counts": dict(counts),
                    "projection_counts": dict(projection_counts),
                    "documents": summary_docs,
                })
            return 2
    if args.summary_json:
        write_run_summary(args.summary_json, {
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "dry_run": args.dry_run,
            "limit": args.limit,
            "school": args.school,
            "include_failed": args.include_failed,
            "low_field_threshold": args.low_field_threshold,
            "processed_count": len(docs),
            "failure_count": failure_count,
            "mean_fields": mean_or_none(field_counts),
            "low_field_docs": low_field_docs,
            "extraction_counts": dict(counts),
            "projection_counts": dict(projection_counts),
            "documents": summary_docs,
        })
    return 0


if __name__ == "__main__":
    sys.exit(main())
