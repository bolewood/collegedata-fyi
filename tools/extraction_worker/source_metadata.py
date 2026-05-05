"""Capture embedded source-file metadata at extraction time.

Reads /CreationDate, /ModDate, /Producer from PDFs and dcterms:created,
dcterms:modified, /creator from XLSX docProps. The result is a small dict
that worker.py persists to cds_documents:

  - source_creation_date    (PDF /CreationDate or XLSX dcterms:created)
  - source_modification_date (PDF /ModDate     or XLSX dcterms:modified)
  - source_producer          (PDF /Producer    or XLSX /creator)

Why this matters: HTTP Last-Modified (captured at archive time by
supabase/functions/_shared/archive.ts) reflects the upload-to-school-
website timestamp. The embedded modification date reflects when the
school finalized the content. Both signals together let downstream
freshness audits and PRD 019's change-intelligence layer reason about
what's genuinely new vs. what's been sitting on the server. They also
fingerprint template usage cleanly (e.g., the 2025-26 CDS Initiative
XLSX template's dcterms:created is 2025-09-26; schools that inherit
the template show that exact date).

Failure mode: any error parsing metadata is swallowed and returns an
empty dict. Metadata capture must never block extraction — bad bytes
that pypdf or openpyxl can't open will still be picked up by the
extractor's main path with its own error handling.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any, Optional


# PDF /CreationDate format per PDF 1.7 §7.9.4: D:YYYYMMDDHHmmSSOHH'mm'
# Examples:
#   D:20260423094838-04'00'        (timezone-aware, UTC-4)
#   D:20251015192248+08'00'        (timezone-aware, UTC+8)
#   D:20260423094838Z              (Zulu/UTC — no hour/minute after Z)
#   D:20260423094838               (timezone-naive — treated as UTC)
#
# The two offset shapes (Z-alone vs ±HH or ±HH'mm') are different lengths,
# so we use an alternation rather than trying to make HH/mm optional after
# the sign character — that way "Z" alone is a clean match instead of
# being mis-fitted as "Z + missing digits."
_PDF_DATE_RE = re.compile(
    r"^D:?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
    r"(?:(Z)|([+-])(\d{2})(?:'?(\d{2}))?'?)?$"
)


def parse_pdf_date(raw: Optional[str]) -> Optional[str]:
    """Parse a PDF date string into ISO 8601. Returns None on any failure.

    PDF dates are awful: PDF 1.7's spec is permissive about which fields
    are present, and pypdf returns the raw string verbatim including the
    leading "D:" prefix. We accept partial dates (year-only is valid) and
    coerce to UTC ISO 8601 so Postgres timestamptz can parse cleanly.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    m = _PDF_DATE_RE.match(text)
    if not m:
        return None
    year, month, day, hour, minute, second, zulu, tz_sign, tz_h, tz_m = m.groups()
    try:
        y = int(year)
        if y < 1900 or y > 2200:
            return None
        dt = datetime(
            y,
            int(month or 1),
            int(day or 1),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            tzinfo=timezone.utc,
        )
    except (ValueError, TypeError):
        return None

    # Apply timezone offset if present. PDF stores local-time + offset;
    # we shift to UTC so all stored timestamps are comparable. Zulu and
    # naive both mean "already in UTC."
    if zulu == "Z" or tz_sign is None:
        return dt.isoformat()
    try:
        offset_minutes = int(tz_h) * 60 + int(tz_m or 0)
    except (ValueError, TypeError):
        return dt.isoformat()
    if tz_sign == "-":
        offset_minutes = -offset_minutes
    # The local datetime was constructed as if it were UTC; subtract the
    # offset to get true UTC.
    from datetime import timedelta
    return (dt - timedelta(minutes=offset_minutes)).isoformat()


def _datetime_to_iso(value: Any) -> Optional[str]:
    """Convert openpyxl's naive UTC datetime (or any datetime) to ISO 8601."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return None


def extract_pdf_metadata(data: bytes) -> dict[str, Optional[str]]:
    """Extract embedded metadata from PDF bytes via pypdf.

    Returns a dict with keys source_creation_date, source_modification_date,
    source_producer. All values nullable. Empty dict on any error so the
    caller can merge unconditionally.
    """
    try:
        import pypdf  # type: ignore
    except ImportError:
        return {}
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        meta = reader.metadata or {}
    except Exception:
        return {}

    creation = parse_pdf_date(meta.get("/CreationDate"))
    modified = parse_pdf_date(meta.get("/ModDate"))
    # /Producer (rendering software) is more useful than /Creator (authoring
    # software) for fingerprinting; both are nullable strings up to ~80 chars.
    producer = meta.get("/Producer")
    if producer is not None:
        producer = str(producer).strip()[:200] or None

    return {
        "source_creation_date": creation,
        "source_modification_date": modified,
        "source_producer": producer,
    }


def extract_xlsx_metadata(data: bytes) -> dict[str, Optional[str]]:
    """Extract docProps metadata from XLSX bytes via openpyxl.

    XLSX stores dcterms:created and dcterms:modified as ISO datetimes,
    plus dc:creator and cp:lastModifiedBy as strings. We surface
    dcterms:* as the date pair and dc:creator as the producer-equivalent.
    """
    try:
        from openpyxl import load_workbook  # type: ignore
    except ImportError:
        return {}
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        props = wb.properties
    except Exception:
        return {}

    creator = props.creator
    if creator is not None:
        creator = str(creator).strip()[:200] or None

    return {
        "source_creation_date": _datetime_to_iso(props.created),
        "source_modification_date": _datetime_to_iso(props.modified),
        "source_producer": creator,
    }


def extract_source_metadata(
    data: bytes,
    source_format: Optional[str],
) -> dict[str, Optional[str]]:
    """Single entry point used by worker.py.

    Routes to the right extractor based on source_format. Returns an
    empty dict for HTML, DOCX (not yet implemented), or unknown formats —
    which is the correct "no embedded date available" answer for those.
    Never raises; bad bytes / missing libs / unknown formats all collapse
    to {} so the caller can merge unconditionally.
    """
    if not data or not source_format:
        return {}
    fmt = source_format.lower()
    if fmt in ("pdf_flat", "pdf_fillable", "pdf_scanned"):
        return extract_pdf_metadata(data)
    if fmt == "xlsx":
        return extract_xlsx_metadata(data)
    # html, docx, and anything else: no embedded date in a useful shape.
    return {}
