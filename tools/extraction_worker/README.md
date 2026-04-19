# extraction_worker

Python worker that turns archived source files into structured canonical extracts. Polls `cds_documents WHERE extraction_status = 'extraction_pending'`, routes to a tier-specific extractor based on the file format, and writes the result back as a `cds_artifacts` row with `kind='canonical'`.

This is the M2 half of the pipeline. M1 (discovery) archives the source bytes; M2 (here) turns them into structured data keyed by canonical CDS question number.

## What's in the directory

| File | Purpose |
|---|---|
| `worker.py` | The main poller. Reads pending rows, downloads sources from Storage, routes by `source_format`, writes canonical artifacts. Tier 2 and Tier 4 are wired end-to-end; Tiers 1/3/5 are stubs that mark `extraction_status=failed` with a reason so the row exits the pending queue. Also runs content-based year detection (ADR 0007) and writes `cds_documents.detected_year`. |
| `tier4_extractor.py` | Tier 4 extraction pipeline. Runs Docling with a baseline config to produce markdown, then hands off to the cleaner. |
| `tier4_cleaner.py` | Schema-targeting post-processor for Docling output. Parses markdown tables, maps row labels to canonical question numbers, handles the common table shapes across the corpus (B1 gender columns, B2 race/ethnicity, C10 class rank, etc.). Bulk of the Tier 4 logic lives here. |
| `watch_resolver_drain.py` | Operator monitor. Polls the archive queue + cds_documents tables and prints a live dashboard of drain progress. Useful during a full-corpus archive run. |
| `requirements.txt` | Pinned deps: `supabase`, `python-dotenv`, `pypdf`, `docling`, `openpyxl`, `python-docx`. |

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

Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

## Tier routing

Routing is driven by `cds_documents.source_format`, which `tier_probe/probe.py` backfills by reading the actual file bytes:

| source_format | Tier | Status | Extractor |
|---|---|---|---|
| `pdf_fillable` | 2 | Shipped | `tools/tier2_extractor/extract.py` — `pypdf.get_fields()` + schema join. ~100% accuracy when applicable. |
| `pdf_flat` | 4 | Shipped | `tier4_extractor.py` + `tier4_cleaner.py` — Docling markdown + schema-targeting cleaner. GT scorer 94% on audited schools. |
| `xlsx` | 1 | Stub | Not yet implemented. Will read the CDS Initiative's filled Excel template via openpyxl. |
| `docx` | 3 | Stub | Not yet implemented. Will read the filled Word template via python-docx. |
| `pdf_scanned` | 5 | Stub | Not yet implemented. OCR + cleaner. Worst case. |

Stub tiers fail fast with a reason in `last_error` so the row exits the pending queue and an operator can see the gap.

## Year detection (ADR 0007)

`worker.py` runs `detect_year_from_pdf_bytes()` on every archived PDF and writes the result to `cds_documents.detected_year`. This is the authoritative year per [ADR 0007](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — the content-derived year wins over the URL-derived guess that the resolver makes. Strict prefix-anchored regex ladder, `y2 = y1 + 1` span validation, collect-all-unique across pages 1-10. Recall ~80% on PDFs; the rest remain `detected_year IS NULL` and consumers fall back to `cds_year` via `cds_manifest.canonical_year`.

## See also

- [`tools/tier2_extractor/`](../tier2_extractor/) — the Tier 2 extractor this worker calls
- [`tools/tier_probe/`](../tier_probe/) — backfills `source_format` so the router can route
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — the tier ladder rationale
- [`docs/decisions/0007-year-authority-moves-to-extraction.md`](../../docs/decisions/0007-year-authority-moves-to-extraction.md) — why year lives here, not in the resolver
