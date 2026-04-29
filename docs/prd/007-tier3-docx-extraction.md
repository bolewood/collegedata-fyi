# PRD 007: Tier 3 DOCX extraction

**Status:** Draft v2 — implementation plan only  
**Created:** 2026-04-20  
**Revised:** 2026-04-29  
**Author:** Anthony + Codex  
**Related:** [ADR 0006](../decisions/0006-tiered-extraction-strategy.md), [ADR 0007](../decisions/0007-year-authority-moves-to-extraction.md), [PRD 005](005-full-schema-extraction.md), [PRD 014](014-cross-year-canonical-schema.md), [Docling document converter](https://docling-project.github.io/docling/reference/document_converter/)

---

## Context

Tier 3 is the last unbuilt first-party extraction tier. Schools that publish
their Common Data Set as a filled Word document currently route to
`source_format='docx'` and fail at extraction time, or worse, route as `xlsx`
because XLSX and DOCX are both ZIP containers.

This tier matters less by raw count than Tier 4, but it matters because the
best-case DOCX path is more deterministic than PDF parsing:

- The CDS Word template contains Structured Document Tags (SDTs). Their
  `w:tag` values correspond to schema `word_tag` values, the same pattern as
  Tier 2's `pdf_tag` lookup.
- Kent State's campus-family DOCX files are the known high-value case: prior
  inspection found hundreds of populated SDTs per document.
- James Madison and other DOCX publishers are plausible additional wins.
- Saint Louis-like documents may preserve visible Word tables while stripping
  SDTs. Those need a fallback, not a hard fail.
- Some archived `.docx` links are not CDS files at all, especially
  CDS Initiative "Summary of Changes" documents. Tier 3 should detect and
  report those cleanly rather than treating them as extraction bugs.

Docling changes the plan. Its current converter supports DOCX input and emits
the same general `DoclingDocument`/Markdown structures we already use for PDFs.
That does **not** make Docling the primary DOCX extractor: Word SDTs are a
stronger source of truth than layout inference. It does make Docling a useful
fallback and diagnostic path for SDT-stripped DOCX files.

## Product goal

Turn DOCX from "known unsupported tier" into a useful deterministic extraction
path for template-preserving Word files, while creating a measured fallback path
for SDT-stripped Word documents.

Success is not "parse every Word document." Success is:

1. SDT-preserving DOCX files produce canonical artifacts with high field counts.
2. DOCX-vs-XLSX routing is content-based and no longer extension/magic-byte-only.
3. SDT-stripped DOCX files get classified into actionable buckets:
   `docx_no_sdts_but_tables`, `docx_not_cds`, `docx_docling_failed`,
   or `docx_unstructured`.
4. Browser projection refresh works exactly like other tiers after successful
   canonical artifact writes.

## Non-goals

- No broad Docling DOCX corpus drain in PR CI.
- No LLM repair for DOCX in this PRD.
- No attempt to support legacy `.doc` binary Word files.
- No promise that Docling fallback reaches Tier 4-quality field counts on day
  one.
- No manual, school-specific DOCX parser unless validation proves one narrow
  school family is worth a targeted exception.

## Strategy

Use a three-lane pipeline, ordered from most deterministic to most heuristic.

### Lane A — OOXML SDT reader, primary path

Read DOCX as Office Open XML directly and extract populated `w:sdt` controls.
Map each SDT tag to `schema.fields[*].word_tag`, then emit canonical values by
question number.

This is the Tier 3 equivalent of Tier 2:

| Tier | Source signal | Mapping key | Expected reliability |
|---|---|---|---|
| Tier 2 fillable PDF | AcroForm fields | `pdf_tag` | deterministic |
| Tier 3 DOCX Lane A | Word SDTs | `word_tag` | deterministic |

Implementation should prefer direct OOXML traversal over high-level
`python-docx` APIs for the core reader. `python-docx` is fine as a helper, but
direct XML access makes it easier to handle:

- nested SDTs
- checkbox SDTs
- dropdown/date controls
- placeholder markers
- repeated section controls
- field tags attached below different XML levels

If a DOCX has enough mapped, populated SDTs, Lane A wins and no fallback runs.

### Lane B — Docling DOCX structural adapter, fallback path

If Lane A has no mapped SDTs, run Docling on the DOCX and inspect the converted
document:

1. Export Markdown and pass it through the existing Tier 4 cleaner.
2. If Docling exposes native table structures for DOCX, adapt those tables into
   the same shape consumed by `tier4_native_tables.py`.
3. Record fallback diagnostics even when field count is low.

This is not a separate hand-written Word table parser at first. The creative
move is to reuse the Tier 4 cleaner's hard-won table/label logic across DOCX
documents by normalizing DOCX tables into the same table stream. If it works,
we avoid building "Tier 3b" from scratch. If it does not, the diagnostics tell
us exactly which table shapes fail.

Lane B artifact producer should be explicit:

- `tier3_docx` for Lane A SDT extraction
- `tier3_docx_docling` or `tier3_docx_fallback` for Docling fallback

Selected-result logic can prefer Lane A over Lane B for the same document and
schema version.

### Lane C — render-to-PDF experiment, last resort

For DOCX files with no SDTs and poor Docling-native table output, test a small
experiment:

1. Render DOCX to PDF with LibreOffice headless.
2. Run the existing Tier 4 Docling PDF extractor/cleaner on that rendered PDF.
3. Compare output to Lane B.

This is deliberately **not** part of the default extractor. It is an M4
validation experiment because it adds operational weight and can introduce
rendering artifacts. It may be useful for a small class of Word documents whose
visual layout is clean but whose DOCX XML is awkward.

## Data model and artifact contract

No new table is required.

Successful DOCX extraction writes `cds_artifacts`:

```json
{
  "kind": "canonical",
  "producer": "tier3_docx",
  "producer_version": "0.1.0",
  "schema_version": "2025-26",
  "notes": {
    "producer": "tier3_docx",
    "producer_version": "0.1.0",
    "source_format": "docx",
    "schema_version": "2025-26",
    "extraction_path": "sdt",
    "stats": {
      "sdt_count": 1204,
      "mapped_sdt_count": 804,
      "populated_sdt_count": 769,
      "values_count": 769,
      "unmapped_sdt_count": 0
    },
    "values": {
      "C.101": {
        "value": "1234",
        "word_tag": "c1_total_first_time_first_year_males_who_applied_total",
        "question": "..."
      }
    },
    "unmapped_fields": []
  }
}
```

Fallback artifacts use the same canonical shape, with:

```json
{
  "producer": "tier3_docx_docling",
  "extraction_path": "docling_markdown",
  "fallback_reason": "no_mapped_sdts"
}
```

The worker should mark unrecoverable DOCX documents as `failed` with a specific
reason in logs/artifact notes rather than a generic `stub_docx`.

Suggested failure categories:

| Category | Meaning |
|---|---|
| `docx_not_cds` | The file is a summary/change/instructions document, not a filled CDS. |
| `docx_no_mapped_sdts` | SDTs exist, but none map to schema `word_tag`. |
| `docx_no_sdts_but_tables` | No SDTs, but visible Word tables exist; fallback candidate. |
| `docx_docling_failed` | Docling could not convert the DOCX. |
| `docx_low_fields` | Extraction succeeded but field count is below threshold. |

## Format routing

Fix routing before extraction work.

The current ZIP-signature logic is insufficient. `PK\x03\x04` means "ZIP
container", not "XLSX". Routing should inspect inner ZIP entries:

| Inner path | Source format |
|---|---|
| `word/document.xml` | `docx` |
| `xl/workbook.xml` | `xlsx` |
| neither | `other` |

This belongs in the shared sniffing path used by the worker and any tier probe.
It should not trust filename extension or content-type when bytes disagree.

## Year detection

ADR 0007 made extraction content authoritative for year. DOCX needs parity:

1. Extract plain text from `word/document.xml`.
2. Search the same year patterns used by PDF detection.
3. Persist `cds_documents.detected_year` when a unique year span is found.
4. Do not use the URL/archive `cds_year` as authority.

Docling's text export can be a fallback for year detection, but direct OOXML
text should be faster and less brittle for DOCX.

## Milestones

### M0 — Corpus and fixture audit

**Goal:** know what DOCX work actually exists before building.

Tasks:

- Query current `cds_documents` for `source_format='docx'`, failed
  ZIP-routed `xlsx` rows, and manual URLs ending in `.docx`.
- Download a fixture set into `.context/tier3-docx-fixtures/`.
- Classify each fixture:
  - SDT-preserving filled CDS
  - SDT-stripped but table-preserving CDS
  - summary/instructions/wrong file
  - corrupt/unsupported
- Pick at least:
  - 3 Kent State-family SDT-preserving docs
  - 1 James Madison candidate
  - 1 Saint Louis-style table-only doc
  - 2 wrong-file summary docs

Exit criteria:

- `docs/plans/prd-007-fixture-audit.md` records counts, school IDs, and
  expected extraction path per fixture.

### M1 — ZIP sniffer and DOCX year detection

**Goal:** route DOCX correctly without extracting it yet.

Tasks:

- Update byte sniffer to distinguish DOCX vs XLSX by inner ZIP paths.
- Add DOCX text extraction for year detection.
- Add unit fixtures for ZIP sniffing:
  - minimal DOCX
  - minimal XLSX
  - ZIP with neither
  - malformed ZIP
- Verify no regression for PDF routing.

Exit criteria:

- Misrouted DOCX-as-XLSX rows can be reclassified.
- Worker still fails DOCX as unimplemented, but for the right reason.

### M2 — Lane A SDT extractor

**Goal:** deterministic canonical artifacts for SDT-preserving DOCX.

Tasks:

- Create `tools/tier3_extractor/extract.py`.
- Build `word_tag -> schema field` index.
- Read SDTs directly from OOXML.
- Skip placeholders.
- Decode common controls:
  - plain text
  - checkbox/boolean
  - dropdown values
  - dates
- Emit canonical JSON in the same shape as Tier 1/Tier 2 artifacts.
- Track stats and unmapped SDTs.
- Add CLI for local inspection.

Exit criteria:

- Kent State-family fixture produces hundreds of mapped values.
- Hand-checked sample values match the source DOCX.
- Wrong-file summary docs do not produce plausible canonical artifacts.

### M3 — Worker integration and projection refresh

**Goal:** DOCX drains behave like every other extraction tier.

Tasks:

- Add `source_format == "docx"` worker route.
- Add dependency to extraction worker requirements.
- Write `producer='tier3_docx'`, version `0.1.0`.
- Respect existing artifact compatibility checks.
- Refresh browser projection after successful DOCX extraction.
- Add summary/log counters for DOCX-specific failure categories.

Exit criteria:

- Running the worker on a single SDT-preserving DOCX writes a canonical artifact
  and projection rows.
- Running on a wrong-file DOCX fails cleanly with `docx_not_cds` or equivalent.

### M4 — Docling fallback spike

**Goal:** decide whether Docling is good enough for SDT-stripped Word docs.

Tasks:

- Run Docling `DocumentConverter` on the SDT-stripped fixtures.
- Export Markdown and run Tier 4 cleaner against it.
- If Docling exposes native DOCX tables, adapt them to the native-table overlay
  path and compare against Markdown-only.
- Compare against a render-to-PDF experiment on the same fixtures.
- Record per-fixture:
  - field count
  - parse errors
  - value-level spot checks
  - runtime
  - failure class

Exit criteria:

- Decision documented:
  - ship Lane B fallback now
  - defer Lane B and only classify table-only DOCX
  - invest in a bespoke Word table parser

### M5 — Small production drain

**Goal:** ship the high-confidence DOCX subset.

Tasks:

- Requeue only SDT-preserving DOCX fixtures/candidates first.
- Drain with bounded ops worker or laptop run.
- Refresh projection document-by-document.
- Write a short findings report with:
  - docs processed
  - successes/failures
  - mean fields
  - low-field docs
  - wrong-file count
  - remaining table-only candidates

Exit criteria:

- Known Kent State-family DOCX files are extracted.
- Queue is clean.
- Backlog has follow-ups for table-only DOCX if needed.

## Validation

### Unit tests

- ZIP sniffer distinguishes XLSX/DOCX.
- DOCX year detection handles normal CDS title text.
- SDT reader extracts nested/plain SDTs.
- Placeholder SDTs are skipped.
- Checkbox/dropdown/date SDTs decode predictably.
- Unknown `word_tag` values go to `unmapped_fields`.

### Fixture tests

For each curated fixture:

- expected extraction path
- expected minimum field count
- expected failure category if not extractable
- 5-10 hand-checked field assertions for successful fixtures

### Regression tests

- Tier 1 XLSX sample still routes as XLSX.
- Tier 2 PDF sample still routes as PDF.
- Tier 4 PDF sample still routes as PDF and extracts.
- Wrong-file DOCX does not create a canonical artifact with misleading values.

## Operational plan

DOCX is suitable for the ops worker path, not regular PR CI:

- PR CI runs unit/fixture tests only.
- Manual GitHub Action or laptop run drains pending DOCX rows.
- Full corpus probing can run from a laptop because it downloads source files.
- The drain summary should flag `docx_low_fields` and `docx_not_cds` so discovery
  cleanup can follow.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Some DOCX files are official templates but have no SDTs | Lane B/M4 measures Docling fallback before building a bespoke table parser. |
| Summary-of-changes DOCX files look CDS-ish by URL | Add explicit wrong-file classifier; do not write canonical artifacts from low-confidence files. |
| Word tags drift by year | Use PRD 014 schema dispatch. Unknown tags stay unmapped until the year schema is added. |
| Docling DOCX conversion loses table semantics | Treat Docling as fallback only; compare Markdown vs native tables vs render-to-PDF before shipping Lane B broadly. |
| LibreOffice rendering is operationally heavy | Keep it as an experiment, not default extraction. |
| python-docx hides SDT details | Core Lane A reader should traverse OOXML directly; use python-docx only where it helps. |

## Decision points

1. **After M0:** Is the current DOCX corpus big enough to justify immediate
   implementation, or should this wait for more DOCX publishers?
2. **After M2:** Are SDT-preserving results strong enough to ship Lane A alone?
3. **After M4:** Is Docling fallback good enough for table-only DOCX, or should
   table-only documents remain deferred?

## Recommended path

Build M1-M3 first. That is the boring, high-confidence slice:

- content-based DOCX routing
- direct SDT extraction
- worker integration
- projection refresh

Then pause. Run M4 as a measurement spike before committing to table-only DOCX
support. If Docling gets enough fields from SDT-stripped Word tables, ship Lane B.
If it does not, leave those documents classified and defer a bespoke Word table
parser until the corpus justifies it.
