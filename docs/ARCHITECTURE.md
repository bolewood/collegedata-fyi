# collegedata.fyi — Architecture

How the pieces fit together at runtime. Complements [`docs/v1-plan.md`](v1-plan.md) (engineering plan, data model details) and [`docs/prd/001-collegedata-fyi-v1.md`](prd/001-collegedata-fyi-v1.md) (product-level framing).

---

## Overview

The project has eight logical pipelines, each running at a different cadence and responsibility boundary:

1. **Schema pipeline** — once per CDS year. Extracts the canonical schema from commondataset.org's official XLSX template into a committed JSON artifact. Also folds per-field checkbox value decoders into the same artifact.
2. **Corpus pipeline** — once per month or so. Builds the canonical school list from IPEDS data and enriches it with URL hints discovered by a pattern-ladder prober.
3. **Discovery pipeline** — nightly via cron. Reads the canonical school list, crawls each school's IR landing page, extracts every CDS-ish document anchor (multi-candidate per ADR 0007 Stage B), archives source bytes to Storage, and upserts one `cds_documents` row per archived file. Academic year is assigned later by the extraction pipeline from page-1 content, not from the URL.
4. **Mirror pipeline** — monthly or ad-hoc. Ingests third-party CDS archives (College Transitions today; Wayback Machine, others later) as a gap-filler when a school's own IR page 404s or is auth-walled. Every row carries a structured `source_provenance` tag so consumers can filter on `school_direct` for authoritative data or include mirror rows for maximum coverage. The mirror never overwrites; the school's own publication always wins.
5. **Extraction pipeline** — triggered by discovery. Pulls each `extraction_pending` row, downloads the archived source, detects format, routes to a tier-specific extractor, and writes a `canonical` artifact back. A schema-aware LLM fallback ([PRD 006](prd/006-llm-fallback.md)) runs after the deterministic Tier 4 cleaner on low-coverage docs and writes a separate `cds_artifacts` row with `producer='tier4_llm_fallback'`; consumers merge the two per Mode B only when the fallback matches the selected Tier 4 base artifact (cleaner wins, fallback fills gaps).
6. **Scorecard pipeline** — once per year. Ingests the federal College Scorecard Most-Recent Institution CSV into `scorecard_summary` (curated 41-column subset, one row per IPEDS UNITID — currently 6,322 rows from the March 2026 / 2022-23-vintage release). Joins to the CDS corpus via `cds_documents.ipeds_id`, sourced from `schools.yaml` at archive time. Exposed through the `cds_scorecard` view at `/rest/v1/cds_scorecard`. The `refresh_summary.py` loader carries a schema-drift guard that aborts loudly on Scorecard column renames (Scorecard's data dictionary is not stable across years). See [`tools/scorecard/README.md`](../tools/scorecard/README.md).
7. **Consumer API** — on demand. PostgREST serves the manifest, `cds_manifest`, `cds_fields`, and `school_browser_rows` at `api.collegedata.fyi/rest/v1/`. Public Storage URLs serve the archived source files. The `browser-search` Edge Function exposes the ranked latest-per-school contract for the queryable browser.
8. **Frontend** — on demand. A Next.js app at `collegedata.fyi` (hosted on Vercel) consumes the PostgREST API and browser-search Edge Function, rendering a searchable school directory, queryable school browser, per-school document archives, and per-year structured field viewers. The visual system is documented in [`web/DESIGN_SYSTEM.md`](../web/DESIGN_SYSTEM.md), with canonical tokens in [`web/src/app/tokens.css`](../web/src/app/tokens.css) and a live reference page at [`/design-system/`](https://collegedata.fyi/design-system/). Every agent or contributor touching UI should read the design system first. See also [`docs/prd/002-frontend.md`](prd/002-frontend.md) and [`docs/prd/010-queryable-data-browser.md`](prd/010-queryable-data-browser.md) for product framing.

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
  │    → fills discovery_seed_url on hits       │            │
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
  │         - Fetch discovery_seed_url landing page                     │
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
  │              │       → tools/tier1_extractor/extract.py      │      │
  │              │         template cell-position map + openpyxl │      │
  │              │       ~100% accuracy on standard template     │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 2  unflattened fillable PDF            │      │
  │              │       → tools/tier2_extractor/extract.py      │      │
  │              │         pypdf.get_fields() + schema join      │      │
  │              │         + value_options decoder               │      │
  │              │       ~100% accuracy when applicable          │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 3  filled DOCX  (PRD 007, not built)   │      │
  │              │       → python-docx reads SDT tags            │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 4  flattened PDF                       │      │
  │              │       → Docling + schema-targeting cleaner    │      │
  │              │       variable quality (GT 94%)               │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 5  image-only scan                     │      │
  │              │       → Tier 4 with force_ocr=True            │      │
  │              │         (EasyOCR on every page)               │      │
  │              ├───────────────────────────────────────────────┤      │
  │              │   Tier 6  structured HTML (PRD 008)           │      │
  │              │       → html_to_markdown (BS4 + lxml)         │      │
  │              │         → tier4_cleaner.clean                 │      │
  │              │         producer='tier6_html'                 │      │
  │              └──────────────────┬────────────────────────────┘      │
  │                                 │                                   │
  │                                 ▼                                   │
  │         INSERT INTO cds_artifacts (kind='canonical', producer=...)  │
  │         UPDATE cds_documents SET extraction_status='extracted'      │
  │                                 │                                   │
  │                                 │   Tier 4 repair layer (PRD 006)   │
  │                                 ▼                                   │
  │              ┌────────────────────────────────────────────┐         │
  │              │ Tier 4 LLM fallback  (tools/extraction_    │         │
  │              │   worker/llm_fallback_worker.py)           │         │
  │              │                                            │         │
  │              │ For each low-coverage tier4_docling:       │         │
  │              │   - slice markdown by subsection           │         │
  │              │   - check cds_llm_cache                    │         │
  │              │   - call Claude Haiku 4.5 with cached      │         │
  │              │     glossary + per-subsection prompt       │         │
  │              │   - validate (type, evidence substring,    │         │
  │              │     sanity, row-merge guard)               │         │
  │              │   - INSERT cds_artifacts (kind='cleaned',  │         │
  │              │     producer='tier4_llm_fallback')         │         │
  │              │                                            │         │
  │              │ Mode B fill_gaps: cleaner always wins;     │         │
  │              │ fallback only fills blank question numbers │         │
  │              └────────────────────────────────────────────┘         │
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
  │                                     public.cds_fields               │
  │                                     public.school_browser_rows      │
  │                                                                     │
  │  <ref>.supabase.co/functions/v1/browser-search                      │
  │    - ranked latest-per-school search over school_browser_rows       │
  │    - answerability metadata for missing vs failing filters          │
  │                                                                     │
  │  Anon key in Authorization header.                                  │
  │  RLS allows public SELECT on the public tables/views.               │
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
| [`tools/finder/build_school_list.py`](../tools/finder/build_school_list.py) | Downloads the IPEDS HD CSV from NCES, filters to 4-year degree-granting US non-profit institutions, merges with existing hand-curated entries in `schools.yaml`, writes back. Preserves hand-curated `discovery_seed_url`, `browse_url`, `sub_institutions`, `notes`, `scrape_policy` (and the legacy `cds_url_hint` alias during migration). |
| [`tools/finder/probe_urls.py`](../tools/finder/probe_urls.py) | For each school with `scrape_policy: unknown`, walks a ladder of URL patterns (`/ir/cds/`, `/institutional-research/common-data-set/`, etc.) × 7 subdomains + 5 year-specific PDF patterns. On a hit, fills in `discovery_seed_url` and flips `scrape_policy` to `active`. Rate-limited to 1 req/s by default. Optional Bing/Google fallback. |
| [`tools/finder/schools.yaml`](../tools/finder/schools.yaml) | The canonical school list. 2,434 entries (82 hand-curated active, 2,350 IPEDS candidates awaiting probe, 2 verified absent). Post-PR-5 fields: `discovery_seed_url` (the resolver's seed URL — may be a direct PDF or a landing page) and optional `browse_url` (human-friendly URL surfaced by the kids worklist). |
| [`tools/finder/school_overrides.yaml`](../tools/finder/school_overrides.yaml) | Operator-supplied per-school overrides, keyed by `school_id`. Carries manual `browse_url`, year-tagged `direct_archive_urls` for Box/Drive/SharePoint-hosted schools, and `hosting_override` blocks that supersede inferred hosting facts. Read at edge-function runtime by `_shared/schools.ts`; NOT touched by `build_school_list.py` so IPEDS regeneration doesn't clobber operator data. |
| [`tools/finder/seed_urls.md`](../tools/finder/seed_urls.md) | Reference doc of seed URL patterns, the pbworks College Lists Wiki, known non-publishers, and known sub-institutional publishers. |

### Discovery + archive pipeline

Full operator runbook, architecture, failure-mode classification, and
production verification are in [`docs/archive-pipeline.md`](./archive-pipeline.md).
Summary of the components:

| Component | Role |
|---|---|
| [`supabase/functions/_shared/`](../supabase/functions/_shared/) | Shared Deno modules imported by all three edge functions: `year.ts` (URL-hint year guesser — **not authoritative for document year** per ADR 0007; used by `pickCandidates` as a partitioning signal and to populate the NOT NULL `cds_year` column), `resolve.ts` (HTML parsing, two-hop, SSRF guard, multi-candidate `pickCandidates`, discriminated `ResolveResult` with optional probe data for hosting inference), `probe_outcome.ts` (typed ProbeOutcome enum + per-outcome cooldown map; category-carrying `PermanentError`/`TransientError`), `hosting.ts` (pure `inferHosting` function — derives CMS, file_storage, auth_required, rendering, WAF from probe headers + final URL), `schools.ts` (schools.yaml + school_overrides.yaml fetch + merge), `storage.ts` (SHA-addressed path helpers), `db.ts` (`cds_documents` + `cds_artifacts` DAL), `archive.ts` (one-school orchestrator; writes `school_hosting_observations` rows when `HOSTING_OBSERVATIONS_ENABLED=true`). |
| [`supabase/functions/discover/index.ts`](../supabase/functions/discover/index.ts) | Resolver dev entry. HTTP `?schools=yale,mit,...` returns a `ResolveResult` per school as JSON. **No writes.** Used for iterating on the resolver and debugging `no_cds_found` cases. Capped at 10 schools per request. |
| [`supabase/functions/archive-process/index.ts`](../supabase/functions/archive-process/index.ts) | Queue consumer. Invoked every 30 s by pg_cron. Claims one row via `claim_archive_queue_row()` RPC, runs `archiveOneSchool`, marks terminal state in a `finally` block guarded by the claim lease. Also supports `?force_school=<id>` for operator backfill that bypasses the queue. |
| [`supabase/functions/archive-enqueue/index.ts`](../supabase/functions/archive-enqueue/index.ts) | Monthly seeder. Invoked daily at 02:00 UTC by pg_cron. Fetches `schools.yaml` from GitHub raw, derives a deterministic `run_id` from the current calendar month, applies per-outcome cooldown (skips schools whose most recent `done`/`failed_permanent` row falls inside its `DEFAULT_COOLDOWN_DAYS` window — 30d for `unchanged_verified`, 90d for `auth_walled_*`, etc.), bulk-upserts one `archive_queue` row per remaining active school with `ignoreDuplicates=true`. Repeated daily runs within a month are no-ops. Operator overrides: `?force_recheck=true` bypasses cooldown; `?cooldown_days=N` applies a uniform window. |
| [`supabase/migrations/20260414170000_archive_pipeline.sql`](../supabase/migrations/20260414170000_archive_pipeline.sql) | Schema foundations. Fixes the silent NULL-uniqueness bug on `cds_documents` (`UNIQUE NULLS NOT DISTINCT`), creates `archive_queue`, defines `claim_archive_queue_row()` with atomic attempts increment + 10-min visibility timeout + `FOR UPDATE SKIP LOCKED`. Includes an inline self-test for the constraint swap. |
| [`supabase/migrations/20260418220000_archive_queue_last_outcome.sql`](../supabase/migrations/20260418220000_archive_queue_last_outcome.sql) | Adds `archive_queue.last_outcome` column (CHECK-constrained to `ArchiveAction` values initially; extended to full `ProbeOutcome` in the next migration). Drives the cooldown filter in `archive-enqueue`. Partial index on `(school_id, processed_at desc) WHERE status='done' AND last_outcome='unchanged_verified'`. |
| [`supabase/migrations/20260418230000_probe_outcome_categories.sql`](../supabase/migrations/20260418230000_probe_outcome_categories.sql) | Extends `archive_queue.last_outcome` CHECK to all 15 `ProbeOutcome` values (success + failure categories like `auth_walled_microsoft`, `dead_url`, `no_pdfs_found`, etc.). Backfills historical `failed_permanent` rows by parsing `last_error` into structured categories. Adds a failure-outcome partial index for analytics. |
| [`supabase/migrations/20260419000000_school_hosting_observations.sql`](../supabase/migrations/20260419000000_school_hosting_observations.sql) | Append-only log of what the resolver learned about each school's hosting environment on each probe. Inferred dimensions (CMS, file_storage, auth_required, rendering, WAF) plus per-observation outcome + truncated error reason. Plus `latest_school_hosting` view (DISTINCT ON per school, most recent) for consumers that want current state without history. Write gated by `HOSTING_OBSERVATIONS_ENABLED` env var in `archive-process`. |
| [`supabase/migrations/20260419100000_source_provenance.sql`](../supabase/migrations/20260419100000_source_provenance.sql) | Adds `cds_documents.source_provenance` (CHECK-constrained: `school_direct` / `mirror_college_transitions` / `operator_manual`; default `school_direct`) + index on `(source_provenance, cds_year)`. The distinguishing-authoritative-from-mirror signal consumers filter on. Threaded through `archiveOneCandidate` → `insertFreshDocument` / `refreshDocumentWithNewSha`; refresh always writes `school_direct` so a school's publication always upgrades a prior mirror copy. |
| [`supabase/migrations/20260414180000_archive_pipeline_cron.sql`](../supabase/migrations/20260414180000_archive_pipeline_cron.sql) | pg_cron schedules. Wires the outer daily + inner 30-s jobs via `net.http_post`, with both the function base URL and the service role key stored as Vault secrets. Gracefully skips scheduling in environments where the Vault secrets are missing (local dev). |
| [`supabase/config.toml`](../supabase/config.toml) | Edge function configuration. `verify_jwt = true` on all three functions. `archive-process` and `archive-enqueue` additionally do an in-handler service-role check via `isServiceRoleAuth()` so that a plain authenticated project user cannot trigger writes. |
| [`schemas/cds_schema_YYYY_YY.json`](../schemas/) | Not directly used by the edge functions. The `sources` bucket path convention and the `cds_documents` column layout both reference concepts from the canonical schema. |

### Mirror pipeline

Ingests third-party CDS archives as a gap-filler. The school's own publication always wins; mirrors only insert rows for (school, year) pairs we don't already have.

| Component | Role |
|---|---|
| [`tools/mirrors/README.md`](../tools/mirrors/README.md) | The mirror pattern. Every mirror subdirectory follows the same contract: `fetch.py` refreshes a committed `catalog.json`; `ingest.py` cross-references against `cds_documents` and calls `force_urls` for the gap set with the right `source_provenance` tag. Documents how to add a new mirror (schema migration + allowlist update + scripts). |
| [`tools/mirrors/college_transitions/`](../tools/mirrors/college_transitions/) | First mirror wired up. Re-hosts 1,983 CDS files across 333 schools on Google Drive (2019-20 through 2024-25 window). `fetch.py` uses Playwright to pull the FooTable's in-memory row data and match schools against our corpus; `ingest.py` POSTs gaps to `archive-process?POST force_urls` with `source_provenance='mirror_college_transitions'`. Spot-check + content-diff diagnostics live in the same directory. |
| [`supabase/functions/archive-process/index.ts`](../supabase/functions/archive-process/index.ts) (`runForceUrls`) | The ingest target. Accepts optional `source_provenance` in the POST body, validates against an allowlist, threads it into `archiveManualUrls` → `archiveOneCandidate` → `insertFreshDocument`. Default behavior (missing / invalid provenance) falls through to `school_direct`, which is correct for the existing manual_urls.yaml / Playwright-collector call sites. |
| [`supabase/functions/_shared/resolve.ts`](../supabase/functions/_shared/resolve.ts) (`rewriteGoogleDriveUrl`) | Handles Drive-hosted mirror URLs. Rewrites `/file/d/<id>/view` and `/open?id=<id>` share URLs to the `uc?export=download&id=<id>` endpoint that returns the actual bytes. Also handles Google Sheets (`docs.google.com/spreadsheets/d/<id>/edit` → `/export?format=xlsx`) so CT's sheet-format entries work. |

### Extraction pipeline

| Component | Role |
|---|---|
| [`tools/extraction_worker/worker.py`](../tools/extraction_worker/worker.py) | Python worker. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`, downloads the archived source, runs `pypdf.get_fields()` to detect format, performs content-based PDF year detection via `detect_year_from_pdf_bytes` and writes the result to `cds_documents.detected_year` — authoritative per [ADR 0007](decisions/0007-year-authority-moves-to-extraction.md) Stage B — then routes to the appropriate tier extractor and writes the result back as a `cds_artifacts` row with `kind=canonical`. Supports a `--detect-year-only --write` harness mode that runs the year detector against every archived document and backfills `detected_year` without touching extraction. Wired end-to-end for Tier 1 (xlsx), Tier 2 (fillable PDF), Tier 4 (flattened PDF via Docling), and Tier 5 (scanned PDF via Tier 4 + force-OCR). Tier 3 (docx) is still a stub pending [PRD 007](prd/007-tier3-docx-extraction.md). |
| [`tools/tier1_extractor/extract.py`](../tools/tier1_extractor/extract.py) | Tier 1 extractor. Parses the CDS Excel template's hidden lookup columns (AA/AC on each `CDS-*` sheet) to build a `{question_number: (sheet, cell_ref)}` map, then reads those cells from any filled XLSX. Emits canonical JSON keyed by `question_number`. Deterministic when the school uses the standard template layout. Median 307 fields populated across 289 tier1_xlsx artifacts on the first full drain (2026-04-20); max 782 fields. |
| [`tools/tier2_extractor/extract.py`](../tools/tier2_extractor/extract.py) | Tier 2 extractor. Reads a CDS PDF via `pypdf.get_fields()`, joins against the schema by `pdf_tag`, decodes button values via `value_options`, emits canonical JSON keyed by `question_number`. Deterministic, ~100% accurate on HMC (31/31 ground-truth fields, verified by `score_tier2.py`). |
| [`tools/extraction_worker/tier4_extractor.py`](../tools/extraction_worker/tier4_extractor.py) | Tier 4 extractor. Converts a flattened CDS PDF with the tuned Docling config (`TableFormer FAST`, OCR on but not forced, 1x DPI, orphan layout clusters disabled). Emits raw markdown, compact native table cells/provenance under `notes.native_tables`, and the cleaner-produced `values` dict. Accepts a `force_ocr` parameter which, when True, swaps in `EasyOcrOptions(force_full_page_ocr=True)` — that's the Tier 5 path for scanned PDFs. |
| [`tools/extraction_worker/tier4_native_tables.py`](../tools/extraction_worker/tier4_native_tables.py) | Compact serializer for Docling native table cells. Preserves row/column offsets, cell flags, bboxes, and table provenance so deterministic native-table parsers can run before any LLM repair. |
| [`tools/extraction_worker/tier4_cleaner.py`](../tools/extraction_worker/tier4_cleaner.py) | Tier 4 schema-targeting cleaner. Parses Docling markdown tables + inline text and emits `{question_number: {"value": str}}` matching the Tier 2 output shape. Handles the 2020 CDS template rename (`freshmen`→`first-year`), the 2024-25→2025-26 gender-category collapse, wrapped row labels (Dartmouth B1 pattern), header-less one-metric-per-row tables (Aims community-college pattern), and non-table fields via `_INLINE_PATTERNS` (C13 application fee, Harvard-style Submitting SAT). GT scorer 94.3% across Harvard/Yale/Dartmouth/HMC (83/88 fields), 100% on critical C1 admissions across the 21 critical fields. [PRD 005](prd/005-full-schema-extraction.md) plans expansion to full 1,105-field coverage via a schema-driven resolver framework. |
| Tier 3 extractor **(not yet built)** | Specified in ADR 0006; design detailed in [PRD 007](prd/007-tier3-docx-extraction.md). Will use `python-docx` to read the CDS Word template's 1,204 Structured Document Tags (SDTs) whose `w:tag` values match the schema's `word_tag` field exactly — same deterministic-lookup pattern as Tier 2. Kent State has ~14 SDT-preserving DOCX files in the corpus averaging 769 populated tags. |
| [`tools/extraction-validator/score_tier2.py`](../tools/extraction-validator/score_tier2.py) | Regression scoring tool for Tier 2 output. Loads a ground-truth YAML, a Tier 2 extract JSON, and an ID map; compares every field with numeric tolerance; emits per-field diff + overall accuracy. Offline quality check, not part of the runtime pipeline. |
| [`tools/extraction-validator/score_tier4.py`](../tools/extraction-validator/score_tier4.py) | Regression scoring tool for Tier 4 output. Takes a Docling markdown file, runs `tier4_cleaner.clean()` against it, joins the resulting values to ground truth via the id_map, and reports per-field match + overall accuracy. Same shape as `score_tier2.py`. Exits non-zero if any critical field fails. `--include-llm-artifact` merges fallback values per Mode B before scoring — the PRD 006 regression check. |
| [`tools/extraction-validator/corpus_survey_tier4.py`](../tools/extraction-validator/corpus_survey_tier4.py) | Read-only corpus survey. Pulls every `tier4_docling` canonical artifact from the DB, re-runs the current cleaner against the stored markdown, and reports distribution of fields-populated + per-question coverage across the corpus. The ongoing coverage gauge — safe to run while the extraction worker is writing. `--include-fallback` additionally loads `tier4_llm_fallback` artifacts and reports cleaner-only vs cleaner+fallback per-section-family delta. |
| [`tools/extraction-validator/inspect_tier4_doc.py`](../tools/extraction-validator/inspect_tier4_doc.py) | Read-only single-doc inspector. Pulls one school's stored Docling markdown and dumps a section slice. Used to diagnose low-coverage docs surfaced by the corpus survey. |
| [`tools/extraction_worker/subsection_slicer.py`](../tools/extraction_worker/subsection_slicer.py) | Locates CDS subsections (H5-H8, C13-C22, D2-D16, G5, C11) in Docling markdown via a six-strategy layered matcher (`##` header, `###` header, bullet, bold, row-label anchor, bounded-window fallback). Reports which strategy hit per subsection so the Phase 0 report can catch docs where subsection scoping breaks down. CLI entry point for inspection. |
| [`tools/extraction_worker/llm_client.py`](../tools/extraction_worker/llm_client.py) | Thin Anthropic SDK wrapper. Splits the prompt into a cacheable glossary (stable across every subsection and every doc) and a doc-specific uncached tail. Per-call cost estimation from a local pricing table keyed by model. Default: Claude Haiku 4.5 with prompt caching. |
| [`tools/extraction_worker/tier4_llm_fallback.py`](../tools/extraction_worker/tier4_llm_fallback.py) | Prompt builder, deterministic validator, and merge policy for the LLM fallback ([PRD 006](prd/006-llm-fallback.md)). Builds per-subsection prompts with pdf_tag disambiguation hints for the 14 irreducibly ambiguous fields, position-within-row hints for D.13-D.16, and anchor-text hints for C.16/C.17 dates. Validators: type check via `_extract_number`/`_extract_currency`, evidence substring against markdown, section-local sanity (MM 1-12, DD 1-31, percent 0-100), row-merge guard, value-in-evidence for numerics. No DB writes — transport-agnostic. |
| [`tools/extraction_worker/llm_fallback_bench.py`](../tools/extraction_worker/llm_fallback_bench.py) | Phase 0 standalone benchmark CLI. Reads existing `tier4_docling` artifacts, runs section-scoped LLM prompts, validates, writes JSON reports to disk. No DB writes. Decision-gate tool: produces cost/coverage numbers before production infrastructure lands. |
| [`tools/extraction_worker/llm_fallback_worker.py`](../tools/extraction_worker/llm_fallback_worker.py) | Phase 1 production worker. Finds eligible low-coverage `tier4_docling` artifacts, slices subsections, checks `cds_llm_cache`, calls the LLM on misses, validates, and writes a `cds_artifacts` row with `producer='tier4_llm_fallback'` per Mode B (fill_gaps). Budget gates per doc + per run; delete-then-insert on the artifact row to avoid duplicate accumulation across re-runs. 244 docs backfilled for 2024-25 on 2026-04-20 (mean 28.2 fields added/doc, ~$0.06/doc). See [`docs/tier4-llm-fallback.md`](tier4-llm-fallback.md). |
| [`supabase/migrations/20260420140000_cds_llm_cache.sql`](../supabase/migrations/20260420140000_cds_llm_cache.sql) | Internal response cache for the Tier 4 LLM fallback. Keyed by `(source_sha256, markdown_sha256, section_name, schema_version, model_name, prompt_version, strategy_version, cleaner_version, missing_fields_sha256)` via a dedicated unique index. `source_sha256` mirrors `cds_documents.source_sha256`; `markdown_sha256` is hashed at runtime from `notes.markdown` on the Docling artifact. Service-role access only. |
| [`tools/extraction-validator/ground_truth/`](../tools/extraction-validator/ground_truth/) | Hand-verified ground truth YAMLs (one per school-year). The scoring reference for both tiers. |
| [`tools/extraction-validator/id_maps/`](../tools/extraction-validator/id_maps/) | Hand-built maps from ground-truth IDs (`b1_ft_firstyear_men`) to canonical question numbers (`B.101`). One file per school-year. Covers Harvey Mudd 2025-26, Harvard 2024-25, Yale 2024-25, Dartmouth 2024-25. |
| [`tools/extraction-validator/references/reducto/`](../tools/extraction-validator/references/reducto/) | Curated Reducto API reference extracts for HMC and Yale. Not used at runtime; kept as a quality benchmark for future Tier 4 work. |

### Consumer API

| Component | Role |
|---|---|
| Supabase PostgREST | Exposes `public.cds_documents`, `public.cds_artifacts`, `public.cleaners`, and the `public.cds_manifest` view at `api.collegedata.fyi/rest/v1/`. Public-read via RLS policies defined in the initial migration. |
| Supabase Storage | Serves archived source files from the `sources` bucket at `{project-ref}.supabase.co/storage/v1/object/public/sources/{school_id}/{cds_year}/{sha256}.{ext}`. The `{cds_year}` segment is the archive-time resolver guess, frozen at upload time; the authoritative content-derived year lives in `cds_documents.detected_year` and is exposed as `canonical_year` in the manifest (see ADR 0007 Stage B trade-offs). SHA-addressed so every version is preserved forever (ADR 0006). Consumers discover the exact path via `cds_manifest.source_storage_path`, never by construction. Public bucket, MIME allowlist enforces PDF/XLSX/DOCX only. |
| [`supabase/migrations/20260413201910_initial_schema.sql`](../supabase/migrations/20260413201910_initial_schema.sql) | Creates the three core tables, RLS policies, the manifest view, the Storage bucket, and the `sources` public-read policy. |
| [`supabase/migrations/20260426120000_queryable_browser_backend.sql`](../supabase/migrations/20260426120000_queryable_browser_backend.sql) | Adds the PRD 010 query surfaces: `cds_field_definitions`, `cds_metric_aliases`, `cds_selected_extraction_result`, `cds_fields`, and `school_browser_rows`. Public-read RLS is enabled on the public tables/views. |
| [`tools/browser_backend/project_browser_data.py`](../tools/browser_backend/project_browser_data.py) | Materializes selected extraction results into `cds_fields` and `school_browser_rows`, seeding field metadata and direct metric aliases from the committed schema artifacts. |
| [`supabase/functions/browser-search/`](../supabase/functions/browser-search/) | Edge Function and pure search contract for ranked latest-per-school queries, including answerability counts and operator/null semantics. |

### Frontend

| Component | Role |
|---|---|
| [`web/`](../web/) | Next.js 16 app hosted on Vercel at `collegedata.fyi`. Consumes the PostgREST API via `@supabase/supabase-js` with the anon key. Read-only, no auth, no write paths. |
| [`web/src/app/page.tsx`](../web/src/app/page.tsx) | Landing page with school search autocomplete and live corpus stats. |
| [`web/src/app/browse/page.tsx`](../web/src/app/browse/page.tsx) | Queryable school browser page backed by `browser-search`. Defaults to latest primary 2024-25+ rows and exposes answerability metadata plus CSV export. |
| [`web/src/app/schools/page.tsx`](../web/src/app/schools/page.tsx) | School directory: searchable, sortable table of all schools with archived CDS data. |
| [`web/src/app/schools/[school_id]/page.tsx`](../web/src/app/schools/[school_id]/page.tsx) | School detail: document list with status badges, PDF download links, sub-institutional support. |
| [`web/src/app/schools/[school_id]/[year]/page.tsx`](../web/src/app/schools/[school_id]/[year]/page.tsx) | Year detail (SEO answer page): key stats block + full structured field viewer grouped by CDS section. |
| [`web/src/lib/queries.ts`](../web/src/lib/queries.ts) | Supabase query layer. `fetchExtract(documentId)` loads the selected canonical artifact and latest `tier4_llm_fallback` artifact in parallel, then merges per Mode B only if the fallback matches the selected base artifact by `base_artifact_id` or legacy markdown hash + cleaner version. The fallback fills question numbers the cleaner left blank; cleaner wins on collision. Callers (`page.tsx`, `opengraph-image.tsx`) render `mergedValues` directly. |
| [`web/src/lib/browser-search.ts`](../web/src/lib/browser-search.ts) | Typed client for the `browser-search` Edge Function. Used by the `/browse` MVP. |
| [`web/src/lib/labels.ts`](../web/src/lib/labels.ts) | Auto-generated CDS field ID to plain-English label map (1,105 fields from `cds_schema_2025_26.json`). |
| [`docs/prd/002-frontend.md`](prd/002-frontend.md) | Full PRD with design decisions, visual spec, artifact JSON shape, and test plan. |

### Data quality

| Component | Role |
|---|---|
| [`tools/data_quality/audit_manifest.py`](../tools/data_quality/audit_manifest.py) | Post-ingest audit. Queries canonical artifacts, flags documents with <5 fields populated as `blank_template` or `low_coverage`. Writes `data_quality_flag` to `cds_documents`. |
| [`tools/data_quality/completeness_report.py`](../tools/data_quality/completeness_report.py) | Top-to-bottom funnel pivot — corpus → discovered → archived → extracted → high_quality, per `cds_year`. Default window = past 5 CDS years. Output: terminal table + JSON. Used to size the coverage picture. |
| [`tools/data_quality/active_schools_missing_recent.py`](../tools/data_quality/active_schools_missing_recent.py) | Per-school CSV of which active schools lack docs for which recent years. Feeds the kids-worklist pipeline below. |
| [`tools/data_quality/kids_worklist.py`](../tools/data_quality/kids_worklist.py) | Kid-friendly batched CSVs (50/batch) of active schools missing recent years. Queries `latest_school_hosting` to skip auth-walled schools, prefers `browse_url` over `discovery_seed_url` for the link column, surfaces a `hosting_note` so contributors know what to expect (Box folder, JS-rendered, "needs landing page", etc.). Applies `school_overrides.yaml` on top of DB observations. |
| [`tools/data_quality/force_resolve_missing.py`](../tools/data_quality/force_resolve_missing.py) | Parallel `force_school` caller. `--all` runs against every active school with a `discovery_seed_url`; default mode targets schools missing recent years. Captures structured `ProbeOutcome` categories into JSONL for analysis. |
| [`supabase/migrations/20260418120000_data_quality_flag.sql`](../supabase/migrations/20260418120000_data_quality_flag.sql) | Adds `data_quality_flag` column to `cds_documents`, exposed in `cds_manifest` view. |
| [`tools/finder/promote_landing_hints.py`](../tools/finder/promote_landing_hints.py) | Rewrites direct-PDF `discovery_seed_url` entries in `schools.yaml` to their parent IR landing pages, enabling multi-year discovery. Applied to 67 schools (`ce1a9ac`). Reads either legacy `cds_url_hint` or post-PR-5 `discovery_seed_url`; always writes the new field name. |

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

As of 2026-04-18, what's built and what isn't:

| Component | Status |
|---|---|
| Schema pipeline | ✅ Built end-to-end. 1,105 fields for 2025-26, 224 button fields decoded. Per-section-tab structural schemas for 6 years (2019-20 through 2025-26) and cross-year diffs for 5 transitions shipped 2026-04-17 (`351af48`, `526ded7`). |
| Corpus pipeline | ✅ Built. `schools.yaml` tracks 2,434+ schools. 617 with archived data, 2,913 documents in the database. Playwright-assisted probing and `promote_landing_hints.py` tool (`b56ef97`) improved landing-page hint quality for 67 schools (`ce1a9ac`). |
| Discovery: M1a dry-run (HTML parsing, year normalization, two-hop) | ✅ Refactored into `_shared/resolve.ts` so it can be reused by the queue consumer. Served by the `discover` edge function as a dry-run dev entry. |
| Discovery: M1b writeback (schools.yaml loading, Storage uploads, `cds_documents` + `cds_artifacts` upserts) | ✅ Implemented in `archive-process` edge function. Uses SHA-addressed Storage paths (`{school}/{year}/{sha256}.{ext}`) and the document-first-then-artifact crash-safe refresh ordering. Verified end-to-end against yale + 9 other schools in production. |
| Discovery: M1c cron schedule (queue fan-out) | ✅ Live 2026-04-15. Daily `archive-enqueue-daily` + per-30s `archive-process-every-30s` running against production. First full drain completed overnight 2026-04-14/15. Resolver enhanced 2026-04-17/18 with well-known-paths fallback (`df574a4`), parent-ancestor walking for sibling years (`39bf219`), Box share-URL rewriter (`ec3c03c`), and `force_urls` batch archive endpoint (`5cc6718`). Playwright URL collector and headless-browser download added for JS-rendered / WAF-blocked schools per [PRD 004](prd/004-js-rendered-resolver.md). |
| Extraction worker (polling loop) | ✅ Full-corpus drain completed 2026-04-20: 3,948 of 4,131 documents extracted (96%). Polls `extraction_pending`, detects format, routes to tier extractors. Includes `\u0000` null-byte stripping for malformed PDF text streams (Berklee fix, `9b7f3f7`). Content-based PDF year detection ([ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)) is write-authoritative. |
| Extraction: Tier 1 (filled XLSX) | ✅ Shipped 2026-04-20. `tools/tier1_extractor/extract.py` parses the CDS Excel template's hidden lookup columns to build a cell-position map, then reads those cells from filled workbooks. 289 tier1_xlsx artifacts written across the first full drain, median 307 fields/doc, max 782. |
| Extraction: Tier 2 (fillable PDF) | ✅ Built as standalone tool, verified 31/31 against HMC ground truth. Wired end-to-end through the worker; Harvey Mudd and Bates extracted successfully in production. 135+ tier2_acroform artifacts. |
| Extraction: Tier 4 (flattened PDF via Docling) | ✅ 3,500+ tier4_docling artifacts as of 2026-04-20. Schema-targeting cleaner: GT scorer 94.3%, critical C1 fields 100%. [PRD 005](prd/005-full-schema-extraction.md) plans the jump from 72-field cleaner coverage to full 1,105-field coverage via a schema-driven resolver framework. |
| Extraction: Tier 4 LLM fallback (PRD 006) | ✅ Phase 0 + Phase 1 shipped 2026-04-20. Schema-aware repair layer on top of the Tier 4 cleaner. 244 docs backfilled across 2024-25, mean 28.2 fields added/doc beyond the cleaner baseline, $14.08 total Anthropic spend, zero regression on audited ground truth. `cds_llm_cache` makes re-runs on unchanged inputs cost $0. Target subsections: H5-H8, C13-C17, D13-D16, G5. Frontend (`web/src/lib/queries.ts:fetchExtract`) merges cleaner + fallback values per Mode B. See [`docs/tier4-llm-fallback.md`](tier4-llm-fallback.md). |
| Extraction: Tier 5 (scanned PDF via OCR) | ✅ Shipped 2026-04-20. Routes `pdf_scanned` through the same Tier 4 extractor with `force_ocr=True`, which swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Verified on Kennesaw State 2023-24 (0 fields under default lazy OCR → 172 fields under force-OCR). Docling's "auto" OCR heuristic doesn't reliably trigger on scanned CDS PDFs, hence the force-mode requirement. |
| Extraction: Tier 3 (filled DOCX) | ❌ Specified in ADR 0006, design in [PRD 007](prd/007-tier3-docx-extraction.md). SDT-based reader (`python-docx` → `w:sdt` elements by tag). Addressable corpus today is ~30-50 documents, with Kent State's 14 SDT-preserving files being the largest single family. Not yet built. |
| Queryable browser backend (PRD 010) | ✅ Backend MVP shipped 2026-04-26. `cds_fields` projects 2024-25+ selected extraction values; `school_browser_rows` serves curated one-row-per-school-year metrics; `browser-search` implements latest-per-school ranked search with answerability metadata. Production projection populated 113,836 field rows and 472 browser rows from 507 documents at launch. |
| Year authority migration | ✅ Stage A + B shipped 2026-04-15 ([ADR 0007](decisions/0007-year-authority-moves-to-extraction.md)). Content detection is authoritative; resolver `pickCandidates` fans out landing-page anchors into multiple `cds_documents` rows; extraction writes `detected_year`; `cds_manifest.canonical_year` prefers content over URL. Stage C was de-scoped to docs-only — full retirement of `cds_year` and `_shared/year.ts` requires dropping `cds_year` from the unique constraint, deferred to a follow-up item in [backlog.md](./backlog.md). |
| Consumer API | ✅ Live at `api.collegedata.fyi/rest/v1/`, plus Supabase Edge Functions. Manifest, field substrate, browser rows, and browser-search respond to production smoke tests. |
| Frontend | ✅ Live at `collegedata.fyi` (Vercel). Includes landing with search, queryable browser, school directory, school detail, year detail with field viewer, about, recipes, and API docs. Consumes PostgREST plus `browser-search`. See [`docs/prd/002-frontend.md`](prd/002-frontend.md) and [`docs/prd/010-queryable-data-browser.md`](prd/010-queryable-data-browser.md). |

"Built" means the code exists and has been exercised against real data. "Not yet built" means the design is specified but no code exists. "Reference extracts exist" means we have the raw output from an external tool but no production path from raw → canonical.

---

## Related docs

- [`docs/prd/001-collegedata-fyi-v1.md`](prd/001-collegedata-fyi-v1.md) — product-level framing, scope, milestones, success criteria
- [`docs/prd/002-frontend.md`](prd/002-frontend.md) — frontend PRD (CEO + Design + Eng reviewed)
- [`docs/prd/003-ai-driven-data-quality.md`](prd/003-ai-driven-data-quality.md) — AI-driven data-quality spike PRD
- [`docs/prd/004-js-rendered-resolver.md`](prd/004-js-rendered-resolver.md) — JS-rendered resolver PRD (hybrid spike)
- [`docs/prd/005-full-schema-extraction.md`](prd/005-full-schema-extraction.md) — Tier 4 cleaner full-schema expansion (hand-coded resolvers)
- [`docs/prd/006-llm-fallback.md`](prd/006-llm-fallback.md) — Tier 4 LLM fallback design (Phase 0 + Phase 1 shipped)
- [`docs/tier4-llm-fallback.md`](tier4-llm-fallback.md) — Tier 4 LLM fallback operator runbook + consumer integration
- [`docs/frontend.md`](frontend.md) — frontend design: pages, components, data flow, SEO, security
- [`web/DESIGN_SYSTEM.md`](../web/DESIGN_SYSTEM.md) — visual system: palette, typography, components, voice (canonical tokens in [`web/src/app/tokens.css`](../web/src/app/tokens.css); live reference at [`web/public/design-system/index.html`](../web/public/design-system/index.html))
- [`docs/design/`](design/) — source-of-truth handoff from the original Claude Design session (HTML prototypes, reference JSX, screenshots)
- [`docs/v1-plan.md`](v1-plan.md) — engineering plan with data model details and milestone breakdown
- [`tools/scorecard/README.md`](../tools/scorecard/README.md) — Scorecard pipeline runbook (operator-facing): annual refresh, schema-drift handling, slug-rationalization gap
- [`docs/research/cds-vs-college-scorecard.md`](research/cds-vs-college-scorecard.md) — CDS vs College Scorecard schema comparison (the source of truth for which Scorecard fields complement CDS vs duplicate it)
- [`docs/research/scorecard-join-recipe.md`](research/scorecard-join-recipe.md) — manual-join curl/Python/SQL recipes (now mostly useful for Scorecard columns outside our curated subset)
- [`docs/research/scorecard-summary-table-v2-plan.md`](research/scorecard-summary-table-v2-plan.md) — design doc the Scorecard pipeline shipped against (now reflects shipped state)
- [`docs/decisions/`](decisions/) — ADRs 0001-0007 for every foundational choice
- [`docs/backlog.md`](backlog.md) — priority queue for near-term work
- [`docs/known-issues/`](known-issues/) — per-school extraction quality notes
