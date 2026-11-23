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
import time
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta, timezone
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
from pdf_text import PdfPageTexts  # noqa: E402
from revalidate_notify import notify_school_revalidation  # noqa: E402


SCHEMA_DIR = _TOOLS_ROOT.parent / "schemas"
TEMPLATE_DIR = SCHEMA_DIR / "templates"
MIN_TIER1_FIELDS = 5
MIN_TIER4_FIELDS = 25
MAX_FIELDS_FOR_SWALLOW_FLAG = 300
# A Tier 4 re-extraction of the same source PDF that ends this many fields or
# more below the previous artifact is held back, not written. Docling drift
# (Sacramento State 2023-24: 274 -> 108 fields on an older Docling) should
# never silently replace a good artifact, and neither should the smaller
# differences between two machines on the same Docling: of 135 documents
# re-extracted on a Mac on 2026-11-21 (112 of them last extracted on the
# GitHub runner), seven ended 13 to 41 fields lower (Concordia Texas 2014-15:
# 222 -> 181) and were written, because the guard then only held a result
# under 60% of the previous count.
# The count is the net one. Fields that merely moved are not a loss: 31 of
# those 135 documents no longer had 10 or more of their old fields, and 15 of
# the 31 ended level or higher (Swarthmore 2001-02: 137 -> 175).
MIN_REEXTRACT_FIELDS_LOST = 10
# Set by --accept-field-loss: write the new extraction even so. For a fix
# that removes ten or more wrong values from one document.
ACCEPT_FIELD_LOSS = False
# The same guard per table, because the net count hides a lost table. Of 191
# 2023-24 documents re-extracted on 2026-11-22, 28 lost most of one table
# while the document as a whole gained fields (Colorado: all 30 values of H2
# gone, 505 -> 512 fields overall; Clemson and Florida A&M: all of I1). The
# previous extractions of those files were converted by an earlier Docling,
# and the pinned one lays some tables out in a way the cleaner does not read.
#
# A value counts as lost only when its number is nowhere in the same section
# of the new extraction, so a row that was renumbered, or read under another
# year's schema, is not a loss. A table is held when it loses this many
# values and more than half of what it had.
MIN_TABLE_VALUES_LOST = 5
# Set by --accept-table-loss, after checking the lost values against the PDF.
ACCEPT_TABLE_LOSS = False
# The same guard for the headline admissions rows, whatever the total field
# count does. A re-extraction of the same file can gain fields overall and
# still lose C1: Docling 2.148.0 dropped the tables by sex from SMU and
# Wentworth 2025-26 and every C1 table from UPenn 2024-25, which went from 122
# fields to 237 while its enrolled total disappeared. The fields are the
# applied, admitted and enrolled totals and their rows for men and women.
HEADLINE_C1_FIELDS = {
    "2023-24": ("C.101", "C.102", "C.105", "C.106", "C.109", "C.110", "C.111", "C.112", "C.117", "C.118", "C.119"),
    "2024-25": ("C.101", "C.102", "C.105", "C.106", "C.109", "C.110", "C.111", "C.112", "C.117", "C.118", "C.119"),
    "2025-26": ("C.101", "C.102", "C.104", "C.105", "C.107", "C.108", "C.110", "C.111", "C.112", "C.113", "C.116", "C.117", "C.118"),
    "2026-27": ("C.101", "C.102", "C.104", "C.105", "C.107", "C.108", "C.110", "C.111", "C.112", "C.113", "C.116", "C.117", "C.118"),
}
# A field counts as lost only when its old value is nowhere in the newly
# converted text: the table it came from is gone. When the number is still in
# the text and merely no longer assigned to the field, that is the cleaner
# declining a value, usually a misread it used to accept, and re-extraction
# must be able to correct those. Measured on the 378 PDF documents
# re-extracted on 2026-11-18 and 19: 12 lost a headline value; in SMU and
# Wentworth the numbers were gone from the text, and in the other ten (years
# read as counts, a 9 as an applicant total) they were all still there.
# Two or more, because a table carries several rows.
MIN_HEADLINE_FIELDS_LOST = 2
# Set by --accept-headline-loss: write the new extraction even so. For the
# case the guard cannot tell apart, a fix that removes wrong headline values.
ACCEPT_HEADLINE_LOSS = False
MIN_TIER2_LABEL_FALLBACK_ACROFORM_FIELDS = 50
# Flattened reprint guard: when a school republishes its fillable CDS PDF as a
# flattened copy with no form fields, compare the earlier fillable PDF's
# >=4-digit numeric field values against the new file's page text.
MIN_FILLABLE_REPRINT_FIELDS = 50
MAX_REPRINT_PAGE_COUNT_DIFF_RATIO = 0.10
MIN_REPRINT_NUMERIC_DIGITS = 4
MIN_REPRINT_SAME_DATA_MATCH_RATIO = 0.90
MAX_REPRINT_MISSING_VALUES_MATCH_RATIO = 0.10
MIN_REPRINT_TEXT_CHARS = 100
MAX_PRIOR_SOURCE_CANDIDATES = 5
PIPELINE_RUN_URL_RE = re.compile(
    r"^https://github\.com/bolewood/collegedata-fyi/actions/runs/[0-9]+$",
)


@dataclass(frozen=True)
class ExtractionOutcome:
    action: str
    refresh_projection: bool = False
    needs_review: bool = False


@dataclass(frozen=True)
class SourceSelectionResult:
    source_artifact: dict[str, Any]
    source_bytes: bytes
    selection_note: Optional[dict[str, Any]] = None
    needs_review: bool = False


@dataclass(frozen=True)
class SchemaResolution:
    schema: dict[str, Any]
    schema_version: str
    canonical_year: Optional[str]
    fallback_used: bool
    fallback_reason: Optional[str]
    schema_path: Path
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parsed_field_count(action: str) -> int | None:
    match = re.search(r"\((\d+)(?:/\d+)? fields\b", action)
    return int(match.group(1)) if match else None


def is_failure_action(action: str) -> bool:
    if action == "already_extracted":
        return False
    action_name = action.split(" (", 1)[0]
    if action == "no_source_artifact" or action.startswith("stub_"):
        return True
    if action_name.startswith("tier1_no_cell_map"):
        return True
    if "_low_fields" in action:
        return True
    if "_error" in action or action_name.endswith("_no_tables"):
        return True
    if action_name.endswith("_field_regression"):
        return True
    return False


def drain_extraction_statuses(include_failed: bool) -> list[str]:
    return ["extraction_pending", "failed"] if include_failed else ["extraction_pending"]


def select_drain_docs(
    rows: list[dict[str, Any]],
    drain_statuses: list[str],
    requeue_document_ids: list[str],
) -> list[dict[str, Any]]:
    """Rows to drain: every requeued document whatever its status, plus any
    other row whose status is drainable."""
    requeued = set(requeue_document_ids)
    return [
        row for row in rows
        if str(row["id"]) in requeued or row.get("extraction_status") in drain_statuses
    ]


def is_field_regression(previous_fields: Optional[int], new_fields: int) -> bool:
    if not previous_fields:
        return False
    return previous_fields - new_fields >= MIN_REEXTRACT_FIELDS_LOST


def field_regression_action(
    client: Client,
    document_id: str,
    canonical: dict[str, Any],
    schema_version: Optional[str],
    new_fields: int,
) -> Optional[str]:
    """The failure action for a Tier 4 result with too few fields to replace
    the previous extraction of the same file, or None when it may be written."""
    if ACCEPT_FIELD_LOSS:
        return None
    previous_fields = previous_canonical_field_count(
        client, document_id, canonical.get("source_sha256"), schema_version,
    )
    if not is_field_regression(previous_fields, new_fields):
        return None
    return (
        f"tier4_field_regression ({new_fields} < {previous_fields} fields; "
        "the previous extraction of this file is kept)"
    )


