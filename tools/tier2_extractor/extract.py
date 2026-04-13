"""
Tier 2 CDS extractor: read AcroForm fields directly from a fillable CDS PDF.

The Common Data Set Initiative publishes a fillable PDF template with 1,089
named AcroForm fields. Schools that distribute the filled template without
flattening preserve those fields in the published PDF, which means their
values can be read deterministically with pypdf — no OCR, no layout parsing,
no LLM.

This is the Tier 2 extraction path. It works if and only if the source PDF
has a populated AcroForm. Flattened PDFs (Tier 4) require a separate layout
extractor. Always probe with `pypdf.get_fields()` before picking a pipeline.

Usage:
    python tools/tier2_extractor/extract.py \\
        scratch/CDS-HMC-2025.2026_shared.pdf \\
        schemas/cds_schema_2025_26.json

Output is a JSON document on stdout keyed by canonical CDS question number
(A.001, B.101, ...) joined to values read from the AcroForm. Populated
fields are emitted as strings; empty fields are omitted. The caller can
join against the full schema to see which canonical fields are missing.
"""

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pypdf


PRODUCER_NAME = "tier2_acroform"
PRODUCER_VERSION = "0.1.0"


def load_schema(schema_path: Path) -> dict:
    with schema_path.open() as f:
        return json.load(f)


def read_acroform(pdf_path: Path) -> dict:
    """Return {field_name: value_string} for every populated AcroForm field."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reader = pypdf.PdfReader(str(pdf_path))
        fields = reader.get_fields()
    if fields is None:
        return {}
    result = {}
    for name, field in fields.items():
        value = field.get("/V")
        if value is None:
            continue
        s = str(value).strip()
        if not s or s == "/":
            continue
        result[name] = s
    return result


def extract(pdf_path: Path, schema: dict) -> dict:
    acroform = read_acroform(pdf_path)

    tag_to_field = {f["pdf_tag"]: f for f in schema["fields"] if f["pdf_tag"]}

    values = {}
    unmapped = []
    for pdf_tag, raw in acroform.items():
        field = tag_to_field.get(pdf_tag)
        if field is None:
            unmapped.append({"pdf_tag": pdf_tag, "value": raw})
            continue
        values[field["question_number"]] = {
            "value": raw,
            "pdf_tag": pdf_tag,
            "word_tag": field.get("word_tag"),
            "question": field.get("question"),
            "section": field.get("section"),
            "subsection": field.get("subsection"),
            "value_type": field.get("value_type"),
        }

    schema_tags = set(tag_to_field)
    present_tags = set(acroform) & schema_tags

    return {
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "schema_version": schema.get("schema_version"),
        "source_pdf": pdf_path.name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": {
            "acroform_fields_total": len(acroform),
            "schema_fields_total": len(tag_to_field),
            "schema_fields_populated": len(present_tags),
            "unmapped_acroform_fields": len(unmapped),
        },
        "values": values,
        "unmapped_fields": unmapped,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("pdf", type=Path, help="Path to a CDS PDF")
    parser.add_argument("schema", type=Path, help="Path to a cds_schema JSON")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Write output here instead of stdout",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print a human-readable summary to stderr",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"error: {args.pdf} does not exist", file=sys.stderr)
        sys.exit(1)
    if not args.schema.exists():
        print(f"error: {args.schema} does not exist", file=sys.stderr)
        sys.exit(1)

    schema = load_schema(args.schema)
    result = extract(args.pdf, schema)

    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    else:
        print(payload)

    if args.summary:
        s = result["stats"]
        print(
            f"\n[{args.pdf.name}]\n"
            f"  acroform fields (populated): {s['acroform_fields_total']}\n"
            f"  schema fields total:         {s['schema_fields_total']}\n"
            f"  schema fields populated:     {s['schema_fields_populated']}"
            f" ({s['schema_fields_populated'] * 100 // max(s['schema_fields_total'], 1)}%)\n"
            f"  unmapped acroform tags:      {s['unmapped_acroform_fields']}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
