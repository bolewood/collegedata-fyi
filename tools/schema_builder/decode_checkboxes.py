"""
Extract AcroForm checkbox value sets from the blank CDS PDF template and
fold them into schemas/cds_schema_{year}.json as a `value_options` array
per field.

Run this once per schema year. It reads the already-built schema JSON
(from build_from_xlsx.py), opens the matching year's blank PDF template,
walks every button field's /_States_ list, pairs each state with a
human-readable label from a curated mapping table, and writes the
updated schema back to the same file.

After this runs, every schema entry whose PDF field is a checkbox or
radio group carries a value_options array like:

    "question_number": "C.701",
    "pdf_tag": "Q111_1",
    "value_options": [
        {"export": "/VI", "label": "Very Important"},
        {"export": "/I",  "label": "Important"},
        {"export": "/C",  "label": "Considered"},
        {"export": "/NC", "label": "Not Considered"},
        {"export": "/Off","label": "Not Selected"}
    ]

The Tier 2 extractor then uses these entries to decode raw AcroForm
export values into human-readable strings at extraction time. Raw
values are still preserved alongside the decoded labels so downstream
consumers can verify.

Usage:
    python tools/schema_builder/decode_checkboxes.py \\
        schemas/templates/cds_2025-26_template.pdf \\
        schemas/cds_schema_2025_26.json

The schema JSON is modified in-place. Run build_from_xlsx.py first if
you need to regenerate the base schema from scratch.
"""

import argparse
import json
import sys
from pathlib import Path

import pypdf


# Curated mapping from AcroForm export values to human-readable labels.
# Every export value the 2025-26 template's 224 button fields can
# actually produce is covered. Sources for ambiguous cases are noted
# inline. When the template changes in a new year, audit this table
# against `decode_checkboxes.py --dump-states` output and update.

LABELS: dict[str, str] = {
    # Generic unchecked state (appears in 156 of 224 button fields)
    "/Off": "Not Selected",

    # Simple checkbox "on" states
    "/X": "Yes",       # 96 fields — standard on-value for single checkboxes
    "/Y": "Yes",       # 80 fields — alternative on-value
    "/On": "Yes",      # 1 field — rare alternative
    "/N": "No",        # 27 fields — explicit "no" state (paired with /Y typically)
    "/Yes": "Yes",
    "/No": "No",
    "/N/A": "Not Applicable",

    # C7 admissions-factor importance (rigor, GPA, test scores, essays...)
    # Appears across Q111_* and Q112_* fields, 18+18+26+18 = 80 uses.
    "/VI": "Very Important",
    "/I": "Important",
    "/C": "Considered",
    "/NC": "Not Considered",

    # Transfer admission unit requirements (D-section)
    "/TFER_REQ": "Required",
    "/TFER_REC": "Recommended",
    "/TFER_RFS": "Required for Some",
    "/TFER_ROS": "Recommended for Some",
    "/TFER_NREQ": "Not Required",

    # First-time admission unit requirements (C-section)
    "/ADMS_REQ": "Required",
    "/ADMS_REC": "Recommended",
    "/ADMS_RFS": "Required for Some",
    "/ADMS_RFS ": "Required for Some",   # trailing-space variant (template quirk)
    "/ADMS_CONSIDER": "Considered",
    "/ADMS_CONSIDER ": "Considered",     # trailing-space variant (template quirk)
    "/ADMS_NOT_USED": "Not Used",

    # Generic test-policy states
    "/REQ": "Required",
    "/REC": "Recommended",

    # A2 Institutional control (self-labeled by the template)
    "/Public": "Public",
    "/Private (nonprofit)": "Private (nonprofit)",
    "/Proprietary": "Proprietary (for-profit)",

    # A3 Student body type (self-labeled)
    "/Coeducational college": "Coeducational",
    "/Men's college": "Men's college",
    "/Women's college": "Women's college",

    # A4 Academic calendar
    "/SEM": "Semester",
    "/QTR": "Quarter",
    "/TRI": "Trimester",
    "/414": "4-1-4",
    "/CON": "Continuous",
    "/DFR": "Differs by Program",
    "/Other": "Other",

    # A5 Degree types (the /X states paired with specific /Off entries)
    # no unique entries — they all use /X and /Off

    # C5 High-school completion
    "/GED": "GED",

    # C6 Open-admission policy (AD_OPEN_MOST field)
    "/O": "Open admission",
    "/S": "Open admission for most students",

    # C14 / D14 Application fee policy for online applications
    "/SAME": "Same fee as paper",
    "/FREE": "No fee for online",
    "/RED": "Reduced fee for online",

    # C21/C22 Notification date year (ACAD_YR field)
    "/2024": "2024",
    "/2023": "2023",

    # F ROTC programs
    # ROTC_ARMY / NAVY / AF states are /B and /C
    # The CDS template offers "On campus / At cooperating institution" options
    # for each service branch. /B is On campus (Base), /C is Cooperating.
    # Note: /C is shared with C7 "Considered" label above; it gets the correct
    # label based on the field context, which is why we look up LABELS[state]
    # per field rather than as a global dedup.
    "/MRN_OPT": "Marine Corps Option",

    # F5 Housing deposit refund (HOUS_DEPOSIT_REFUND field)
    # States are /F /P /N /N/A → Full / Partial / None / Not Applicable
    "/F": "Full refund",
    "/P": "Partial refund",

    # Generic "none" fallback
    "/NON": "None",
}

