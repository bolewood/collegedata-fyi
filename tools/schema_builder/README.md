# schema_builder

Builds the canonical CDS schema JSON from the official commondataset.org Excel template.

## Why this exists

Every year, the Common Data Set Initiative publishes three fillable templates for schools to use: PDF, XLSX, and DOCX. All three reference the same underlying field set. The XLSX template is the convenient one for us because it ships with an `Answer Sheet` tab that lists every canonical field in one place, with:

- **Question Number** (`A.001`, `B.101`, `C.201`, …) — the stable CDS identifier
- **US News PDF Tag** (`CDS_NAME`, `AP_RECD_1ST_MEN_N`, `EN_FRSH_FT_MEN_N`, …) — the form-field name used by the PDF template's AcroForm widgets and by US News's distribution of the filled data
- **Word Tag** (`a0_first_name`, `c1_total_first_time_first_year_males_who_applied_total`, …) — the field name used by the DOCX template
- **Question text** — the human-readable prompt
- **Section / Sub-Section / Category / Student Group / Cohort / Residency / Unit load / Gender / Value type** — the structural metadata

This is `cds_schema_vN`. We do not hand-author it. We extract it.

The 2025-26 Answer Sheet has **1,105 fields across 10 sections**, with 1,089 having a PDF tag (the remaining 16 are computed totals that don't exist as AcroForm widgets because Excel/PDF derives them via formulas).

## What this script does

`build_from_xlsx.py` reads one CDS XLSX template and writes one canonical schema JSON.

1. Open the workbook with `openpyxl`
2. Find the `Answer Sheet` tab (error if the sheet name has changed — the script is strict about header layout so we notice if the CDS Initiative changes the template structure)
3. Validate the 15 expected column headers in row 1
4. Iterate every data row, keep rows that have a non-empty Question Number, drop the rest (header separators, blank rows)
5. Normalize empty cells to `null`, coerce the sort order to an integer
6. Flag rows with no PDF tag as `"computed": true` — these are canonical fields that exist as questions but are derived from sub-values rather than stored in a form field
7. Sort output by the template's Sort Order column, preserving authoring order for downstream consumers who want to render sections in the same order the template does
8. Write the result as pretty-printed JSON

## Usage

```bash
# From the repo root
python tools/schema_builder/build_from_xlsx.py \
    scratch/CDS-PDF-2025-2026-Excel_Template.xlsx \
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

A separate year-diff script could eventually produce `schemas/cds_schema_2024_25-to-2025_26.diff.json` listing added / removed / changed fields. Not built yet.

## Known limitations

1. **Strict header validation.** If the CDS Initiative reorders, renames, or adds columns to the Answer Sheet in a future year, this script will refuse to run until the `EXPECTED_HEADERS` list is updated. That is intentional — silently accepting a drifted template would produce a silently drifted schema. Update the constant when you verify the new template year.

2. **The XLSX template is the authority, not the PDF template.** The PDF has 1,089 AcroForm fields but the XLSX lists 1,105 canonical fields. The 16-row delta is canonical questions that don't have AcroForm widgets (computed totals). Both are "real" CDS fields from the consumer's point of view, but only one tier has automatic population.

3. **Licensing.** The Common Data Set is a collaborative open survey instrument with no published terms of service at commondataset.org. The CDS Initiative is a working group, not a rights-holder, and individual schools own the data inside their own filled CDS. Derived schemas produced by this script can ship in the public repo without further review. The official template files themselves still live in `scratch/` as working artifacts rather than being committed — they're harmless but they're not the publishable form, the schema JSON is.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — consumes the schema to extract values from fillable CDS PDFs
- [`tools/extraction-validator/`](../extraction-validator/) — scores any producer's output against hand-verified ground truth
- [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md) — the realization that this schema approach was possible
