# extraction_worker

Python worker that turns archived source files into structured canonical extracts. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`, routes to a tier-specific extractor based on the file format, and writes the result back as a `cds_artifacts` row with `kind='canonical'`.

This is the M2 half of the pipeline. M1 (discovery) archives the source bytes; M2 (here) turns them into structured data keyed by canonical CDS question number.

## What's in the directory

| File | Purpose |
|---|---|
| `worker.py` | The main poller. Reads pending rows, downloads sources from Storage, routes by `source_format`, writes canonical artifacts. Tier 1 (xlsx), Tier 2 (pdf_fillable), Tier 4 (pdf_flat), and Tier 5 (pdf_scanned via Tier 4 + force-OCR) are wired end-to-end; Tier 3 (docx) is still a stub pending [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). Also runs content-based year detection (ADR 0007) and writes `cds_documents.detected_year`. |
| `tier4_extractor.py` | Tier 4 extraction pipeline. Runs Docling with the tuned `production-fast-no-orphan-clusters` config to produce markdown, persists compact native table cells, then hands off to the cleaner. Accepts a `force_ocr` parameter which the worker sets to True for `pdf_scanned` sources — this enables Tier 5 via the same pipeline with EasyOCR forced on every page. |
| `tier4_cleaner.py` | Schema-targeting post-processor for Docling output. Parses markdown tables, maps row labels to canonical question numbers, handles the common table shapes across the corpus (B1 gender columns, B2 race/ethnicity, C10 class rank, etc.). Bulk of the Tier 4 logic lives here. |
| `tier4_native_tables.py` | Compact serializer for Docling native table cells. Preserves row/column offsets, cell flags, bboxes, and table provenance in `notes.native_tables` so deterministic native-table parsers can run before any LLM repair. |
| `subsection_slicer.py` | PRD 006 Phase 0. Locates CDS subsections (H5-H8, C13-C22, D2-D16, G5, C11) in Docling markdown via a layered six-strategy matcher. CLI: `python subsection_slicer.py <output.md>`. |
| `llm_client.py` | PRD 006 Phase 0. Anthropic SDK wrapper with prompt-cache split (cached head + uncached tail) and per-call cost estimation. Claude Haiku 4.5 default. |
| `tier4_llm_fallback.py` | PRD 006 Phase 0. Prompt builder, deterministic validator (type/evidence/sanity/row-merge), and merge policy for the LLM fallback. No DB writes. |
| `llm_fallback_bench.py` | PRD 006 Phase 0. Standalone benchmark CLI. Reads existing `tier4_docling` artifacts, runs section-scoped LLM prompts, validates responses, writes JSON report to disk. No DB writes. |
| `watch_resolver_drain.py` | Operator monitor. Polls the archive queue + cds_documents tables and prints a live dashboard of drain progress. Useful during a full-corpus archive run. |
| `requirements.txt` | Pinned deps: `supabase`, `pypdf`, `docling`, `openpyxl`, `easyocr`. `anthropic` is required for the LLM fallback (PRD 006 Phase 0) — install separately. `python-docx` is required once Tier 3 ships (PRD 007). |

## Usage

```bash
cd tools/extraction_worker

# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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

