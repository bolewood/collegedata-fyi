"""
Build the canonical 2023-24 CDS schema.

The 2023-24 XLSX template does not include the machine-readable Answer Sheet
used by 2024-25 and later years. It does, however, share the 2024-25 canonical
field ordering closely, and the 2023-24 fillable PDF publishes the AcroForm
field names. This script synthesizes a rebuildable canonical schema by:

  1. using the 2024-25 canonical schema as the field identity base,
  2. validating/rewriting PDF tags against the 2023-24 PDF AcroForm keys,
  3. converting the 2024-25 Unknown-gender rows to the 2023-24 Another Gender
     rows where the PDF uses NON_BINARY tags, and
  4. dropping the 2024-25 Unknown-gender rows that are not present in 2023-24.

Usage:
    python tools/schema_builder/build_2023_24_canonical.py
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pypdf


DEFAULT_BASE_SCHEMA = Path("schemas/cds_schema_2024_25.json")
DEFAULT_PDF = Path("schemas/templates/cds_2023-24_template.pdf")
DEFAULT_OUTPUT = Path("schemas/cds_schema_2023_24.json")


def load_pdf_field_names(pdf_path: Path) -> set[str]:
    reader = pypdf.PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    return set(fields)


def nonbinary_tag_for_unknown_tag(pdf_tag: str | None, pdf_tags: set[str]) -> str | None:
    if not pdf_tag:
        return None
    candidates = [
        pdf_tag.replace("_UNK_", "_NON_BINARY_"),
        re.sub(r"_UNK_N$", "_NON_BINARY_N", pdf_tag),
    ]
    for candidate in candidates:
        if candidate in pdf_tags:
            return candidate
    return None


def previous_another_gender_field(
    fields_by_qnum: dict[str, dict[str, Any]],
    question_number: str,
) -> dict[str, Any] | None:
    section, raw_number = question_number.split(".", 1)
    if not raw_number.isdigit():
        return None
    previous = fields_by_qnum.get(f"{section}.{int(raw_number) - 1:03d}")
    if previous and previous.get("gender") == "Another Gender":
        return previous
    return None


DIMENSION_KEYS = [
    "section",
    "subsection",
    "category",
    "student_group",
    "cohort",
    "residency",
    "unit_load",
    "value_type",
]


def dimension_signature(field: dict[str, Any]) -> tuple[str | None, ...]:
    return tuple(field.get(key) for key in DIMENSION_KEYS)


def synthesize_schema(
    base_schema: dict[str, Any],
    pdf_tags: set[str],
    *,
    pdf_source_name: str,
) -> dict[str, Any]:
    fields = [copy.deepcopy(field) for field in base_schema["fields"]]
    fields_by_qnum = {field["question_number"]: field for field in fields}
    another_by_signature: dict[tuple[str | None, ...], list[dict[str, Any]]] = {}
    for field in fields:
        if field.get("gender") == "Another Gender":
            another_by_signature.setdefault(dimension_signature(field), []).append(field)

    drop_qnums: set[str] = set()
    nonbinary_tags_assigned = 0

    for field in fields:
        if field.get("gender") != "Unknown":
            continue

        replacement_tag = nonbinary_tag_for_unknown_tag(field.get("pdf_tag"), pdf_tags)
        matches = another_by_signature.get(dimension_signature(field), [])
        target = matches[0] if len(matches) == 1 else None
        if target is None:
            target = previous_another_gender_field(fields_by_qnum, field["question_number"])
        if replacement_tag and target:
            target["pdf_tag"] = replacement_tag
            target["computed"] = False
            nonbinary_tags_assigned += 1
        drop_qnums.add(field["question_number"])

    synthesized_fields: list[dict[str, Any]] = []
    for field in fields:
        if field["question_number"] in drop_qnums:
            continue

        pdf_tag = field.get("pdf_tag")
        if pdf_tag == "EN_TOT_UG_N" and "EN_TOT _UG_N" in pdf_tags:
            field["pdf_tag"] = "EN_TOT _UG_N"
            field["computed"] = False
        elif pdf_tag and pdf_tag not in pdf_tags:
            field["pdf_tag"] = None

        if field.get("pdf_tag") is None:
            field.pop("value_options", None)
        synthesized_fields.append(field)

    schema = {
        "schema_version": "2023-24",
        "source_filename": "cds_2023-24_template.xlsx + cds_2023-24_template.pdf",
        "source_note": (
            "Synthesized from the 2024-25 canonical schema, the 2023-24 "
            "per-section XLSX structural template, and 2023-24 PDF AcroForm "
            f"field names from {pdf_source_name}. The 2023-24 template has no "
            "Answer Sheet tab, so field identity is inherited from the closest "
            "canonical predecessor and corrected for 2023-24 gender fields."
        ),
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "field_count": len(synthesized_fields),
        "sections": copy.deepcopy(base_schema.get("sections", [])),
        "fields": synthesized_fields,
        "synthesis": {
            "base_schema_version": base_schema.get("schema_version"),
            "pdf_field_count": len(pdf_tags),
            "unknown_gender_fields_dropped": len(drop_qnums),
            "nonbinary_pdf_tags_assigned": nonbinary_tags_assigned,
        },
    }
    return schema


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-schema", type=Path, default=DEFAULT_BASE_SCHEMA)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    base_schema = json.loads(args.base_schema.read_text())
    pdf_tags = load_pdf_field_names(args.pdf)
    schema = synthesize_schema(base_schema, pdf_tags, pdf_source_name=args.pdf.name)

    args.output.write_text(json.dumps(schema, indent=2) + "\n")

    tagged = sum(1 for field in schema["fields"] if field.get("pdf_tag"))
    print(f"wrote {args.output}")
    print(f"  schema_version: {schema['schema_version']}")
    print(f"  total fields:   {schema['field_count']}")
    print(f"  with pdf_tag:   {tagged}")
    print(f"  source fields:  {schema['synthesis']['pdf_field_count']}")
    print(f"  dropped unk:    {schema['synthesis']['unknown_gender_fields_dropped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
