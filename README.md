# collegedata.fyi

**College facts pulled straight from each school's Common Data Set.**

An open, reproducible library of US college data. We find each school's Common Data Set PDF, extract it with [Docling](https://github.com/DS4SD/docling), and publish both the raw PDF and the raw structured extract alongside a queryable manifest. No hand-cleaned numbers, no opinionated schema — just ground truth you can build on top of.

> **Status: early V1.** The extraction is deliberately raw. Some schools contain known bugs — see [`docs/known-issues/`](docs/known-issues/). Do not read values from the raw Docling JSON without validating against the source PDF.

## What's here

- **Source PDFs** for each school + year combination we've found
- **Raw Docling JSON** extracts alongside each PDF
- **A public manifest** of `(school, year, source_url, pdf_sha256, extraction_status)` exposed at `https://api.collegedata.fyi`
- **An extensible artifact model** so community cleanup tools can publish normalized outputs alongside the raw data without replacing it

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

1. A Supabase Edge Function runs on cron, discovers new or changed CDS PDFs, and records them in Postgres.
2. A Python worker picks up `extraction_pending` documents, runs Docling, and stores raw JSON artifacts in Supabase Storage.
3. PostgREST exposes the manifest as a public read-only API at `api.collegedata.fyi`.
4. Community cleanup tools can register via [`cleaners.yaml`](cleaners.yaml) and publish their own artifacts alongside the raw output — see [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md) for the rationale.

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
