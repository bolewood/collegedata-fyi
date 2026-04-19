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
| `pdf_scanned` | PDF with no AcroForm and no extractable text | Tier 5 (OCR — not yet implemented) |
| `xlsx` | XLSX magic bytes `PK\x03\x04` + `.xlsx` content | Tier 1 (openpyxl Answer Sheet — not yet implemented) |
| `docx` | DOCX magic bytes `PK\x03\x04` + `word/document.xml` | Tier 3 (python-docx — not yet implemented) |
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

# Re-probe rows that already have source_format (if extraction logic changed
# how it reads the bytes and you want to reclassify)
python probe.py --refresh
```

Env vars (read from `.env` at the repo root): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

Prints a per-row log (`school_id / cds_year → source_format`) and a final distribution histogram so you can see the tier breakdown at a glance.

## Known distribution (April 2026)

The 2026-04-16 probe of a 32-school sample measured:
- 84% `pdf_flat` (→ Tier 4)
- 6% `pdf_fillable` (→ Tier 2, the high-accuracy path)
- 10% other / miscellaneous

The full-corpus distribution across 1,675 docs will surface as the extraction worker drains.

## See also

- [`tools/extraction_worker/`](../extraction_worker/) — consumes `source_format` and routes to tier extractors
- [`docs/decisions/0006-tiered-extraction-strategy.md`](../../docs/decisions/0006-tiered-extraction-strategy.md) — why the tiers exist and why this separation matters
