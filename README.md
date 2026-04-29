# collegedata.fyi

**College facts pulled straight from each school's Common Data Set.**

Open-source Common Data Set API, searchable college admissions dataset, and preservation archive for U.S. higher education data.

An open, reproducible library of US college data. We find each school's Common Data Set document, extract it into a canonical schema, and publish both the raw source file and the structured extract alongside a queryable manifest. No hand-cleaned numbers, no opinionated schema of our own — we use the one the CDS Initiative already publishes. Just ground truth you can build on top of.

> **Status: V1 live at [collegedata.fyi](https://collegedata.fyi).** 697 schools indexed, 3,924 archived CDS documents, structured extraction on 3,841 of them (98%). Five of six extraction tiers shipped: filled XLSX (template cell-position map), fillable PDF (AcroForm), flattened PDF (Docling + schema-targeting cleaner), image-only scan (force-OCR), and structured HTML (HTML normalizer reusing the Tier 4 cleaner). DOCX is the only remaining tier and is scoped in [PRD 007](docs/prd/007-tier3-docx-extraction.md). GT scorer 94% on hand-audited schools; C1 admissions fields at 50-60% Tier 4 coverage corpus-wide. See [`docs/extraction-quality.md`](docs/extraction-quality.md) for full coverage by section, [`docs/known-issues/`](docs/known-issues/) for per-school notes.

## Why this exists

There is no free public API for Common Data Set information. Every school publishes to its own URL, most as PDFs, with no central index. If you want to compare admissions statistics across schools, the options today are "write a custom scraper for each institution," "pay a commercial data provider," or "give up and use IPEDS instead," which is federal compliance data that lacks the admissions granularity the CDS captures.

Two recent discoveries made this project much cheaper to build than it would have been a year ago:

1. The CDS Initiative publishes a canonical machine-readable schema in the official 2025-26 Excel template. We extract it programmatically — 1,105 fields keyed by stable question numbers — so there's no schema-design work, and every school's data lands in the same shape.
2. A meaningful minority of school CDS PDFs are actually unflattened fillable forms with named AcroForm fields. For those schools, extraction is deterministic via `pypdf.get_fields()` and matches ground truth perfectly. Harvey Mudd 2025-26 is the verified case.

Combine those two and an open CDS library that was a multi-month engineering project a year ago is now a weekend's worth of effort. That is the actual reason this project exists now.

We also archive source files on discovery, because some schools do occasionally remove historical CDS from their websites — MIT's 2023-era CDS URLs, for example, were all removed during a 2024-2026 domain migration. This is a side benefit of the architecture, not the headline.

## What's here

- **[collegedata.fyi](https://collegedata.fyi)** — a public frontend for browsing, searching, and downloading archived CDS documents, plus an institution directory of every active Title-IV school whether or not we have a CDS for it
- **Source files** (PDF, XLSX, DOCX) for each school + year combination we've found, archived on discovery
- **Canonical structured extracts** keyed to the CDS Initiative's own field IDs (A.001, B.101, C.101, ...), with provenance linking every value back to the source
- **An institution directory and coverage transparency layer** ([PRD 015](docs/prd/015-institution-directory-and-cds-coverage.md)) — every active, undergraduate-serving Title-IV institution gets a searchable identity page and an honest CDS coverage status (`CDS available` / `Older CDS available` / `No public CDS found` / `Not checked yet`). The public coverage table at [`/coverage`](https://collegedata.fyi/coverage) makes the gap visible.
- **A public API** at `https://api.collegedata.fyi` that tracks discovery status, last-verified dates, participation status, per-document provenance, and per-institution coverage state
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
2. A Python worker routes each document to the appropriate extractor based on its source format. Tiers that ship today: filled XLSX → template cell-position map + openpyxl (deterministic on the standard template layout); fillable PDF with AcroForm fields → deterministic direct read ([`tools/tier2_extractor/`](tools/tier2_extractor/)); flattened PDF → Docling layout extraction + a schema-targeting cleaner ([`tools/extraction_worker/tier4_cleaner.py`](tools/extraction_worker/tier4_cleaner.py)); image-only scans → force-OCR pass through the same Docling pipeline; structured HTML → HTML normalizer reusing the Tier 4 cleaner. Remaining tier scoped but not yet built: filled DOCX via Structured Document Tags ([PRD 007](docs/prd/007-tier3-docx-extraction.md)).
3. All extractors produce output keyed to the CDS Initiative's canonical field IDs using the schema at [`schemas/`](schemas/). Cross-school queries join on that field ID regardless of which extractor produced the values.
4. PostgREST exposes the manifest as a public read-only API at `api.collegedata.fyi`. The `cds_scorecard` view at `/rest/v1/cds_scorecard` joins each archived CDS document with the federal College Scorecard (post-graduation earnings, federal debt, net price by income bracket, completion) — see [`tools/scorecard/README.md`](tools/scorecard/README.md).
5. Community cleanup tools can register via `cleaners.yaml` and publish their own artifacts alongside the primary ones — see [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md) for the rationale.

Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Ecosystem and related projects

collegedata.fyi sits between official higher-education data systems and the document-processing tools needed to make decentralized CDS files queryable:

- [Common Data Set Initiative](https://commondataset.org/) — the canonical CDS templates and field definitions this project follows.
- [College Scorecard API](https://collegescorecard.ed.gov/data/api/) — federal outcomes, net-price, debt, completion, and earnings data; joined into `cds_scorecard`.
- [IPEDS](https://nces.ed.gov/ipeds/) — federal postsecondary reporting system and the source of school identity metadata such as UNITID.
- [Docling](https://github.com/docling-project/docling) — open-source document conversion toolkit used for flattened PDF, scanned PDF, and layout-aware extraction.
- [UrbanInstitute/ipeds-scraper](https://github.com/UrbanInstitute/ipeds-scraper) — downloader for IPEDS complete data files.
- [UrbanInstitute/education-data-package-r](https://github.com/UrbanInstitute/education-data-package-r) — R package for accessing education data including IPEDS and College Scorecard data.
- [karllhughes/colleges](https://github.com/karllhughes/colleges) — open API of U.S. colleges and universities.
- [kielni/ipeds-sql](https://github.com/kielni/ipeds-sql) — IPEDS data loaded into a SQL-friendly shape.

## Docs and decisions

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — nine-pipeline map of the whole system (schema, corpus, discovery, mirror, extraction, scorecard, institution directory + coverage, consumer API, frontend)
- [`docs/extraction-quality.md`](docs/extraction-quality.md) — current accuracy by tier, per-section corpus-wide coverage, and reproducible scoring commands
- [`docs/recipes/`](docs/recipes/) — worked examples with real data: interactive visualizations, XLSX starters, and API queries. Start with [acceptance rate vs yield](docs/recipes/acceptance-vs-yield.md)
- [`docs/v1-plan.md`](docs/v1-plan.md) — living project plan for V1
- [`docs/prd/002-frontend.md`](docs/prd/002-frontend.md) — frontend PRD (reviewed via /autoplan: CEO + Design + Eng review)
- [`docs/prd/003-ai-driven-data-quality.md`](docs/prd/003-ai-driven-data-quality.md) — AI-driven data-quality spike PRD (M1 only, approved via /autoplan)
- [`docs/archive-pipeline.md`](docs/archive-pipeline.md) — deep dive on the discovery/archive queue
- [`tools/scorecard/README.md`](tools/scorecard/README.md) — College Scorecard pipeline runbook (`/rest/v1/cds_scorecard` returns CDS docs joined with federal earnings, debt, net price by income, completion)
- [`docs/research/cds-vs-college-scorecard.md`](docs/research/cds-vs-college-scorecard.md) — CDS vs College Scorecard schema comparison
- [`docs/decisions/`](docs/decisions/) — Architectural Decision Records
- [`docs/known-issues/`](docs/known-issues/) — per-school extraction quality notes

## Contributing

This project is designed around community contribution from day one. Two especially valuable ways to help right now:

**Add a school to the discovery scraper.** If `collegedata.fyi` doesn't know about a school's CDS, it's usually because the school's website doesn't match our default URL patterns. PR a new entry to `schools.yaml` with a known-good URL or search pattern.

**Write a cleanup tool.** Our in-tree cleaner handles ~380 fields well after the Phase 6 expansion, but Docling markdown has a long tail of format variants we don't cover — community college templates, pre-2020 terminology, wrapped cells (see [`docs/known-issues/`](docs/known-issues/), [`docs/extraction-quality.md`](docs/extraction-quality.md), and the corpus survey). Raw Docling markdown lives at `cds_artifacts.notes.markdown` on every Tier 4 artifact, keyed by document. A cleanup tool reads the markdown, normalizes its target fields, and publishes the result as a new artifact with its own `producer` tag. Register your tool in `cleaners.yaml` and the CI will run it against the corpus. Per [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md), we don't pick a winner — every contributor's artifact is published alongside the primary ones.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contributor guide, including how to add a school, fix your own school's data, write a cleaner, and become a co-maintainer.

## Authors

Created and maintained by Anthony S. at [Bolewood Group, LLC](https://bolewood.com/). Contributions welcome — see the Contributing section above.

## License

MIT — see [`LICENSE`](LICENSE). Copyright © 2026 Anthony S. and Bolewood Group, LLC.