# State codes where the single letter has multiple meanings depending
# on which field it appears in. The decoder applies these per-field
# overrides when the field's pdf_tag matches.
#
# Structure: {pdf_tag: {export_value: override_label}}
PDF_TAG_OVERRIDES: dict[str, dict[str, str]] = {
    "ROTC_ARMY":  {"/B": "On campus",             "/C": "At cooperating institution"},
    "ROTC_NAVY":  {"/B": "On campus",             "/C": "At cooperating institution"},
    "ROTC_AF":    {"/B": "On campus",             "/C": "At cooperating institution"},
}


def load_button_states(pdf_path: Path) -> dict[str, list[str]]:
    """Return {pdf_tag: [state_1, state_2, ...]} for every button field."""
    reader = pypdf.PdfReader(str(pdf_path))
    fields = reader.get_fields()
    if fields is None:
        raise ValueError(f"{pdf_path} has no AcroForm fields")
    result: dict[str, list[str]] = {}
    for name, f in fields.items():
        if f.get("/FT") != "/Btn":
            continue
        states = f.get("/_States_")
        if not states:
            continue
        result[name] = list(states)
    return result


def label_for(pdf_tag: str, export: str) -> tuple[str, bool]:
    """Resolve the human-readable label for a given (pdf_tag, export_value).

    Returns (label, was_known). was_known is True when the export value
    was found in PDF_TAG_OVERRIDES or LABELS; False when the function
    fell back to stripping the leading slash off the export value."""
    overrides = PDF_TAG_OVERRIDES.get(pdf_tag, {})
    if export in overrides:
        return overrides[export], True
    if export in LABELS:
        return LABELS[export], True
    return export.lstrip("/"), False


def decode_schema(schema: dict, button_states: dict[str, list[str]]) -> tuple[int, list[tuple[str, str]]]:
    """Fold value_options into every schema field whose pdf_tag is a button.

    Returns (fields_decoded, unknown_state_pairs) where unknown_state_pairs
    is a list of (pdf_tag, export_value) tuples for states that fell
    through to the raw export-value fallback."""
    decoded = 0
    unknowns: list[tuple[str, str]] = []
    for field in schema["fields"]:
        pdf_tag = field.get("pdf_tag")
        if not pdf_tag:
            continue
        states = button_states.get(pdf_tag)
        if not states:
            continue
        value_options = []
        for state in states:
            label, was_known = label_for(pdf_tag, state)
            if not was_known:
                unknowns.append((pdf_tag, state))
            value_options.append({
                "export": state,
                "label": label,
            })
        field["value_options"] = value_options
        decoded += 1
    return decoded, unknowns


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("pdf", type=Path, help="Blank CDS PDF template for the schema year")
    parser.add_argument("schema", type=Path, help="schemas/cds_schema_{year}.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"error: {args.pdf} does not exist", file=sys.stderr)
        sys.exit(1)
    if not args.schema.exists():
        print(f"error: {args.schema} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Reading button states from {args.pdf}")
    states = load_button_states(args.pdf)
    print(f"  Found {len(states)} button fields")

    print(f"Loading schema from {args.schema}")
    schema = json.loads(args.schema.read_text())
    print(f"  {schema.get('field_count', len(schema['fields']))} canonical fields")

    decoded, unknowns = decode_schema(schema, states)
    print()
    print(f"Decoded value_options on {decoded} schema fields")
    if unknowns:
        print(f"  {len(unknowns)} state values fell back to raw export (not in LABELS table):")
        for pdf_tag, state in unknowns[:10]:
            print(f"    {state!r:<30} in field {pdf_tag}")
        if len(unknowns) > 10:
            print(f"    ... and {len(unknowns) - 10} more")

    # Show a sample of decoded fields
    sample = [f for f in schema["fields"] if "value_options" in f][:5]
    print()
    print("Sample decoded fields:")
    for f in sample:
        print(f"  {f['question_number']} ({f['pdf_tag']}):")
        for opt in f["value_options"]:
            print(f"    {opt['export']:<25} → {opt['label']}")
        print()

    if args.dry_run:
        print("Dry run — schema file not modified.")
        return

    args.schema.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote updated schema to {args.schema}")


if __name__ == "__main__":
    main()
