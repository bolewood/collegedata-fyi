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
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PRODUCER_NAME = "tier4_docling"
PRODUCER_VERSION = "0.2.0"
DOCLING_CONFIG_NAME = "production-fast-no-orphan-clusters"
DOCLING_NATIVE_TABLES_VERSION = "docling_table_cells_compact_v1"


def extract(pdf_path: Path, force_ocr: bool = False) -> dict:
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
    values = clean(markdown)
    native_tables = compact_tables(doc)

    return {
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
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
        },
        "markdown": markdown,
        "native_tables": native_tables,
        "values": values,
    }


def extract_from_bytes(pdf_bytes: bytes, force_ocr: bool = False) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        return extract(Path(tmp.name), force_ocr=force_ocr)
