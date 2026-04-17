# collegedata.fyi — Architecture

How the pieces fit together at runtime. Complements [`docs/v1-plan.md`](v1-plan.md) (engineering plan, data model details) and [`docs/prd/001-collegedata-fyi-v1.md`](prd/001-collegedata-fyi-v1.md) (product-level framing).

---

## Overview

The project has six logical pipelines, each running at a different cadence and responsibility boundary:

1. **Schema pipeline** — once per CDS year. Extracts the canonical schema from commondataset.org's official XLSX template into a committed JSON artifact. Also folds per-field checkbox value decoders into the same artifact.
2. **Corpus pipeline** — once per month or so. Builds the canonical school list from IPEDS data and enriches it with URL hints discovered by a pattern-ladder prober.
3. **Discovery pipeline** — nightly via cron. Reads the canonical school list, crawls each school's IR landing page, extracts every CDS-ish document anchor (multi-candidate per ADR 0007 Stage B), archives source bytes to Storage, and upserts one `cds_documents` row per archived file. Academic year is assigned later by the extraction pipeline from page-1 content, not from the URL.
4. **Extraction pipeline** — triggered by discovery. Pulls each `extraction_pending` row, downloads the archived source, detects format, routes to a tier-specific extractor, and writes a `canonical` artifact back.
5. **Consumer API** — on demand. PostgREST serves the manifest and the `cds_manifest` view at `api.collegedata.fyi/rest/v1/`. Public Storage URLs serve the archived source files.
6. **Frontend** — on demand. A Next.js app at `collegedata.fyi` (hosted on Vercel) consumes the PostgREST API and renders a searchable school directory, per-school document archives, and per-year structured field viewers. See [`docs/prd/002-frontend.md`](prd/002-frontend.md).

Each pipeline is independently runnable. None of them requires any of the others to be live for the others to work. This is deliberate: the project ships incrementally, one pipeline at a time, rather than requiring the full stack to be up before anything is useful.

---

## Data flow diagram

