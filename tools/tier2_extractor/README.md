# tier2_extractor

Deterministic CDS extraction from fillable PDFs via AcroForm fields.

## Why this exists

The Common Data Set Initiative publishes a fillable PDF template each year. Schools that distribute the filled template **without flattening** preserve the 1,089 named AcroForm form fields in their published PDF. Those field names are canonical (`AP_RECD_1ST_MEN_N`, `EN_FRSH_FT_WMN_N`, …) and map one-to-one with entries in the [`schemas/cds_schema_{year}.json`](../../schemas/) artifact produced by [`tools/schema_builder/`](../schema_builder/).

When a PDF has a populated AcroForm, extraction is a 20-line job: read the fields with `pypdf.get_fields()`, join against the schema, emit canonical JSON keyed by question number (`A.001`, `B.101`, `C.101`, …). No OCR. No layout parsing. No LLM. No ambiguity. The published values are exactly what the school entered.

This is the **Tier 2** extraction path in the project's tiered strategy:

| Tier | Input | Extractor | Accuracy |
|---|---|---|---|
| Tier 1 | Filled XLSX | `openpyxl` → Answer Sheet | ~100% when available, but no schools are known to publish this format |
| **Tier 2** | Unflattened fillable PDF | **this tool** | **~100% when AcroForm is populated** |
| Tier 3 | Filled DOCX | `python-docx` → Word tags | ~100% when available (not yet observed in the wild) |
| Tier 4 | Flattened PDF | Docling/Reducto + cleaner | variable, hard path |
| Tier 5 | Image-only scan | OCR + cleaner | worst case |

Tier 2 works if and only if `pypdf.get_fields()` returns a non-empty dict for the source PDF. Flattened PDFs (Yale 2024-25, Harvard 2024-25) return `None` and need Tier 4. The scraper should probe every incoming PDF with this check first before routing to a heavier pipeline.

## Origin story

This tool exists because of a realization we should have had earlier: Harvey Mudd's 2025-26 CDS, the exact school our initial Docling audit documented as "degraded with real data corruption" (see [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md)), is an unflattened fillable PDF with **1,026 AcroForm fields and 558 populated**. Every ground-truth value Docling misaligned is sitting in a named form field that `pypdf.get_fields()` reads correctly. The C1 row-shift "Docling bug" was never a bug at the source. We were using the wrong tool on a source that had structured data ready to read.

## Usage

```bash
# Extract canonical JSON to stdout
python tools/tier2_extractor/extract.py \
    scratch/CDS-HMC-2025.2026_shared.pdf \
    schemas/cds_schema_2025_26.json

# Write to file, print a summary to stderr
python tools/tier2_extractor/extract.py \
    scratch/CDS-HMC-2025.2026_shared.pdf \
    schemas/cds_schema_2025_26.json \
    --output /tmp/hmc_tier2.json \
    --summary
```

Example summary output:

```
[CDS-HMC-2025.2026_shared.pdf]
  acroform fields (populated): 558
  schema fields total:         1089
  schema fields populated:     558 (51%)
  unmapped acroform tags:      0
```

`unmapped acroform tags: 0` is what you want to see. It means every field name the PDF uses is known to the schema for that year. A non-zero count indicates either a drifted schema year or a school that added custom fields; both are worth investigating.

## Output JSON shape

```json
{
  "producer": "tier2_acroform",
  "producer_version": "0.1.0",
  "schema_version": "2025-26",
  "source_pdf": "CDS-HMC-2025.2026_shared.pdf",
  "extracted_at": "2026-04-13T06:30:00Z",
  "stats": {
    "acroform_fields_total": 558,
    "schema_fields_total": 1089,
    "schema_fields_populated": 558,
    "unmapped_acroform_fields": 0
  },
  "values": {
    "C.101": {
      "value": "3452",
      "pdf_tag": "AP_RECD_1ST_MEN_N",
      "word_tag": "c1_total_first_time_first_year_males_who_applied_total",
      "question": "Total first-time, first-year males who applied",
      "section": "First-Time, First-Year Admission",
      "subsection": null,
      "value_type": "Number"
    }
  },
  "unmapped_fields": []
}
```

Only populated fields are emitted. Downstream consumers who want a full-coverage view can join this output against the schema to see which canonical fields are absent.

The `values` dict is keyed by canonical `question_number`, which is the stable cross-school join key. A consumer asking "what did every school report for C.101?" iterates `values["C.101"]` across every school's Tier 2 output.

## Tested against

