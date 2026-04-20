# extraction_worker

Python worker that turns archived source files into structured canonical extracts. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`, routes to a tier-specific extractor based on the file format, and writes the result back as a `cds_artifacts` row with `kind='canonical'`.

This is the M2 half of the pipeline. M1 (discovery) archives the source bytes; M2 (here) turns them into structured data keyed by canonical CDS question number.

## What's in the directory

| File | Purpose |
|---|---|
| `worker.py` | The main poller. Reads pending rows, downloads sources from Storage, routes by `source_format`, writes canonical artifacts. Tier 1 (xlsx), Tier 2 (pdf_fillable), Tier 4 (pdf_flat), and Tier 5 (pdf_scanned via Tier 4 + force-OCR) are wired end-to-end; Tier 3 (docx) is still a stub pending [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). Also runs content-based year detection (ADR 0007) and writes `cds_documents.detected_year`. |
| `tier4_extractor.py` | Tier 4 extraction pipeline. Runs Docling with a baseline config to produce markdown, then hands off to the cleaner. Accepts a `force_ocr` parameter which the worker sets to True for `pdf_scanned` sources — this enables Tier 5 via the same pipeline with EasyOCR forced on every page. |
| `tier4_cleaner.py` | Schema-targeting post-processor for Docling output. Parses markdown tables, maps row labels to canonical question numbers, handles the common table shapes across the corpus (B1 gender columns, B2 race/ethnicity, C10 class rank, etc.). Bulk of the Tier 4 logic lives here. |
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

# Content-based year detection only, no extraction writes
python worker.py --detect-year-only                 # report
python worker.py --detect-year-only --write         # backfill detected_year
```

Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `ANTHROPIC_API_KEY` (for the LLM fallback — PRD 006).

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
| `pdf_flat` | 4 | Shipped | `tier4_extractor.py` + `tier4_cleaner.py` — Docling markdown + schema-targeting cleaner. GT scorer 94% on audited schools. |
| `pdf_scanned` | 5 | Shipped 2026-04-20 | Same pipeline as Tier 4 with `force_ocr=True`. Worker passes the flag into `tier4_extractor.extract()` which swaps in `EasyOcrOptions(force_full_page_ocr=True)`. Docling's default "auto" OCR doesn't reliably trigger on scanned CDS PDFs — force mode is needed. |
| `docx` | 3 | Stub (PRD 007) | Not yet implemented. Will use `python-docx` to read Structured Document Tags (SDTs) — the DOCX template has 1,204 SDTs with tags that match schema `word_tag` values exactly. See [PRD 007](../../docs/prd/007-tier3-docx-extraction.md). |

Stub tiers fail fast with a reason in `last_error` so the row exits the pending queue and an operator can see the gap.

## Year detection (ADR 0007)

`worker.py` runs `detect_year_from_pdf_bytes()` on every archived PDF and writes the result to `cds_documents.detected_year`. This is the authoritative year per [ADR 0007](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — the content-derived year wins over the URL-derived guess that the resolver makes. Strict prefix-anchored regex ladder, `y2 = y1 + 1` span validation, collect-all-unique across pages 1-10. Recall ~80% on PDFs; the rest remain `detected_year IS NULL` and consumers fall back to `cds_year` via `cds_manifest.canonical_year`.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — the Tier 2 extractor this worker calls
- [`tools/tier_probe/`](../tier_probe/) — backfills `source_format` so the router can route
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — the tier ladder rationale
- [`docs/decisions/0007-year-authority-moves-to-extraction.md`](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — why year lives here, not in the resolver
