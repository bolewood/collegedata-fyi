# schema_builder

Builds the canonical CDS schema JSON from the official commondataset.org Excel template.
It also contains the structural-schema and overlay helpers used for historical
template support.

## Why this exists

Every year, the Common Data Set Initiative publishes three fillable templates for schools to use: PDF, XLSX, and DOCX. All three reference the same underlying field set. The XLSX template is the convenient one for us because it ships with an `Answer Sheet` tab that lists every canonical field in one place, with:

- **Question Number** (`A.001`, `B.101`, `C.201`, …) — the stable CDS identifier
- **US News PDF Tag** (`CDS_NAME`, `AP_RECD_1ST_MEN_N`, `EN_FRSH_FT_MEN_N`, …) — the form-field name used by the PDF template's AcroForm widgets and by US News's distribution of the filled data
- **Word Tag** (`a0_first_name`, `c1_total_first_time_first_year_males_who_applied_total`, …) — the field name used by the DOCX template
- **Question text** — the human-readable prompt
- **Section / Sub-Section / Category / Student Group / Cohort / Residency / Unit load / Gender / Value type** — the structural metadata

This is `cds_schema_vN`. We do not hand-author it. We extract it.

The 2025-26 Answer Sheet has **1,105 fields across 10 sections**, with 1,089 having a PDF tag (the remaining 16 are computed totals that don't exist as AcroForm widgets because Excel/PDF derives them via formulas). The 2024-25 Answer Sheet is reduced: it has the canonical field list and structural metadata, but it omits `Sort Order`, `US News PDF Tag`, and `Word Tag`. The 2023-24 template has no Answer Sheet at all, so its canonical schema is synthesized from the 2024-25 canonical field map plus the 2023-24 fillable PDF's AcroForm tags.

## What this script does

`build_from_xlsx.py` reads one CDS XLSX template and writes one canonical schema JSON.

1. Open the workbook with `openpyxl`
2. Find the `Answer Sheet` tab (error if the sheet name has changed)
3. Map row 1 by header name, allowing known optional columns to be absent in reduced layouts
4. Iterate every data row, keep rows that have a non-empty Question Number, drop the rest (header separators, blank rows)
5. Normalize question numbers to the dotted canonical format (`A01` -> `A.001`, `C8G01` -> `C.8G01`)
6. Normalize empty cells to `null`, coerce the sort order to an integer where present, otherwise preserve worksheet order
7. Flag rows with no PDF tag as `"computed": true` only when the template actually has a PDF-tag column. Reduced layouts with no PDF-tag column emit `pdf_tag: null` without marking every field computed.
8. Sort output by the template's Sort Order column when present, preserving authoring order for downstream consumers who want to render sections in the same order the template does
9. Write the result as pretty-printed JSON

## Usage

```bash
# From the repo root
python tools/schema_builder/build_from_xlsx.py \
    schemas/templates/cds_2025-26_template.xlsx \
    schemas/cds_schema_2025_26.json
```

Expected output:

```
wrote schemas/cds_schema_2025_26.json
  schema_version: 2025-26
  total fields:   1105
  with pdf_tag:   1089
  computed:       16
  sections:       10
```

## Output JSON shape

```json
{
  "schema_version": "2025-26",
  "source_filename": "CDS-PDF-2025-2026-Excel_Template.xlsx",
  "source_note": "Extracted from the 'Answer Sheet' tab of ...",
  "extracted_at": "2026-04-13T06:29:00Z",
  "field_count": 1105,
  "sections": [
    "General Information",
    "Enrollment And Persistence",
    "First-Time, First-Year Admission",
    "Transfer Admission",
    "Academic Offerings and Policies",
    "Student Life",
    "Annual Expenses",
    "Financial Aid",
    "Instructional Faculty And Class Size",
    "Disciplinary Areas of Degrees Conferred"
  ],
  "fields": [
    {
      "sort_order": 1,
      "question_number": "A.001",
      "pdf_tag": "CDS_NAME",
      "word_tag": "a0_first_name",
      "question": "First Name:",
      "section": "General Information",
      "subsection": "Respondent Information",
      "category": "All",
      "student_group": "All",
      "cohort": "All",
      "residency": "All",
      "unit_load": "All",
      "gender": "All",
      "value_type": "Text",
      "computed": false
    }
  ]
}
```

`fields` is an ordered array, not a keyed object, so downstream consumers can iterate in authoring order. Build your own index on `question_number` or `pdf_tag` at load time — both are guaranteed unique within a single schema year.

## Year-to-year stability

The CDS changes modestly year-to-year. New years ship with their own Answer Sheet, and some field definitions get added, renamed, or removed. This script is meant to run once per template year, producing a new `schemas/cds_schema_{year}.json` artifact. Downstream tools should load the schema whose year matches the CDS year they are processing, not assume a single global schema.

PRD 014 defines the cross-year semantic diff format that classifies fields as `direct`, `derived`, `preserved-only`, or `unmapped`.

For a reduced Answer Sheet year such as 2024-25, run the canonical diff tool
before checkbox decoding so it can write validated `pdf_tag` values into the
source schema:

```bash
python tools/schema_builder/canonical_diff.py \
    schemas/cds_schema_2024_25.json \
    schemas/cds_schema_2025_26.json \
    schemas/cds_schema_2024_25-to-2025_26.diff.json \
    --source-pdf schemas/templates/cds_2024-25_template.pdf \
    --update-source-schema

python tools/schema_builder/decode_checkboxes.py \
    schemas/templates/cds_2024-25_template.pdf \
    schemas/cds_schema_2024_25.json
```

Generate the 2024-25 structural schema from the row-metadata per-section tabs:

```bash
python tools/schema_builder/build_from_tabs.py \
    schemas/templates/cds_2024-25_template.xlsx \
    schemas/cds_schema_2024_25.structural.json
```

For older template years that do not have an Answer Sheet, attach conservative
canonical overlays for the high-value C1/C7/C9 product slice:

```bash
python tools/schema_builder/build_core_table_overlay.py
```

The core table overlays map only rows whose semantics are clear against the
2025-26 canonical schema. Ambiguous drift, such as older "another gender" rows,
gender-specific residency breakdowns, or removed C7 factors without a 2025-26
equivalent, remains in `unmapped` with a reason for QA.

For 2023-24, build the structural schema from the archived XLSX and then build
the synthesized canonical schema from the 2024-25 canonical schema plus the
archived 2023-24 fillable PDF:

```bash
python tools/schema_builder/build_from_tabs.py \
    schemas/templates/cds_2023-24_template.xlsx \
    schemas/cds_schema_2023_24.structural.json

python tools/schema_builder/build_2023_24_canonical.py

python tools/schema_builder/decode_checkboxes.py \
    schemas/templates/cds_2023-24_template.pdf \
    schemas/cds_schema_2023_24.json
```

This is intentionally limited to 2023-24 for now. It drops the 2024-25
`Unknown` gender rows that do not exist in the 2023-24 template, assigns the
2023 PDF's `NON_BINARY` tags to the corresponding `Another Gender` canonical
rows, and validates every retained `pdf_tag` against the 2023 PDF form keys.

## Known limitations

1. **Known-header validation.** The script detects columns by header name, so reordered headers and the reduced 2024-25 layout are supported. Unknown headers still fail loudly because silently accepting a redesigned template would produce a silently drifted schema.

2. **The XLSX template is the authority, not the PDF template.** The PDF has 1,089 AcroForm fields but the XLSX lists 1,105 canonical fields. The 16-row delta is canonical questions that don't have AcroForm widgets (computed totals). Both are "real" CDS fields from the consumer's point of view, but only one tier has automatic population.

3. **Licensing and archival policy.** The Common Data Set is a collaborative open survey instrument with no published terms of service at commondataset.org. The CDS Initiative is a working group, not a rights-holder, and individual schools own the data inside their own filled CDS. Derived schemas produced by these scripts can ship in the public repo without further review. Official templates needed for reproducible canonical schema builds are archived in `schemas/templates/`; provenance and SHA-256 hashes are recorded in `schemas/templates/SOURCES.md`.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — consumes the schema to extract values from fillable CDS PDFs
- [`tools/extraction-validator/`](../extraction-validator/) — scores any producer's output against hand-verified ground truth
- [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md) — the realization that this schema approach was possible
