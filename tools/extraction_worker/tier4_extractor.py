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

Configuration: uses the "baseline" Docling config (TableFormer FAST,
OCR on but not forced, 1x DPI) which scored 21/21 on critical C1
fields across 3 schools in the bake-off. See
tools/extraction-validator/bakeoff-results.md for the full comparison.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PRODUCER_NAME = "tier4_docling"
PRODUCER_VERSION = "0.1.0"


def extract(pdf_path: Path) -> dict:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = True
    pipeline.do_table_structure = True
    pipeline.table_structure_options.mode = TableFormerMode.FAST
    pipeline.table_structure_options.do_cell_matching = True
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
    values = clean(markdown)

    return {
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "source_pdf": pdf_path.name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {
            "markdown_length": len(markdown),
            "page_count": page_count,
            "schema_fields_populated": len(values),
        },
        "markdown": markdown,
        "values": values,
    }


def extract_from_bytes(pdf_bytes: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        return extract(Path(tmp.name))
