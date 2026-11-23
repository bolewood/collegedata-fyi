# extraction_worker

Python worker that turns archived source files into structured canonical
extracts. Polls pending rows newest-first, routes to a tier-specific extractor
based on byte-derived `source_format`, and writes the result back as a
`cds_artifacts` row with `kind='canonical'`.

This is the M2 half of the pipeline. M1 (discovery) archives the source bytes; M2 (here) turns them into structured data keyed by canonical CDS question number.

## What's in the directory

| File | Purpose |
|---|---|
| `worker.py` | The main poller. Reads pending rows with recency priority, downloads sources from Storage, routes by `source_format`, writes canonical artifacts, and refreshes browser projections after successful writes unless disabled. Tier 1 (xlsx), Tier 2 (pdf_fillable), Tier 4 (pdf_flat), Tier 5 (pdf_scanned via Tier 4 + force-OCR), and Tier 6 (structured HTML) are wired end-to-end; Tier 3 (docx) is still a stub pending [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). Also runs content-based year detection (ADR 0007), writes `cds_documents.detected_year`, reconciles already-extracted pending rows, and supports graceful deadline exits for bounded ops runs. |
| `tier4_extractor.py` | Tier 4 extraction pipeline. Runs Docling with the tuned `production-fast-no-orphan-clusters` config to produce markdown, persists compact native table cells, then hands off to the cleaner. Accepts a `force_ocr` parameter which the worker sets to True for `pdf_scanned` sources — this enables Tier 5 via the same pipeline with EasyOCR forced on every page. |
| `tier4_cleaner.py` | Schema-targeting post-processor for Docling output. Parses markdown tables, maps row labels to canonical question numbers, handles the common table shapes across the corpus (B1 gender columns, B2 race/ethnicity, C10 class rank, etc.). Bulk of the Tier 4 logic lives here. |
| `tier4_native_tables.py` | Compact serializer for Docling native table cells. Preserves row/column offsets, cell flags, bboxes, and table provenance in `notes.native_tables` so deterministic native-table parsers can run before any LLM repair. |
| `subsection_slicer.py` | PRD 006 Phase 0. Locates CDS subsections (H5-H8, C13-C22, D2-D16, G5, C11) in Docling markdown via a layered six-strategy matcher. CLI: `python subsection_slicer.py <output.md>`. |
| `llm_client.py` | PRD 006 Phase 0. Anthropic SDK wrapper with prompt-cache split (cached head + uncached tail) and per-call cost estimation. Claude Haiku 4.5 default. |
| `tier4_llm_fallback.py` | PRD 006 Phase 0. Prompt builder, deterministic validator (type/evidence/sanity/row-merge), and merge policy for the LLM fallback. No DB writes. |
| `llm_fallback_bench.py` | PRD 006 Phase 0. Standalone benchmark CLI. Reads existing `tier4_docling` artifacts, runs section-scoped LLM prompts, validates responses, writes JSON report to disk. No DB writes. |
| `llm_fallback_worker.py` | PRD 006 Phase 1. Operator-run worker (not in any scheduled workflow): for documents that already have a `tier4_docling` artifact, slices target subsections, checks `cds_llm_cache`, calls the LLM within per-doc/per-run budget caps, validates deterministically, and merges. Flags: `--mode shadow\|fill_gaps`, `--max-cost-per-doc`, `--max-cost-per-run`, `--report`. |
| `pdf_text.py` | Per-page PDF text with a pdfium fallback when pypdf cannot read a page, so a PDF with a good text layer is not sniffed as scanned. |
| `source_metadata.py` | Captures embedded source-file metadata (PDF `/CreationDate`, `/ModDate`, `/Producer`; XLSX `dcterms`) that the worker persists to `cds_documents`. |
| `dependency_check.py` | Startup guard: exits unless the venv matches `requirements.lock` (override with `--allow-dependency-drift`). |
| `html_to_markdown.py` | Tier 6: normalizes archived HTML into the pipe-delimited markdown the Tier 4 cleaner consumes. |
| `revalidate_notify.py` | After a run, POSTs changed `school_id`s to `/api/revalidate` so only those school pages regenerate (see below). |
| `backfill_quality_flags.py` | Adds missing data-quality flags (`blank_template`, `low_coverage`, single-section) to already-extracted Tier 1/Tier 2 documents. |
| `b1_derive_totals.py` | Derives CDS B1 "All" gender totals from FT + PT components when the source leaves them blank. |
| `prd014_m5_drain.py` | PRD 014 M5 staged requeue and rollback helper for year-aware schema re-extraction. |
| `watch_resolver_drain.py` | Operator monitor. Polls the archive queue + cds_documents tables and prints a live dashboard of drain progress. Useful during a full-corpus archive run. |
| `requirements.txt` / `requirements.lock` | Top-level deps (Docling pinned exactly) and the full Python 3.12 lock generated from them. Install from the lock; `worker.py` exits when the venv drifts from it (`dependency_check.py`). `anthropic` is required for the LLM fallback (PRD 006 Phase 0) — install separately. `python-docx` is required once Tier 3 ships (PRD 007). |