```
                     ┌────────────────────────────────────────────────┐
                     │              commondataset.org                 │
                     │   Official CDS templates (XLSX, PDF, DOCX)     │
                     │         published once per CDS year            │
                     └───────────────────┬────────────────────────────┘
                                         │
                                         │   Offline, once per year
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       SCHEMA PIPELINE                               │
  │                                                                     │
  │  tools/schema_builder/build_from_xlsx.py                            │
  │    reads XLSX "Answer Sheet" tab → extracts 1,105 canonical fields  │
  │                                                                     │
  │  tools/schema_builder/decode_checkboxes.py                          │
  │    reads blank PDF template → walks 224 Btn-type /_States_ lists    │
  │    → folds value_options into each schema entry                     │
  │                                                                     │
  │                         ──────────────▶  schemas/cds_schema_YYYY_YY.json
  │                                          (committed artifact)       │
  └─────────────────────────────────────────────────────────────────────┘
                                         │
                                         │   consumed by every extractor
                                         ▼
        ┌──────────────────┐   ┌────────────────┐   ┌──────────────────┐
        │  NCES IPEDS HD   │   │  Seed URLs     │   │ Canonical schema │
        │  (federal CSV)   │   │  (pbworks)     │   │ (committed JSON) │
        └────────┬─────────┘   └────────┬───────┘   └────────┬─────────┘
                 │                      │                    │
                 │   Offline, monthly   │                    │
                 ▼                      ▼                    │
  ┌─────────────────────────────────────────────┐            │
  │              CORPUS PIPELINE                │            │
  │                                             │            │
  │  build_school_list.py                       │            │
  │    IPEDS → schools.yaml (2,434 entries)     │            │
  │                                             │            │
  │  probe_urls.py                              │            │
  │    walks URL pattern ladder for each        │            │
  │    scrape_policy: unknown school            │            │
  │    → fills cds_url_hint on hits             │            │
  │                                             │            │
  │                 ──────────────▶  tools/finder/schools.yaml
  │                                  (committed artifact)    │
  └─────────────────────────┬───────────────────┘            │
                            │                                │
                            │   loaded at cron                │
                            ▼                                │
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       DISCOVERY PIPELINE                            │
  │                      (online, daily cron)                           │
  │                                                                     │
  │  supabase/functions/archive-process/index.ts                        │
  │    1. Load schools.yaml                                             │
  │    2. For each scrape_policy ∈ {active, verified_partial}:          │
  │         - Fetch cds_url_hint landing page                           │
  │         - Parse HTML, extract every CDS-ish document anchor         │
  │           (href or link-text matches /cds|common data set/)         │
  │         - Follow HTML subpages one hop (CMU pattern)                │
  │         - pickCandidates: return every qualifying anchor (ADR 0007  │
  │           Stage B) so a landing page like Lafayette's 19-year       │
  │           archive produces 19 candidates, not one                   │
  │         - HEAD each discovered document                             │
  │    3. For each candidate URL:                                       │
  │         - Download source bytes                                     │
  │         - Compute sha256                                            │
  │         - Upload to Storage at                                      │
  │           sources/{school_id}/{cds_year}/{sha256}.{ext}             │
  │           (SHA-addressed; consumers query source path via           │
  │            cds_manifest.source_storage_path, not by construction)   │
  │         - Upsert cds_documents row with                             │
  │           source_url, source_sha256, source_page_count,             │
  │           discovered_at, last_verified_at,                          │
  │           extraction_status = 'extraction_pending'                  │
  │                                                                     │
  │                                                                     │
  │            ┌──────────────────────┐   ┌────────────────────────┐    │
  │            │  Supabase Storage    │   │  Supabase Postgres     │    │
  │            │  (sources bucket)    │   │  (cds_documents table) │    │
  │            └──────────┬───────────┘   └────────────┬───────────┘    │
  └───────────────────────┼────────────────────────────┼────────────────┘
                          │                            │
                          │                            │ extraction_status
                          │                            │ = extraction_pending
                          │                            │
                          │   polled via supabase-py   │
                          ▼                            ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       EXTRACTION PIPELINE                           │
  │                   (Python worker, triggered)                        │
  │                                                                     │
  │  tools/extraction_worker/worker.py  (M2 skeleton live, Tier 2 only) │
  │    1. SELECT * FROM cds_documents WHERE extraction_status =         │
  │         'extraction_pending' ORDER BY school_id                     │
  │    2. For each row:                                                 │
  │         - Download archived source from Storage                     │
  │         - Run pypdf.get_fields() to detect format                   │
  │         - Set cds_documents.source_format                           │
  │         - Detect document year from page 1-10 content via           │
  │           detect_year_from_pdf_bytes (strict prefix-anchored        │
  │           regex, collect-all-unique), write to                      │
  │           cds_documents.detected_year — authoritative per ADR 0007 │
  │         - Route to tier-specific extractor:                         │
  │                                                                     │
  │              ┌───────────────────────────────────────────────┐      │
  │              │   Tier 1  filled XLSX                         │      │
  │              │       → openpyxl reads Answer Sheet           │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 2  unflattened fillable PDF            │      │
  │              │       → tools/tier2_extractor/extract.py      │      │
  │              │         pypdf.get_fields() + schema join      │      │
  │              │         + value_options decoder               │      │
  │              │       ~100% accuracy when applicable          │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 3  filled DOCX                         │      │
  │              │       → python-docx reads Word tags           │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 4  flattened PDF                       │      │
  │              │       → Docling + schema-targeting cleaner    │      │
  │              │         OR Reducto with canonical schema     │      │
  │              │       variable quality                        │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 5  image-only scan                     │      │
  │              │       → OCR + cleaner                         │      │
  │              │       worst case                              │      │
  │              └──────────────────┬────────────────────────────┘      │
  │                                 │                                   │
  │                                 ▼                                   │
  │         INSERT INTO cds_artifacts (kind='canonical', producer=...)  │
  │         UPDATE cds_documents SET extraction_status='extracted'      │
  │                                                                     │
  └─────────────────────────┬───────────────────────────────────────────┘
                            │
                            │   artifacts available for query
                            ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       CONSUMER PIPELINE                             │
  │                       (on-demand, public)                           │
  │                                                                     │
  │  api.collegedata.fyi → PostgREST → public.cds_documents             │
  │                                     public.cds_artifacts            │
  │                                     public.cleaners                 │
  │                                     public.cds_manifest (view)      │
  │                                                                     │
  │  Anon key in Authorization header.                                  │
  │  RLS allows public SELECT on all four objects.                      │
  │                                                                     │
  │  Example queries:                                                   │
  │    GET /rest/v1/cds_manifest?school_id=eq.yale                      │
  │    GET /rest/v1/cds_artifacts?kind=eq.canonical&document_id=eq.UUID │
  │                                                                     │
  │  Archived source downloads (path comes from                         │
  │  cds_manifest.source_storage_path, SHA-addressed):                  │
  │    GET https://<ref>.supabase.co/storage/v1/object/public/sources/  │
  │        yale/2024-25/{sha256}.pdf                                    │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## Component reference

Each component has its own README. This section lists every file that does something in the data flow above, with a one-line description and pointer to the deeper docs.

### Schema pipeline

| Component | Role |
|---|---|
| [`tools/schema_builder/build_from_xlsx.py`](../tools/schema_builder/build_from_xlsx.py) | Reads `scratch/CDS-PDF-YYYY-YYYY-Excel_Template.xlsx`, walks the Answer Sheet tab, writes `schemas/cds_schema_YYYY_YY.json` with one entry per canonical CDS field. 1,105 fields for 2025-26. |
| [`tools/schema_builder/decode_checkboxes.py`](../tools/schema_builder/decode_checkboxes.py) | Reads the blank CDS PDF template, walks every AcroForm `Btn` field's `/_States_` list, maps each state to a human-readable label via a curated `LABELS` table + per-tag overrides, folds a `value_options` array into each schema entry. Makes the Tier 2 extractor's output human-readable for checkbox/radio fields. |
| [`schemas/cds_schema_2025_26.json`](../schemas/cds_schema_2025_26.json) | The canonical schema artifact. Consumed by every extractor and by the `decode_checkboxes.py` augmentation step. |
| [`tools/schema_builder/README.md`](../tools/schema_builder/README.md) | Deeper docs for the schema pipeline. |

### Corpus pipeline

| Component | Role |
|---|---|
| [`tools/finder/build_school_list.py`](../tools/finder/build_school_list.py) | Downloads the IPEDS HD CSV from NCES, filters to 4-year degree-granting US non-profit institutions, merges with existing hand-curated entries in `schools.yaml`, writes back. Preserves hand-curated `cds_url_hint`, `sub_institutions`, `notes`, `scrape_policy`. |
| [`tools/finder/probe_urls.py`](../tools/finder/probe_urls.py) | For each school with `scrape_policy: unknown`, walks a ladder of URL patterns (`/ir/cds/`, `/institutional-research/common-data-set/`, etc.) × 7 subdomains + 5 year-specific PDF patterns. On a hit, fills in `cds_url_hint` and flips `scrape_policy` to `active`. Rate-limited to 1 req/s by default. Optional Bing/Google fallback. |
| [`tools/finder/schools.yaml`](../tools/finder/schools.yaml) | The canonical school list. 2,434 entries (82 hand-curated active, 2,350 IPEDS candidates awaiting probe, 2 verified absent). |
| [`tools/finder/seed_urls.md`](../tools/finder/seed_urls.md) | Reference doc of seed URL patterns, the pbworks College Lists Wiki, known non-publishers, and known sub-institutional publishers. |

### Discovery + archive pipeline

Full operator runbook, architecture, failure-mode classification, and
production verification are in [`docs/archive-pipeline.md`](./archive-pipeline.md).
Summary of the components:

| Component | Role |
|---|---|
| [`supabase/functions/_shared/`](../supabase/functions/_shared/) | Shared Deno modules imported by all three edge functions: `year.ts` (URL-hint year guesser — **not authoritative for document year** per ADR 0007; used by `pickCandidates` as a partitioning signal and to populate the NOT NULL `cds_year` column), `resolve.ts` (HTML parsing, two-hop, SSRF guard, multi-candidate `pickCandidates`, discriminated `ResolveResult`), `schools.ts` (schools.yaml fetch + validation), `storage.ts` (SHA-addressed path helpers), `db.ts` (`cds_documents` + `cds_artifacts` DAL), `archive.ts` (one-school orchestrator with `TransientError`/`PermanentError` classification). |
| [`supabase/functions/discover/index.ts`](../supabase/functions/discover/index.ts) | Resolver dev entry. HTTP `?schools=yale,mit,...` returns a `ResolveResult` per school as JSON. **No writes.** Used for iterating on the resolver and debugging `no_cds_found` cases. Capped at 10 schools per request. |
| [`supabase/functions/archive-process/index.ts`](../supabase/functions/archive-process/index.ts) | Queue consumer. Invoked every 30 s by pg_cron. Claims one row via `claim_archive_queue_row()` RPC, runs `archiveOneSchool`, marks terminal state in a `finally` block guarded by the claim lease. Also supports `?force_school=<id>` for operator backfill that bypasses the queue. |
| [`supabase/functions/archive-enqueue/index.ts`](../supabase/functions/archive-enqueue/index.ts) | Monthly seeder. Invoked daily at 02:00 UTC by pg_cron. Fetches `schools.yaml` from GitHub raw, derives a deterministic `run_id` from the current calendar month, bulk-upserts one `archive_queue` row per active school with `ignoreDuplicates=true`. Repeated daily runs within a month are no-ops. |
| [`supabase/migrations/20260414170000_archive_pipeline.sql`](../supabase/migrations/20260414170000_archive_pipeline.sql) | Schema foundations. Fixes the silent NULL-uniqueness bug on `cds_documents` (`UNIQUE NULLS NOT DISTINCT`), creates `archive_queue`, defines `claim_archive_queue_row()` with atomic attempts increment + 10-min visibility timeout + `FOR UPDATE SKIP LOCKED`. Includes an inline self-test for the constraint swap. |
| [`supabase/migrations/20260414180000_archive_pipeline_cron.sql`](../supabase/migrations/20260414180000_archive_pipeline_cron.sql) | pg_cron schedules. Wires the outer daily + inner 30-s jobs via `net.http_post`, with both the function base URL and the service role key stored as Vault secrets. Gracefully skips scheduling in environments where the Vault secrets are missing (local dev). |
| [`supabase/config.toml`](../supabase/config.toml) | Edge function configuration. `verify_jwt = true` on all three functions. `archive-process` and `archive-enqueue` additionally do an in-handler service-role check via `isServiceRoleAuth()` so that a plain authenticated project user cannot trigger writes. |
| [`schemas/cds_schema_YYYY_YY.json`](../schemas/) | Not directly used by the edge functions. The `sources` bucket path convention and the `cds_documents` column layout both reference concepts from the canonical schema. |

### Extraction pipeline

| Component | Role |
|---|---|
| [`tools/extraction_worker/worker.py`](../tools/extraction_worker/worker.py) | Python worker. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`, downloads the archived source, runs `pypdf.get_fields()` to detect format, performs content-based PDF year detection via `detect_year_from_pdf_bytes` and writes the result to `cds_documents.detected_year` — authoritative per [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md) Stage B — then routes to the appropriate tier extractor and writes the result back as a `cds_artifacts` row with `kind=canonical`. Supports a `--detect-year-only --write` harness mode that runs the year detector against every archived document and backfills `detected_year` without touching extraction. Wired end-to-end for Tier 2 (fillable PDF) and Tier 4 (flattened PDF via Docling). Tier 1/3/5 are still stubs that mark `extraction_status=failed` with a reason so the row exits the pending queue. |
| [`tools/tier2_extractor/extract.py`](../tools/tier2_extractor/extract.py) | Tier 2 extractor. Reads a CDS PDF via `pypdf.get_fields()`, joins against the schema by `pdf_tag`, decodes button values via `value_options`, emits canonical JSON keyed by `question_number`. Deterministic, ~100% accurate on HMC (31/31 ground-truth fields, verified by `score_tier2.py`). |
| [`tools/extraction_worker/tier4_extractor.py`](../tools/extraction_worker/tier4_extractor.py) | Tier 4 extractor. Converts a flattened CDS PDF to markdown via Docling (baseline config: TableFormer FAST, OCR on but not forced, 1x DPI). Scored 21/21 on critical C1 fields across 3 schools in the bake-off (commit `e15a5d3`). Emits raw markdown plus the cleaner-produced `values` dict. |
| [`tools/extraction_worker/tier4_cleaner.py`](../tools/extraction_worker/tier4_cleaner.py) | Tier 4 schema-targeting cleaner. Parses Docling markdown tables + inline text and emits `{question_number: {"value": str}}` matching the Tier 2 output shape. Handles the 2020 CDS template rename (`freshmen`→`first-year`), the 2024-25→2025-26 gender-category collapse, wrapped row labels (Dartmouth B1 pattern), header-less one-metric-per-row tables (Aims community-college pattern), and non-table fields via `_INLINE_PATTERNS` (C13 application fee, Harvard-style Submitting SAT). GT scorer 94.3% across Harvard/Yale/Dartmouth/HMC (83/88 fields), 100% on critical C1 admissions across the 21 critical fields. Corpus coverage of first-year admissions sits at 50–59% per field across 443 tier4_docling artifacts and climbs as new fixes ship. |
| Tier 1 / Tier 3 / Tier 5 extractors **(not yet built)** | Specified in ADR 0006. Tier 1 (filled XLSX via openpyxl), Tier 3 (filled DOCX via python-docx), Tier 5 (image-only scanned PDF via OCR). Documents in these formats are ingested and their `source_format` is recorded, but `extraction_status` stays at `extraction_pending` until the matching extractor ships. |
| [`tools/extraction-validator/score_tier2.py`](../tools/extraction-validator/score_tier2.py) | Regression scoring tool for Tier 2 output. Loads a ground-truth YAML, a Tier 2 extract JSON, and an ID map; compares every field with numeric tolerance; emits per-field diff + overall accuracy. Offline quality check, not part of the runtime pipeline. |
| [`tools/extraction-validator/score_tier4.py`](../tools/extraction-validator/score_tier4.py) | Regression scoring tool for Tier 4 output. Takes a Docling markdown file, runs `tier4_cleaner.clean()` against it, joins the resulting values to ground truth via the id_map, and reports per-field match + overall accuracy. Same shape as `score_tier2.py`. Exits non-zero if any critical field fails. |
| [`tools/extraction-validator/corpus_survey_tier4.py`](../tools/extraction-validator/corpus_survey_tier4.py) | Read-only corpus survey. Pulls every `tier4_docling` canonical artifact from the DB, re-runs the current cleaner against the stored markdown, and reports distribution of fields-populated + per-question coverage across the corpus. The ongoing coverage gauge — safe to run while the extraction worker is writing. |
| [`tools/extraction-validator/inspect_tier4_doc.py`](../tools/extraction-validator/inspect_tier4_doc.py) | Read-only single-doc inspector. Pulls one school's stored Docling markdown and dumps a section slice. Used to diagnose low-coverage docs surfaced by the corpus survey. |
| [`tools/extraction-validator/ground_truth/`](../tools/extraction-validator/ground_truth/) | Hand-verified ground truth YAMLs (one per school-year). The scoring reference for both tiers. |
| [`tools/extraction-validator/id_maps/`](../tools/extraction-validator/id_maps/) | Hand-built maps from ground-truth IDs (`b1_ft_firstyear_men`) to canonical question numbers (`B.101`). One file per school-year. Covers Harvey Mudd 2025-26, Harvard 2024-25, Yale 2024-25, Dartmouth 2024-25. |
| [`tools/extraction-validator/references/reducto/`](../tools/extraction-validator/references/reducto/) | Curated Reducto API reference extracts for HMC and Yale. Not used at runtime; kept as a quality benchmark for future Tier 4 work. |