def previous_canonical_field_count(
    client: Client,
    document_id: str,
    source_sha256: Optional[str],
    schema_version: Optional[str],
) -> Optional[int]:
    """Field count of the newest canonical artifact, when it was built from
    the same source PDF under the same schema. None otherwise (or when the
    source is unknown): another year's schema numbers its fields differently,
    so its count is not comparable to within ten fields."""
    if not source_sha256:
        return None
    rows = (
        client.table("cds_artifacts")
        .select(
            "schema_version,notes->stats->schema_fields_populated,"
            "notes->source_sha256,notes->source_artifact->sha256"
        )
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    row = rows[0]
    if str(row.get("schema_version") or "") != str(schema_version or ""):
        return None
    if source_sha256 not in (row.get("source_sha256"), row.get("sha256")):
        return None
    try:
        return int(row.get("schema_fields_populated") or 0)
    except (TypeError, ValueError):
        return None


def _positive_number(record: Any) -> bool:
    value = record.get("value") if isinstance(record, dict) else None
    try:
        return float(str(value).replace(",", "").strip()) > 0
    except (TypeError, ValueError):
        return False


def headline_fields_lost(
    previous_values: Optional[dict[str, Any]],
    new_values: dict[str, Any],
    schema_version: Optional[str],
    new_text: str,
) -> list[str]:
    """Headline C1 fields the previous extraction read as a positive number,
    the new one does not have, and whose number is nowhere in ``new_text``
    (the new extraction's converted text)."""
    if not previous_values:
        return []
    numbers_in_text = set(re.findall(r"\d+", (new_text or "").replace(",", "")))
    lost = []
    for field_id in HEADLINE_C1_FIELDS.get(str(schema_version), ()):
        previous = previous_values.get(field_id)
        if not _positive_number(previous):
            continue
        record = new_values.get(field_id)
        value = record.get("value") if isinstance(record, dict) else None
        if value is not None and str(value).strip() != "":
            continue
        digits = re.sub(r"\.0+$", "", str(previous.get("value")).replace(",", "").strip())
        if digits not in numbers_in_text:
            lost.append(field_id)
    return lost


_NOT_FETCHED: Any = object()


def headline_regression_action(
    client: Client,
    document_id: str,
    canonical: dict[str, Any],
    schema_version: Optional[str],
    previous: Any = _NOT_FETCHED,
) -> Optional[str]:
    """The failure action for a Tier 4 result that must not replace the
    previous extraction of the same file, or None when it may be written.

    Only the Docling markdown is searched for the lost numbers, not the PDF
    layout text or OCR text the cleaner also reads. That is deliberate:
    Wentworth 2025-26 still has its applied counts in the layout text, on
    lines too broken for the cleaner to read, and the rows were lost all the
    same. The cost is that a fix which stops accepting a value read only from
    layout or OCR text is held too, and needs --accept-headline-loss. None of
    the ten corrections measured on 2026-11-19 was of that kind.

    The enrolled rows rarely trip it: a CDS repeats first-year enrollment in
    section B, so those numbers are usually still in the text."""
    if ACCEPT_HEADLINE_LOSS:
        return None
    if previous is _NOT_FETCHED:
        previous = previous_canonical(client, document_id, canonical.get("source_sha256"))
    same_schema = previous is not None and str(previous[0] or "") == str(schema_version or "")
    lost = headline_fields_lost(
        previous[1] if same_schema else None,
        canonical.get("values") or {},
        schema_version,
        str(canonical.get("markdown") or ""),
    )
    if len(lost) < MIN_HEADLINE_FIELDS_LOST:
        return None
    return (
        f"tier4_headline_field_regression (lost {', '.join(lost)}; "
        "the previous extraction of this file is kept)"
    )


def previous_canonical_values(
    client: Client,
    document_id: str,
    source_sha256: Optional[str],
    schema_version: Optional[str],
) -> Optional[dict[str, Any]]:
    """Values of the newest canonical artifact, when it was made from the same
    source file under the same schema. None otherwise: a different file or a
    different numbering is not comparable field by field."""
    previous = previous_canonical(client, document_id, source_sha256)
    if previous is None or str(previous[0] or "") != str(schema_version or ""):
        return None
    return previous[1]


def previous_canonical(
    client: Client,
    document_id: str,
    source_sha256: Optional[str],
) -> Optional[tuple[Optional[str], dict[str, Any]]]:
    """(schema version, values) of the newest canonical artifact, when it was
    made from the same source file. None when it read another file.

    An artifact that records no source is attributed to the file that was
    current when it was written, the rule the reconcile gate uses."""
    if not source_sha256:
        return None
    rows = (
        client.table("cds_artifacts")
        .select(
            "id,kind,sha256,created_at,schema_version,"
            "source_sha:notes->>source_sha256,"
            "source_artifact_sha:notes->source_artifact->>sha256,"
            "selection_latest_sha:notes->source_selection->>latest_sha256"
        )
        .eq("document_id", document_id)
        .execute()
        .data
        or []
    )
    canonicals = [r for r in rows if r.get("kind") == "canonical"]
    if not canonicals:
        return None
    newest = max(canonicals, key=lambda r: _artifact_time(r["created_at"]))
    if not newest.get("source_sha") and newest.get("source_artifact_sha"):
        # Some artifacts record their source only under notes.source_artifact,
        # the second place previous_canonical_field_count looks.
        newest = dict(newest, source_sha=newest["source_artifact_sha"])
    if _canonical_source_sha(newest, rows) != source_sha256:
        return None
    detail = (
        client.table("cds_artifacts")
        .select("notes->values")
        .eq("id", newest["id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    values = detail[0].get("values") if detail else None
    if not isinstance(values, dict):
        return None
    return newest.get("schema_version"), values


_TABLE_FIELD_RE = re.compile(r"^([A-Z])\.(\d+[A-Z]?)\d\d$")


def _table_of(field_id: str) -> Optional[str]:
    """"H.2A07" -> "H2A", "C.1104" -> "C11", "B.126" -> "B1"."""
    match = _TABLE_FIELD_RE.match(str(field_id))
    return match.group(1) + match.group(2) if match else None


_PLAIN_NUMBER_RE = re.compile(r"-?(?:\d{1,15}(?:\.\d{0,10})?|\.\d{1,10})")


def _comparable_number(record: Any) -> Optional[str]:
    """A value as a plain number string, or None when it is not a number or is
    zero. Zeros and ticks ("X", "Yes") are everywhere in a CDS, so their
    presence elsewhere in a section says nothing about one field."""
    value = record.get("value") if isinstance(record, dict) else record
    text = str(value if value is not None else "").replace(",", "").replace("$", "").replace("%", "").strip()
    # Plain digits only. Decimal also accepts "1E1000000", "nan" and
    # "Infinity", and normalising a huge exponent raises or allocates a
    # megabyte-long string.
    if not _PLAIN_NUMBER_RE.fullmatch(text):
        return None
    number = Decimal(text)
    if number == 0:
        return None
    # One spelling per number: "25.70", "25.7" and 25.7 are the same value,
    # as are "1322.0" and "1322".
    return format(number.normalize(), "f")


def tables_lost(
    previous_values: Optional[dict[str, Any]],
    new_values: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    """{table: (values lost, values it had)} for every table that lost at
    least MIN_TABLE_VALUES_LOST numbers and more than half of its numbers.

    A number is lost when no field in the same section of ``new_values``
    still holds it. Each field of the new extraction accounts for one field
    of the old one, so a table of small numbers (C5's units, I3's class
    counts) is not hidden by one "4" elsewhere in the section. Section A
    (names, addresses, phone numbers) is not compared."""
    if not previous_values:
        return {}
    kept: dict[str, Counter[str]] = {}
    for field_id, record in new_values.items():
        number = _comparable_number(record)
        if number is not None:
            kept.setdefault(str(field_id)[:1], Counter())[number] += 1
    had: dict[str, int] = {}
    lost: dict[str, int] = {}
    for field_id, record in sorted(previous_values.items(), key=lambda item: str(item[0])):
        table = _table_of(field_id)
        if table is None or table.startswith("A"):
            continue
        number = _comparable_number(record)
        if number is None:
            continue
        had[table] = had.get(table, 0) + 1
        available = kept.get(table[:1])
        if available is not None and available[number] > 0:
            available[number] -= 1
        else:
            lost[table] = lost.get(table, 0) + 1
    return {
        table: (count, had[table])
        for table, count in sorted(lost.items())
        if count >= MIN_TABLE_VALUES_LOST and count * 2 > had[table]
    }


def table_regression_action(
    previous: Optional[tuple[Optional[str], dict[str, Any]]],
    canonical: dict[str, Any],
) -> Optional[str]:
    """The failure action for a Tier 4 result that drops most of a table the
    previous extraction of the same file had, or None when it may be written.

    ``previous`` is what ``previous_canonical`` returned. Its schema version
    is not checked: the comparison is by value within a section, which holds
    across the form years' numberings, and the extractions that most need it
    (April and May 2026, cleaned under the 2025-26 schema whatever the year)
    never share a schema with their re-extraction."""
    if ACCEPT_TABLE_LOSS or previous is None:
        return None
    lost = tables_lost(previous[1], canonical.get("values") or {})
    if not lost:
        return None
    detail = ", ".join(f"{table} lost {count} of {total}" for table, (count, total) in lost.items())
    return f"tier4_table_field_regression ({detail}; the previous extraction of this file is kept)"


def normalized_ledger_source_format(value: Any) -> str:
    source_format = str(value or "unknown")
    if source_format in {
        "pdf_fillable",
        "pdf_flat",
        "pdf_scanned",
        "xlsx",
        "docx",
        "html",
        "other",
    }:
        return source_format
    return "unknown"


def extraction_ledger_tier(source_format: str, action: str) -> str:
    if action == "reconciled":
        return "reconciliation"
    if "fallback_tier4" in action:
        return "tier4_fallback"
    if action.startswith("overlay"):
        # PRD 038: the template overlay writes no ledger row (its own entry point, no run ledger). If one ever
        # reaches here it is "unknown": a new tier value needs a CHECK-constraint migration, not in M3.
        return "unknown"
    return {
        "xlsx": "tier1",
        "pdf_fillable": "tier2",
        "docx": "tier3",
        "pdf_flat": "tier4",
        "pdf_scanned": "tier4_ocr",
        "html": "tier6",
        "other": "unsupported",
    }.get(source_format, "unknown")


def extraction_ledger_failure_code(action: str) -> str:
    if not is_failure_action(action):
        return "none"
    if action == "no_source_artifact":
        return "source_missing"
    if action.startswith("download_error"):
        return "source_download_failed"
    if action.startswith("stub_"):
        return "unsupported_format"
    if action.startswith("tier1_no_cell_map"):
        return "schema_failed"
    if "_low_fields" in action or "_no_tables" in action:
        return "low_coverage"
    if "artifact_insert_error" in action:
        return "artifact_write_failed"
    if action.startswith("worker_error"):
        return "worker_failed"
    if "_error" in action:
        return "extraction_failed"
    return "unknown_failure"


def extraction_ledger_outcome(action: str, *, force_reextract: bool) -> str:
    if action == "reconciled":
        return "reconciled"
    if is_failure_action(action):
        return "failed"
    if action == "already_extracted" or action.endswith("_already_extracted"):
        return "already_current"
    return "re_extracted" if force_reextract else "extracted"


def document_identity_needs_repair(doc: dict[str, Any]) -> bool:
    """True when the row is missing UNITID or is labeled with its slug."""
    school_id = str(doc.get("school_id") or "").strip()
    name = str(doc.get("school_name") or "").strip()
    ipeds = str(doc.get("ipeds_id") or "").strip()
    return bool(school_id) and ((not ipeds) or (not name) or name == school_id)


def stamp_document_identity(
    client: Client,
    doc: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Attach directory name + UNITID before extract/ledger publish.

    Archive writers are supposed to stamp these. The Python headless path
    historically omitted them, so the extraction queue must not copy a
    slug-as-name / null-IPEDS row into the public activity log.
    """
    if not document_identity_needs_repair(doc):
        return doc
    school_id = str(doc.get("school_id") or "").strip()
    document_id = str(doc.get("id") or "")
    try:
        result = (
            client.table("institution_directory")
            .select("school_id,school_name,ipeds_id")
            .eq("school_id", school_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        print(
            f"    identity_lookup_error: school={school_id} document={document_id} "
            f"{type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return doc
    rows = result.data or []
    if not rows:
        return doc
    row = rows[0]
    name = str(row.get("school_name") or "").strip()
    ipeds = str(row.get("ipeds_id") or "").strip()
    if not name or not ipeds:
        return doc
    patch: dict[str, str] = {}
    if not str(doc.get("ipeds_id") or "").strip():
        doc["ipeds_id"] = ipeds
        patch["ipeds_id"] = ipeds
    current_name = str(doc.get("school_name") or "").strip()
    if not current_name or current_name == school_id:
        doc["school_name"] = name
        patch["school_name"] = name
    if patch and not dry_run and document_id:
        try:
            client.table("cds_documents").update(patch).eq("id", document_id).execute()
        except Exception as e:
            print(
                f"    identity_write_error: school={school_id} document={document_id} "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
    return doc


def extraction_ledger_item(
    doc: dict[str, Any],
    action: str,
    *,
    ordinal: int,
    force_reextract: bool,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    source_format = normalized_ledger_source_format(doc.get("source_format"))
    return {
        "ordinal": ordinal,
        "document_id": str(doc["id"]),
        "school_id": str(doc["school_id"]),
        "school_name": str(doc.get("school_name") or doc["school_id"]),
        "canonical_year": str(
            doc.get("detected_year") or doc.get("cds_year") or "unknown"
        ),
        "occurred_at": occurred_at or utc_now_iso(),
        "outcome": extraction_ledger_outcome(
            action,
            force_reextract=force_reextract,
        ),
        "source_format": source_format,
        "extraction_tier": extraction_ledger_tier(source_format, action),
        "field_count": parsed_field_count(action),
        "failure_code": extraction_ledger_failure_code(action),
    }


def sanitize_pipeline_run_url(value: str | None) -> str | None:
    if value and PIPELINE_RUN_URL_RE.fullmatch(value):
        return value
    return None


def low_field_quality_flag(fields: int, threshold: int = MIN_TIER4_FIELDS) -> str | None:
    if fields >= threshold:
        return None
    return "blank_template" if fields == 0 else "low_coverage"


def is_single_section_source(values: dict, fields: int) -> bool:
    """One CDS section archived as the whole document.

    Regent 2020-21 Section A, Utah 2022-23 Section A, Randolph-Macon 2023-24
    Section F. Section C is exempt: C-only is the resolver's intentional
    admissions fallback and still serves real data.
    """
    if fields >= 150:
        return False
    sections = {str(key).split(".", 1)[0].upper() for key in values}
    return bool(sections) and "C" not in sections and len(sections) <= 2


def extraction_quality_flag(canonical: dict, threshold: int = MIN_TIER4_FIELDS) -> str | None:
    """Return a recoverable extraction quality flag for weak canonical artifacts."""
    stats = canonical.get("stats") or {}
    fields = int(stats.get("schema_fields_populated") or 0)
    flag = low_field_quality_flag(fields, threshold)
    if flag:
        return flag
    page_count = int(stats.get("page_count") or 0)
    if page_count >= 20 and fields < 100:
        return "low_coverage"

    values = canonical.get("values") or {}
    if is_single_section_source(values, fields):
        return "low_coverage"
    markdown = str(canonical.get("markdown") or "")
    markdown_lower = markdown.lower()
    if fields < 150:
        has_c1_anchor = (
            "c1. first-time" in markdown_lower
            or "first-time, first-year student applicants" in markdown_lower
            or "first-time, first-year admission" in markdown_lower
        )
        has_c9_anchor = (
            "submitting sat scores" in markdown_lower
            or "c9. percent and number" in markdown_lower
        )
        c1_keys = {"C.101", "C.102", "C.104", "C.105", "C.116", "C.117", "C.118", "C.119"}
        c9_keys = {"C.901", "C.902", "C.903", "C.904", "C.905", "C.906", "C.907", "C.914", "C.915", "C.916"}
        if (has_c1_anchor and not c1_keys.intersection(values)) or (
            has_c9_anchor and not c9_keys.intersection(values)
        ):
            return "low_coverage"

    # A swallowed H15 answer only hides a document that is also thin. A
    # 600-field CDS with one polluted free-text answer stays visible;
    # tier4_cleaner.trim_h15_spill strips the spill at extraction.
    for qn in ("H.1501",):
        if fields >= MAX_FIELDS_FOR_SWALLOW_FLAG:
            break
        rec = values.get(qn) or {}
        text = str(rec.get("value") or "")
        compact = re.sub(r"\s+", "", text).lower()
        if len(text) > 5000 and (
            "instructionalfacultyandclasssize" in compact
            or "disciplinaryareasofdegreesconferred" in compact
        ):
            return "low_coverage"

    return None


def mean_or_none(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def extraction_run_exit_code(failure_count: int) -> int:
    return 1 if failure_count > 0 else 0


def row_start_year(row: dict[str, Any]) -> int | None:
    year = row.get("detected_year") or row.get("cds_year") or ""
    try:
        return int(str(year)[:4])
    except Exception:
        return None


def discovered_at_sort_value(row: dict[str, Any]) -> int:
    value = str(row.get("discovered_at") or "")
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return 0
    return int(digits[:20])


def pending_doc_priority_key(row: dict[str, Any]) -> tuple[int, int, str]:
    """Sort pending rows so fresh/current files beat older alphabetical backlog."""
    year = row_start_year(row) or -1
    school_id = str(row.get("school_id") or "")
    return (-year, -discovered_at_sort_value(row), school_id)


def write_run_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


LEDGER_PAYLOAD_KEYS = frozenset({
    "p_run_id",
    "p_trigger",
    "p_run_url",
    "p_started_at",
    "p_finished_at",
    "p_dry_run",
    "p_stopped_reason",
    "p_pending_remaining",
    "p_run_error_code",
    "p_items",
})


def record_extraction_ledger_payload(
    client: Client,
    payload: dict[str, Any],
) -> tuple[bool, Exception | None]:
    last_error: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(0.5 * attempt)
        try:
            client.rpc("record_pipeline_extraction_run", payload).execute()
            return True, None
        except Exception as exc:
            last_error = exc
    return False, last_error


def replay_extraction_ledger(client: Client, path: Path) -> bool:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or set(payload) != LEDGER_PAYLOAD_KEYS:
        raise ValueError("ledger replay payload has unknown or missing keys")
    if not isinstance(payload.get("p_items"), list):
        raise ValueError("ledger replay p_items must be a list")
    recorded, error = record_extraction_ledger_payload(client, payload)
    if not recorded:
        raise RuntimeError("ledger replay failed after 3 attempts") from error
    return True


def notify_web_of_changed_schools(school_ids: set[str], dry_run: bool) -> None:
    """Best-effort ISR revalidation for schools whose data just changed.

    No-op unless COLLEGEDATA_REVALIDATE_URL and REVALIDATE_SECRET are set;
    never raises, so it cannot change the run's exit code.
    """
    if dry_run or not school_ids:
        return
    try:
        notify = notify_school_revalidation(school_ids)
    except Exception as e:  # noqa: BLE001
        print(f"revalidate_notify_error: {type(e).__name__}", file=sys.stderr, flush=True)
        return
    if notify["enabled"]:
        print(
            f"revalidate: notified web of {notify['sent']}/{len(school_ids)} "
            f"school(s), errors={notify['errors']}",
            flush=True,
        )


def finalize_extraction_run(
    client: Client,
    *,
    run_id: str,
    trigger: str,
    run_url: str | None,
    summary_path: Path | None,
    summary: dict[str, Any],
    ledger_items: list[dict[str, Any]],
    run_error_code: str,
) -> bool:
    """Persist the machine summary and the closed, normalized run ledger."""
    payload = {
        "p_run_id": run_id,
        "p_trigger": trigger,
        "p_run_url": sanitize_pipeline_run_url(run_url),
        "p_started_at": summary["started_at"],
        "p_finished_at": summary["finished_at"],
        "p_dry_run": bool(summary["dry_run"]),
        "p_stopped_reason": summary["stopped_reason"],
        "p_pending_remaining": int(summary["pending_remaining"]),
        "p_run_error_code": run_error_code,
        "p_items": ledger_items,
    }
    recorded, last_error = record_extraction_ledger_payload(client, payload)
    summary_ok = True
    if summary_path:
        try:
            write_run_summary(summary_path, summary)
        except Exception as exc:
            summary_ok = False
            message = str(exc).splitlines()[0][:200]
            print(
                f"extraction summary write failed: {type(exc).__name__}: {message}",
                file=sys.stderr,
                flush=True,
            )
    if recorded:
        return summary_ok

    message = str(last_error).splitlines()[0][:200] if last_error else "unknown"
    print(
        "extraction ledger write failed after 3 attempts: "
        f"{type(last_error).__name__}: {message}",
        file=sys.stderr,
        flush=True,
    )
    replay_path = (
        summary_path.parent / "ledger-replay.json"
        if summary_path
        else Path("scratch/extraction-worker") / f"ledger-replay-{run_id}.json"
    )
    try:
        write_run_summary(replay_path, payload)
        print(
            f"Replay payload saved to {replay_path}.",
            file=sys.stderr,
            flush=True,
        )
    except Exception as exc:
        replay_message = str(exc).splitlines()[0][:200]
        print(
            "ledger replay payload write failed: "
            f"{type(exc).__name__}: {replay_message}",
            file=sys.stderr,
            flush=True,
        )
    return False


def count_extraction_pending(client: Client) -> int:
    try:
        result = (
            client.table("cds_documents")
            .select("id", count="exact", head=True)
            .eq("extraction_status", "extraction_pending")
            .execute()
        )
        return int(result.count or 0)
    except Exception:
        return 0


def infer_stopped_reason(
    *,
    stopped_early: bool,
    hit_error: bool,
    limit: int | None,
    processed_count: int,
    pending_remaining: int,
) -> str:
    if hit_error:
        return "error"
    if stopped_early:
        return "deadline"
    if limit and processed_count >= limit and pending_remaining > 0:
        return "cap"
    return "complete"


def with_heartbeat_fields(
    payload: dict[str, Any],
    *,
    stopped_reason: str,
    extracted: int,
    failed: int,
    pending_remaining: int,
) -> dict[str, Any]:
    out = dict(payload)
    out["stopped_reason"] = stopped_reason
    out["extracted"] = extracted
    out["failed"] = failed
    out["pending_remaining"] = pending_remaining
    return out


def extraction_success(action: str, *, needs_review: bool = False) -> ExtractionOutcome:
    return ExtractionOutcome(action, refresh_projection=True, needs_review=needs_review)


def extraction_no_project(action: str, *, needs_review: bool = False) -> ExtractionOutcome:
    return ExtractionOutcome(action, refresh_projection=False, needs_review=needs_review)


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


def canonical_schema_paths(schema_dir: Path = SCHEMA_DIR) -> list[Path]:
    canonical_name_re = re.compile(r"^cds_schema_\d{4}_\d{2}\.json$")
    return [
        path
        for path in sorted(schema_dir.glob("cds_schema_*.json"))
        if canonical_name_re.match(path.name)
    ]


def load_schema_registry(schema_dir: Path = SCHEMA_DIR) -> dict[str, tuple[Path, dict[str, Any]]]:
    registry: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in canonical_schema_paths(schema_dir):
        schema = load_schema(path)
        version = schema.get("schema_version")
        if version and isinstance(schema.get("fields"), list):
            registry[str(version)] = (path, schema)
    if not registry:
        raise RuntimeError(f"no canonical schemas found in {schema_dir}")
    return registry


def latest_schema_version(registry: dict[str, tuple[Path, dict[str, Any]]]) -> str:
    def key(version: str) -> tuple[int, int]:
        match = re.match(r"^((?:19|20)\d{2})-(\d{2})$", version)
        if not match:
            return (0, 0)
        return (int(match.group(1)), int(match.group(2)))

    return max(registry, key=key)


# The schema for a document whose year has none of its own and is not newer
# than every schema here: an undated file, or a year before the first canonical
# schema. Those files cannot be on a newer form, every stored result for them
# is keyed by this numbering, and a newer schema would file their values under
# rows they do not print (2026-27 reassigns the C1 total form names and moves
# the spreadsheet rows). Pinned, so adding a template year changes nothing for
# them.
BASELINE_FALLBACK_SCHEMA_VERSION = "2025-26"


def _year_start(version: Optional[str]) -> Optional[int]:
    match = re.match(r"^((?:19|20)\d{2})-\d{2}$", version or "")
    return int(match.group(1)) if match else None


def fallback_schema_version(
    canonical_year: Optional[str],
    registry: dict[str, tuple[Path, dict[str, Any]]],
) -> str:
    """A year newer than every schema here uses the newest one (the form it
    was most likely built from); anything else uses the pinned baseline."""
    latest = latest_schema_version(registry)
    if BASELINE_FALLBACK_SCHEMA_VERSION not in registry:
        return latest
    year, newest = _year_start(canonical_year), _year_start(latest)
    if year is not None and newest is not None and year > newest:
        return latest
    return BASELINE_FALLBACK_SCHEMA_VERSION


def canonical_year_for_doc(doc: dict, detected_year: Optional[str] = None) -> Optional[str]:
    return detected_year or doc.get("detected_year") or doc.get("canonical_year") or doc.get("cds_year")


def resolve_schema_for_year(
    canonical_year: Optional[str],
    registry: dict[str, tuple[Path, dict[str, Any]]],
) -> SchemaResolution:
    if canonical_year and canonical_year in registry:
        path, schema = registry[canonical_year]
        return SchemaResolution(
            schema=schema,
            schema_version=str(schema.get("schema_version") or canonical_year),
            canonical_year=canonical_year,
            fallback_used=False,
            fallback_reason=None,
            schema_path=path,
        )

    fallback_version = fallback_schema_version(canonical_year, registry)
    path, schema = registry[fallback_version]
    reason = "missing_canonical_year" if not canonical_year else f"no_schema_for_{canonical_year}"
    return SchemaResolution(
        schema=schema,
        schema_version=str(schema.get("schema_version") or fallback_version),
        canonical_year=canonical_year,
        fallback_used=True,
        fallback_reason=reason,
        schema_path=path,
    )


# A template year and the earlier year whose form it extends without
# renumbering. A school can file a year's data on the earlier form (all five
# 2026-27 documents archived before the 2026-27 template came out did). For a
# flattened PDF that does not matter: the cleaner reads the text and the two
# years share their numbering. A fillable PDF or a spreadsheet is read by form
# name or by cell, and those differ: 2026-27 gave the C1 total form names to a
# new row and moved 410 spreadsheet cells.
PREVIOUS_FORM_OF = {"2026-27": "2025-26"}
# A file must carry at least this many of the earlier form's names before its
# missing new names are taken to mean anything.
MIN_FORM_NAMES_TO_JUDGE = 100


def _pdf_form_names(data: bytes) -> set[str]:
    try:
        return set((pypdf.PdfReader(BytesIO(data)).get_fields() or {}).keys())
    except Exception:
        return set()


def _workbook_question_numbers(data: bytes) -> set[str]:
    """Question numbers in a workbook's own lookup columns (the template's
    hidden AA/AC layer, which a filled copy keeps)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            return set(build_cell_map(Path(tmp.name)))
    except Exception:
        return set()


def resolve_schema_for_form(
    resolution: SchemaResolution,
    registry: dict[str, tuple[Path, dict[str, Any]]],
    source_format: Optional[str],
    data: bytes,
) -> SchemaResolution:
    """Use the earlier form's schema for a fillable PDF or spreadsheet that
    was built on the earlier form.

    The file is on the earlier form when it carries that form's names and none
    of the names the newer template added. A file this cannot judge (too few
    names, unreadable) keeps the schema it was given."""
    previous = PREVIOUS_FORM_OF.get(resolution.schema_version)
    if previous is None or previous not in registry:
        return resolution
    if source_format == "pdf_fillable":
        key, present = "pdf_tag", _pdf_form_names(data)
    elif source_format == "xlsx":
        key, present = "question_number", _workbook_question_numbers(data)
    else:
        return resolution
    previous_path, previous_schema = registry[previous]
    previous_names = {f.get(key) for f in previous_schema["fields"]} - {None}
    added_names = ({f.get(key) for f in resolution.schema["fields"]} - {None}) - previous_names
    if len(present & previous_names) < MIN_FORM_NAMES_TO_JUDGE or present & added_names:
        return resolution
    return SchemaResolution(
        schema=previous_schema,
        schema_version=str(previous_schema.get("schema_version") or previous),
        canonical_year=resolution.canonical_year,
        fallback_used=True,
        fallback_reason=f"form_is_{previous}",
        schema_path=previous_path,
    )


def template_path_for_schema_version(schema_version: str) -> Path:
    return TEMPLATE_DIR / f"cds_{schema_version}_template.xlsx"


def build_cell_maps_for_schemas(
    registry: dict[str, tuple[Path, dict[str, Any]]],
) -> dict[str, dict[str, tuple[str, str]]]:
    cell_maps: dict[str, dict[str, tuple[str, str]]] = {}
    for schema_version in sorted(registry):
        template_path = template_path_for_schema_version(schema_version)
        if not template_path.exists():
            continue
        try:
            cell_map = build_cell_map(template_path)
        except Exception as e:
            print(
                f"Tier 1 cell map failed for {schema_version}: {e}",
                flush=True,
            )
            continue
        if cell_map:
            cell_maps[schema_version] = cell_map
            print(
                f"Tier 1 cell map loaded for {schema_version}: {len(cell_map)} fields",
                flush=True,
            )
        else:
            print(
                f"Tier 1 cell map unavailable for {schema_version}: template has no hidden lookup map",
                flush=True,
            )
    return cell_maps


def fetch_latest_source_artifact(client: Client, document_id: str) -> Optional[dict]:
    result = (
        client.table("cds_artifacts")
        .select("storage_path,sha256")
        .eq("document_id", document_id)
        .eq("kind", "source")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def fetch_latest_source_path(client: Client, document_id: str) -> Optional[str]:
    artifact = fetch_latest_source_artifact(client, document_id)
    return artifact["storage_path"] if artifact else None


def download_source(client: Client, storage_path: str) -> bytes:
    return client.storage.from_("sources").download(storage_path)


def fetch_prior_source_artifacts(
    client: Client,
    document_id: str,
    latest_sha256: Optional[str],
    limit: int = MAX_PRIOR_SOURCE_CANDIDATES,
) -> list[dict]:
    """Return distinct prior `kind='source'` rows for `document_id`, newest first."""
    try:
        rows = (
            client.table("cds_artifacts")
            .select("storage_path,sha256,created_at")
            .eq("document_id", document_id)
            .eq("kind", "source")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
            .data
            or []
        )
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    seen_shas: set[str] = {latest_sha256} if latest_sha256 else set()
    prior: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        storage_path = row.get("storage_path")
        sha = row.get("sha256")
        if not storage_path:
            continue
        if sha and sha in seen_shas:
            continue
        if sha:
            seen_shas.add(sha)
        prior.append(row)
        if len(prior) >= limit:
            break
    return prior


def normalize_reprint_numeric_value(raw: str) -> Optional[str]:
    """Normalize a form field value (strip $ and commas) when it is numeric with
    at least MIN_REPRINT_NUMERIC_DIGITS digits."""
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    if not re.fullmatch(r"[\d.%]+", cleaned):
        return None
    if sum(ch.isdigit() for ch in cleaned) < MIN_REPRINT_NUMERIC_DIGITS:
        return None
    return cleaned


def _extract_fillable_reprint_values(
    pdf_bytes: bytes,
) -> Optional[tuple[int, int, list[str]]]:
    """Return (page_count, filled_field_count, numeric_values) for a fillable PDF,
    or None if the bytes are not a PDF with AcroForm fields."""
    if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
        return None
    try:
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        fields = reader.get_fields()
        page_count = len(reader.pages)
    except Exception:
        return None
    if not fields or page_count <= 0:
        return None
    filled_count = 0
    numeric_values: list[str] = []
    for field in fields.values():
        val = field.get("/V") if isinstance(field, dict) else None
        if val is None or val in ("", "/Off", "/"):
            continue
        s = str(val).strip()
        if not s or s in ("/", "/Off"):
            continue
        filled_count += 1
        norm = normalize_reprint_numeric_value(s)
        if norm is not None:
            numeric_values.append(norm)
    return page_count, filled_count, numeric_values


def compare_fillable_reprint_candidate(
    latest_bytes: bytes,
    latest_artifact: dict[str, Any],
    candidate_bytes: bytes,
    candidate_artifact: dict[str, Any],
) -> Optional[SourceSelectionResult]:
    """Compare a newest flat PDF against an earlier fillable PDF candidate.

    Returns None when the newest file is not a fieldless PDF or when the
    candidate does not meet the fillable field-count and page-count gates.
    Otherwise returns the selected source artifact/bytes and an auditable
    `selection_note` dict for `notes.source_selection`.
    """
    if len(latest_bytes) < 4 or latest_bytes[:4] != b"%PDF":
        return None
    try:
        latest_pages = PdfPageTexts(latest_bytes)
        if latest_pages.reader.get_fields():
            return None
        latest_page_count = len(latest_pages)
    except Exception:
        return None
    if latest_page_count <= 0:
        return None

    fillable_info = _extract_fillable_reprint_values(candidate_bytes)
    if fillable_info is None:
        return None
    fillable_page_count, filled_count, numeric_values = fillable_info
    if filled_count < MIN_FILLABLE_REPRINT_FIELDS:
        return None
    page_diff_ratio = abs(latest_page_count - fillable_page_count) / fillable_page_count
    if page_diff_ratio > MAX_REPRINT_PAGE_COUNT_DIFF_RATIO + 1e-9:
        return None
    if not numeric_values:
        return None

    page_texts = [latest_pages.text(i) or "" for i in range(latest_page_count)]
    full_text = "\n".join(page_texts)
    normalized_text = full_text.replace("$", "").replace(",", "")
    text_chars = len(full_text.strip())

    total_values = len(numeric_values)
    matched_values = sum(
        1
        for val in numeric_values
        if val in normalized_text or val.rstrip("%") in normalized_text
    )
    raw_ratio = matched_values / total_values
    match_ratio = round(raw_ratio, 4)

    latest_sha = latest_artifact.get("sha256")
    candidate_sha = candidate_artifact.get("sha256")

    if raw_ratio >= MIN_REPRINT_SAME_DATA_MATCH_RATIO:
        chosen_artifact = candidate_artifact
        chosen_bytes = candidate_bytes
        chosen_sha = candidate_sha
        reason = "flattened_reprint_same_data"
        needs_review = False
    elif (
        text_chars >= MIN_REPRINT_TEXT_CHARS
        and raw_ratio <= MAX_REPRINT_MISSING_VALUES_MATCH_RATIO
    ):
        chosen_artifact = candidate_artifact
        chosen_bytes = candidate_bytes
        chosen_sha = candidate_sha
        reason = "print_to_pdf_values_missing_from_text"
        needs_review = True
    else:
        chosen_artifact = latest_artifact
        chosen_bytes = latest_bytes
        chosen_sha = latest_sha
        reason = "edition_values_changed"
        needs_review = False

    selection_note = {
        "chosen_sha256": chosen_sha,
        "candidate_sha256": candidate_sha,
        "latest_sha256": latest_sha,
        "match_ratio": match_ratio,
        "matched_values": matched_values,
        "total_values": total_values,
        "reason": reason,
        "needs_review": needs_review,
    }
    return SourceSelectionResult(
        source_artifact=chosen_artifact,
        source_bytes=chosen_bytes,
        selection_note=selection_note,
        needs_review=needs_review,
    )


def select_source_for_extraction(
    client: Client,
    document_id: str,
    latest_artifact: dict[str, Any],
    latest_bytes: bytes,
) -> SourceSelectionResult:
    """Choose the source artifact to extract before format routing.

    When the newest source is a PDF with no form fields and an earlier source
    artifact for the same document is a fillable PDF with >=50 filled fields
    and a page count within ±10%, compare >=4-digit numeric form values against
    the newest PDF's page text.
    """
    if len(latest_bytes) < 4 or latest_bytes[:4] != b"%PDF":
        return SourceSelectionResult(latest_artifact, latest_bytes)
    try:
        latest_pages = PdfPageTexts(latest_bytes)
        if latest_pages.reader.get_fields() or len(latest_pages) <= 0:
            return SourceSelectionResult(latest_artifact, latest_bytes)
    except Exception:
        return SourceSelectionResult(latest_artifact, latest_bytes)

    prior_artifacts = fetch_prior_source_artifacts(
        client, document_id, latest_artifact.get("sha256"),
    )
    for candidate_artifact in prior_artifacts:
        storage_path = candidate_artifact.get("storage_path")
        if not storage_path:
            continue
        try:
            candidate_bytes = download_source(client, storage_path)
        except Exception:
            continue
        decision = compare_fillable_reprint_candidate(
            latest_bytes, latest_artifact, candidate_bytes, candidate_artifact,
        )
        if decision is not None:
            return decision

    return SourceSelectionResult(latest_artifact, latest_bytes)


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
# Title-line layouts (CDS Initiative template):
#   Common Data Set 2025-2026
#   CDS 2025-26
#
# Section-package layouts (Factbook PDFs that print the CDS title, a
# section heading, then the year on the following lines):
#   Common Data Set
#   Section A1. General Information
#   2026-2027
#
# The section-title pattern stays prefix-anchored on "Common Data Set"
# and only allows a short heading (plus one optional extra line, e.g. a
# school name) between the title and the year. A bare 2006-07 in
# section J still cannot match. Zero hits or multiple distinct valid
# spans still return None (ADR 0007: miss, don't corrupt).
_YEAR_PATTERNS = [
    re.compile(
        r"Common\s+Data\s+Set\s*[,:]?\s*(20\d{2})\s*" + _DASH_CLASS + r"\s*(20\d{2}|\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bCDS\s*[,:]?\s*(20\d{2})\s*" + _DASH_CLASS + r"\s*(20\d{2}|\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"Common\s+Data\s+Set\s+"
        r"Section\s+[A-J]\d{0,2}\.?\s+"
        r"[A-Za-z][A-Za-z0-9 ,.&'()/-]{0,80}"
        r"(?:\s+[A-Za-z][A-Za-z0-9 ,.&'()/-]{2,60})?"
        r"\s+(20\d{2})\s*" + _DASH_CLASS + r"\s*(20\d{2}|\d{2})",
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


def collect_year_spans_from_text(text: str) -> set[str]:
    """Collect valid CDS year spans from already-extracted plain text.

    Shared by PDF page text and DOCX tag-stripped XML so the regex
    ladder stays in one place. Uniqueness is the caller's job.
    """
    spans: set[str] = set()
    if not text:
        return spans
    for pattern in _YEAR_PATTERNS:
        for m in pattern.finditer(text):
            span = _normalize_year_span(m.group(1), m.group(2))
            if span:
                spans.add(span)
    return spans


def unique_detected_year(spans: set[str]) -> Optional[str]:
    """ADR 0007: one unique valid span is a year; zero or many is None."""
    if len(spans) == 1:
        return next(iter(spans))
    return None


def detect_year_from_text(text: str) -> Optional[str]:
    """Detect a CDS year from plain text. Tests should use this, not PDFs."""
    return unique_detected_year(collect_year_spans_from_text(text))


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
    pages = PdfPageTexts(data)
    for page_idx in range(page_count):
        text = pages.text(page_idx)
        if text is None:
            print(
                f"    pdf_error: page {page_idx} text unreadable by pypdf and pdfium",
                file=sys.stderr,
                flush=True,
            )
            continue
        spans |= collect_year_spans_from_text(text)
    # Zero hits → undetected. Multiple distinct hits → ambiguous →
    # treat as undetected per the strict invariant. Both cases return
    # None; they're bucketed identically in the harness summary.
    return unique_detected_year(spans)


# ── Year fallback for documents the archive filed without a year ──────────
#
# The archive files a document under cds_year "unknown" when neither its URL
# nor its link text names a year. If the strict title patterns above then
# find no year, or two, nothing from the document is published: its
# canonical year stays "unknown". 22 of 38 such documents on 2026-11-19 were
# real CDS files, 12 of them their school's only one (Colorado State titles
# its file "Common Data Set FY2026"; UC Davis's names two years).
#
# Two more signals, used ONLY for those documents, never to override a year
# the archive or the strict patterns gave:
#
# 1. The template's reference date. Every CDS template since at least
#    1999-00 asks for figures "as of October 15, <year>", the fall of the
#    CDS year. On 67 known-year documents sampled 2026-11-19 it matched the
#    known year in all but one, a reused template with a stale date, which
#    disagreed with the strict span and is refused by (a).
#    (a) If the strict patterns found any span, the reference date must
#        match one of them.
#    (b) If they found none, the reference date must not disagree with the
#        fall term the document mentions most (rule 2's test).
# 2. When there is no reference date and the strict patterns found two or
#    more spans, the fall term the document mentions far more than any
#    other ("Fall 2022" in C1, C9, ...) picks among those spans. It never
#    introduces a year the strict patterns did not find. (34 of 34 in the
#    same sample.)
# "as of" is required: C21/C22 early-plan dates and H aid deadlines can also
# fall on October 15, of the year before the CDS year.
_REFERENCE_DATE_RE = re.compile(
    r"as\s+of\s+October\s+15\s*,?\s+((?:19|20)\d{2})", re.IGNORECASE
)
_CDS_NAME_RE = re.compile(r"Common\s+Data\s+Set|\bCDS\b")
_FALL_TERM_RE = re.compile(r"\bFall\s+((?:19|20)\d{2})\b")
YEAR_FALLBACK_MAX_PAGES = 20
YEAR_FALLBACK_STRICT_PAGES = 10  # the pages detect_year_from_pdf_bytes reads
YEAR_FALLBACK_MIN_FALL_MENTIONS = 5
UNKNOWN_CDS_YEAR = "unknown"


def _span_starting(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


def _dominant_fall_year(text: str) -> Optional[int]:
    """The fall term mentioned at least YEAR_FALLBACK_MIN_FALL_MENTIONS times
    and at least twice as often as any other, or None."""
    falls = Counter(int(y) for y in _FALL_TERM_RE.findall(text or "")).most_common(2)
    if not falls or falls[0][1] < YEAR_FALLBACK_MIN_FALL_MENTIONS:
        return None
    if len(falls) > 1 and falls[0][1] < 2 * falls[1][1]:
        return None
    return falls[0][0]


def fallback_year_from_text(strict_text: str, text: str) -> Optional[str]:
    """Year for a document with no year, from the reference date or the
    dominant fall term. `strict_text` is the text the strict patterns read;
    `text` is the wider text searched for the two signals. None when the
    text never names the Common Data Set, or the signals are missing,
    several, or contradict each other or the strict spans."""
    text = text or ""
    if not _CDS_NAME_RE.search(text):
        return None  # an enrollment report or self-study, not a CDS
    spans = collect_year_spans_from_text(strict_text)
    reference_years = {int(y) for y in _REFERENCE_DATE_RE.findall(text)}
    dominant_fall = _dominant_fall_year(text)
    if len(reference_years) == 1:
        reference_year = next(iter(reference_years))
        candidate = _span_starting(reference_year)
        if spans:
            return candidate if candidate in spans else None
        # No title span to check against: a reused template can carry last
        # year's date, and then the fall term it is filled in for disagrees.
        if dominant_fall is not None and dominant_fall != reference_year:
            return None
        return candidate
    if reference_years or len(spans) < 2 or dominant_fall is None:
        return None
    candidate = _span_starting(dominant_fall)
    return candidate if candidate in spans else None


def detect_year_fallback_from_pdf_bytes(data: bytes) -> Optional[str]:
    """fallback_year_from_text over the first pages of a PDF. None for
    anything that is not a readable PDF."""
    if len(data) < 4 or data[:4] != b"%PDF":
        return None
    try:
        pages = PdfPageTexts(data)
        page_count = min(YEAR_FALLBACK_MAX_PAGES, len(pages))
    except Exception as e:
        print(
            f"    pdf_error: year fallback could not open the PDF: {type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return None
    texts = [pages.text(i) or "" for i in range(page_count)]
    return fallback_year_from_text(
        "\n".join(texts[:YEAR_FALLBACK_STRICT_PAGES]), "\n".join(texts)
    )


def school_has_document_for_year(client: Client, doc: dict, year: str) -> bool:
    """True when another live document of the same school (and the same
    sub-institution) already carries `year`. Giving a second document that
    year would publish two rows for it."""
    rows = (
        client.table("cds_documents")
        .select("id,cds_year,detected_year,sub_institutional")
        .eq("school_id", doc.get("school_id"))
        .is_("removed_at", "null")
        .execute()
        .data
        or []
    )
    own = next((row for row in rows if row.get("id") == doc.get("id")), doc)
    sub_institution = own.get("sub_institutional") or None
    for row in rows:
        if row.get("id") == doc.get("id"):
            continue
        if (row.get("sub_institutional") or None) != sub_institution:
            continue
        if (row.get("detected_year") or row.get("cds_year")) == year:
            return True
    return False


def fallback_year_for_unfiled_document(
    client: Client, doc: dict, pdf_bytes: bytes
) -> Optional[str]:
    """The fallback year for a document the archive filed without a year,
    or None. Only for a document with no stored year of either kind, and
    never a year another of the school's documents already has. Never
    raises: a failure here leaves the document without a year, as before."""
    if doc.get("detected_year"):
        return None
    if (doc.get("cds_year") or UNKNOWN_CDS_YEAR) != UNKNOWN_CDS_YEAR:
        return None
    label = f"school={doc.get('school_id')} document={doc.get('id')}"
    try:
        year = detect_year_fallback_from_pdf_bytes(pdf_bytes)
        if not year:
            return None
        if school_has_document_for_year(client, doc, year):
            print(
                f"    year_fallback_conflict: {label} year={year} is already "
                "another document's; left without a year",
                flush=True,
            )
            return None
    except Exception as e:
        print(
            f"    year_fallback_error: {label} {type(e).__name__}: {e}",
            file=sys.stderr,
            flush=True,
        )
        return None
    print(f"    year_fallback: {label} year={year}", flush=True)
    return year


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
    return collect_year_spans_from_text(text)


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

    return unique_detected_year(spans)


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


def strip_leading_html_noise(head: str) -> str:
    head = head.lstrip("\ufeff").lstrip()
    while head.startswith("<!--"):
        end = head.find("-->")
        if end < 0:
            return head
        head = head[end + 3 :].lstrip()
    return head


def sniff_format_from_bytes(data: bytes) -> str:
    """Best-effort format detection when cds_documents.source_format is null.
    Returns one of the extraction_status enum values the migration allows
    (pdf_fillable / pdf_flat / pdf_scanned / xlsx / docx / other)."""
    if len(data) >= 4 and data[:4] == b"%PDF":
        try:
            pages = PdfPageTexts(data)
            fields = pages.reader.get_fields()
            if fields:
                return "pdf_fillable"
            # no fields → text-sniff first few pages. A page pypdf cannot
            # parse falls back to pdfium; a page neither can read is unknown,
            # not empty, so an unreadable sample never forces full OCR.
            total = 0
            readable = 0
            for i in range(min(3, len(pages))):
                text = pages.text(i)
                if text is not None:
                    readable += 1
                    total += len(text)
            if total >= 100:
                return "pdf_flat"
            return "pdf_scanned" if readable else "other"
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
        head = strip_leading_html_noise(
            data[:512].decode("utf-8", errors="ignore").lower()
        )
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


def choose_source_format(declared: Optional[str], data: bytes) -> tuple[str, bool]:
    """Choose the extraction route, preferring byte sniff over stale DB labels."""
    sniffed = sniff_format_from_bytes(data)
    if sniffed != "other" and sniffed != declared:
        return sniffed, True
    return declared or sniffed, False


def artifact_already_extracted(
    client: Client,
    document_id: str,
    producer: str,
    producer_version: str,
    schema_version: Optional[str] = None,
    source_sha256: Optional[str] = None,
    latest_source_sha256: Optional[str] = None,
) -> bool:
    """Idempotency: if an artifact with the same (document, kind, producer,
    version, schema, source sha) tuple already exists, skip writing a duplicate.

    The source sha check matters when a document row is refreshed in place with
    a corrected or republished PDF. Older canonical artifacts may not carry
    source provenance; those are treated as stale when source_sha256 is known.
    When `latest_source_sha256` differs from `source_sha256` (a prior fillable
    source was selected over a newer flattened reprint), require the canonical
    artifact to record that `source_selection.latest_sha256` so an older
    pre-reprint Tier 2 artifact does not suppress writing the audited decision.
    """
    query = (
        client.table("cds_artifacts")
        .select("id,notes,created_at")
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .eq("producer", producer)
        .eq("producer_version", producer_version)
    )
    if schema_version:
        query = query.eq("schema_version", schema_version)
    result = query.order("created_at", desc=True).limit(10).execute()
    rows = result.data or []
    if not source_sha256:
        return bool(rows)
    for row in rows:
        notes = row.get("notes") or {}
        row_sha = notes.get("source_sha256")
        if not row_sha:
            source_artifact = notes.get("source_artifact")
            if isinstance(source_artifact, dict):
                row_sha = source_artifact.get("sha256")
        if row_sha != source_sha256:
            continue
        if latest_source_sha256:
            selection = notes.get("source_selection")
            if not isinstance(selection, dict):
                continue
            if selection.get("latest_sha256") != latest_source_sha256:
                continue
        # An extraction of these bytes exists, but a later one read another
        # file: the document was pointed elsewhere, extracted, and pointed
        # back. The later one is what gets served, so this one does not make
        # the document extracted; a fresh extraction has to be written.
        return not _superseded_by_other_bytes(client, document_id, row, source_sha256)
    return False


def _superseded_by_other_bytes(
    client: Client,
    document_id: str,
    matched: dict[str, Any],
    source_sha256: str,
) -> bool:
    """True if a canonical artifact written after ``matched`` records a
    different source file. Artifacts that record no source are not judged."""
    matched_at = matched.get("created_at")
    if not matched_at:
        return False
    rows = (
        client.table("cds_artifacts")
        .select("id,created_at,source_sha:notes->>source_sha256")
        .eq("document_id", document_id)
        .eq("kind", "canonical")
        .execute()
        .data
        or []
    )
    for other in rows:
        if other.get("id") == matched.get("id") or not other.get("created_at"):
            continue
        other_sha = other.get("source_sha") or (other.get("notes") or {}).get("source_sha256")
        if (
            other_sha
            and other_sha != source_sha256
            and _artifact_time(other["created_at"]) > _artifact_time(matched_at)
        ):
            return True
    return False


def attach_source_metadata(canonical: dict, source_artifact: dict) -> None:
    source_sha256 = source_artifact.get("sha256")
    source_storage_path = source_artifact.get("storage_path")
    if source_sha256:
        canonical["source_sha256"] = source_sha256
    if source_storage_path:
        canonical["source_storage_path"] = source_storage_path
    if source_sha256 or source_storage_path:
        canonical["source_artifact"] = {
            k: v for k, v in {
                "sha256": source_sha256,
                "storage_path": source_storage_path,
            }.items() if v
        }


def attach_source_selection(
    canonical: dict,
    selection_note: Optional[dict[str, Any]],
) -> None:
    """Attach `notes.source_selection` and, when flagged for review, a
    `quality_warnings` entry on the canonical artifact."""
    if not selection_note:
        return
    canonical["source_selection"] = dict(selection_note)
    if selection_note.get("needs_review"):
        warnings_list = canonical.setdefault("quality_warnings", [])
        warnings_list.append({
            "code": "flattened_reprint_values_missing_from_text",
            "severity": "warning",
            "needs_review": True,
            "chosen_sha256": selection_note.get("chosen_sha256"),
            "candidate_sha256": selection_note.get("candidate_sha256"),
            "latest_sha256": selection_note.get("latest_sha256"),
            "match_ratio": selection_note.get("match_ratio"),
            "matched_values": selection_note.get("matched_values"),
            "total_values": selection_note.get("total_values"),
            "message": (
                "Newest source PDF has a text layer but almost none of the "
                "prior fillable PDF's numeric values appear in its text "
                "(likely print-to-PDF vector paths); extracted from prior "
                "fillable source and marked for review."
            ),
        })


def attach_schema_metadata(canonical: dict, resolution: SchemaResolution) -> dict:
    canonical["schema_version"] = resolution.schema_version
    if resolution.fallback_used:
        canonical["schema_fallback_used"] = True
        canonical["schema_fallback_reason"] = resolution.fallback_reason
        if resolution.canonical_year:
            canonical["schema_year_proxy_for"] = resolution.canonical_year
    else:
        canonical["schema_fallback_used"] = False
    return canonical


def run_tier2(pdf_bytes: bytes, schema: dict) -> dict:
    """Run tier2_extractor.extract against in-memory bytes. The extractor
    expects a Path, so we materialize to a NamedTemporaryFile briefly.
    Returns the canonical dict."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        return tier2_extract(Path(tmp.name), schema)


def annotate_tier2_unmapped_fields(canonical: dict) -> int:
    """Promote Tier 2 unmapped AcroForm tags into an explicit warning.

    The Tier 2 extractor already preserves `unmapped_fields` and a stats count
    in the artifact notes. This annotation gives operators and downstream
    consumers a stable quality-warning hook without introducing a new
    extraction status enum.
    """
    stats = canonical.get("stats") or {}
    unmapped_count = int(stats.get("unmapped_acroform_fields") or 0)
    if unmapped_count <= 0:
        return 0
    unmapped_fields = canonical.get("unmapped_fields") or []
    sample_tags = [
        str(item.get("pdf_tag"))
        for item in unmapped_fields[:10]
        if isinstance(item, dict) and item.get("pdf_tag")
    ]
    warnings_list = canonical.setdefault("quality_warnings", [])
    warnings_list.append({
        "code": "tier2_unmapped_acroform_fields",
        "severity": "warning",
        "count": unmapped_count,
        "sample_pdf_tags": sample_tags,
        "message": (
            "Populated AcroForm fields were present in the source PDF but did "
            "not map to the selected CDS schema."
        ),
    })
    return unmapped_count


def should_fallback_tier2_to_tier4(canonical: dict) -> bool:
    """Detect fillable PDFs whose AcroForm fields are populated but unusable.

    Some schools publish fillable PDFs whose field names are visible prompt labels
    ("Men_10", "Closing Date_5") instead of canonical CDS tags
    ("AP_RECD_1ST_MEN_N"). Exact Tier 2 mapping will recover almost nothing even
    though the PDF has real data. In that case, treat Tier 2 as a failed route and
    let the Tier 4 layout cleaner parse the visible tables.
    """
    stats = canonical.get("stats") or {}
    acroform_fields = int(stats.get("acroform_fields_total") or 0)
    mapped_fields = int(stats.get("schema_fields_populated") or 0)
    unmapped_fields = int(stats.get("unmapped_acroform_fields") or 0)
    if acroform_fields < MIN_TIER2_LABEL_FALLBACK_ACROFORM_FIELDS:
        return False
    if mapped_fields >= MIN_TIER1_FIELDS:
        return False
    return unmapped_fields >= int(acroform_fields * 0.8)


def _run_tier1(
    client: Client,
    document_id: str,
    school_id: str,
    xlsx_bytes: bytes,
    source_format: str,
    resolution: SchemaResolution,
    cell_map: dict,
    source_artifact: dict,
    dry_run: bool,
    force_reextract: bool = False,
) -> ExtractionOutcome:
    """Tier 1 path: template cell map, or workbook-native answer columns.

    ``cell_map`` may be empty when the year has no hidden lookup template
    (notably 2023-24). ``tier1_extract`` then scans Question Number / Answer
    columns in the filled workbook.
    """
    try:
        canonical = tier1_extract(xlsx_bytes, resolution.schema, cell_map)
        attach_schema_metadata(canonical, resolution)
        attach_source_metadata(canonical, source_artifact)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier1_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]
    fields = canonical.get("stats", {}).get("schema_fields_populated", 0)

    if fields < MIN_TIER1_FIELDS:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier1_low_fields ({fields} fields)")

    # Tier 1 used to clear the flag unconditionally, so 5-24 field XLSX
    # extractions were served unflagged.
    quality_flag = extraction_quality_flag(canonical)

    if not dry_run:
        if not force_reextract and artifact_already_extracted(
            client, document_id, producer, producer_version,
            resolution.schema_version, canonical.get("source_sha256"),
        ):
            mark_extraction_status(client, document_id, "extracted", source_format)
            apply_extraction_quality_flag(client, document_id, quality_flag)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)
        apply_extraction_quality_flag(client, document_id, quality_flag)

    return extraction_success(f"tier1_extracted ({fields} fields)")


def _run_tier6(
    client: Client,
    document_id: str,
    school_id: str,
    html_bytes: bytes,
    source_format: str,
    resolution: SchemaResolution,
    schema_index,
    source_artifact: dict,
    dry_run: bool,
    force_reextract: bool = False,
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
        values = tier4_clean(markdown, schema=schema_index)
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
        "producer_version": "0.1.3",
        "schema_version": resolution.schema_version,
        "schema_fallback_used": resolution.fallback_used,
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
    if resolution.fallback_used:
        canonical["schema_fallback_reason"] = resolution.fallback_reason
        if resolution.canonical_year:
            canonical["schema_year_proxy_for"] = resolution.canonical_year
    attach_source_metadata(canonical, source_artifact)

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]
    stats = canonical.get("stats", {})
    fields = int(stats.get("schema_fields_populated") or 0)
    quality_flag = extraction_quality_flag(canonical)

    if not dry_run:
        if not force_reextract and artifact_already_extracted(
            client, document_id, producer, producer_version,
            resolution.schema_version, canonical.get("source_sha256"),
        ):
            mark_extraction_status(client, document_id, "extracted", source_format)
            if quality_flag:
                mark_document_quality_flag(client, document_id, quality_flag)
            else:
                clear_recoverable_quality_flag(client, document_id)
            return extraction_no_project("already_extracted")

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)
        if quality_flag:
            mark_document_quality_flag(client, document_id, quality_flag)
        else:
            clear_recoverable_quality_flag(client, document_id)

    return extraction_success(f"tier6_extracted ({len(values)} fields, {len(markdown)} md chars)")


def _run_tier4(
    client: Client,
    document_id: str,
    school_id: str,
    pdf_bytes: bytes,
    source_format: str,
    resolution: SchemaResolution,
    schema_index,
    source_artifact: dict,
    dry_run: bool,
    force_reextract: bool = False,
    source_selection: Optional[dict[str, Any]] = None,
) -> ExtractionOutcome:
    """Tier 4 path: Docling baseline → markdown artifact.

    For pdf_scanned, forces full-page EasyOCR since Docling's auto OCR
    heuristic doesn't reliably trigger on scanned documents.
    """
    from tier4_extractor import extract_from_bytes as tier4_extract

    force_ocr = source_format == "pdf_scanned"
    try:
        canonical = tier4_extract(
            pdf_bytes,
            force_ocr=force_ocr,
            schema=schema_index,
            schema_version=resolution.schema_version,
            schema_fallback_used=resolution.fallback_used,
        )
        if resolution.fallback_used:
            canonical["schema_fallback_reason"] = resolution.fallback_reason
            if resolution.canonical_year:
                canonical["schema_year_proxy_for"] = resolution.canonical_year
        attach_source_metadata(canonical, source_artifact)
        attach_source_selection(canonical, source_selection)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier4_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]
    stats = canonical.get("stats", {})
    fields = int(stats.get("schema_fields_populated") or 0)
    quality_flag = extraction_quality_flag(canonical)

    if not dry_run:
        latest_sha256 = (
            source_selection.get("latest_sha256")
            if isinstance(source_selection, dict)
            else None
        )
        if not force_reextract and artifact_already_extracted(
            client, document_id, producer, producer_version,
            resolution.schema_version, canonical.get("source_sha256"),
            latest_source_sha256=latest_sha256,
        ):
            mark_extraction_status(client, document_id, "extracted", source_format)
            if quality_flag:
                mark_document_quality_flag(client, document_id, quality_flag)
            else:
                clear_recoverable_quality_flag(client, document_id)
            return extraction_no_project("already_extracted")

        held = field_regression_action(client, document_id, canonical, resolution.schema_version, fields)
        if held:
            # Keep the existing artifact (and its flag) current; the
            # document is still extracted, just not by this run.
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project(held)
        # One read of the previous extraction serves both guards below.
        previous = (
            None
            if ACCEPT_HEADLINE_LOSS and ACCEPT_TABLE_LOSS
            else previous_canonical(client, document_id, canonical.get("source_sha256"))
        )
        held = headline_regression_action(
            client, document_id, canonical, resolution.schema_version, previous=previous,
        ) or table_regression_action(previous, canonical)
        if held:
            # Keep serving the previous extraction; the failure action puts
            # the document in the run summary for a look.
            mark_extraction_status(client, document_id, "extracted", source_format)
            return extraction_no_project(held)

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)
        if quality_flag:
            mark_document_quality_flag(client, document_id, quality_flag)
        else:
            clear_recoverable_quality_flag(client, document_id)

    md_len = stats.get("markdown_length", 0)
    pages = stats.get("page_count", 0)
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
    if status == "extracted":
        # First transition only. A later reconcile or re-mark must not
        # rewrite extracted_at (PRD 029).
        client.table("cds_documents").update(
            {"extracted_at": datetime.now(timezone.utc).isoformat()},
        ).eq("id", document_id).is_("extracted_at", "null").execute()


def mark_document_quality_flag(
    client: Client,
    document_id: str,
    flag: str | None,
) -> None:
    client.table("cds_documents").update(
        {"data_quality_flag": flag},
    ).eq("id", document_id).execute()


def apply_extraction_quality_flag(
    client: Client,
    document_id: str,
    quality_flag: str | None,
) -> None:
    """Set the recoverable flag for this extraction, or clear a stale one."""
    if quality_flag:
        mark_document_quality_flag(client, document_id, quality_flag)
    else:
        clear_recoverable_quality_flag(client, document_id)


def clear_recoverable_quality_flag(client: Client, document_id: str) -> None:
    client.table("cds_documents").update(
        {"data_quality_flag": None},
    ).eq("id", document_id).in_(
        "data_quality_flag", ["blank_template", "low_coverage"],
    ).execute()


def _artifact_time(value: Any) -> datetime:
    """A PostgREST timestamp as an aware datetime (fraction digits vary)."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def has_canonical_for_current_bytes(
    client: Client,
    document_id: str,
    source_sha256: Optional[str],
) -> bool:
    """True if the document's NEWEST canonical artifact was produced from its
    current source bytes.

    The newest one is judged because it is the one that gets served: an older
    extraction of the current bytes does not help when a later one read a
    different file.

    An artifact that records the source it read (``notes.source_sha256``, or
    ``notes.source_selection.latest_sha256`` when an earlier fillable source
    was chosen over a flattened reprint) is matched on that. One that records
    nothing is attributed to the source that was current when it was written:
    the most recently archived source artifact at or before its
    ``created_at``, because extraction always downloads the document's current
    source.

    "Written after the current bytes were first archived" is not enough. A
    document can go from file A to file B and back to A (Penn State's slug was
    pointed at each campus's file in turn): an extraction of B was written
    after A was first archived, and counting it marked the document extracted
    while it still served B's values.

    When the current source artifact can't be identified (no source row
    matching the document's ``source_sha256``), this returns False so the
    document stays pending rather than being marked extracted against stale
    bytes.

    This is the gate for the reconcile pass — it answers "is this document
    actually extracted?" without paying the cost of re-running Docling.
    """
    if not source_sha256:
        return False
    rows = (
        client.table("cds_artifacts")
        .select(
            "kind,sha256,created_at,"
            "source_sha:notes->>source_sha256,"
            "selection_latest_sha:notes->source_selection->>latest_sha256"
        )
        .eq("document_id", document_id)
        .execute()
        .data
        or []
    )
    canonicals = [r for r in rows if r.get("kind") == "canonical"]
    if not canonicals or not any(
        r.get("kind") == "source" and r.get("sha256") == source_sha256 for r in rows
    ):
        return False
    newest = max(canonicals, key=lambda r: _artifact_time(r["created_at"]))
    if newest.get("source_sha"):
        return source_sha256 in (newest["source_sha"], newest.get("selection_latest_sha"))
    return _canonical_source_sha(newest, rows) == source_sha256


def _canonical_source_sha(canonical: dict[str, Any], rows: list[dict[str, Any]]) -> Optional[str]:
    """The source file a canonical artifact was made from: the hash it
    records, or failing that the source archived most recently at or before
    it was written. ``rows`` are the document's artifact rows."""
    if canonical.get("source_sha"):
        return canonical["source_sha"]
    # Sources in the order they were archived. Rows written at the same
    # instant keep the order the database returned them in.
    sources = sorted(
        ((_artifact_time(r["created_at"]), r.get("sha256")) for r in rows if r.get("kind") == "source"),
        key=lambda item: item[0],
    )
    written_at = _artifact_time(canonical["created_at"])
    current_then = [sha for archived_at, sha in sources if archived_at <= written_at]
    return current_then[-1] if current_then else None


def reconcile_pending_documents(
    client: Client,
    docs: list[dict[str, Any]],
    projection_definitions: Optional[dict],
    projection_enabled: bool,
    dry_run: bool,
) -> tuple[set[str], Counter]:
    """Cheap, extraction-free status repair.

    A document can sit in ``extraction_pending`` even though a valid canonical
    artifact of its current bytes already exists — e.g. after a producer-version
    requeue that the heavy drain never caught up on, or a worker run killed
    mid-batch. Those documents serve real data but the public ``cds_manifest``
    still reports "pending/processing" to users. This pass flips every such
    document to ``extracted`` with a single DB query per row and no Docling, so
    the symptom self-heals instead of persisting for weeks.

    Producer-version upgrades are intentionally NOT handled here: this only
    decides whether the current bytes have been extracted at all. Re-running a
    newer extractor over already-extracted bytes is a separate quality concern,
    driven explicitly via ``--force-reextract``, and must not hold a document in
    a user-visible "pending" state.

    Returns the set of reconciled document ids (to exclude from the heavy
    drain) and a Counter of outcomes.
    """
    reconciled: set[str] = set()
    counts: Counter = Counter()
    for doc in docs:
        document_id = str(doc["id"])
        if not has_canonical_for_current_bytes(
            client, document_id, doc.get("source_sha256")
        ):
            continue
        reconciled.add(document_id)
        counts["reconciled"] += 1
        if dry_run:
            continue
        mark_extraction_status(client, document_id, "extracted")
        # No extraction ran here, so quality state stays as the extraction
        # that produced the canonical left it. Clearing here unflagged
        # low-field docs during the 2026-06-01 reconcile.
        if projection_enabled and projection_definitions is not None:
            try:
                refresh_browser_projection(client, document_id, projection_definitions)
            except Exception as e:
                counts["projection_errors"] += 1
                message = str(e).splitlines()[0][:200]
                print(
                    f"    reconcile_projection_error: document={document_id} "
                    f"{type(e).__name__}: {message}",
                    file=sys.stderr,
                    flush=True,
                )
    return reconciled, counts


def write_source_metadata(
    client: Client,
    document_id: str,
    data: bytes,
    source_format: Optional[str],
) -> None:
    """Persist embedded source-file metadata to cds_documents.

    Best-effort — failures swallowed so metadata capture never blocks
    extraction. Reads /CreationDate, /ModDate, /Producer (PDF) or
    dcterms:created, dcterms:modified, /creator (XLSX) and writes to
    source_creation_date / source_modification_date / source_producer
    columns added by migration 20260505160000_archive_observability.sql.

    Why best-effort: pypdf and openpyxl both occasionally raise on
    malformed bytes. The extraction tier paths have their own error
    handling and would still proceed; this metadata is supplementary
    signal, not blocking. See tools/extraction_worker/source_metadata.py
    for the parsing logic.
    """
    try:
        from source_metadata import extract_source_metadata
        meta = extract_source_metadata(data, source_format)
    except Exception:
        return
    # Only write when we actually have non-null fields. An empty dict means
    # the format was HTML/DOCX/unknown or the bytes wouldn't parse — in
    # both cases we leave the columns alone rather than overwriting
    # potentially-good prior values with NULL.
    payload = {k: v for k, v in meta.items() if v is not None}
    if not payload:
        return
    try:
        client.table("cds_documents").update(payload).eq(
            "id", document_id,
        ).execute()
    except Exception:
        # Persistent failure shouldn't break extraction. Log via stderr
        # so operators see the issue in worker.log.
        print(
            f"    source_metadata: persist failed for {document_id} "
            f"({source_format})",
            file=sys.stderr,
            flush=True,
        )


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


def maybe_run_overlay(client: Client, doc: dict[str, Any]) -> None:
    """PRD 038: run the template overlay after the Tier 4 outcome, only when OVERLAY_WORKER_ENABLED is on (default off).

    The overlay package is imported lazily and only here, inside try/except: with the flag off nothing overlay-related
    is imported or run, and with the flag on a broken or missing overlay package is logged and ignored. Whatever
    happens, the document's status, quality flag, ledger item and projection are not touched.
    """
    import os

    if str(os.environ.get("OVERLAY_WORKER_ENABLED", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        from overlay_entry import run_overlay_in_loop

        result = run_overlay_in_loop(client, doc)
        if result is not None:
            print(
                f"    overlay: document={doc.get('id')} status={result.status} reason={result.reason}",
                flush=True,
            )
    except BaseException as e:  # noqa: BLE001 - nothing the overlay does may stop the drain (incl. SystemExit from a bad import)
        if isinstance(e, KeyboardInterrupt):
            raise
        print(f"    overlay_error: document={doc.get('id')} {type(e).__name__}", file=sys.stderr, flush=True)


def extract_one(
    client: Client,
    doc: dict,
    schema_registry: dict[str, tuple[Path, dict[str, Any]]],
    dry_run: bool,
    cell_maps: dict[str, dict[str, tuple[str, str]]] | None = None,
    force_reextract: bool = False,
) -> ExtractionOutcome:
    """Process a single cds_documents row. Returns a short action string
    for logging. Does NOT raise — every failure is caught and recorded
    as extraction_status='failed' with a category for the summary."""
    document_id = doc["id"]
    school_id = doc["school_id"]

    latest_source_artifact = fetch_latest_source_artifact(client, document_id)
    if not latest_source_artifact:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return extraction_no_project("no_source_artifact")
    storage_path = latest_source_artifact["storage_path"]

    try:
        latest_bytes = download_source(client, storage_path)
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed")
        return extraction_no_project(f"download_error: {e}")

    selection = select_source_for_extraction(
        client, document_id, latest_source_artifact, latest_bytes,
    )
    source_artifact = selection.source_artifact
    pdf_bytes = selection.source_bytes
    selection_note = selection.selection_note
    needs_review = selection.needs_review
    if selection_note:
        doc["source_selection"] = selection_note
        if needs_review:
            doc["needs_review"] = True
        print(
            f"    source_selection: school={school_id} document={document_id} "
            f"chosen={selection_note.get('chosen_sha256')} "
            f"candidate={selection_note.get('candidate_sha256')} "
            f"latest={selection_note.get('latest_sha256')} "
            f"match_ratio={selection_note.get('match_ratio')} "
            f"reason={selection_note.get('reason')} "
            f"needs_review={needs_review}",
            file=sys.stderr if needs_review else sys.stdout,
            flush=True,
        )

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
    if not detected_year:
        # The archive filed this document without a year and the strict
        # patterns did not settle one. See fallback_year_from_text.
        detected_year = fallback_year_for_unfiled_document(client, doc, pdf_bytes)
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
        # Activity is built after extract_one returns. Keep the in-memory
        # year in sync with the write so the ledger does not publish the
        # archive-time sentinel (often "unknown") after detection.
        doc["detected_year"] = detected_year

    canonical_year = canonical_year_for_doc(doc, detected_year)
    resolution = resolve_schema_for_year(canonical_year, schema_registry)
    if resolution.fallback_used:
        print(
            f"    schema_fallback: school={school_id} document={document_id} "
            f"canonical_year={canonical_year or 'unknown'} "
            f"using={resolution.schema_version} reason={resolution.fallback_reason}",
            flush=True,
        )

    source_format, format_corrected = choose_source_format(doc.get("source_format"), pdf_bytes)
    if format_corrected:
        print(
            f"    format_correction: school={school_id} document={document_id} "
            f"stored={doc.get('source_format') or 'null'} detected={source_format}",
            flush=True,
        )
    # Activity is built after extract_one returns. Preserve the byte-sniffed
    # route on the in-memory row when the database label was stale or null.
    doc["source_format"] = source_format

    form_resolution = resolve_schema_for_form(resolution, schema_registry, source_format, pdf_bytes)
    if form_resolution is not resolution:
        print(
            f"    schema_for_form: school={school_id} document={document_id} "
            f"canonical_year={canonical_year or 'unknown'} "
            f"using={form_resolution.schema_version} reason={form_resolution.fallback_reason}",
            flush=True,
        )
        resolution = form_resolution

    # Capture embedded source-file metadata (PDF /CreationDate, /ModDate,
    # /Producer or XLSX dcterms:created, dcterms:modified, /creator) and
    # persist to cds_documents. Best-effort: failures here never block
    # extraction. See tools/extraction_worker/source_metadata.py and
    # migration 20260505160000_archive_observability.sql.
    if not dry_run:
        write_source_metadata(client, document_id, pdf_bytes, source_format)

    # 2024-25 / 2025-26 templates ship a hidden lookup map. 2023-24 and older
    # official templates are visual-only, so build_cell_maps_for_schemas leaves
    # those years empty. Tier 1 still works for many filled workbooks via the
    # embedded Question Number / Answer column scanner — pass an empty map so
    # that fallback can run instead of hard-failing the cron on tier1_no_cell_map.
    if source_format == "xlsx":
        cell_map = dict((cell_maps or {}).get(resolution.schema_version) or {})
        if not cell_map:
            print(
                f"    tier1_no_template_map: school={school_id} "
                f"document={document_id} schema_version={resolution.schema_version}; "
                "trying workbook-native answer columns",
                flush=True,
            )
        return _run_tier1(
            client, document_id, school_id, pdf_bytes,
            source_format, resolution, cell_map, source_artifact, dry_run,
            force_reextract,
        )

    # Tier 6 (PRD 008): HTML → markdown → tier4_cleaner. Must run before
    # the "pdf_*" and "pdf_fillable" branches since the variable name
    # `pdf_bytes` is reused for raw source bytes regardless of format.
    if source_format == "html":
        from tier4_cleaner import SchemaIndex
        schema_index = SchemaIndex(resolution.schema_path)
        return _run_tier6(
            client, document_id, school_id, pdf_bytes,
            source_format, resolution, schema_index, source_artifact, dry_run,
            force_reextract,
        )

    # pdf_scanned routes to Tier 4 too — Docling's do_ocr=True lazily runs
    # OCR (default engine: EasyOCR) on pages with no extractable text, which
    # is exactly the pdf_scanned case. If OCR quality is insufficient, a
    # follow-up can add a dedicated Tier 5 path with force_full_page_ocr=True.
    if source_format in ("pdf_flat", "pdf_scanned"):
        from tier4_cleaner import SchemaIndex
        schema_index = SchemaIndex(resolution.schema_path)
        return _run_tier4(
            client, document_id, school_id, pdf_bytes,
            source_format, resolution, schema_index, source_artifact, dry_run,
            force_reextract, source_selection=selection_note,
        )

    if source_format != "pdf_fillable":
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"stub_{source_format}")

    # Tier 2 path.
    try:
        canonical = run_tier2(pdf_bytes, resolution.schema)
        attach_schema_metadata(canonical, resolution)
        attach_source_metadata(canonical, source_artifact)
        attach_source_selection(canonical, selection_note)
        unmapped_count = annotate_tier2_unmapped_fields(canonical)
        if unmapped_count:
            sample_tags = [
                item.get("pdf_tag")
                for item in (canonical.get("unmapped_fields") or [])[:5]
                if isinstance(item, dict)
            ]
            print(
                f"    tier2_unmapped_warning: school={school_id} "
                f"document={document_id} count={unmapped_count} "
                f"sample_tags={sample_tags}",
                file=sys.stderr,
                flush=True,
            )
        if should_fallback_tier2_to_tier4(canonical):
            print(
                f"    tier2_label_acroform_fallback: school={school_id} "
                f"document={document_id} "
                f"mapped={canonical.get('stats', {}).get('schema_fields_populated', 0)} "
                f"unmapped={unmapped_count}",
                file=sys.stderr,
                flush=True,
            )
            from tier4_cleaner import SchemaIndex
            schema_index = SchemaIndex(resolution.schema_path)
            outcome = _run_tier4(
                client, document_id, school_id, pdf_bytes,
                source_format, resolution, schema_index, source_artifact, dry_run,
                force_reextract, source_selection=selection_note,
            )
            return ExtractionOutcome(
                action=f"tier2_label_acroform_fallback_{outcome.action}",
                refresh_projection=outcome.refresh_projection,
                needs_review=outcome.needs_review or needs_review,
            )
    except Exception as e:
        if not dry_run:
            mark_extraction_status(client, document_id, "failed", source_format)
        return extraction_no_project(f"tier2_error: {e}")

    producer = canonical["producer"]
    producer_version = canonical["producer_version"]
    # Tier 2 never evaluated quality before; a fillable PDF of one section
    # was served as a full CDS.
    quality_flag = extraction_quality_flag(canonical)
    latest_sha256 = (
        selection_note.get("latest_sha256")
        if isinstance(selection_note, dict)
        else None
    )

    if not dry_run:
        if not force_reextract and artifact_already_extracted(
            client, document_id, producer, producer_version,
            resolution.schema_version, canonical.get("source_sha256"),
            latest_source_sha256=latest_sha256,
        ):
            # Idempotent re-run: the row was already extracted with this
            # producer version at some earlier point. Mark extracted and
            # move on without writing a duplicate.
            mark_extraction_status(client, document_id, "extracted", source_format)
            apply_extraction_quality_flag(client, document_id, quality_flag)
            return extraction_no_project("already_extracted", needs_review=needs_review)

        try:
            insert_canonical_artifact(client, document_id, canonical)
        except Exception as e:
            mark_extraction_status(client, document_id, "failed", source_format)
            return extraction_no_project(f"artifact_insert_error: {e}")

        mark_extraction_status(client, document_id, "extracted", source_format)
        apply_extraction_quality_flag(client, document_id, quality_flag)

    # Log a few headline stats from the canonical output for visibility.
    stats = canonical.get("stats") or {}
    _populated = stats.get("schema_fields_populated", 0)
    _total = stats.get("schema_fields_total", 0)
    _unmapped = stats.get("unmapped_acroform_fields", 0)
    action_prefix = "extracted_needs_review" if needs_review else "extracted"
    return extraction_success(
        f"{action_prefix} ({_populated}/{_total} fields, {_unmapped} unmapped)",
        needs_review=needs_review,
    )


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
        "--trigger",
        choices=("schedule", "dispatch", "operator"),
        default="operator",
        help="Closed run-origin label for the extraction activity ledger.",
    )
    parser.add_argument(
        "--run-url",
        default=None,
        help=(
            "Optional GitHub Actions run URL. The database allowlist drops "
            "all non-repository, query-string, and otherwise unsafe URLs."
        ),
    )
    parser.add_argument(
        "--replay-ledger-json",
        type=Path,
        default=None,
        help=(
            "Replay a normalized ledger-replay.json payload from a prior "
            "failed run without reprocessing documents."
        ),
    )
    parser.add_argument(
        "--schema",
        default=None,
        help=(
            "Debug override: force one CDS schema JSON for every document "
            "and disable year-aware schema dispatch for this run."
        ),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--deadline-minutes",
        type=float,
        default=None,
        help=(
            "Wall-clock budget. The worker stops the heavy drain gracefully "
            "before this many minutes elapse, writes its summary, and exits 0 "
            "instead of being hard-killed by a CI job timeout (which loses "
            "forward progress and reports the run as cancelled). Set it below "
            "the workflow's timeout-minutes."
        ),
    )
    parser.add_argument(
        "--reconcile-pending",
        action="store_true",
        help=(
            "Before the heavy drain, cheaply flip any extraction_pending "
            "document that already has a canonical artifact of its current "
            "source bytes to 'extracted' (no re-extraction). Repairs documents "
            "left stuck as 'pending/processing' in cds_manifest. Reconciled "
            "documents are excluded from the drain."
        ),
    )
    parser.add_argument("--school", default=None, help="Only process this school_id")
    parser.add_argument(
        "--document-ids",
        default=None,
        help=(
            "Comma-separated cds_documents.id values to process. Still honors "
            "extraction_status filtering, so use after requeueing extracted "
            "documents to extraction_pending."
        ),
    )
    parser.add_argument(
        "--requeue-document-ids",
        default=None,
        help=(
            "Comma-separated cds_documents.id values to process whatever their "
            "extraction_status. Their status is left alone until each one is "
            "re-extracted, so already-served data stays visible while the run "
            "works through the list. If --document-ids is omitted, these IDs "
            "also become the processing filter."
        ),
    )
    parser.add_argument(
        "--source-format",
        default=None,
        help=(
            "Comma-separated source_format filter, e.g. "
            "pdf_flat,pdf_scanned. Useful for scoped operator re-drains."
        ),
    )
    parser.add_argument(
        "--min-year-start",
        type=int,
        default=None,
        help=(
            "Only process rows whose detected_year/cds_year starts at or after "
            "this year, e.g. 2024. Applied before --limit."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-dependency-drift",
        action="store_true",
        help="Run even when installed packages or Python differ from requirements.lock",
    )
    parser.add_argument(
        "--accept-headline-loss",
        action="store_true",
        help=(
            "Write a Tier 4 re-extraction even when it loses headline C1 fields the previous "
            "extraction of the same file had. Use after checking that the old values were wrong."
        ),
    )
    parser.add_argument(
        "--accept-field-loss",
        action="store_true",
        help=(
            f"Write a Tier 4 re-extraction even when it ends {MIN_REEXTRACT_FIELDS_LOST} or more fields below "
            "the previous extraction of the same file. Use after checking that the lost values were wrong."
        ),
    )
    parser.add_argument(
        "--accept-table-loss",
        action="store_true",
        help=(
            f"Write a Tier 4 re-extraction even when one table loses {MIN_TABLE_VALUES_LOST} or more values and "
            "over half of what the previous extraction of the same file had. Use after checking the lost "
            "values against the PDF."
        ),
    )
    parser.add_argument(
        "--force-reextract",
        action="store_true",
        help=(
            "Write a fresh canonical artifact even when the same document, "
            "producer version, schema, and source hash were already extracted. "
            "Use for managed local re-drains after cleaner-only code changes."
        ),
    )
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
    named_documents = any(
        value.strip()
        for value in f"{args.document_ids or ''},{args.requeue_document_ids or ''}".split(",")
    )
    for switch in ("accept_headline_loss", "accept_field_loss", "accept_table_loss"):
        if getattr(args, switch) and not named_documents:
            # Each switch turns its guard off for every document in the run,
            # so it is only taken for documents named one by one.
            parser.error(f"--{switch.replace('_', '-')} needs --document-ids or --requeue-document-ids")
    global ACCEPT_HEADLINE_LOSS, ACCEPT_FIELD_LOSS, ACCEPT_TABLE_LOSS
    ACCEPT_HEADLINE_LOSS = bool(args.accept_headline_loss)
    ACCEPT_FIELD_LOSS = bool(args.accept_field_loss)
    ACCEPT_TABLE_LOSS = bool(args.accept_table_loss)

    from dependency_check import check_environment

    drift = check_environment()
    if drift:
        print(
            "environment does not match tools/extraction_worker/requirements.lock: "
            + "; ".join(drift[:12])
            + (f" (+{len(drift) - 12} more)" if len(drift) > 12 else ""),
            file=sys.stderr,
        )
        if not args.allow_dependency_drift:
            print(
                "rebuild: python3.12 -m venv .venv && .venv/bin/pip install -r "
                "requirements.lock (or pass --allow-dependency-drift)",
                file=sys.stderr,
            )
            return 2

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

    if args.replay_ledger_json:
        try:
            replay_extraction_ledger(client, args.replay_ledger_json)
            print(f"Replayed extraction ledger: {args.replay_ledger_json}")
            return 0
        except Exception as exc:
            message = str(exc).splitlines()[0][:200]
            print(
                f"extraction ledger replay failed: {type(exc).__name__}: {message}",
                file=sys.stderr,
            )
            return 2

    if args.detect_year_only:
        return run_detect_year_only(
            client,
            school_filter=args.school,
            limit=args.limit,
            write=args.write,
        )

    if args.schema:
        schema_path = Path(args.schema)
        schema = load_schema(schema_path)
        schema_version = str(schema.get("schema_version") or "override")
        schema_registry = {schema_version: (schema_path, schema)}
        print(
            f"WARNING: --schema override forces schema_version={schema_version} "
            "for every document; year-aware dispatch is disabled.",
            file=sys.stderr,
            flush=True,
        )
    else:
        schema_registry = load_schema_registry()
        print(
            "Loaded canonical schemas: "
            + ", ".join(sorted(schema_registry)),
            flush=True,
        )

    cell_maps = build_cell_maps_for_schemas(schema_registry)
    source_formats = [
        value.strip()
        for value in (args.source_format or "").split(",")
        if value.strip()
    ]
    document_ids = [
        value.strip()
        for value in (args.document_ids or "").split(",")
        if value.strip()
    ]
    requeue_document_ids = [
        value.strip()
        for value in (args.requeue_document_ids or "").split(",")
        if value.strip()
    ]
    if requeue_document_ids and not document_ids:
        document_ids = requeue_document_ids
    if requeue_document_ids:
        # Requeued documents are selected by id, not flipped to
        # extraction_pending up front: the site hides admissions figures for
        # pending documents, so a 500-document requeue used to blank those
        # pages for hours. Each document's status changes only when its own
        # extraction finishes.
        print(
            f"Requeued {len(requeue_document_ids)} document(s) for in-place "
            "re-extraction.",
            flush=True,
        )

    query = client.table("cds_documents").select(
        "id, school_id, school_name, ipeds_id, cds_year, detected_year, "
        "source_format, extraction_status, discovered_at, source_sha256",
    )
    drain_statuses = drain_extraction_statuses(args.include_failed)
    if not requeue_document_ids:
        query = query.in_("extraction_status", drain_statuses)
    if args.school:
        query = query.eq("school_id", args.school)
    if document_ids:
        query = query.in_("id", document_ids)
    if source_formats:
        query = query.in_("source_format", source_formats)
    query = query.order("school_id")

    run_id = str(uuid.uuid4())
    started_at = utc_now_iso()
    docs = select_drain_docs(
        query.execute().data or [], drain_statuses, requeue_document_ids,
    )
    if args.min_year_start is not None:
        docs = [
            doc for doc in docs
            if (row_start_year(doc) or 0) >= args.min_year_start
        ]
    docs = sorted(docs, key=pending_doc_priority_key)

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

    # Cheap status repair runs over the FULL pending set (before --limit), so a
    # single scheduled run heals the whole "stuck pending" backlog instead of
    # nibbling at it 25 rows a day. --force-reextract opts out: the operator
    # explicitly wants the bytes re-extracted, not short-circuited.
    reconcile_counts: Counter = Counter()
    changed_school_ids: set[str] = set()
    ledger_items: list[dict[str, Any]] = []
    if args.reconcile_pending and not args.force_reextract:
        reconciled_ids, reconcile_counts = reconcile_pending_documents(
            client,
            [d for d in docs if d.get("extraction_status") == "extraction_pending"],
            projection_definitions,
            projection_enabled,
            args.dry_run,
        )
        if reconciled_ids and not args.dry_run:
            changed_school_ids.update(
                str(d["school_id"])
                for d in docs
                if str(d["id"]) in reconciled_ids and d.get("school_id")
            )
        if reconciled_ids:
            verb = "Would reconcile" if args.dry_run else "Reconciled"
            print(
                f"{verb} {len(reconciled_ids)} already-extracted document(s) "
                "to 'extracted' (no re-extraction).",
                flush=True,
            )
            reconciled_at = utc_now_iso()
            reconcile_base = len(ledger_items)
            ledger_items.extend(
                extraction_ledger_item(
                    stamp_document_identity(client, doc, dry_run=args.dry_run),
                    "reconciled",
                    ordinal=reconcile_base + index,
                    force_reextract=False,
                    occurred_at=reconciled_at,
                )
                for index, doc in enumerate(
                    (
                        row
                        for row in docs
                        if str(row["id"]) in reconciled_ids
                    ),
                    1,
                )
            )
            docs = [d for d in docs if str(d["id"]) not in reconciled_ids]

    if args.limit:
        docs = docs[:args.limit]
    if not docs:
        print(
            "No rows left to drain"
            + (" after reconcile." if reconcile_counts.get("reconciled") else "."),
        )
        pending_remaining = count_extraction_pending(client)
        hit_reconcile_error = bool(reconcile_counts["projection_errors"])
        summary = with_heartbeat_fields({
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
            "review_docs": [],
            "extraction_counts": {},
            "projection_counts": dict(projection_counts),
            "reconcile_counts": dict(reconcile_counts),
            "stopped_early": False,
            "documents": [],
        }, stopped_reason=infer_stopped_reason(
            stopped_early=False,
            hit_error=hit_reconcile_error,
            limit=args.limit,
            processed_count=0,
            pending_remaining=pending_remaining,
        ), extracted=0, failed=0, pending_remaining=pending_remaining)
        notify_web_of_changed_schools(changed_school_ids, args.dry_run)
        ledger_ok = finalize_extraction_run(
            client,
            run_id=run_id,
            trigger=args.trigger,
            run_url=args.run_url,
            summary_path=args.summary_json,
            summary=summary,
            ledger_items=ledger_items,
            run_error_code=(
                "projection_error" if hit_reconcile_error else "none"
            ),
        )
        return 0 if ledger_ok and not hit_reconcile_error else 2

    print(
        f"Processing {len(docs)} document(s){' (dry run)' if args.dry_run else ''}...",
        flush=True,
    )

    deadline: datetime | None = None
    if args.deadline_minutes:
        deadline = utc_now() + timedelta(minutes=args.deadline_minutes)

    counts: Counter = Counter()
    summary_docs: list[dict[str, Any]] = []
    field_counts: list[int] = []
    low_field_docs: list[dict[str, Any]] = []
    review_docs: list[dict[str, Any]] = []
    failure_count = 0
    stopped_early = False
    for i, doc in enumerate(docs, 1):
        if deadline is not None and utc_now() >= deadline:
            remaining = len(docs) - (i - 1)
            print(
                f"Deadline reached ({args.deadline_minutes:g} min); stopping "
                f"gracefully with {remaining} document(s) unprocessed. Their "
                "extraction_status is unchanged and the next run will resume.",
                flush=True,
            )
            stopped_early = True
            break
        # extract_one is contracted not to raise, but schema/format setup
        # paths can still throw on a malformed or out-of-range document (e.g.
        # an old CDS year that resolves to a schema without a 'fields' key).
        # One bad row must not abort the whole drain and strand every
        # remaining document — mark it failed and keep going.
        doc = stamp_document_identity(client, doc, dry_run=args.dry_run)
        try:
            outcome = extract_one(
                client,
                doc,
                schema_registry,
                args.dry_run,
                cell_maps,
                force_reextract=args.force_reextract,
            )
        except Exception as e:
            if not args.dry_run:
                try:
                    mark_extraction_status(
                        client, str(doc["id"]), "failed", doc.get("source_format"),
                    )
                except Exception:
                    pass
            message = str(e).splitlines()[0][:200]
            print(
                f"    worker_error: school={doc.get('school_id')} "
                f"document={doc['id']} {type(e).__name__}: {message}",
                file=sys.stderr,
                flush=True,
            )
            outcome = extraction_no_project(f"worker_error: {type(e).__name__}: {message}")
        if not args.dry_run:
            maybe_run_overlay(client, doc)                 # PRD 038: flag off by default; never changes `outcome`
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
        if (
            not args.dry_run
            and not failed
            and outcome.refresh_projection
            and doc.get("school_id")
        ):
            changed_school_ids.add(str(doc["school_id"]))
        doc_needs_review = bool(outcome.needs_review or doc.get("needs_review"))
        if doc_needs_review:
            review_docs.append({
                "document_id": str(doc["id"]),
                "school_id": doc["school_id"],
                "source_format": doc.get("source_format"),
                "field_count": fields,
                "action": outcome.action,
                "source_selection": doc.get("source_selection"),
            })

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

        ledger_items.append(
            extraction_ledger_item(
                doc,
                outcome.action,
                ordinal=len(ledger_items) + 1,
                force_reextract=args.force_reextract,
            )
        )
        summary_doc: dict[str, Any] = {
            "document_id": str(doc["id"]),
            "school_id": doc["school_id"],
            "canonical_year": doc.get("detected_year") or doc.get("cds_year"),
            "source_format": doc.get("source_format"),
            "action": outcome.action,
            "field_count": fields,
            "failed": failed,
            "needs_review": doc_needs_review,
            "projection_field_count": projection_field_count,
            "projection_browser_row": projection_browser_row,
        }
        if doc.get("source_selection") is not None:
            summary_doc["source_selection"] = doc["source_selection"]
        summary_docs.append(summary_doc)
        print(f"[{i:4d}/{len(docs)}] {doc['school_id']}: {outcome.action}{projection_note}", flush=True)

    processed_count = sum(counts.values())

    print()
    if reconcile_counts.get("reconciled"):
        print(f"=== reconciled (no re-extraction): {reconcile_counts['reconciled']} ===")
    print("=== extraction results ===")
    for bucket, n in counts.most_common():
        print(f"  {bucket:30s} {n:5d}")
    print(f"  {'total':30s} {processed_count:5d}")
    if stopped_early:
        print(f"  {'(stopped at deadline)':30s}")
    if projection_enabled or projection_counts:
        print()
        print("=== browser projection refresh ===")
        for bucket in ("documents", "fields", "browser_rows", "errors", "setup_error"):
            if projection_counts[bucket]:
                print(f"  {bucket:30s} {projection_counts[bucket]:5d}")
    hit_projection_error = bool(
        projection_counts["errors"]
        or projection_counts["setup_error"]
        or reconcile_counts["projection_errors"]
    )
    pending_remaining = count_extraction_pending(client)
    extracted = max(0, processed_count - failure_count)
    summary = with_heartbeat_fields({
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "dry_run": args.dry_run,
        "limit": args.limit,
        "school": args.school,
        "include_failed": args.include_failed,
        "low_field_threshold": args.low_field_threshold,
        "processed_count": processed_count,
        "failure_count": failure_count,
        "mean_fields": mean_or_none(field_counts),
        "low_field_docs": low_field_docs,
        "review_docs": review_docs,
        "extraction_counts": dict(counts),
        "projection_counts": dict(projection_counts),
        "reconcile_counts": dict(reconcile_counts),
        "stopped_early": stopped_early,
        "documents": summary_docs,
    }, stopped_reason=infer_stopped_reason(
        stopped_early=stopped_early,
        hit_error=hit_projection_error,
        limit=args.limit,
        processed_count=processed_count,
        pending_remaining=pending_remaining,
    ), extracted=extracted, failed=failure_count, pending_remaining=pending_remaining)
    notify_web_of_changed_schools(changed_school_ids, args.dry_run)
    ledger_ok = finalize_extraction_run(
        client,
        run_id=run_id,
        trigger=args.trigger,
        run_url=args.run_url,
        summary_path=args.summary_json,
        summary=summary,
        ledger_items=ledger_items,
        run_error_code="projection_error" if hit_projection_error else "none",
    )
    if hit_projection_error or not ledger_ok:
        return 2
    return extraction_run_exit_code(failure_count)


if __name__ == "__main__":
    sys.exit(main())
