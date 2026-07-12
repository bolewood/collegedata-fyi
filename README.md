# collegedata.fyi

**College facts pulled from school-published Common Data Sets and source-labeled federal data.**

Open-source Common Data Set API, searchable college admissions dataset, federal baseline fact layer, and preservation archive for U.S. higher education data.

An open, reproducible library of US college data. We find each school's Common Data Set document, extract it into a canonical schema, and publish both the raw source file and the structured extract alongside a queryable manifest. For schools without a public CDS, we now publish a curated NCES/IPEDS federal baseline keyed by `ipeds_id` (zero-padded UNITID) and labeled as federal data. No hand-cleaned numbers, no unlabeled source blending: CDS remains the school-authored source, IPEDS and Scorecard remain federal context.

> **Status: V1 live at [collegedata.fyi](https://collegedata.fyi).** 6,322 institutions indexed through the federal directory, 3,950 archived CDS documents, 3,792 documents extracted, 200,957 public `cds_fields` rows, 475 `school_browser_rows`, and 383 `school_merit_profile` rows. Five of six extraction tiers shipped: filled XLSX, fillable PDF, flattened PDF, image-only scan, and structured HTML. DOCX is the only remaining tier and is scoped in [PRD 007](docs/prd/007-tier3-docx-extraction.md). The live product now includes institution coverage transparency, source-labeled NCES/IPEDS baseline facts, academic positioning, admission strategy, match-list building, merit profile data, Scorecard outcomes, and a PRD 019 change-intelligence alpha for source-linked year-over-year CDS deltas. Public change events are explicitly review-gated. See [`docs/extraction-quality.md`](docs/extraction-quality.md) for current CDS extraction coverage and [`tools/ipeds/README.md`](tools/ipeds/README.md) for the IPEDS release pipeline.

## Why this exists

There is no free public API for Common Data Set information. Every school publishes to its own URL, most as PDFs, with no central index. If you want to compare admissions statistics across schools, the options today are "write a custom scraper for each institution," "pay a commercial data provider," or fall back to IPEDS. IPEDS is the right federal baseline for broad coverage, but it lacks the current-year, school-authored admissions granularity the CDS captures.

Two recent discoveries made this project much cheaper to build than it would have been a year ago:

1. The CDS Initiative publishes a canonical machine-readable schema in the official 2025-26 Excel template. We extract it programmatically — 1,105 fields keyed by stable question numbers — so there's no schema-design work, and every school's data lands in the same shape.
2. A meaningful minority of school CDS PDFs are actually unflattened fillable forms with named AcroForm fields. For those schools, extraction is deterministic via `pypdf.get_fields()` and matches ground truth perfectly. Harvey Mudd 2025-26 is the verified case.

Combine those two and an open CDS library that was a multi-month engineering project a year ago is now a weekend's worth of effort. That is the actual reason this project exists now.

We also archive source files on discovery, because some schools do occasionally remove historical CDS from their websites — MIT's 2023-era CDS URLs, for example, were all removed during a 2024-2026 domain migration. This is a side benefit of the architecture, not the headline.

## What's here

- **[collegedata.fyi](https://collegedata.fyi)** — a public frontend for browsing, searching, and downloading archived CDS documents, plus an institution directory of every active Title-IV school whether or not we have a CDS for it
- **Source files** (PDF, XLSX, DOCX, and structured HTML) for each school + year combination we've found, archived on discovery
- **Canonical structured extracts** keyed to the CDS Initiative's own field IDs (A.001, B.101, C.101, ...), with provenance linking every value back to the source
- **An institution directory and coverage transparency layer** ([PRD 015](docs/prd/015-institution-directory-and-cds-coverage.md)) — every active, undergraduate-serving Title-IV institution gets a searchable identity page and an honest CDS coverage status (`CDS available` / `Older CDS available` / `No public CDS found` / `Not checked yet`). The public coverage table at [`/coverage`](https://collegedata.fyi/coverage) makes the gap visible.
- **A source-labeled NCES/IPEDS federal baseline** ([PRD 021](docs/prd/021-ipeds-coverage-layer.md)) — curated enrollment, admissions, cost, aid, and outcome-adjacent facts for in-scope institutions, especially schools where no public CDS is archived. Provisional/final release status, source table/variable, imputation status, and definition-alignment notes stay visible.
- **Fit-data products on top of the raw CDS** — academic positioning ([PRD 016](docs/prd/016-academic-positioning-card.md)), admission strategy ([PRD 016B](docs/prd/016B-admission-strategy-card.md)), match-list building ([PRD 017](docs/prd/017-match-list-builder.md)), and merit profile data ([PRD 018](docs/prd/018-open-college-fit-data.md))
- **Change intelligence alpha** ([PRD 019](docs/prd/019-cds-change-intelligence.md)) — deterministic year-over-year events for material deltas, newly missing/reported fields, producer or quality changes, and an operator review workflow before anything becomes public or reportable
- **A public API** at `https://api.collegedata.fyi` that tracks discovery status, last-verified dates, participation status, per-document provenance, per-institution coverage state, browser-ready admissions/profile rows, source-labeled IPEDS baseline facts, Scorecard joins, and merit-aid profiles
- **An extensible artifact model** so community cleanup tools can publish their own extracts alongside the primary ones without replacing them

## Quick look

**Browse the site:** [collegedata.fyi](https://collegedata.fyi) — search for a school, view archived CDS years, download archived source files or a per-school-year XLSX/CSV spreadsheet of the extracted values, or browse extracted field values.

**Query the API:**

Simple no-auth endpoints for agents, CLIs, and notebooks:

```bash
curl 'https://www.collegedata.fyi/api/schools/search?q=mit'
curl 'https://www.collegedata.fyi/api/schools/mit/facts?categories=admissions,cost,outcomes'
curl 'https://www.collegedata.fyi/api/compare?schools=mit,yale,university-of-chicago'
curl 'https://www.collegedata.fyi/openapi.json'
```

Raw PostgREST remains available for power users:

```bash
ANON_KEY="<copy the public anon key from https://www.collegedata.fyi/api>"

# List all live schools in the manifest
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?removed_at=is.null&select=school_id,school_name,canonical_year&order=school_name' \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY"

# Find a specific school's documents
curl 'https://api.collegedata.fyi/rest/v1/cds_manifest?school_id=eq.yale&removed_at=is.null&order=canonical_year.desc' \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY"

# Get the structured extract for a document
curl 'https://api.collegedata.fyi/rest/v1/cds_artifacts?document_id=eq.<uuid>&kind=eq.canonical' \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY"

# Historical IPEDS facts: use ipeds_id, field_key, and a data_year range for fast reads
curl 'https://api.collegedata.fyi/rest/v1/ipeds_facts?ipeds_id=eq.110635&field_key=in.(retention_rate_full_time,graduation_rate_6yr)&data_year=gte.2019&data_year=lte.2024&select=ipeds_id,data_year,field_key,value_numeric,source_table,source_variable&order=data_year.asc' \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY"
```

## How it works

1. Supabase Edge Functions run on cron, discover new or changed CDS documents at each school's Institutional Research URL, and record them in Postgres. Source bytes are archived in Storage on first discovery so we still have them if the school later removes the original. Schools that publish one CDS year as separate A-J section PDFs are assembled into one logical extraction source while preserving each original section file as provenance.
2. A Python worker prioritizes fresh CDS years, routes each document from byte-derived `source_format`, and extracts by tier. Tiers that ship today: filled XLSX -> template or embedded answer-column cell map + openpyxl; fillable PDF with AcroForm fields -> deterministic direct read ([`tools/tier2_extractor/`](tools/tier2_extractor/)); flattened PDF -> Docling layout extraction + schema-targeting cleaner ([`tools/extraction_worker/tier4_cleaner.py`](tools/extraction_worker/tier4_cleaner.py)); image-only scans -> force-OCR pass through the same Docling pipeline; structured HTML -> HTML normalizer reusing the Tier 4 cleaner. Remaining tier scoped but not yet built: filled DOCX via Structured Document Tags ([PRD 007](docs/prd/007-tier3-docx-extraction.md)).
3. All extractors produce output keyed to CDS canonical field IDs using the schemas at [`schemas/`](schemas/). 2025-26 and 2024-25 are canonical template years; 2023-24 is supported by a synthesized canonical schema built from the official 2023-24 PDF form tags plus the 2024-25 field map. Older structural schemas remain available for audits and overlays.
4. The IPEDS pipeline loads official NCES metadata workbooks and selected CSV table ZIPs into release, metadata, raw-row, and curated-fact tables. Historical releases from 2004-05 through 2024-25 can be loaded with Access fallback for older releases. `school_facts_unified` is the public serving view for source-labeled federal baseline facts; `ipeds_current_facts` is backed by a materialized cache; raw IPEDS rows are preserved for audit, not treated as the product API.
5. PostgREST exposes the manifest, field substrate, browser rows, institution coverage, IPEDS facts, Scorecard joins, and merit profiles as a public read-only API at `api.collegedata.fyi`. The `browser-search` Edge Function powers the queryable browser and match list; `school_merit_profile` joins Section H CDS facts with federal affordability/outcome fields.
6. PRD 019 projects selected year-over-year changes from comparable primary CDS rows into `cds_field_change_events`. Generated candidates are service-role/operator data by default; the school-page "What changed" card only reads events marked `public_visible=true` after verification.
7. Community cleanup tools can register via `cleaners.yaml` and publish their own artifacts alongside the primary ones — see [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md) for the rationale.

Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Ecosystem and related projects

collegedata.fyi sits between official higher-education data systems and the document-processing tools needed to make decentralized CDS files queryable:

- [Common Data Set Initiative](https://commondataset.org/) — the canonical CDS templates and field definitions this project follows.
- [College Scorecard API](https://collegescorecard.ed.gov/data/api/) — federal outcomes, net-price, debt, completion, and earnings data; joined into `cds_scorecard`.
- [IPEDS](https://nces.ed.gov/ipeds/) — federal postsecondary reporting system, source of UNITID identity metadata, and source for the PRD 021 federal baseline fact layer.
- [Docling](https://github.com/docling-project/docling) — open-source document conversion toolkit used for flattened PDF, scanned PDF, and layout-aware extraction.
- [UrbanInstitute/ipeds-scraper](https://github.com/UrbanInstitute/ipeds-scraper) — downloader for IPEDS complete data files.
- [UrbanInstitute/education-data-package-r](https://github.com/UrbanInstitute/education-data-package-r) — R package for accessing education data including IPEDS and College Scorecard data.
- [karllhughes/colleges](https://github.com/karllhughes/colleges) — open API of U.S. colleges and universities.
- [kielni/ipeds-sql](https://github.com/kielni/ipeds-sql) — IPEDS data loaded into a SQL-friendly shape.

## Docs and decisions

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — eleven-pipeline map of the whole system (schema, corpus, discovery, mirror, extraction, scorecard, institution directory + coverage, IPEDS federal baseline, change intelligence, consumer API, frontend)
- [`docs/data-extraction-pipeline.md`](docs/data-extraction-pipeline.md) — operational diagram of the discovery/archive/extraction/projection flow, including cadence, storage, and known issues
- [`docs/extraction-quality.md`](docs/extraction-quality.md) — current accuracy by tier, per-section corpus-wide coverage, and reproducible scoring commands
- [`docs/api-usage-attribution.md`](docs/api-usage-attribution.md) — low-PII friendly API usage attribution for MCP, CLI, and cooperative external integrations
- [`docs/recipes/`](docs/recipes/) — worked examples with real data: interactive visualizations, XLSX starters, and API queries. Start with [acceptance rate vs yield](docs/recipes/acceptance-vs-yield.md)
- [`docs/plans/prd-019-spike-and-qa.md`](docs/plans/prd-019-spike-and-qa.md) — PRD 019 spike and QA summary, including the first calibration-run numbers and review gates
- [`docs/v1-plan.md`](docs/v1-plan.md) — living project plan for V1
- [`docs/prd/002-frontend.md`](docs/prd/002-frontend.md) — frontend PRD (reviewed via /autoplan: CEO + Design + Eng review)
- [`docs/prd/003-ai-driven-data-quality.md`](docs/prd/003-ai-driven-data-quality.md) — AI-driven data-quality spike PRD (M1 only, approved via /autoplan)
- [`docs/archive-pipeline.md`](docs/archive-pipeline.md) — deep dive on the discovery/archive queue
- [`tools/scorecard/README.md`](tools/scorecard/README.md) — College Scorecard pipeline runbook (`/rest/v1/cds_scorecard` returns CDS docs joined with federal earnings, debt, net price by income, completion)
- [`tools/ipeds/README.md`](tools/ipeds/README.md) — NCES/IPEDS release loader and scheduled release-probe runbook
- [`docs/research/cds-vs-college-scorecard.md`](docs/research/cds-vs-college-scorecard.md) — CDS vs College Scorecard schema comparison
- [`docs/decisions/`](docs/decisions/) — Architectural Decision Records
- [`docs/known-issues/`](docs/known-issues/) — per-school extraction quality notes

## Contributing

This project is designed around community contribution from day one. Two especially valuable ways to help right now:

**Add a school to the discovery scraper.** If `collegedata.fyi` doesn't know about a school's CDS, it's usually because the school's website doesn't match our default URL patterns. PR a new entry to `schools.yaml` with a known-good URL or search pattern.

**Write a cleanup tool.** Our in-tree cleaner handles the high-value 2024-25/2025-26 browser and school-page surfaces well, including admissions, SAT/ACT, Section H aid, and several large enrollment grids, but Docling markdown still has a long tail of format variants we don't cover (see [`docs/known-issues/`](docs/known-issues/), [`docs/extraction-quality.md`](docs/extraction-quality.md), and the corpus survey). Raw Docling markdown lives at `cds_artifacts.notes.markdown` on every Tier 4 artifact, keyed by document. A cleanup tool reads the markdown, normalizes its target fields, and publishes the result as a new artifact with its own `producer` tag. Register your tool in `cleaners.yaml` and the CI will run it against the corpus. Per [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md), we don't pick a winner — every contributor's artifact is published alongside the primary ones.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contributor guide, including how to add a school, fix your own school's data, write a cleaner, and become a co-maintainer.

## Authors

Created and maintained by Anthony S. at [Bolewood Group, LLC](https://bolewood.com/). Contributions welcome — see the Contributing section above.

## License

MIT — see [`LICENSE`](LICENSE). Copyright © 2026 Anthony S. and Bolewood Group, LLC.

One exception: the curated discovery content under [`data/discovery/`](data/discovery/)
(experience-card library, interest ontology, explanation templates, discovery policy
definitions) is licensed [CC BY-SA 4.0](data/discovery/LICENSE) — publicly inspectable,
attribution and share-alike required. Contributions to that directory require a
contribution agreement; see [`data/discovery/README.md`](data/discovery/README.md).
