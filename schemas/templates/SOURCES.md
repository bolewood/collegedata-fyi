# CDS template archive

Official commondataset.org templates archived in this repo to keep the schema
pipeline reproducible across years and to insulate the project from CDN churn.

The CDS Initiative occasionally rotates or removes prior-year templates from
their public CDN — the 2024-25 template, for example, was removed from
commondataset.org sometime in 2025 and was only recoverable via the Internet
Archive. Keeping these files committed means contributors can always rebuild
the schema from source without hunting them down again.

## Why these files belong here

The repo's existing convention (per `tools/schema_builder/README.md`) was to
keep raw templates in `scratch/` and only commit the derived schema JSON. That
convention is correct for templates that are reliably available from
commondataset.org. It breaks down once a template ages off the CDN.

Decision: when a template is no longer available from its original publisher,
archive it here. When it is still available, archiving here is also fine —
it removes the "is this still up?" failure mode from the contributor workflow.

The template files themselves are working artifacts of the CDS Initiative.
The Common Data Set has no published terms of service at commondataset.org,
the Initiative is a working group rather than a rights-holder, and these
templates are widely redistributed by participating institutions. See
`tools/schema_builder/README.md` for the full licensing rationale that already
covers the derived schemas — the same reasoning extends to the template files.

## Provenance

| File | SHA-256 | Source | Snapshot |
|---|---|---|---|
| `cds_2024-25_template.xlsx` | `24d16e066e331426802aad6e4886edffaa2887b0267310f0539d890b68485cf5` | `https://commondataset.org/wp-content/uploads/2024/11/2024-2025-CDS-Template_Updated_11_08_24.xlsx` | `https://web.archive.org/web/20250321004409/https://commondataset.org/wp-content/uploads/2024/11/2024-2025-CDS-Template_Updated_11_08_24.xlsx` |
| `cds_2024-25_template.pdf`  | `8c02492902d1d7a6128581ab615df024db1ffa1ce8d38ae923a31aad1225d9f0` | `https://commondataset.org/wp-content/uploads/2024/11/CDS-2024-2025-TEMPLATE.pdf` | `https://web.archive.org/web/20250321004409/https://commondataset.org/wp-content/uploads/2024/11/CDS-2024-2025-TEMPLATE.pdf` |
| `cds_2025-26_template.xlsx` | `2f4f8dabeb286578d68ded3dea39c65ce8d10f696ab160a109dd10126cb0f3fe` | `https://commondataset.org/wp-content/uploads/2025/11/CDS-PDF-2025-2026-Excel_Template.xlsx` | `https://web.archive.org/web/20260428185533/https://commondataset.org/wp-content/uploads/2025/11/CDS-PDF-2025-2026-Excel_Template.xlsx` |
| `cds_2025-26_template.pdf`  | `d154e4f325bf17028cc2892cc4212164e68b24051685c56ccfa1d0b2b064e98e` | `https://commondataset.org/wp-content/uploads/2025/11/CDS-PDF-2025-2026_PDF_Template.pdf` | `https://web.archive.org/web/20260428185557/https://commondataset.org/wp-content/uploads/2025/11/CDS-PDF-2025-2026_PDF_Template.pdf` |

The Wayback Machine snapshot date for the 2024-25 files is 2025-03-21. The
2025-26 files were captured on 2026-04-28.

## File naming

`cds_<academic-year>_template.<ext>` where `<academic-year>` is hyphenated
short form (e.g., `2024-25`, `2025-26`). This drops the inconsistent
publisher-side names (which vary year to year — sometimes `CDS_YYYY-YYYY`,
sometimes `CDS-YYYY-YYYY-TEMPLATE`, sometimes `YYYY-YYYY-CDS-Template_Updated_*`)
in favor of one repo-side convention.

The original filenames are recorded in the Source column above for traceability.

## Adding a new year

When the CDS Initiative publishes a new template (e.g., 2026-27):

1. Download the XLSX and fillable PDF from commondataset.org.
2. Drop them into this directory using the naming convention:
   `cds_<academic-year>_template.{xlsx,pdf}`.
3. Add a row to the provenance table above with the source URL, the Wayback
   snapshot URL (capture one if none exists yet — it's a five-minute job and it
   protects future contributors), and the SHA-256.
4. Follow the contributor process in PRD 014 to build the canonical schema and
   wire it into the year-aware extractors.

## Older years (2019-20 through 2023-24)

Not currently archived here. Those years use structural schemas only (no
canonical Answer Sheet exists in those templates), and the originals are still
on commondataset.org as of this writing. If a future contributor wants to
archive them as a defensive measure, follow the same process.
