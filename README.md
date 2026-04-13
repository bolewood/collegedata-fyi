# collegedata.fyi

**College facts pulled straight from each school's Common Data Set.**

An open, reproducible library of US college data. We find each school's Common Data Set document, extract it into a canonical schema, and publish both the raw source file and the structured extract alongside a queryable manifest. No hand-cleaned numbers, no opinionated schema of our own — we use the one the CDS Initiative already publishes. Just ground truth you can build on top of.

> **Status: early V1.** Extraction quality varies by source format. Fillable PDFs are read deterministically via AcroForm fields; flattened PDFs fall through to a layout-extraction path that is still under development. See [`docs/known-issues/`](docs/known-issues/) for per-school notes.

## Why this matters now

Two things changed in 2024-2026 that make this project time-sensitive.

1. **The April 2024 DOJ ruling on ADA Title II** requires public universities to make all hosted PDFs WCAG 2.1 AA compliant. The traditional CDS template, with its dense multi-column demographic and financial-aid tables, is structurally hostile to screen readers and extremely difficult to remediate. To limit legal exposure, many risk-averse public universities are **actively removing historical CDS PDFs from their websites** rather than retrofit them for accessibility. Documents that existed last year are disappearing now.

2. **The CDS Initiative is publicly endorsing machine-readable formats.** The 2025-26 Word template includes a note from the Initiative suggesting institutions use "Large Language Models, VBA macros, or Python scripts" to extract data from legacy PDFs into CSV files, and the Initiative is asking publishers to accept raw machine-readable data rather than continuing to rely on "beautifully formatted but legally perilous PDFs."

Put those together and the project's mission is sharper than it was a month ago. We are not just an open data library. We are an **active preservation archive** for public-accountability documents that are vanishing in real time, and our architecture aligns with what the standards body itself is publicly asking for. Every PDF we find gets archived in Supabase Storage the moment we see it. Every manifest row tracks when we last verified the source was still live. If a school removes their CDS next year, we still have it, and consumers can still query the data.

## What's here

- **Source files** (PDF, and eventually XLSX / DOCX) for each school + year combination we've found, archived on discovery
- **Canonical structured extracts** keyed to the CDS Initiative's own field IDs (A.001, B.101, C.101, …), with provenance linking every value back to the source
- **A public manifest** exposed at `https://api.collegedata.fyi` that tracks discovery status, last-verified dates, participation status, and per-document provenance
- **An extensible artifact model** so community cleanup tools can publish their own extracts alongside the primary ones without replacing them

## Quick look

```bash
# List every document in the manifest
curl 'https://api.collegedata.fyi/rest/v1/cds_documents?select=*'

# Find a specific school's most recent CDS
curl 'https://api.collegedata.fyi/rest/v1/cds_documents?school_id=eq.yale&order=cds_year.desc&limit=1'

# List all artifacts for that document (raw + any cleaners that have run)
curl 'https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.<uuid>'
```

(API not live yet — pending M0 milestone. See [`docs/v1-plan.md`](docs/v1-plan.md).)

## How it works

1. A Supabase Edge Function runs on cron, discovers new or changed CDS documents at each school's Institutional Research URL, and records them in Postgres. The source file is downloaded and archived in Storage on first discovery so we still have it if the school later removes the original.
2. A Python worker routes each document to the appropriate extractor based on its source format. The tier ladder is roughly: fillable PDF with AcroForm fields → deterministic direct read ([`tools/tier2_extractor/`](tools/tier2_extractor/)); flattened PDF → layout extraction via Docling or a third-party service, plus a schema-targeting cleaner; image-only scan → OCR + cleaner.
3. All extractors produce output keyed to the CDS Initiative's canonical field IDs using the schema at [`schemas/`](schemas/). Cross-school queries join on that field ID regardless of which extractor produced the values.
4. PostgREST exposes the manifest as a public read-only API at `api.collegedata.fyi`.
5. Community cleanup tools can register via `cleaners.yaml` and publish their own artifacts alongside the primary ones — see [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md) for the rationale.

Full architecture: [`docs/v1-plan.md`](docs/v1-plan.md).

## Docs and decisions

- [`docs/v1-plan.md`](docs/v1-plan.md) — living project plan for V1
- [`docs/decisions/`](docs/decisions/) — Architectural Decision Records
- [`docs/known-issues/`](docs/known-issues/) — per-school extraction quality notes

## Contributing

This project is designed around community contribution from day one. Two especially valuable ways to help right now:

**Add a school to the discovery scraper.** If `collegedata.fyi` doesn't know about a school's CDS, it's usually because the school's website doesn't match our default URL patterns. PR a new entry to `schools.yaml` with a known-good URL or search pattern.

**Write a cleanup tool.** Raw Docling output has real quirks (see [`docs/known-issues/`](docs/known-issues/)). A cleanup tool reads raw artifacts, normalizes them, and publishes the result as a new artifact kind. Register your tool in `cleaners.yaml` and the CI will run it against the corpus.

See `CONTRIBUTING.md` (coming soon) for details.

## Authors

Created and maintained by Anthony S. at [Bolewood Group, LLC](https://bolewood.com/). Contributions welcome — see the Contributing section above.

## License

MIT — see [`LICENSE`](LICENSE). Copyright © 2026 Anthony S. and Bolewood Group, LLC.
