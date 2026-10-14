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
| `cds_2021-22_template.xlsx` | `107854d01f83f41b8b4bca3e284ff238b8c8c9389cfa222cf494e5d46a5f3d64` | `https://commondataset.org/wp-content/uploads/2022/03/CDS_2021-2022.xlsx` | `https://web.archive.org/web/20220326165040id_/https://commondataset.org/wp-content/uploads/2022/03/CDS_2021-2022.xlsx` |
| `cds_2021-22_template.pdf`  | `2809bd6e69a68a4aa171f8fa588eddafab1156642e5b3e68773677fbe95b8d83` | `https://commondataset.org/wp-content/uploads/2022/03/CDS_2021-2022-2.pdf` | `https://web.archive.org/web/20220326165048id_/https://commondataset.org/wp-content/uploads/2022/03/CDS_2021-2022-2.pdf` |
| `cds_2022-23_template.xlsx` | `ba5f64acb6bd8c333d488621382f4ea30cb48609492ac02e51f4b33df30cd65e` | `https://commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.xlsx` | `https://web.archive.org/web/20221127152052id_/https://commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.xlsx` |
| `cds_2022-23_template.pdf`  | `17379faf264a8247f76bd588435d435e58b3e5615e1505a6784ca216733953ab` | `https://commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.pdf` | `https://web.archive.org/web/20221127152033id_/https://commondataset.org/wp-content/uploads/2022/11/CDS_2022-2023.pdf` |
| `cds_2023-24_template.xlsx` | `4c82edcccdf30032105d6684bbe648dfb457a8498e6b1396d5f5fd68b8f279e4` | `CDS_2023-2024-1.xlsx` user-provided official/Wayback template attachment | pending |
| `cds_2023-24_template.pdf`  | `2adbe3d16d6ff3144fb9675da67d6d6c9ff9c942a3b597121d50a0084f61c65f` | `CDS_2023-2024-with-auto-sum.pdf` user-provided official/Wayback template attachment | pending |
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

## 2021-22 and 2022-23

Recovered from the Internet Archive in October 2026; commondataset.org no
longer serves them to scripted clients. 2021-22 is the first year with a
fillable, tagged PDF. Its March 2022 revision (`CDS_2021-2022-2.pdf`, 1,027
AcroForm fields) is archived here because the original October 2021 PDF lacks
three H2A fields; the October 2021 XLSX was never captured, so the March 2022
XLSX is the only one available. The two published 2022-23 PDFs (October and
November 2022) are byte-identical.

Neither year has a canonical schema; extraction still resolves them to the
2025-26 schema. A 2023-24-style synthesized schema built from these PDFs'
AcroForm keys was tried in October 2026 and not adopted. On the stored Tier 4
markdown for both years, first-year C1 counts matched IPEDS less often than
with the 2025-26 fallback (1,459 vs 1,636 stage readings within 2%). Tier 2 C1
totals were identical, and about 100 fewer fields per fillable PDF were
captured.

## Older years (2014-15 through 2020-21)

Not archived here. Their official PDFs are flat print exports with no AcroForm
fields, and their XLSX/Word templates carry no tags, so they support structural
schemas only. Verified Wayback copies of every year's templates, with source
URLs and hashes, were collected in October 2026 if a future contributor needs
them.

## 2023-24 exception

The 2023-24 template has no Answer Sheet tab, but it is close enough to the
2024-25 canonical schema to support a year-specific synthesized canonical
schema. The XLSX above is archived for structural rebuilds; the fillable PDF is
archived because its AcroForm keys provide the exact 2023-24 PDF tags used by
Tier 2 extraction.