## Reproducible extraction

Extraction output depends on the exact Docling, torch, OCR and parser builds,
so the worker runs only on an environment that matches `requirements.lock`
and `/.python-version`. It exits at startup otherwise; `--allow-dependency-drift`
overrides that for experiments. To change a dependency, edit `requirements.txt`,
regenerate the lock (command at the top of `requirements.txt`), bump
`tier4_extractor.PRODUCER_VERSION` when extraction output can change, and
compare field counts on a re-extraction sample before merging.

Re-extractions an operator starts, of any size, run on the operator's Mac
while a working session is open. The GitHub-hosted `ops-extraction-worker`
workflow is for the scheduled drain and other unattended runs; do not dispatch
re-extraction batches to it by default. The reasons are cost and speed: a
document takes about 30 seconds on an Apple-silicon Mac and 3 to 4 minutes on
a hosted runner (November 2026). Even with identical pins, the two machines do
not convert every document the same way (next section), so compare field
counts for each batch.

A local run cannot refresh the site's cached pages unless `.env` carries
`REVALIDATE_SECRET`. Afterwards run
`gh workflow run ops-page-refresh.yml -f hours=<hours since the batch started> -f dry_run=false`.

### Installed fonts change the output

Some PDFs in the corpus do not embed their fonts (mostly older Word exports
that name Times New Roman or Arial). docling-parse draws every page
for the layout model and, for a font that is not embedded, substitutes one it
finds in the system and user font directories. The layout model is sensitive to that
choice. With identical code, models and text cells, the first page of
Arkansas State 2008-09 drawn with Liberation fonts gave 58 detected regions;
the same page drawn with Times New Roman gave 112.

Measured in November 2026 on six PDFs without embedded fonts (same code,
models and cleaner):

| Fonts installed | Fields | Checked boxes found |
|---|---|---|
| macOS system fonts | 1,354 | 376 |
| Linux: Microsoft core fonts, DejaVu | 1,352 | 383 |
| Linux: DejaVu only | 1,340 | 364 |
| Linux: DejaVu, Noto, FreeFont, URW | 1,338 | 363 |
| Linux: the row above plus Liberation | 1,171 | 142 |

Two PDFs with embedded fonts gave the same result on every setup. The last
setup reproduces, character for character, what the GitHub runner produced for
Portland State 2016-17. What the Liberation setup loses is checkbox answers
and lines merged into one paragraph (Arkansas State 2008-09: 2 checked boxes
found against 77 on macOS).

The `ops-extraction-worker` workflow therefore deletes Liberation fonts before
it runs the worker and makes sure a DejaVu font is installed. Do both on any
other Linux host. The remaining setups still differ from each other on
individual documents, so compare field counts when a document moves between
machines.

Not measured: the visual OCR fallback draws pages with `pdftoppm`, which also
substitutes installed fonts, so its input changes with the font set too.

