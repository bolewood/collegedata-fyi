"""
Build a canonical CDS schema JSON from the commondataset.org Excel template.

Reads the `Answer Sheet` tab of the official XLSX template and emits a
structured schema describing every canonical field in the CDS for that year.

The Answer Sheet is maintained by the Common Data Set Initiative and is
the authoritative source of truth for which fields exist, what their IDs
are, and how they map to PDF form-field names. Every version of the CDS
has its own Answer Sheet; this script is expected to run once per template
year.

Usage:
    python tools/schema_builder/build_from_xlsx.py \\
        scratch/CDS-PDF-2025-2026-Excel_Template.xlsx \\
        schemas/cds_schema_2025_26.json

The output is a JSON document with:
    - metadata (year, source filename, extracted_at)
    - sections: ordered list of section labels seen
    - fields: ordered list of field records, each containing question_number,
      pdf_tag, word_tag, question text, section metadata, value type,
      and a `computed` flag for canonical fields that are derived rather
      than stored in a form field.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl


ANSWER_SHEET_NAME = "Answer Sheet"
EXPECTED_HEADERS = [
    "Sort Order",
    "Question Number",
    "US News PDF Tag",
    "Word Tag",
    "Question",
    "Answer",
    "Section",
    "Sub-Section",
    "Category",
    "Student Group",
    "Cohort",
    "Residency",
    "Unit load",
    "Gender",
    "Value type",
]


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def build_schema(xlsx_path: Path) -> dict:
    wb = openpyxl.load_workbook(xlsx_path, data_only=False)
    if ANSWER_SHEET_NAME not in wb.sheetnames:
        raise ValueError(
            f"Workbook {xlsx_path} has no sheet named {ANSWER_SHEET_NAME!r}. "
            f"Sheets found: {wb.sheetnames}"
        )
    ws = wb[ANSWER_SHEET_NAME]

    header = [_clean(c.value) for c in ws[1]]
    for i, expected in enumerate(EXPECTED_HEADERS):
        if i >= len(header) or header[i] != expected:
            raise ValueError(
                f"Unexpected Answer Sheet header at column {i + 1}: "
                f"got {header[i]!r}, expected {expected!r}. "
                f"The template structure may have changed for a new CDS year."
            )

    fields = []
    sections_seen = []
    sections_set = set()

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 15:
            continue
        question_number = _clean(row[1])
        if not question_number:
            continue

        pdf_tag = _clean(row[2])
        section = _clean(row[6])

        if section and section not in sections_set:
            sections_set.add(section)
            sections_seen.append(section)

        field = {
            "sort_order": int(row[0]) if row[0] is not None else None,
            "question_number": question_number,
            "pdf_tag": pdf_tag,
            "word_tag": _clean(row[3]),
            "question": _clean(row[4]),
            "section": section,
            "subsection": _clean(row[7]),
            "category": _clean(row[8]),
            "student_group": _clean(row[9]),
            "cohort": _clean(row[10]),
            "residency": _clean(row[11]),
            "unit_load": _clean(row[12]),
            "gender": _clean(row[13]),
            "value_type": _clean(row[14]),
            "computed": pdf_tag is None,
        }
        fields.append(field)

    fields.sort(key=lambda f: f["sort_order"] if f["sort_order"] is not None else 10**9)

    return {
        "schema_version": _infer_year_from_filename(xlsx_path.name),
        "source_filename": xlsx_path.name,
        "source_note": (
            "Extracted from the 'Answer Sheet' tab of the commondataset.org "
            "Common Data Set Excel template. This file is derived from the "
            "CDS Initiative's canonical schema and reflects their field "
            "definitions; it is not hand-authored."
        ),
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "field_count": len(fields),
        "sections": sections_seen,
        "fields": fields,
    }


def _infer_year_from_filename(name: str) -> str:
    import re

    m = re.search(r"(\d{4})[-_](\d{4})", name)
    if m:
        y1, y2 = m.group(1), m.group(2)
        return f"{y1}-{y2[-2:]}"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("xlsx", type=Path, help="Path to the CDS XLSX template")
    parser.add_argument("output", type=Path, help="Path to write the schema JSON")
    args = parser.parse_args()

    if not args.xlsx.exists():
        print(f"error: {args.xlsx} does not exist", file=sys.stderr)
        sys.exit(1)

    schema = build_schema(args.xlsx)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(schema, f, indent=2)

    with_pdf_tag = sum(1 for f in schema["fields"] if f["pdf_tag"])
    computed = sum(1 for f in schema["fields"] if f["computed"])
    print(
        f"wrote {args.output}\n"
        f"  schema_version: {schema['schema_version']}\n"
        f"  total fields:   {schema['field_count']}\n"
        f"  with pdf_tag:   {with_pdf_tag}\n"
        f"  computed:       {computed}\n"
        f"  sections:       {len(schema['sections'])}"
    )


if __name__ == "__main__":
    main()