| PDF | AcroForm populated | Result |
|---|---:|---|
| `CDS-HMC-2025.2026_shared.pdf` | 558 / 1089 (51%) | 13/13 ground-truth spot checks match, 0 unmapped tags |
| `yale_cds_2024-25_rmd_20250612.pdf` | 0 | flattened — Tier 2 not available |
| `HarvardUniversity_CDS_2024-2025.pdf` | 0 | flattened — Tier 2 not available |
| `CDS-PDF-2025-2026_PDF_Template.pdf` | 75 | blank template with SUM-formula zeros |

Ground truth checked on HMC:

```
B1 full-time first-year men    109    EN_FRSH_FT_MEN_N        B.101
B1 full-time first-year women  125    EN_FRSH_FT_WMN_N        B.126
C1 applied men                 3452   AP_RECD_1ST_MEN_N       C.101
C1 applied women               1761   AP_RECD_1ST_WMN_N       C.102
C1 applied unknown             4      AP_RECD_1ST_UNK_N       C.103
C1 applied total               5217   AP_RECD_1ST_N           C.116
C1 admitted men                276    AP_ADMT_1ST_MEN_N       C.104
C1 admitted women              365    AP_ADMT_1ST_WMN_N       C.105
C1 admitted unknown            2      AP_ADMT_1ST_UNK_N       C.106
C1 admitted total              643    AP_ADMT_1ST_N           C.117
C2 waitlist offered            685    AP_RECD_WAIT_N          C.202
C2 waitlist accepted           439    AP_ACPT_WAIT_N          C.203
C2 waitlist admitted           0      AP_ADMT_WAIT_N          C.204
```

Every value matches the hand-verified numbers in [`tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml`](../extraction-validator/ground_truth/harvey-mudd-2025-26.yaml).

## Known gaps

1. **Checkbox values are cryptic.** AcroForm button widgets return PDF export values like `/VI` (very important), `/X` (yes/checked), `/NON` (none), `/SAME`, `/P` (partial). These are not human-readable. Each checkbox field has a known set of possible values defined in the blank template's widget dictionary; a future enhancement should extract that mapping once per schema year and emit decoded strings alongside the raw export value. Estimated ~30 lines of code plus one more field per schema entry. Until then, downstream consumers need to know how to decode the `/`-prefixed values for each `C.701`-style multi-choice field.

2. **Header/metadata fields are sometimes blank.** HMC's AcroForm has no value for `NAME` (`A.101` — name of institution) or the respondent address fields, even though the visible PDF clearly shows them. The institution filled the data tables but left the header fields for the Adobe template to render from elsewhere. For those canonical fields, the extractor emits nothing and the downstream consumer should prefer external metadata (the `schools.yaml` entry the scraper used to find the PDF, or the `cds_documents.school_name` column in the manifest). The schema builder could eventually flag "prefer external" fields.

3. **No school-identity detection.** This tool extracts values. It does not know which school the PDF is for. That mapping is the scraper's job — it knew which school it was downloading when it fetched the file. The Tier 2 output deliberately omits `school_id` / `school_name` so that callers cannot accidentally rely on extractor-provided identity.

4. **Pypdf xref warnings.** Some PDFs (Yale specifically) emit "Ignoring wrong pointing object" warnings during `PdfReader` construction. These are harmless — pypdf is repairing a mildly broken cross-reference table — but they clutter stderr. Suppressed with a `warnings.catch_warnings()` block in the extractor, but if a user runs `pypdf` directly they will see them.

5. **Value strings are not type-coerced.** Every value is emitted as a string, even when the schema's `value_type` says `Number`. The schema carries enough metadata for downstream code to coerce per field; this tool intentionally does not lose fidelity by parsing at extraction time. (Original string preserved for provenance.)

## Tier 2 vs Tier 4 routing

The scraper should probe every incoming PDF:

```python
import pypdf
reader = pypdf.PdfReader(pdf_path)
fields = reader.get_fields()
if fields and any(f.get("/V") is not None for f in fields.values()):
    tier = "tier2"      # route to tools/tier2_extractor
else:
    tier = "tier4"      # route to Docling/Reducto + cleaner
```

Store the detected tier alongside the manifest row so consumers can filter by producer quality.

## See also

- [`tools/schema_builder/`](../schema_builder/) — builds the canonical schema JSON this tool consumes
- [`schemas/cds_schema_2025_26.json`](../../schemas/cds_schema_2025_26.json) — the 2025-26 canonical schema
- [`tools/extraction-validator/`](../extraction-validator/) — neutral scorer for comparing producers against hand-verified ground truth
- [`docs/known-issues/harvey-mudd-2025-26.md`](../../docs/known-issues/harvey-mudd-2025-26.md) — the correction record explaining why this tool exists
