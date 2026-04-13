# ADR 0006: Tiered extraction strategy for CDS documents

**Date:** 2026-04-13
**Status:** Accepted
**Supersedes:** none
**Extends:** [ADR 0002 — Publish raw over clean](0002-publish-raw-over-clean.md)

## Context

ADR 0002 scoped V1 as "publish raw Docling output alongside the source PDF, let cleanup happen as a separate community layer." That decision was correct given its assumptions: one extractor (Docling), one input format (flattened PDF), one output shape (producer-specific raw JSON). The project's architecture at that point had `cds_artifacts` rows tagged with `kind=raw_docling` and no schema normalization.

Three things changed after ADR 0002 was written.

**First, we discovered that HMC's source PDF was a fillable form.** The "C1 row-shift corruption" documented in [`docs/known-issues/harvey-mudd-2025-26.md`](../known-issues/harvey-mudd-2025-26.md) was treated as a Docling layout-extraction bug for days before we probed the file with `pypdf.get_fields()` and found 1,026 named AcroForm fields with 558 populated, including every C1/C2 value we had been trying to reconstruct through layout reasoning. `AP_RECD_1ST_MEN_N = 3452`, `AP_RECD_1ST_WMN_N = 1761`, `AP_ADMT_1ST_MEN_N = 276`. The data was sitting in named form fields the whole time. Our audit was solving a problem the source document did not have, because we chose a layout extractor for a structured-form input.

**Second, we realized the CDS Initiative publishes a canonical schema.** The 2025-26 Excel template's "Answer Sheet" tab contains 1,105 canonical field definitions with stable question numbers (`A.001`, `B.101`, `C.101`, ...), US News PDF tags, DOCX field tags, question text, and section metadata. We extract it programmatically via [`tools/schema_builder/build_from_xlsx.py`](../../tools/schema_builder/build_from_xlsx.py) and publish the result as [`schemas/cds_schema_2025_26.json`](../../schemas/cds_schema_2025_26.json). There is no design work to do for a target schema because the Common Data Set Initiative already did it. This completely changes the value proposition of ADR 0002's "cleaners will normalize raw output" — cleaners now have a concrete, versioned target schema from day one, and so do first-party extractors.

**Third, we observed that real schools distribute CDS documents in multiple formats.** Our three-school audit (HMC, Yale, Harvard) showed:

- HMC: unflattened fillable PDF with populated AcroForm fields (Tier 2)
- Yale: flattened PDF, no form fields (Tier 4)
- Harvard: flattened PDF, no form fields (Tier 4)

Plus the official commondataset.org template is published in three formats every year: XLSX with a computed Answer Sheet, PDF with AcroForm fields, and DOCX with Word tags. Some schools distribute the filled XLSX directly (Tier 1 — not yet observed in our sample but supported by the template), some publish the unflattened PDF (Tier 2 — HMC confirmed), some publish flattened PDFs from the same template (Tier 4 — Yale, Harvard confirmed), and some publish image-only scans (Tier 5 — not yet observed in our sample but possible for older historical documents).

These three shifts together mean the original "one extractor, one output shape" model is inadequate. Different input formats have fundamentally different quality characteristics when extracted. A single `raw_docling` artifact kind lumps 100%-accurate Tier 2 output and variable-quality Tier 4 output into the same bucket, which obscures the distinction that matters most to consumers.

## Decision

Route each archived source file to a tier-specific extractor based on its detected format, with all tiers targeting the same canonical schema.

### Tier ladder

| Tier | Input format | Extractor | Producer tag | Observed in corpus |
|---|---|---|---|---|
| 1 | Filled XLSX | `openpyxl` reading the Answer Sheet tab | `tier1_xlsx` | Not yet observed |
| 2 | Unflattened fillable PDF | `pypdf.get_fields()` via [`tools/tier2_extractor/`](../../tools/tier2_extractor/) | `tier2_acroform` | HMC 2025-26 |
| 3 | Filled DOCX | `python-docx` reading Word tags | `tier3_docx` | Not yet observed |
| 4 | Flattened PDF | Layout extractor (Docling, Reducto) + schema-targeting cleaner | `docling`, `reducto`, `community-<name>` | Yale 2024-25, Harvard 2024-25 |
| 5 | Image-only scan | OCR (Tesseract or similar) + cleaner | `tier5_ocr` | Not yet observed |

### Detection

Format detection is a separate step from extraction, performed by the Python worker (not the Deno edge function). The worker:

1. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`
2. Downloads the archived source file from the `sources` Storage bucket
3. Runs `pypdf.get_fields()` against the file (for PDFs) or inspects file headers (for XLSX/DOCX)
4. Sets `cds_documents.source_format` to one of: `pdf_fillable | pdf_flat | pdf_scanned | xlsx | docx | other`
5. Routes the source to the appropriate extractor based on the detected format
6. Writes extraction output as a new `cds_artifacts` row with the tier-specific `producer` tag and `kind = 'canonical'`
7. Updates `cds_documents.extraction_status` to `extracted` (success) or `failed` (extractor error)

Format detection lives in the worker, not the edge function, for two reasons:

- `pypdf` is Python-only and much more battle-tested than any Deno PDF library at AcroForm inspection. Porting detection to Deno would require shipping and maintaining a less mature library, and the edge function would gain nothing from detecting format at discovery time since the downstream worker has to inspect the file anyway.
- The discovery edge function's single responsibility is to find and archive source URLs. Detection and routing are extraction concerns, not discovery concerns. Splitting them cleanly is an ADR 0001 implication — Deno for discovery, Python for extraction.

### Canonical schema as the unifying contract

All tiers target the same canonical schema published at `schemas/cds_schema_{year}.json`. Each canonical artifact's `cds_artifacts.schema_version` column records which year's schema the extract targets, enabling consumers to handle cross-year queries explicitly when the schema changes between years (gender categories, B4-B21 Pell disaggregation, etc. — see the schema year-diff item in the backlog).

A `canonical` artifact from Tier 2 and a `canonical` artifact from Tier 4 have the same JSON shape, the same field IDs, and the same semantic meaning. They differ only in their `producer` tag, which tells consumers how to weight trust. A downstream query like "give me the latest canonical extract for school X, year Y" naturally returns the highest-quality available producer because the `cds_manifest` view already resolves "most recent canonical artifact per document."

### Producer precedence

When multiple `canonical` artifacts exist for the same `(document_id)`, consumers should prefer in this order:

1. `tier2_acroform` (deterministic, ~100% accurate when source is fillable)
2. `tier1_xlsx` or `tier3_docx` (equally deterministic but not yet observed in practice)
3. `reducto` (reasoning extractor, high accuracy on flat PDFs when the schema-constrained mode is used)
4. `docling` + cleaner (variable accuracy, depends on the cleaner)
5. `community-<name>` (variable; consumers should evaluate per-cleaner)
6. `tier5_ocr` (lowest confidence, for image-only sources)

The V1 `cds_manifest` view's `latest_canonical_artifact_id` correlated subquery picks the most recently created canonical artifact regardless of producer, which is pragmatic for a project with few artifacts per document. A future version of the view could implement explicit producer precedence ordering, but that's deferred until we see real multi-producer collisions in the wild.

## Why

Three reasons, in order of importance.

**The canonical schema makes normalization a publisher-side concern, not a consumer-side concern.** ADR 0002's framing assumed consumers would normalize raw extractor output against whatever shape made sense for their use case. That was defensible when we had no published target schema. Now that the CDS Initiative publishes a canonical schema and we extract it programmatically, "normalize to the canonical shape" is a fixed, stable, well-defined operation. Doing it once in the extraction pipeline and publishing the result is strictly better than making every consumer do it independently. The artifact model still supports raw producer output (`raw_docling`, `raw_reducto`) for reproducibility and debugging, but the primary artifact consumers read is `canonical`.

**Format-specific extractors produce materially different quality.** A single `kind=raw_docling` bucket collapses three very different realities: "this was a fillable PDF we ran the wrong tool on" (HMC), "this was a genuine flat PDF Docling handled well" (Yale), and "this was a flat PDF Docling handled poorly" (HMC if it had actually been flat). The tier structure makes the quality distinction first-class, visible in the database schema (via `producer` and `source_format`), and queryable. A consumer who only wants Tier 2 output can filter on `producer = 'tier2_acroform'` and get deterministic, verified results. A consumer who accepts Tier 4 with known caveats can explicitly opt in.

**It costs nothing to do right.** The data model changes required by this ADR (`source_format`, `schema_version`, `producer` as a free-text field, `kind = 'canonical'` as a new enum value) were already added to the initial schema migration in M0 ([`supabase/migrations/20260413201910_initial_schema.sql`](../../supabase/migrations/20260413201910_initial_schema.sql)). The Tier 2 extractor already exists as a standalone tool. The schema builder already exists. The `cds_schema_2025_26.json` artifact already exists. This ADR ratifies a de facto architecture that has been shipping across the last several commits; writing it down is documentation, not implementation.

## Trade-offs accepted

**Format detection adds a step before extraction.** Every extraction-pending row goes through `pypdf.get_fields()` first, which is ~10 ms. Trivial overhead in exchange for correct tier routing.

**Multiple producers per `kind=canonical` means collision handling.** If Tier 2 and a community cleaner both produce `canonical` artifacts for the same document, the consumer needs a policy for which to prefer. V1 uses "most recent wins" via the `cds_manifest` view's `ORDER BY created_at DESC LIMIT 1` subquery. This is wrong in edge cases (a stale Tier 2 artifact beats a fresh community cleaner), but it's simple and predictable and we can tighten it when real multi-producer collisions surface. Explicit producer precedence ordering in the view is a P2 backlog item.

**Tier 1 / Tier 3 / Tier 5 extractors do not yet exist.** Only Tier 2 (AcroForm) is built. Tier 4 is under development (the Reducto reference extracts exist but no schema-targeting cleaner is in place yet). Tier 1 / Tier 3 / Tier 5 are specified in this ADR so the data model and routing logic are consistent, but nobody has written the code. This is fine for V1 — we can detect the format, record it in `source_format`, and flip `extraction_status = failed` with a `notes.reason = "tier not implemented"` for schools whose source falls into an unimplemented tier. Those rows unblock automatically when the missing extractor ships.

**Tier routing is based on a sample of N=3 schools.** The assumption that format is the right axis to route on (vs. school type, vs. year, vs. publisher identity) rests on a very small empirical base. If the wild corpus turns out to have significant variance within a single format (e.g. "fillable PDFs from one vendor parse cleanly while fillable PDFs from another vendor don't, even though both have populated AcroForm fields"), the tier model becomes leaky. The V1 response is: widen the sample during M1 and observe what breaks before generalizing. The `cds_documents.notes` field can record per-school quirks that don't fit the clean tier story.

**ADR 0002's "community cleaners are the normalization layer" framing is weakened.** Community cleaners still exist and can still target the canonical schema, but they're no longer the only path from raw to canonical — first-party extractors now produce canonical output directly. This is a deliberate scope broadening: V1 ships with a first-party reference implementation for each tier rather than waiting for the community to close the normalization gap. Community cleaners remain welcome and are still supported by the `cleaners` table and the artifact model, but they are no longer on the critical path.

## Data model implications (already shipped)

These columns were added to the initial schema migration in M0 in anticipation of this ADR:

- `cds_documents.source_format` — CHECK constraint enumerates `pdf_fillable | pdf_flat | pdf_scanned | xlsx | docx | other`
- `cds_documents.extraction_status` — CHECK constraint includes `extraction_pending`, `extracted`, `failed`, `not_applicable`
- `cds_artifacts.kind` — CHECK constraint includes `source | canonical | raw_docling | raw_reducto | cleaned | schema_v1_normalized`
- `cds_artifacts.producer` — free-text, stores `tier2_acroform | docling | reducto | community-<name> | ...`
- `cds_artifacts.schema_version` — free-text, stores `"2025-26"` etc.

See [`supabase/migrations/20260413201910_initial_schema.sql`](../../supabase/migrations/20260413201910_initial_schema.sql).

## Relationship to existing ADRs

- **ADR 0001 (Supabase-only architecture).** Unchanged. The tier routing lives inside the Python worker, which ADR 0001 already places outside the edge function.
- **ADR 0002 (Publish raw over clean).** Extended but not superseded. Source files are still immutable and archived on discovery. Raw producer outputs are still published (`kind = raw_docling`, `raw_reducto`) for reproducibility. What changes: the primary artifact consumers read is `kind = canonical`, produced directly by the extractor pipeline rather than by a downstream cleanup pass.
- **ADR 0003 (MIT license).** Unchanged.
- **ADR 0004 (canonical domain).** Unchanged.
- **ADR 0005 (repo on bolewood org).** Unchanged.

## Open items

- First-party Tier 4 implementation. The Reducto reference extracts exist as research artifacts; a production Tier 4 extractor that produces canonical-schema output from flat PDFs has not been written yet. On the backlog.
- Producer precedence ordering in `cds_manifest`. Current view picks most recent; should eventually pick highest-quality producer. P2 backlog.
- Checkbox value decoding for Tier 2. Raw AcroForm export values (`/VI`, `/X`, `/NON`) need per-field decoding against the blank template's widget dictionaries. P1 backlog item.
- Corpus-wide format distribution. We have N=3 audit data. M1 will produce N in the hundreds and let us measure the actual Tier 2 / Tier 4 / Tier 5 distribution for the first time.
