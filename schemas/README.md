# CDS schemas

Canonical and structural CDS schemas extracted from the commondataset.org Excel templates.

## Two shapes, one directory

| File | Source tab | Scope | What it has |
|---|---|---|---|
| `cds_schema_2024_25.json` | `Answer Sheet` | 2024-25 | Canonical question_numbers (A.001, B.101, ...), section hierarchy. The source Answer Sheet omits pdf_tag and word_tag metadata. |
| `cds_schema_2025_26.json` | `Answer Sheet` | 2025-26 | Canonical question_numbers (A.001, B.101, ...), pdf_tag, word_tag, section hierarchy, value_options decoder |
| `cds_schema_YYYY_YY.structural.json` | `CDS-A` through `CDS-J` | 2019-20 through 2025-26 | Per-year structural layout: subsections, row labels, column headers, answer-cell refs. No canonical question_numbers. |

The Answer Sheet tab exists in the 2024-25 and 2025-26 templates. It is the CDS Initiative's machine-readable canonical spec and is the authoritative source for question_numbers. The 2024-25 Answer Sheet is reduced: it omits `Sort Order`, `US News PDF Tag`, and `Word Tag`, so the generated schema records `pdf_tag: null` and `word_tag: null` until follow-on synthesis fills those gaps.

Older templates do not have an Answer Sheet, so `cds_schema_YYYY_YY.structural.json` remains the best programmatic source for 2019-20 through 2023-24.

## Generators

- `tools/schema_builder/build_from_xlsx.py` — Answer Sheet → canonical schema for 2024-25 and later canonical template years.
- `tools/schema_builder/build_from_tabs.py` — per-section tabs → structural schema. Works across all years.
- `tools/schema_builder/canonical_diff.py` — canonical schema → classified cross-year diff and validated `pdf_tag` synthesis for reduced Answer Sheet years.
- `tools/schema_builder/decode_checkboxes.py` — folds per-field checkbox value lists into the canonical schema (runs after `build_from_xlsx.py`).

## Why both

**Canonical schema** is what the Tier 2 / Tier 4 extractors target today. Every extracted value is keyed by canonical question_number for the source schema year. Cross-year consumers should use the canonical diff/equivalence artifacts rather than assume the same question_number always means the same field.

**Structural schemas** unlock year-over-year comparison. Each year's schema captures that year's specific field set (including renames like `freshmen → first-year`, category changes like `Men/Women/Another Gender → Male/Female/Unknown`, and section redesigns like the 2022-23 template overhaul). A diff tool can compare two structural schemas to flag exactly what changed — which is what consumers querying across years need to know.

## Cross-year coverage

| Year | Canonical | Structural | XLSX source |
|---|---|---|---|
| 2019-20 | — | ✅ | commondataset.org/wp-content/uploads/2020/04/CDS_2019-2020.xlsx |
| 2020-21 | — | ✅ | commondataset.org/wp-content/uploads/2020/11/CDS_2020-2021.xlsx |
| 2021-22 | — | ✅ | commondataset.org/wp-content/uploads/2021/10/CDS_2021-2022.xlsx |
| 2022-23 | — | ✅ | commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.xlsx |
| 2023-24 | — | ✅ | commondataset.org/wp-content/uploads/2023/11/CDS_2023-2024.xlsx |
| 2024-25 | ✅ | — | `schemas/templates/cds_2024-25_template.xlsx` |
| 2025-26 | ✅ | ✅ | `schemas/templates/cds_2025-26_template.xlsx` |

## Question-number format

Canonical schemas normalize question numbers to one of two forms:

```text
<section-letter>.<digits-zero-padded-to-3+>
<section-letter>.<sub-letter-suffix>
```

Examples: `A01` becomes `A.001`, `A511` becomes `A.511`, `B2101` becomes `B.2101`, and sub-letter IDs such as `A0A`, `C8G01`, and `H2A01` become `A.0A`, `C.8G01`, and `H.2A01`.

## Template archive

Official templates needed to reproduce canonical schemas live in `schemas/templates/`, with source URLs, snapshots where available, and SHA-256 hashes recorded in `schemas/templates/SOURCES.md`. PRD 014 documents the yearly contributor process for adding future canonical template years.

## Next steps

- Wire the 2024-25 to 2025-26 semantic diff into the database equivalence layer described in PRD 014.
- Overlay canonical question_numbers onto older structural schemas by fuzzy-matching row labels + column headers against the 2025-26 canonical schema. That enables cross-year field identity even where the schema drifted.