A document already extracted with Liberation installed is not redone on its
own, because its producer version and source are unchanged. Re-extract it with
`--requeue-document-ids <uuid> --force-reextract`.

## Usage

```bash
cd tools/extraction_worker

# One-time setup (Python 3.12, see /.python-version)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock

# Run the worker (polls and extracts until the pending queue drains)
python worker.py

# Work one school at a time (useful for debugging a specific case)
python worker.py --school yale --limit 1

# Run a bounded drain and write the same summary JSON used by ops Actions
python worker.py --limit 25 \
    --seed-projection-metadata \
    --summary-json ../../scratch/extraction-summary.json

# Isolate extraction from browser serving-table writes
python worker.py --skip-projection-refresh --limit 10

# Scoped operator re-drain: only 2024+ Tier 4/Tier 5 PDFs
python worker.py --source-format pdf_flat,pdf_scanned --min-year-start 2024

# Graceful CI/operator budget: stop before the hard timeout and still write
# summary/projection progress.
python worker.py --limit 25 --deadline-minutes 25 --summary-json ../../scratch/extraction-summary.json

# Repair rows stuck in extraction_pending when a prior run was cancelled after
# writing the current canonical artifact.
python worker.py --reconcile-pending --limit 100 --summary-json ../../scratch/reconcile-summary.json

# Managed Docling re-drain on the operator's Mac (see "Reproducible
# extraction"). Requeued documents are processed in
# place: each keeps its status and served data until its own re-extraction
# finishes, then cds_fields/school_browser_rows refresh for it.
python worker.py \
    --env ../../.env \
    --requeue-document-ids <uuid>,<uuid> \
    --document-ids <uuid>,<uuid> \
    --limit 2 \
    --min-year-start 2024 \
    --seed-projection-metadata \
    --summary-json ../../scratch/extraction_worker/local-redrain-summary.json

# Force a new artifact even if producer/schema/source SHA already match.
# Use only for managed cleaner/extractor redrains after code changes.
python worker.py --requeue-document-ids <uuid> --force-reextract --limit 1

# A re-extraction of the same file is held (the previous artifact stays) when
# it ends 10 or more fields lower, loses headline admissions rows, or loses
# most of one table (5 or more numbers and over half of what the table had,
# counting only numbers found nowhere else in the same section). Any tier's
# result that would become the served extraction with under half the fields of
# the one served now (when that has 50 or more) is held too. The worker
# then exits 1 and names the document. After checking the lost values against
# the PDF, write the new result with the matching switch:
python worker.py --requeue-document-ids <uuid> --document-ids <uuid> --force-reextract --accept-field-loss
python worker.py --requeue-document-ids <uuid> --document-ids <uuid> --force-reextract --accept-headline-loss
python worker.py --requeue-document-ids <uuid> --document-ids <uuid> --force-reextract --accept-table-loss

# Re-clean: run the current cleaner on the conversion a document's newest
# Tier 4 artifact of the same file stored, without converting the PDF again.
# The cleaning takes about a second instead of about thirty, and there is no
# conversion drift, because nothing is converted. Use it after a cleaner
# change, for named documents only.
# - The PDF is still downloaded, for its text layer and for the bounded OCR
#   pass on the documents that need it.
# - The new artifact records which artifact converted the PDF in
#   notes.conversion, and keeps that run's notes.docling_config.
# - The field-count, table and collapse guards apply as usual. The headline
#   guard only fires when the conversion lost the C1 numbers, which a re-clean
#   cannot do, so a cleaner change that drops a C1 value is caught by the
#   other guards or by the scoreboard, not by that one.
# - Documents are kept at least 8 seconds apart (--reclean-interval): each one
#   still reads and writes a large artifact row.
# - A document with no stored conversion of its current file, or whose stored
#   conversion used other settings (a different Docling config name or OCR
#   mode), is skipped: action tier4_reclean_skipped in the summary, nothing
#   written, not in the run ledger. Run those without --reclean.
# - After a change to Docling, its models, the pipeline options or the
#   installed fonts, run a full conversion, not a re-clean.
python worker.py --requeue-document-ids <uuid>,<uuid> --force-reextract --reclean \
    --summary-json ../../scratch/extraction-drain/local/reclean.summary.json

# Fresh-year drain: process the newest archived CDS rows before old backlog
python worker.py --min-year-start 2025 --include-failed --limit 25

# Ledger and run-origin flags (used by the ops workflow; operators rarely
# need them): --trigger {schedule,dispatch,operator}, --run-url <actions url>,
# --replay-ledger-json <file> to replay a failed run's extraction-run ledger
# without reprocessing documents, --schema <path> (debug override: forces one schema for every
# document and disables year-aware dispatch), and --dry-run.

# Content-based year detection only, no extraction writes
python worker.py --detect-year-only                 # report
python worker.py --detect-year-only --write         # backfill detected_year
```

Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `ANTHROPIC_API_KEY` (for the LLM fallback — PRD 006).