# Content-based year detection only, no extraction writes
python worker.py --detect-year-only                 # report
python worker.py --detect-year-only --write         # backfill detected_year
```

Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `ANTHROPIC_API_KEY` (for the LLM fallback — PRD 006).

## GitHub Actions ops workflow

`.github/workflows/ops-extraction-worker.yml` is the bounded production-ish
wrapper around `worker.py`. It is separate from PR CI and is meant for small
pending-row drains, not corpus-wide Docling/OCR work.

The workflow supports both a daily scheduled drain and manual dispatch. Manual
inputs are `limit`, `school`, `include_failed`, `seed_projection_metadata`, and
`low_field_threshold`. GitHub-hosted runs reject `limit` values over 100; full
corpus drains should run on an operator laptop or a self-hosted runner.

Required GitHub Secrets:

| Secret | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL for worker reads/writes. |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role credential for archive, artifact, and projection writes. |

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

## CI workflow

`.github/workflows/ci.yml` is intentionally minimal. It runs Python unit tests
for the extraction worker/browser projection, Deno tests for Supabase functions,
and the Next.js typecheck/build. It does not perform live extraction, service
role writes, projection rebuilds, or full Docling corpus drains.

## LLM fallback benchmark (PRD 006, Phase 0)

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
| `xlsx` | 1 | Shipped 2026-04-20 | [`tools/tier1_extractor/extract.py`](../tier1_extractor/) — template cell-position map + openpyxl. ~100% accuracy when school uses the standard template. Median 307 fields/doc. |
| `pdf_fillable` | 2 | Shipped | `tools/tier2_extractor/extract.py` — `pypdf.get_fields()` + schema join. ~100% accuracy when applicable. |
| `pdf_flat` | 4 | Shipped | `tier4_extractor.py` + `tier4_cleaner.py` — Docling markdown + schema-targeting cleaner, with compact native table cells persisted for deterministic repair. GT scorer 94% on audited schools. |
| `pdf_scanned` | 5 | Shipped 2026-04-20 | Same pipeline as Tier 4 with `force_ocr=True`. Worker passes the flag into `tier4_extractor.extract()` which swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Docling's default "auto" OCR doesn't reliably trigger on scanned CDS PDFs — force mode is needed. |
| `docx` | 3 | Stub (PRD 007) | Not yet implemented. Will use `python-docx` to read Structured Document Tags (SDTs) — the DOCX template has 1,204 SDTs with tags that match schema `word_tag` values exactly. See [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). |
| `html` | 6 | Shipped 2026-04-20 | `html_to_markdown.py` (BeautifulSoup + lxml) normalizes archived HTML into the pipe-delimited markdown shape the Tier 4 cleaner already consumes. No bespoke parser — reuses `_parse_markdown_tables` + `_normalize_label` + `SchemaIndex.filter`. MIT 2024-25 reference: 152 fields populated. Archived bytes are served with `text/plain` content-type from the public sources bucket to prevent XSS. Producer: `tier6_html`. See [PRD 008](../../docs/prd/008-html-extraction.md). |

Stub tiers fail fast with a reason in `last_error` so the row exits the pending queue and an operator can see the gap.

## Year-aware schema dispatch

PRD 014 M3 made schema selection year-aware for deterministic extraction paths.
The worker loads all canonical `schemas/cds_schema_*.json` files at startup,
then chooses the schema for each document from `detected_year || cds_year`.
If no matching canonical schema exists, the worker uses the most recent
available schema and records `notes.schema_fallback_used: true`,
`notes.schema_fallback_reason`, and `notes.schema_version` on the artifact.

Tier 1 uses a schema-matched template cell map when one exists. The 2025-26
template uses hidden AA/AC lookup columns; the 2024-25 template uses the
reduced section-tab layout with question numbers in column A and answer cells
in column C. Tier 2 joins AcroForm values against the selected schema. Tier 4,
Tier 5, and Tier 6 pass a year-matched `SchemaIndex` into the cleaner for
schema filters and value metadata.

Known limitation: Tier 4's hand-coded phrase/field maps are still maintained
against the 2025-26 reference frame. M3 makes `SchemaIndex.filter()` and schema
metadata year-aware, but the full phrase-matcher conversion is deferred to
PRD 014 M6.

## Year detection (ADR 0007)

`worker.py` runs `detect_year_from_pdf_bytes()` on every archived PDF and writes the result to `cds_documents.detected_year`. This is the authoritative year per [ADR 0007](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — the content-derived year wins over the URL-derived guess that the resolver makes. Strict prefix-anchored regex ladder, `y2 = y1 + 1` span validation, collect-all-unique across pages 1-10. Recall ~80% on PDFs; the rest remain `detected_year IS NULL` and consumers fall back to `cds_year` via `cds_manifest.canonical_year`.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — the Tier 2 extractor this worker calls
- [`tools/tier_probe/`](../tier_probe/) — backfills `source_format` so the router can route
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — the tier ladder rationale
- [`docs/decisions/0007-year-authority-moves-to-extraction.md`](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — why year lives here, not in the resolver