### Consumer API

| Component | Role |
|---|---|
| Supabase PostgREST | Exposes `public.cds_documents`, `public.cds_artifacts`, `public.cleaners`, and the `public.cds_manifest` view at `api.collegedata.fyi/rest/v1/`. Public-read via RLS policies defined in the initial migration. |
| Supabase Storage | Serves archived source files from the `sources` bucket at `{project-ref}.supabase.co/storage/v1/object/public/sources/{school_id}/{cds_year}/{sha256}.{ext}`. The `{cds_year}` segment is the archive-time resolver guess, frozen at upload time; the authoritative content-derived year lives in `cds_documents.detected_year` and is exposed as `canonical_year` in the manifest (see ADR 0007 Stage B trade-offs). SHA-addressed so every version is preserved forever (ADR 0006). Consumers discover the exact path via `cds_manifest.source_storage_path`, never by construction. Public bucket, MIME allowlist enforces PDF/XLSX/DOCX only. |
| [`supabase/migrations/20260413201910_initial_schema.sql`](../supabase/migrations/20260413201910_initial_schema.sql) | Creates the three core tables, RLS policies, the manifest view, the Storage bucket, and the `sources` public-read policy. |

### Frontend

| Component | Role |
|---|---|
| [`web/`](../web/) | Next.js 16 app hosted on Vercel at `collegedata.fyi`. Consumes the PostgREST API via `@supabase/supabase-js` with the anon key. Read-only, no auth, no write paths. |
| [`web/src/app/page.tsx`](../web/src/app/page.tsx) | Landing page with school search autocomplete and live corpus stats. |
| [`web/src/app/schools/page.tsx`](../web/src/app/schools/page.tsx) | School directory: searchable, sortable table of all schools with archived CDS data. |
| [`web/src/app/schools/[school_id]/page.tsx`](../web/src/app/schools/[school_id]/page.tsx) | School detail: document list with status badges, PDF download links, sub-institutional support. |
| [`web/src/app/schools/[school_id]/[year]/page.tsx`](../web/src/app/schools/[school_id]/[year]/page.tsx) | Year detail (SEO answer page): key stats block + full structured field viewer grouped by CDS section. |
| [`web/src/lib/labels.ts`](../web/src/lib/labels.ts) | Auto-generated CDS field ID to plain-English label map (1,105 fields from `cds_schema_2025_26.json`). |
| [`docs/prd/002-frontend.md`](prd/002-frontend.md) | Full PRD with design decisions, visual spec, artifact JSON shape, and test plan. |