## Managed Docling runs

Managed Docling drains run locally on the operator's Mac, whatever their size
(see "Reproducible extraction"). Local runs have no 60-minute GitHub-hosted
timeout and can write complete logs under `scratch/`. GitHub Actions is for
automation: the small scheduled backlog drain, CI, and other unattended jobs.

For extractor or cleaner changes, bump the relevant `producer_version` before
re-draining. The worker is idempotent by `(document_id, producer,
producer_version, schema_version, source_sha256)` and will otherwise skip
matching artifacts as `already_extracted`. The source-SHA check means a newly
archived byte revision can still extract even when producer and schema versions
are unchanged. `--force-reextract` opts out for deliberate managed redrains.

## GitHub Actions ops workflow

`.github/workflows/ops-extraction-worker.yml` is the bounded production-ish
wrapper around `worker.py`. It is separate from PR CI and is meant for the
scheduled automation path, not managed Docling re-drains.

The workflow supports both a daily scheduled drain and manual dispatch. Manual
inputs are `limit`, `school`, `document_ids`, `requeue_document_ids`,
`include_failed`, `seed_projection_metadata`, `low_field_threshold`,
`min_year_start`, and `deadline_minutes` (default 100; scheduled runs use 25).
`source_format` is a `worker.py` flag, not a workflow input.
GitHub-hosted runs reject `limit` values over 100; full corpus drains should run
on an operator laptop or a self-hosted runner.

The default claim order is deliberately recency-first: the worker sorts by
content-derived `detected_year` when available, then archive-time `cds_year`,
then `discovered_at`. That means a fresh 2025-26 Yale file is handled before an
old historical backlog row. Use `--min-year-start` for intentional fresh-year
drains and leave it unset for normal backlog work.

Required GitHub Secrets:

| Secret | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL for worker reads/writes. |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role credential for archive, artifact, and projection writes. |

Optional (web cache refresh):

| Name | Kind | Purpose |
|---|---|---|
| `REVALIDATE_SECRET` | Secret | Shared secret for `POST /api/revalidate` (same value as the Vercel production env var). |
| `COLLEGEDATA_REVALIDATE_URL` | Variable (or secret) | `https://www.collegedata.fyi/api/revalidate`. |

When both are set, the worker POSTs the `school_id`s whose data changed
(re-extracted + projected, or reconciled) in batches of 100 after the run, so
only those school pages regenerate. School pages otherwise wait for the daily
sweep (`tools/ops/revalidate_pages.py`) or the 7-day ISR window. Best effort: short timeout, errors are logged
(`revalidate_notify_error`) and never change the exit code; no-op if either
value is unset. See `revalidate_notify.py`.

Manual revalidation:

```sh
curl -sS -X POST https://www.collegedata.fyi/api/revalidate \
  -H "Authorization: Bearer $REVALIDATE_SECRET" -H "Content-Type: application/json" \
  -d '{"school_ids": ["yale", "mit"]}'
# everything (lazy: pages rebuild on next visit; use sparingly)
curl -sS -X POST https://www.collegedata.fyi/api/revalidate \
  -H "Authorization: Bearer $REVALIDATE_SECRET" -H "Content-Type: application/json" \
  -d '{"all": true}'
```

