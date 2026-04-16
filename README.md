# collegedata.fyi

**College facts pulled straight from each school's Common Data Set.**

An open, reproducible library of US college data. We find each school's Common Data Set document, extract it into a canonical schema, and publish both the raw source file and the structured extract alongside a queryable manifest. No hand-cleaned numbers, no opinionated schema of our own — we use the one the CDS Initiative already publishes. Just ground truth you can build on top of.

> **Status: V1 live at [collegedata.fyi](https://collegedata.fyi).** Browse 337 schools, 1,000+ archived CDS documents, with structured field extraction for fillable PDFs. Flattened PDF extraction (84% of the corpus) is under active development via Docling. See [`docs/known-issues/`](docs/known-issues/) for per-school notes.

## Why this exists

There is no free public API for Common Data Set information. Every school publishes to its own URL, most as PDFs, with no central index. If you want to compare admissions statistics across schools, the options today are "write a custom scraper for each institution," "pay a commercial data provider," or "give up and use IPEDS instead," which is federal compliance data that lacks the admissions granularity the CDS captures.

Two recent discoveries made this project much cheaper to build than it would have been a year ago:

1. The CDS Initiative publishes a canonical machine-readable schema in the official 2025-26 Excel template. We extract it programmatically — 1,105 fields keyed by stable question numbers — so there's no schema-design work, and every school's data lands in the same shape.
2. A meaningful minority of school CDS PDFs are actually unflattened fillable forms with named AcroForm fields. For those schools, extraction is deterministic via `pypdf.get_fields()` and matches ground truth perfectly. Harvey Mudd 2025-26 is the verified case.

Combine those two and an open CDS library that was a multi-month engineering project a year ago is now a weekend's worth of effort. That is the actual reason this project exists now.

We also archive source files on discovery, because some schools do occasionally remove historical CDS from their websites — MIT's 2023-era CDS URLs, for example, were all removed during a 2024-2026 domain migration. This is a side benefit of the architecture, not the headline.

## What's here

- **[collegedata.fyi](https://collegedata.fyi)** — a public frontend for browsing, searching, and downloading archived CDS documents
- **Source files** (PDF, XLSX, DOCX) for each school + year combination we've found, archived on discovery
- **Canonical structured extracts** keyed to the CDS Initiative's own field IDs (A.001, B.101, C.101, ...), with provenance linking every value back to the source
- **A public API** at `https://api.collegedata.fyi` that tracks discovery status, last-verified dates, participation status, and per-document provenance
- **An extensible artifact model** so community cleanup tools can publish their own extracts alongside the primary ones without replacing them

## Quick look

**Browse the site:** [collegedata.fyi](https://collegedata.fyi) — search for a school, view archived CDS years, download source PDFs, or browse extracted field values.

**Query the API:**
```bash
# List all schools in the manifest
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?select=school_id,school_name,canonical_year&order=school_name'

# Find a specific school's documents
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?school_id=eq.yale&order=canonical_year.desc'

# Get the structured extract for a document
curl 'https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical'
```

## How it works

1. A Supabase Edge Function runs on cron, discovers new or changed CDS documents at each school's Institutional Research URL, and records them in Postgres. The source file is downloaded and archived in Storage on first discovery so we still have it if the school later removes the original.
2. A Python worker routes each document to the appropriate extractor based on its source format. The tier ladder is roughly: fillable PDF with AcroForm fields → deterministic direct read ([`tools/tier2_extractor/`](tools/tier2_extractor/)); flattened PDF → layout extraction via Docling or a third-party service, plus a schema-targeting cleaner; image-only scan → OCR + cleaner.
3. All extractors produce output keyed to the CDS Initiative's canonical field IDs using the schema at [`schemas/`](schemas/). Cross-school queries join on that field ID regardless of which extractor produced the values.
4. PostgREST exposes the manifest as a public read-only API at `api.collegedata.fyi`.
5. Community cleanup tools can register via `cleaners.yaml` and publish their own artifacts alongside the primary ones — see [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md) for the rationale.

Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Docs and decisions

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — six-pipeline map of the whole system (schema, corpus, discovery, extraction, consumer API, frontend)
- [`docs/v1-plan.md`](docs/v1-plan.md) — living project plan for V1
- [`docs/prd/002-frontend.md`](docs/prd/002-frontend.md) — frontend PRD (reviewed via /autoplan: CEO + Design + Eng review)
- [`docs/archive-pipeline.md`](docs/archive-pipeline.md) — deep dive on the discovery/archive queue
- [`docs/research/cds-vs-college-scorecard.md`](docs/research/cds-vs-college-scorecard.md) — CDS vs College Scorecard schema comparison
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