---

## How the pipelines compose

The five pipelines are loosely coupled but they do depend on each other in specific ways. A quick walkthrough of "what happens when" for each type of work:

**When a new CDS year is published by commondataset.org:**
1. Download the new XLSX template to `scratch/`
2. Run `build_from_xlsx.py` → produces `schemas/cds_schema_YYYY_YY.json`
3. Run `decode_checkboxes.py` → folds `value_options` into the same file
4. Commit the new schema file
5. Discovery pipeline picks it up automatically on next run (via the committed artifact, not a separate deploy)

**When a new school is added to the corpus:**
1. `build_school_list.py` runs against the latest IPEDS release → new school appears in `schools.yaml` with `scrape_policy: unknown`
2. `probe_urls.py` runs against the new `unknown` rows → finds a landing URL if the school has one, flips to `scrape_policy: active`
3. On the next discovery cron, the new school is crawled
4. On the next extraction worker run, any newly archived documents get extracted
5. Consumers can query the new data via the same `cds_manifest` endpoint

**When a consumer wants to know a specific school's 2024-25 CDS:**
```
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?school_id=eq.yale&canonical_year=eq.2024-25'
```
Returns a row from the `cds_manifest` view with the latest canonical artifact ID and the archived source path. Prefer `canonical_year` over `cds_year` — the former coalesces the content-derived `detected_year` (authoritative per ADR 0007) over the archive-time resolver guess. Follow `latest_canonical_artifact_id` to get the structured extract, or follow `source_storage_path` to download the original file.

