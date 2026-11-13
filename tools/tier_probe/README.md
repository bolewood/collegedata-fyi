# tier_probe

Classifies every archived CDS document by file format so the extraction worker's router can route correctly without re-downloading the file. Reads the bytes from the `sources` Storage bucket, inspects the PDF structure (AcroForm presence, extractable text, XLSX/DOCX magic), and writes the result back to `cds_documents.source_format`.

Run once per archive drain, or any time a new batch of documents lands in `extraction_pending`.

## What's in the directory

| File | Purpose |
|---|---|
| `probe.py` | The probe. Reads every `cds_documents` row (or a filtered subset), looks up its latest `kind='source'` artifact, downloads the bytes, and classifies. |
| `requirements.txt` | `supabase`, `python-dotenv`, `pypdf`, `openpyxl`, `python-docx`. |

## Classification rules

| source_format | Detection | Routes to |
|---|---|---|
| `pdf_fillable` | PDF with an AcroForm that has ≥1 populated field | Tier 2 (deterministic `pypdf.get_fields()` extraction) |
| `pdf_flat` | PDF with no AcroForm but extractable text | Tier 4 (Docling markdown + cleaner) |
| `pdf_scanned` | PDF with no AcroForm and no extractable text | Tier 5 (Tier 4 with force-OCR) |
| `xlsx` | ZIP magic bytes + XLSX workbook internals | Tier 1 (openpyxl template/embedded answer-column extraction) |
| `docx` | ZIP magic bytes + `word/document.xml` | Tier 3 (python-docx SDT reader — not yet implemented) |
| `html` | Archived bytes start with an HTML doctype/`<html>`/`<head>` | Tier 6 (`html_to_markdown.py` then the Tier 4 cleaner) |
| `other` | Parse error or unexpected content type | Fails fast; operator investigates |

## Usage

```bash
cd tools/tier_probe

# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Probe everything that doesn't have a source_format yet
python probe.py

# Test against 20 rows without writing
python probe.py --limit 20 --dry-run

# Target one school
python probe.py --school yale

# Write per-row details to JSON (use scratch/ for run artifacts)
python probe.py --limit 20 --dry-run --json-out ../../scratch/tier_probe/probe.json

# Re-probe rows that already have source_format (if extraction logic changed
# how it reads the bytes and you want to reclassify)
python probe.py --refresh
```

Other flags: `--env <path>` (default `.env`), `--json-out <file>`. Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

Prints a per-row log (`school_id / cds_year → source_format`) and a final distribution histogram so you can see the tier breakdown at a glance.

## Source-format distribution

The live distribution changes with every archive run; see
[/pipeline-observation](https://www.collegedata.fyi/pipeline-observation) or
query `cds_manifest.source_format` through the public API. Order of magnitude as
of Nov 2026: mostly `pdf_flat`, a few hundred `xlsx`, a couple hundred
`pdf_fillable`, and small numbers of `pdf_scanned`, `html`, `docx` and `other`.

PR #44 made ZIP classification content-aware, so DOCX files no longer route as
XLSX just because both formats start with `PK\x03\x04`.

## See also

- [`tools/extraction_worker/`](../extraction_worker/) — consumes `source_format` and routes to tier extractors
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — why the tiers exist and why this separation matters