Responses: `200 {revalidated, schools, tags, paths, rejected}`, `400` bad body
(max 100 ids, lowercase slugs), `401` bad token, `503` secret not configured.

Each workflow run uploads an `extraction-worker-summary` artifact containing
`summary.json` and `worker.log`. The JSON is designed for quick triage:

| Field | Meaning |
|---|---|
| `processed_count` | Number of rows claimed for the run. |
| `failure_count` | Rows that ended in an error state. |
| `mean_fields` | Mean populated canonical field count across successful artifacts. |
| `low_field_docs` | Documents below `--low-field-threshold`, with school/source details. |
| `extraction_counts` | Result buckets from the extraction pass. |
| `projection_counts` | Browser projection writes, skipped rows, and projection errors. |
| `reconcile_counts` | Rows repaired by `--reconcile-pending` without heavy extraction. |
| `documents` | Per-document action, producer, schema, field count, and error details. |

After writing the summary, the worker exits non-zero if `failure_count` is
greater than zero. Failure classification uses the action name before any
parenthesized detail, so actions such as `html_no_tables (0 fields)` cannot be
misreported as success. The workflow keeps its summary, notification, and
artifact steps on `if: always()`, which makes the run visibly red without losing
the evidence needed to diagnose it.

The workflow always passes `--reconcile-pending` unless `--force-reextract` is
used locally. This keeps cancelled or timeout-interrupted rows from accumulating
in the pending queue when their current-source artifact already exists.

## CI workflow

`.github/workflows/ci.yml` is intentionally minimal. It runs Python unit tests
for the extraction worker/browser projection, Deno tests for Supabase functions,
and the Next.js typecheck/build. It does not perform live extraction, service
role writes, projection rebuilds, or full Docling corpus drains.

## LLM fallback (PRD 006)

`llm_fallback_worker.py` (Phase 1) is operator-run and is not called by any
workflow in `.github/workflows/`; see its module docstring for usage and budget
caps. See [`docs/tier4-llm-fallback.md`](../../docs/tier4-llm-fallback.md) for
the current status. The benchmark harness below is the Phase 0 tool.

### Benchmark (Phase 0)

Standalone benchmark harness. No DB writes. Reads existing `tier4_docling`
artifacts and runs section-scoped LLM prompts against Claude Haiku 4.5,
validates responses deterministically, and writes JSON reports.

```bash
cd tools/extraction_worker
source .venv/bin/activate
pip install anthropic                  # one-time

# Smoke test — one school, one subsection
python llm_fallback_bench.py \
    --school yale --year 2024-25 \
    --subsections H5 \
    --out-dir ../../scratch/llm-bench/

# Phase 0 benchmark — three GT schools, priority subsections
python llm_fallback_bench.py \
    --school harvard,yale,dartmouth --year 2024-25 \
    --subsections H5,H6,H7,H8,C13,C14,C15,C16,C17,D13,D14,D15,D16,G5 \
    --max-cost-per-doc 0.05 \
    --out-dir ../../scratch/llm-bench/

# Dry run (no API call; prints prompt sizes only)
python llm_fallback_bench.py --dry-run \
    --school yale --year 2024-25 --subsections H5 \
    --out-dir ../../scratch/llm-bench/
```

Each run writes `run-<timestamp>/_manifest.json` + `<school>.json` with
per-subsection costs, cache hit rates, acceptance counts, rejection
reasons, and the slicer strategy that located each subsection. Decision-gate
evaluation per PRD 006 reads the manifest.

## Tier routing

Routing is driven by `cds_documents.source_format`, which `tier_probe/probe.py` backfills by reading the actual file bytes:

| source_format | Tier | Status | Extractor |
|---|---|---|---|
| `xlsx` | 1 | Shipped 2026-04-20; hardened 2026-05-03 | [`tools/tier1_extractor/extract.py`](../tier1_extractor/) — template or embedded answer-column cell-position map + openpyxl. ~100% accuracy when school uses the standard template or preserves workbook-native question/answer columns. |
| `pdf_fillable` | 2 | Shipped | `tools/tier2_extractor/extract.py` — `pypdf.get_fields()` + schema join. ~100% accuracy when applicable. |
| `pdf_flat` | 4 | Shipped | `tier4_extractor.py` + `tier4_cleaner.py` — Docling markdown + schema-targeting cleaner, with compact native table cells persisted for deterministic repair. GT scorer 94% on audited schools. |
| `pdf_scanned` | 5 | Shipped 2026-04-20 | Same pipeline as Tier 4 with `force_ocr=True`. Worker passes the flag into `tier4_extractor.extract()` which swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Docling's default "auto" OCR doesn't reliably trigger on scanned CDS PDFs — force mode is needed. |
| `docx` | 3 | Stub (PRD 007); routed correctly | Not yet implemented. Will use `python-docx` to read Structured Document Tags (SDTs) — the DOCX template has 1,204 SDTs with tags that match schema `word_tag` values exactly. ZIP internals are inspected so DOCX no longer false-routes as XLSX. See [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). |
| `html` | 6 | Shipped 2026-04-20 | `html_to_markdown.py` (BeautifulSoup + lxml) normalizes archived HTML into the pipe-delimited markdown shape the Tier 4 cleaner already consumes. No bespoke parser — reuses `_parse_markdown_tables` + `_normalize_label` + `SchemaIndex.filter`. MIT 2024-25 reference: 152 fields populated. Archived bytes are served with `text/plain` content-type from the public sources bucket to prevent XSS. Producer: `tier6_html`. See [PRD 008](../../docs/prd/008-html-extraction.md). |

Stub tiers fail fast with a reason in `last_error` so the row exits the pending queue and an operator can see the gap.

## Year-aware schema dispatch

PRD 014 M3 made schema selection year-aware for deterministic extraction paths.
The worker loads all canonical `schemas/cds_schema_*.json` files at startup,
then chooses the schema for each document from `detected_year || cds_year`.
If no matching canonical schema exists, the worker falls back and records
`notes.schema_fallback_used: true`, `notes.schema_fallback_reason`, and
`notes.schema_version` on the artifact. A year newer than every schema falls
back to the newest one. Anything else (an undated file, a year before 2023-24)
falls back to 2025-26, which is pinned (`BASELINE_FALLBACK_SCHEMA_VERSION`):
those files cannot be on a newer form, and their stored results are keyed by
the 2025-26 numbering.
The canonical years are 2023-24, 2024-25, 2025-26 and 2026-27 (the
non-structural `schemas/cds_schema_*.json` files); 2019-20
through 2022-23 still use structural schemas/overlays only and therefore fall
back for deterministic extraction.

Tier 1 uses a schema-matched template cell map when one exists. The 2025-26
and 2026-27 templates use hidden AA/AC lookup columns (410 cells moved between
the two years, so the maps are not interchangeable); the 2024-25 template uses the reduced
section-tab layout. The archived 2023-24 XLSX is a visual form layout and
currently does not produce a Tier 1 cell map. If a map produces fewer than 25
populated values, Tier 1 scans the workbook itself for embedded Question Number /
Answer columns and uses that map only when it recovers more fields. Tier 2 joins
AcroForm values against the selected schema. Tier 4, Tier 5, and Tier 6 pass a
year-matched `SchemaIndex` into the cleaner for schema filters and value
metadata.

2026-27 keeps the 2025-26 question numbers and adds twelve fields. Tier 1 and
Tier 2 read all twelve through the template's own cell map and form names when
the file is on the 2026-27 form. A school can also file 2026-27 data on the
2025-26 form; `resolve_schema_for_form` detects a spreadsheet or fillable PDF
that carries none of the names 2026-27 added and reads it with the 2025-26
schema (`schema_fallback_reason: form_is_2025-26`). The
Tier 4 cleaner treats 2026-27 as the 2025-26 numbering (`_NUMBERED_LIKE_2025_26`)
and does not read the twelve new fields yet.