**When a school removes their CDS from the web:**
1. The periodic re-check job (M3+ scope, on the backlog) HEADs every known `source_url` on some cadence
2. When a URL starts returning 404, the re-check job sets `cds_documents.removed_at = now()`
3. The archived file in Storage is untouched — consumers can still download the source, they just know the live URL is dead
4. The `cds_manifest` view still returns the row; consumers can filter on `removed_at is not null` if they care

**When a school refuses to publish (University of Chicago, Reed):**
1. In `schools.yaml`, their entry has `scrape_policy: verified_absent`
2. The discovery pipeline skips them (doesn't waste probes)
3. On first discovery pipeline run, their `cds_documents` row is upserted with `participation_status = verified_absent` and `extraction_status = not_applicable`
4. Consumers querying "schools with no CDS" get these as a first-class state, distinct from "schools we haven't found yet"

---

## Environment and deployment

Data infrastructure runs on **Supabase** (single vendor per ADR 0001). The frontend is hosted on **Vercel** (presentation layer only, per ADR 0001's distinction between data infrastructure and presentation).

| Component | Platform | Notes |
|---|---|---|
| Schema migrations | Supabase | `supabase/migrations/` + `supabase db push` |
| Discovery edge functions | Supabase | `supabase/functions/` + `supabase functions deploy` |
| Postgres tables, views, RLS | Supabase | Managed by migrations |
| Storage bucket | Supabase | Created by initial migration via `storage.buckets` insert |
| Cron schedule | Supabase | `pg_cron` + `net.http_post` |
| API custom domain | Supabase | `api.collegedata.fyi` → PostgREST |
| PostgREST API | Supabase | Automatic from Postgres + RLS policies |
| Python extraction worker | External | Local laptop for V1, GitHub Actions cron for scale |
| **Frontend** | **Vercel** | Next.js at `collegedata.fyi`, consumes PostgREST API |
| Offline corpus tools | Local | Pure Python, no Supabase interaction |
| Offline schema tools | Local | Pure Python, no Supabase interaction |

The offline tools (schema + corpus) produce committed artifacts that ship with the repo. The online pipelines (discovery + extraction + consumer API) run against Supabase. The frontend runs on Vercel and reads from the Supabase API via the anon key.

---

## Where the architecture is still incomplete

As of 2026-04-15, what's built and what isn't:

| Component | Status |
|---|---|
| Schema pipeline | ✅ Built end-to-end. 1,105 fields for 2025-26, 224 button fields decoded. |
| Corpus pipeline | ✅ Built. 2,434 schools in `schools.yaml`, 839 archivable (scrape_policy=active + cds_url_hint present + no sub_institutions). Probe runs are ongoing. |
| Discovery: M1a dry-run (HTML parsing, year normalization, two-hop) | ✅ Refactored into `_shared/resolve.ts` so it can be reused by the queue consumer. Served by the `discover` edge function as a dry-run dev entry. |
| Discovery: M1b writeback (schools.yaml loading, Storage uploads, `cds_documents` + `cds_artifacts` upserts) | ✅ Implemented in `archive-process` edge function. Uses SHA-addressed Storage paths (`{school}/{year}/{sha256}.{ext}`) and the document-first-then-artifact crash-safe refresh ordering. Verified end-to-end against yale + 9 other schools in production. |
| Discovery: M1c cron schedule (queue fan-out) | ✅ Live 2026-04-15. Daily `archive-enqueue-daily` + per-30s `archive-process-every-30s` running against production. First full drain completed overnight 2026-04-14/15: 535 done, 302 failed_permanent, 518 archived. Failure analysis in [`docs/archive-pipeline.md`](./archive-pipeline.md) and [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md). |
| Extraction worker (polling loop) | ✅ M2 skeleton live (commit `db520e6`). Polls `extraction_pending`, detects format, routes to tier extractors. Content-based PDF year detection ([ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)) is now write-authoritative: `detect_year_from_pdf_bytes` runs on every archived doc and writes `cds_documents.detected_year`, which the `cds_manifest.canonical_year` view prefers over `cds_year`. Stage B backfill 2026-04-15 populated `detected_year` on 379 of 518 archived rows (73%) via the `--detect-year-only --write` harness. |
| Extraction: Tier 2 (fillable PDF) | ✅ Built as standalone tool, verified 31/31 against HMC ground truth. Wired end-to-end through the worker; Harvey Mudd and Bates extracted successfully in production. |
| Extraction: Tier 4 (flattened PDF via Docling) | ✅ Wired end-to-end through the worker (commit `37293ab`). Docling baseline config (TableFormer FAST, 1x DPI) chosen after a 9-config bake-off scored 21/21 on critical C1 fields across Yale, Harvard, and Dartmouth (commit `e15a5d3`). Output is raw markdown stored in `cds_artifacts.notes`; a schema-targeting cleaner to map markdown → canonical question numbers is a follow-up. Reducto reference extracts remain in `tools/extraction-validator/references/reducto/` as a quality benchmark for a potential future upgrade. |
| Extraction: Tier 1 / 3 / 5 | ❌ Specified in ADR 0006, not yet built. Worker routes these to a stub that records `extraction_status=failed` with a tier-not-implemented reason so the rows exit the pending queue. |
| Year authority migration | ✅ Stage A + B shipped 2026-04-15 ([ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)). Content detection is authoritative; resolver `pickCandidates` fans out landing-page anchors into multiple `cds_documents` rows; extraction writes `detected_year`; `cds_manifest.canonical_year` prefers content over URL. Stage C was de-scoped to docs-only — full retirement of `cds_year` and `_shared/year.ts` requires dropping `cds_year` from the unique constraint, deferred to a follow-up item in [backlog.md](./backlog.md). |
| Consumer API | ✅ Live at `api.collegedata.fyi/rest/v1/`. All three tables + the view respond to curl. |
| Frontend | ✅ Live at `collegedata.fyi` (Vercel). 5 pages: landing with search, school directory, school detail, year detail with field viewer, about. Consumes the PostgREST API. See [`docs/prd/002-frontend.md`](prd/002-frontend.md). |

"Built" means the code exists and has been exercised against real data. "Not yet built" means the design is specified but no code exists. "Reference extracts exist" means we have the raw output from an external tool but no production path from raw → canonical.

---

## Related docs

- [`docs/prd/001-collegedata-fyi-v1.md`](prd/001-collegedata-fyi-v1.md) — product-level framing, scope, milestones, success criteria
- [`docs/prd/002-frontend.md`](prd/002-frontend.md) — frontend PRD (CEO + Design + Eng reviewed)
- [`docs/frontend.md`](frontend.md) — frontend design: pages, components, data flow, SEO, security
- [`docs/v1-plan.md`](v1-plan.md) — engineering plan with data model details and milestone breakdown
- [`docs/research/cds-vs-college-scorecard.md`](research/cds-vs-college-scorecard.md) — CDS vs College Scorecard schema comparison
- [`docs/research/scorecard-join-recipe.md`](research/scorecard-join-recipe.md) — how to join CDS data with Scorecard
- [`docs/research/scorecard-summary-table-v2-plan.md`](research/scorecard-summary-table-v2-plan.md) — V2 plan for hosting Scorecard summary data
- [`docs/decisions/`](decisions/) — ADRs 0001-0007 for every foundational choice
- [`docs/backlog.md`](backlog.md) — priority queue for near-term work
- [`docs/known-issues/`](known-issues/) — per-school extraction quality notes
