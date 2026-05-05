"""
Tier 4 CDS extractor: convert a flattened PDF to markdown via Docling.

Flattened CDS PDFs have no AcroForm fields — the Tier 2 pypdf path
can't read them. Docling converts the visual layout back to structured
markdown using its PDF pipeline (layout analysis + TableFormer for
table structure recovery).

The output is raw markdown, not canonical question-number-keyed values.
A schema-targeting cleaner that maps Docling markdown → canonical CDS
fields is a follow-up. For now, the markdown is stored as-is in the
canonical artifact so the extraction_pending queue clears and consumers
can read the full CDS content in a structured text format.

Configuration: uses the tuned Tier 4 Docling config (TableFormer FAST,
OCR on but not forced, 1x DPI, orphan layout clusters disabled). The
no-orphan layout setting was selected in PRD 0111A's 2024-25+ spike because
it increased full-cleaner field recovery without introducing conflicts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PRODUCER_NAME = "tier4_docling"
PRODUCER_VERSION = "0.3.7"
DOCLING_CONFIG_NAME = "production-fast-no-orphan-clusters"
DOCLING_NATIVE_TABLES_VERSION = "docling_table_cells_compact_v1"
SCANNED_ADMISSIONS_OCR_MAX_PAGE = 35


def _extract_pdf_layout_text(pdf_path: Path) -> str:
    """Best-effort embedded-text layout supplement for Docling blind spots."""
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        chunks = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text(extraction_mode="layout") or "")
            except Exception:
                chunks.append(page.extract_text() or "")
        return "\n\n".join(chunks)
    except Exception:
        return ""


def _visual_ocr_candidate_pages(pdf_path: Path) -> list[int]:
    """Return 1-indexed pages where visual OCR can recover high-value fields.

    Some PDFs have a normal text layer for labels but render filled-in values
    as drawing commands. Docling and pypdf then see blank cells even though the
    source PDF visibly contains the numbers. Keep this supplement focused on
    admissions pages so low-field documents do not trigger a full-corpus OCR tax.
    """
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        pages: set[int] = set()
        triggers = (
            "c1. first-time",
            "first-time, first-year student applicants",
            "residency breakdowns for total applicants",
            "total first-time, first-year (degree-seeking) who applied",
            "c2. first time",
            "c2. first-time",
            "waiting listtotal",
            "c9. percent and number",
            "submitting sat scores",
        )
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            lowered = text.lower()
            if any(trigger in lowered for trigger in triggers):
                pages.add(idx)
        return sorted(pages)
    except Exception:
        return []


def _extract_visual_ocr_text(
    pdf_path: Path,
    *,
    fallback_page_count: int | None = None,
) -> tuple[str, list[int]]:
    """Best-effort Tesseract supplement for visually rendered table values."""
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        return "", []

    pages = _visual_ocr_candidate_pages(pdf_path)
    if not pages and fallback_page_count:
        pages = list(range(1, min(fallback_page_count, SCANNED_ADMISSIONS_OCR_MAX_PAGE) + 1))
    if not pages:
        return "", []

    chunks: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for page_no in pages:
            prefix = tmp / f"page_{page_no}"
            try:
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page_no),
                        "-l",
                        str(page_no),
                        "-png",
                        "-r",
                        "160",
                        str(pdf_path),
                        str(prefix),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                images = sorted(tmp.glob(f"page_{page_no}-*.png"))
                if not images:
                    continue
                ocr = subprocess.run(
                    ["tesseract", str(images[0]), "stdout", "--psm", "4"],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                ).stdout
            except Exception:
                continue
            if ocr.strip():
                chunks.append(f"\n\n--- OCR PAGE {page_no} ---\n{ocr}")
    return "\n".join(chunks), pages


def _needs_visual_ocr_supplement(markdown: str, values: dict[str, dict]) -> bool:
    if len(values) >= 100:
        return False
    c1_missing = (
        "first-time, first-year student" in markdown.lower()
        and not any(qn in values for qn in ("C.101", "C.117", "C.118", "C.119"))
    )
    c9_missing = (
        "submitting sat scores" in markdown.lower()
        and not any(qn in values for qn in ("C.901", "C.903", "C.905", "C.914"))
    )
    return c1_missing or c9_missing


def extract(
    pdf_path: Path,
    force_ocr: bool = False,
    schema=None,
    schema_version: str | None = None,
    schema_fallback_used: bool = False,
) -> dict:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        TableFormerMode,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = True
    # When force_ocr is set (pdf_scanned path), OCR every page with EasyOCR
    # explicitly. Docling's default "auto" OCR detection doesn't reliably
    # trigger on scanned PDFs in our corpus — verified on Kennesaw State
    # 2023-24 which produced 14 chars across 31 pages under auto mode but
    # full extracted content under force_full_page_ocr=True.
    if force_ocr:
        pipeline.ocr_options = EasyOcrOptions(force_full_page_ocr=True)
    pipeline.do_table_structure = True
    pipeline.table_structure_options.mode = TableFormerMode.FAST
    pipeline.table_structure_options.do_cell_matching = True
    pipeline.layout_options.create_orphan_clusters = False
    pipeline.images_scale = 1.0

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
    )

    result = converter.convert(str(pdf_path))
    doc = result.document
    markdown = doc.export_to_markdown()

    page_count = 0
    try:
        page_count = len(doc.pages)
    except Exception:
        pass

    # Run the schema-targeting cleaner to map markdown → canonical fields.
    from tier4_cleaner import clean
    from tier4_native_tables import compact_tables
    pdf_layout_text = _extract_pdf_layout_text(pdf_path)
    supplemental_text = pdf_layout_text
    values = clean(markdown, schema=schema, supplemental_text=supplemental_text)
    visual_ocr_text = ""
    visual_ocr_pages: list[int] = []
    if _needs_visual_ocr_supplement(markdown, values):
        # Scanned PDFs have no embedded text layer for pypdf to select pages
        # from. If Docling's full-page OCR still left admissions values blank,
        # use a bounded Tesseract pass over the front CDS sections instead of
        # silently skipping the visual supplement.
        fallback_page_count = page_count if force_ocr else None
        visual_ocr_text, visual_ocr_pages = _extract_visual_ocr_text(
            pdf_path,
            fallback_page_count=fallback_page_count,
        )
        if visual_ocr_text:
            # Put OCR first. Section slicers such as C9 stop at the first
            # C10 boundary they see; if embedded layout text comes first and
            # has blank cells, the later OCR repair block would be hidden.
            supplemental_text = f"{visual_ocr_text}\n\n{pdf_layout_text}"
            values = clean(markdown, schema=schema, supplemental_text=supplemental_text)
    native_tables = compact_tables(doc)

    artifact = {
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "schema_version": schema_version or getattr(schema, "schema_version", None) or "2025-26",
        "schema_fallback_used": schema_fallback_used,
        "docling_config": {
            "name": DOCLING_CONFIG_NAME,
            "do_ocr": pipeline.do_ocr,
            "force_ocr": force_ocr,
            "do_table_structure": pipeline.do_table_structure,
            "table_structure_mode": str(pipeline.table_structure_options.mode.value),
            "do_cell_matching": pipeline.table_structure_options.do_cell_matching,
            "layout_create_orphan_clusters": pipeline.layout_options.create_orphan_clusters,
            "native_tables_version": DOCLING_NATIVE_TABLES_VERSION,
        },
        "source_pdf": pdf_path.name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {
            "markdown_length": len(markdown),
            "page_count": page_count,
            "schema_fields_populated": len(values),
            "native_table_count": native_tables["table_count"],
            "native_table_cell_count": native_tables["cell_count"],
            "pdf_layout_text_length": len(pdf_layout_text),
            "visual_ocr_text_length": len(visual_ocr_text),
            "visual_ocr_pages": visual_ocr_pages,
        },
        "markdown": markdown,
        "native_tables": native_tables,
        "values": values,
    }
    return artifact


def extract_from_bytes(
    pdf_bytes: bytes,
    force_ocr: bool = False,
    schema=None,
    schema_version: str | None = None,
    schema_fallback_used: bool = False,
) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        return extract(
            Path(tmp.name),
            force_ocr=force_ocr,
            schema=schema,
            schema_version=schema_version,
            schema_fallback_used=schema_fallback_used,
        )