Known limitation: Tier 4's hand-coded phrase/field maps are still maintained
against the 2025-26 reference frame. M3 makes `SchemaIndex.filter()` and schema
metadata year-aware, but the full phrase-matcher conversion is deferred to
PRD 014 M6.

## Year detection (ADR 0007)

`worker.py` runs `detect_year_from_pdf_bytes()` on every archived PDF and writes the result to `cds_documents.detected_year`. This is the authoritative year per [ADR 0007](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — the content-derived year wins over the URL-derived guess that the resolver makes. Strict prefix-anchored regex ladder, `y2 = y1 + 1` span validation, collect-all-unique across pages 1-10. Adjacent `Common Data Set YYYY-YYYY` / `CDS YYYY-YY` titles match, and so do section-package layouts that print `Common Data Set`, a `Section …` heading, then the year on the following lines. A bare year in the body still does not count. Recall ~80% on PDFs; the rest remain `detected_year IS NULL` and consumers fall back to `cds_year` via `cds_manifest.canonical_year`.

To backfill `detected_year` after a detector change (read-only first):

```
python tools/extraction_worker/worker.py --detect-year-only --school university-of-kansas
python tools/extraction_worker/worker.py --detect-year-only --school university-of-kansas --write
```

`--write` updates `cds_documents.detected_year` only. It does not re-extract.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — the Tier 2 extractor this worker calls
- [`tools/tier_probe/`](../tier_probe/) — backfills `source_format` so the router can route
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — the tier ladder rationale
- [`docs/decisions/0007-year-authority-moves-to-extraction.md`](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — why year lives here, not in the resolver

## Template overlay (PRD 038 M3; off by default)

`overlay_entry.py` runs the PRD 038 template overlay as its own entry point and writes a `kind='cleaned'`,
`producer='tier2_template_overlay'` artifact. It is never imported by `worker.py` at module load.

**Contract: one serial writer.** There is no database uniqueness on overlay artifacts. Before extracting, the tool skips a
document when an overlay with the same (document, producer version, field-map version, source sha, Lane 2 requested)
exists; two concurrent writers can both insert, which is harmless because the newest eligible overlay wins in every
selector. This is a best-effort skip, not general idempotency.

- `python tools/extraction_worker/overlay_entry.py --env .env --document-ids <id>,<id> --no-lane2`: dry run (the default):
  extract and print a summary, write nothing. Add `--write` to insert the artifact. Neither mode writes a heartbeat or
  ledger row, refreshes the projection or notifies the web. Lane 2 (numeric OCR) costs roughly 2 minutes per vector-path
  document; `--no-lane2` skips it.
- `--rehold [--hold-threshold 0.10|off] [--hold-classes numeric,choice,checkbox_box] [--write]`: no extraction; recompute
  `held` from the stored comparison facts and append a new artifact. The Tier 4 disagreement hold is OFF unless a threshold is
  given (`--hold-threshold 0.05`, or `OVERLAY_HOLD_THRESHOLD` in the environment or `--env FILE`); structural holds always apply.
- `--pdf-dir DIR --out-dir DIR`: local mode over `<sha256>.pdf` files, no database.
- `OVERLAY_WORKER_ENABLED=1` makes the routine worker loop call the overlay after the Tier 4 outcome (default off; never
  under `--dry-run`).
- Serving (PRD 038 A15): the default served set is `numeric,choice,checkbox_box,ocr_numeric` (OCR from vector pages only) in the Python projection,
  the web and the SQL view; `OVERLAY_SERVE_CLASSES` overrides it in Python and the web and `none` serves nothing. See
  `tools/browser_backend/overlay_serving.py` and PRD 038 A13/A14. The raw artifact rows are publicly readable through
  the `cds_artifacts` API; no selected-result consumer serves overlay values unless that variable names classes.
