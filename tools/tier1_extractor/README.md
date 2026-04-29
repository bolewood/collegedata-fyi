# tier1_extractor

Deterministic CDS extraction from filled Excel workbooks via the template's cell-position map.

## Why this exists

The Common Data Set Initiative publishes an Excel template each year with section tabs (`CDS-A` through `CDS-J`) where schools fill in their values. The template also has an `Answer Sheet` tab with hidden lookup columns (`AA` = question number, `AC` = formula pointing at the answer cell on the matching section tab) that assemble every canonical field into one flat list.

Most filled XLSX files published by schools **strip the Answer Sheet** — they only ship the section tabs with data in the exact cell positions the template reserved. That makes the Answer Sheet useless as a direct key, but the template's formulas tell us exactly which cell holds each canonical field's answer. Parse the template once, apply the resulting `(sheet, cell)` map to any filled XLSX, and you get deterministic extraction with no layout parsing and no fuzzy matching.

This is the **Tier 1** extraction path:

| Tier | Input | Extractor | Accuracy |
|---|---|---|---|
| **Tier 1** | **Filled XLSX** | **this tool** | **~100% when school uses the standard template** |
| Tier 2 | Unflattened fillable PDF | `tools/tier2_extractor/` | ~100% when AcroForm is populated |
| Tier 3 | Filled DOCX | `tools/tier3_extractor/` (PRD 007) | ~100% when SDTs preserved |
| Tier 4 | Flattened PDF | Docling + cleaner | 94% on ground-truth fields |
| Tier 5 | Image-only scan | Tier 4 with force-OCR | variable |

## How it works

`build_cell_map(template_path)` opens the template in formula mode (not data-only). For the 2025-26 template, it walks every `CDS-*` sheet's hidden columns AA and AC, and parses each `=IF($D$4<>"",$D$4,"")`-style formula to extract the target cell reference. For the reduced 2024-25 answer sheet, where the hidden formula columns are not published, it falls back to the section-tab layout and maps each visible `Question Number` row to the adjacent `Answer` cell. The result is a `{question_number: (sheet_name, cell_ref)}` map with one entry per schema field for the selected template year.

`extract(xlsx_path, schema, cell_map)` opens the filled workbook in data-only mode, reads the value at each mapped cell, and emits canonical JSON keyed by `question_number`. Missing sheets are flagged in the stats; missing cells count as empty.

The extraction worker computes one cell map per canonical schema at startup and picks the map that matches the document's resolved schema year. Parsing each template takes ~2s; extracting a filled workbook takes ~1s.

## Usage

```bash
cd tools/tier1_extractor

# Extract canonical JSON to stdout
python extract.py \
    path/to/filled.xlsx \
    ../../schemas/cds_schema_2025_26.json

# Write to file, print summary to stderr
python extract.py \
    path/to/filled.xlsx \
    ../../schemas/cds_schema_2025_26.json \
    --output /tmp/extracted.json \
    --summary

# Use a non-default template
python extract.py \
    path/to/filled.xlsx \
    ../../schemas/cds_schema_2025_26.json \
    --template path/to/other-template.xlsx
```

Example summary:

```
[MissouriS-and-T-CDS 2025-26 Gold for Posting.xlsx]
  cell map fields:         1105
  schema fields populated: 711 (64%)
  empty cells:             394
  missing sheets:          []
```

## Output shape

```json
{
  "producer": "tier1_xlsx",
  "producer_version": "0.1.0",
  "schema_version": "2025-26",
  "source_xlsx": "MissouriS-and-T-CDS 2025-26 Gold for Posting.xlsx",
  "extracted_at": "2026-04-20T17:00:00Z",
  "stats": {
    "cell_map_fields_total": 1105,
    "schema_fields_populated": 711,
    "empty_cells": 394,
    "missing_sheets": []
  },
  "values": {
    "A.001": {
      "value": "Rachel",
      "word_tag": "a0_first_name",
      "question": "First Name:",
      "section": "General Information",
      "subsection": "Respondent Information",
      "value_type": "Text"
    }
  }
}
```

Same shape as Tier 2's output (keyed by canonical `question_number`) so downstream consumers don't have to care which tier produced a given artifact.

## Tested against

| XLSX | Fields populated | Result |
|---|---:|---|
| Missouri S&T 2025-26 | 711 / 1105 (64%) | End-to-end dry run, every sampled value matches source |
| Aims Community College 2022-23 | 274 / 1105 (25%) | Drain pass |
| Adelphi University (multiple years) | 36-58 | Drain pass, older template years |

Corpus-wide: **289 tier1_xlsx artifacts** written across the first full drain (2026-04-20), median 307 fields populated, max 782.

## Known gaps

1. **Only shipped canonical years get deterministic maps.** The worker currently ships 2024-25 and 2025-26 templates. Filled XLSXs from 2019-20 or other unshipped years can use different cell positions; those docs fall back to the latest known schema unless a template/schema pair is added for that year.
2. **Custom template variants.** Some schools post an Excel file that looks like a CDS but uses a custom layout (no standard section tabs, or renamed tabs). These fail with `"File contains no valid workbook part"` or populate zero fields. Route them to Tier 4 via PDF conversion as a fallback.
3. **Format-sniffer false positives.** The worker's `sniff_format_from_bytes` currently returns `xlsx` for any ZIP file starting with `PK\x03\x04` — including DOCX files. When Tier 1 hits a DOCX, openpyxl raises `"File contains no valid workbook part"` and the worker marks the doc failed. PRD 007 adds an inner-file-list peek to the sniffer so DOCX routes to Tier 3 instead.
4. **No type coercion.** Every value is emitted as a string, matching the Tier 2 pattern. Downstream consumers coerce per field using the schema's `value_type` metadata.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — the AcroForm Tier 2 extractor; Tier 1 mirrors its output shape
- [`tools/schema_builder/`](../schema_builder/) — builds the canonical schema JSON from the same Excel template
- [`schemas/templates/cds_2024-25_template.xlsx`](../../schemas/templates/) and [`schemas/templates/cds_2025-26_template.xlsx`](../../schemas/templates/) — templates Tier 1 parses for year-specific cell maps
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — tier ladder rationale
