# CDS schemas

Canonical and structural CDS schemas extracted from the commondataset.org Excel templates.

## Two shapes, one directory

| File | Source tab | Scope | What it has |
|---|---|---|---|
| `cds_schema_2025_26.json` | `Answer Sheet` | 2025-26 only | Canonical question_numbers (A.001, B.101, …), pdf_tag, word_tag, section hierarchy, value_options decoder |
| `cds_schema_YYYY_YY.structural.json` | `CDS-A` through `CDS-J` | 2019-20 through 2025-26 | Per-year structural layout: subsections, row labels, column headers, answer-cell refs. No canonical question_numbers. |

The Answer Sheet tab exists **only** in the 2025-26 template. It's the CDS Initiative's machine-readable canonical spec and is the authoritative source for question_numbers. Older templates don't have it, so `cds_schema_YYYY_YY.structural.json` is the best we can do programmatically for 2019-20 through 2023-24.

2024-25 XLSX is not currently in the archive — the commondataset.org CDN removed it when the 2025-26 template shipped. We may be able to get it by contacting the CDS Initiative directly.

## Generators

- `tools/schema_builder/build_from_xlsx.py` — Answer Sheet → canonical schema. 2025-26 only.
- `tools/schema_builder/build_from_tabs.py` — per-section tabs → structural schema. Works across all years.
- `tools/schema_builder/decode_checkboxes.py` — folds per-field checkbox value lists into the canonical schema (runs after `build_from_xlsx.py`).

## Why both

**Canonical schema** is what the Tier 2 / Tier 4 extractors target today. Every extracted value is keyed by canonical question_number, which is stable across the 2025-26 year.

**Structural schemas** unlock year-over-year comparison. Each year's schema captures that year's specific field set (including renames like `freshmen → first-year`, category changes like `Men/Women/Another Gender → Male/Female/Unknown`, and section redesigns like the 2022-23 template overhaul). A diff tool can compare two structural schemas to flag exactly what changed — which is what consumers querying across years need to know.

## Cross-year coverage

| Year | Canonical | Structural | XLSX source |
|---|---|---|---|
| 2019-20 | — | ✅ | commondataset.org/wp-content/uploads/2020/04/CDS_2019-2020.xlsx |
| 2020-21 | — | ✅ | commondataset.org/wp-content/uploads/2020/11/CDS_2020-2021.xlsx |
| 2021-22 | — | ✅ | commondataset.org/wp-content/uploads/2021/10/CDS_2021-2022.xlsx |
| 2022-23 | — | ✅ | commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.xlsx |
| 2023-24 | — | ✅ | commondataset.org/wp-content/uploads/2023/11/CDS_2023-2024.xlsx |
| 2024-25 | — | — | missing — not on commondataset.org; only PDF available |
| 2025-26 | ✅ | ✅ | `scratch/CDS-PDF-2025-2026-Excel_Template.xlsx` |

## Next steps

- Build a schema diff tool that compares two structural schemas and produces a human-readable changelog (additions, removals, renames). This is the P1 backlog item "Cross-year schema diff tool."
- Get the 2024-25 XLSX (contact commondataset.org directly, or archive the PDF → structural-schema round trip).
- Overlay canonical question_numbers onto older structural schemas by fuzzy-matching row labels + column headers against the 2025-26 canonical schema. That enables cross-year field identity even where the schema drifted.
