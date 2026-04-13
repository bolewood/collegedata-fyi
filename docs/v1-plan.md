# collegedata.fyi — V1 Project Plan

**Status:** Draft, ready to start
**Last updated:** 2026-04-11
**Canonical domain:** collegedata.fyi (API at `api.collegedata.fyi`)

> This is a living document. Update it when decisions change rather than freezing it in time. Point-in-time decisions and their rationale are preserved as ADRs in [`docs/decisions/`](decisions/).

## What we're building

An open-source library of college Common Data Set (CDS) information, published at **collegedata.fyi**. V1 is deliberately scoped as "rag-tag but useful": discover CDS PDFs across college websites, extract them with Docling, and publish both the raw PDFs and the raw Docling JSON alongside a queryable manifest. No hand-cleaned data, no opinionated schema — just reproducible ground truth that the community can build on top of.

The bet is that the two hardest problems in this space ("where is each school's CDS?" and "turn the PDF into structured data") are independently valuable even in their roughest form, and that shipping the scraper + raw extracts is more useful to more people than waiting until we have perfectly normalized data.

**Naming and framing.** The public name is `collegedata.fyi`, deliberately not `opencds.io` or similar. "CDS" is inside-baseball — IR professionals know it instantly, everyone else reads it as a medical or music acronym. The `.fyi` TLD is an honest promise ("here's the reference, here's where to look it up") that matches V1's raw-and-rough scope without overclaiming the freshness or cleanliness that `.live` or `.org` would imply. README copy should lead with "college facts pulled straight from each school's Common Data Set" rather than "an open CDS library" so non-technical visitors get oriented without a glossary.

## Why this scope

We ran Docling against two test PDFs (Yale 2024-25 and Harvey Mudd 2025-26) to sanity-check the extraction quality.

Yale came out essentially clean. Section hierarchy, numeric tables, checkbox states, multi-page table continuations, and hyperlinks all survived. The main quirks were cosmetic: empty tables flattened to paragraphs, single-cell boxed values promoted to H2 headings, and some `nan` artifacts.

Harvey Mudd exposed the real shape of the problem. The C1 applicants/admits table was misaligned so that 3452/1761/4 values shifted into the wrong rows — meaning a naive consumer would silently read wrong numbers for every applicant/admit field. The B1 enrollment header collapsed its merged Full-Time/Part-Time columns. Checkboxes were dropped throughout Section C. Running page headers got promoted to H2. Section C1-C2 appeared before the "C. FIRST-TIME, FIRST-YEAR ADMISSION" heading because of reading-order confusion. Year numerals came through kerned ("202 5 -202 6").

The honest conclusion from this: extraction quality varies dramatically by school, and any V1 that tries to publish "clean" data will either lie or block indefinitely on the long tail. Publishing raw Docling output with provenance is a promise we can keep today. The cleanup becomes a separate, versionable, community-contributable layer on top.

## V1 scope

Three independently useful pieces, each shippable on its own.

**V1a — CDS Finder.** A Google-dorking scraper that takes a school name and returns the canonical URL of its most recent CDS PDF. This is genuinely useful even if nobody ever touches the Docling half — journalists, researchers, and anyone building a college-search tool currently has no index of where these PDFs live. Output is a manifest row: `(school_id, cds_year, source_pdf_url, pdf_sha256, discovered_at)`. A `schools.yaml` file holds per-school URL patterns for the long tail where the default dorks fail, and contributors can PR new patterns.

**V1b — Raw Extraction Pipeline.** For each PDF in the manifest, run Docling and publish the resulting JSON blob to Storage. No cleanup, no normalization. The only promise is "this is what Docling saw." The raw PDF is published alongside the JSON so anyone can verify against the source.

**V1c — Public Manifest API.** A Supabase-hosted Postgres table exposed read-only through PostgREST, served under `api.collegedata.fyi` via Supabase custom domain. Consumers query `https://api.collegedata.fyi/rest/v1/cds_manifest?school=eq.yale` and get JSON back. No custom backend, no UI required. Using the custom domain from day one matters because the URL ends up in documentation and example `curl` commands — we don't want to migrate those post-launch.

Explicitly out of scope for V1: a cleaned/normalized data schema, per-field validation, a web UI, and any claim that the data is accurate enough to make decisions on. Those come in V2 once we see how contributors engage.

## Architecture

Single vendor for everything: **Supabase**. No Railway, no AWS, no GCP needed.

**Supabase Postgres** holds the manifest and provenance: `cds_documents` (one row per school/year), `cds_artifacts` (one row per derived file, tagged with kind/producer/version), and `cleaners` (registry of known cleanup tools). Row-level security exposes the tables read-only through PostgREST, which gives us a free public API.

**Supabase Storage** holds the actual bytes: raw PDFs under `{school}/{year}/source.pdf`, raw Docling JSON under `{school}/{year}/raw/docling-{version}.json`, and any future derived artifacts under `{school}/{year}/cleaned/{producer}-{version}.json`. Storage is S3-compatible and free-tier generous.

**Supabase Edge Functions on cron** run the scraper. Edge functions are Deno, which is a clean fit for "fetch URLs, compute sha256, upsert Postgres rows, push bytes to Storage." A daily cron discovers new or changed PDFs and flags them `extraction_pending`. Execution logs live in the Supabase dashboard — one click to see whether the weekly refresh ran.

**Docling extraction runs separately.** Edge functions can't run Docling (it's Python, memory-hungry, and extraction is slow). For V1, this is just a local Python script: poll `extraction_pending` rows, run Docling, push the JSON back, flip the flag. For <100 schools this is fine as a laptop job notified by email when the edge function finds new work. When it grows, the same script moves to a GitHub Actions cron workflow with zero architectural changes. The worker is pluggable — the only contract is "read `extraction_pending`, write artifacts, flip the flag."

## Data model

```
cds_documents
  id              uuid pk
  school_id       text          -- slug, e.g. "yale", "harvey-mudd"
  school_name     text
  cds_year        text          -- e.g. "2024-25"
  source_pdf_url  text
  pdf_sha256      text
  pdf_page_count  int
  discovered_at   timestamptz
  status          text          -- discovered | extraction_pending | extracted | failed
  unique (school_id, cds_year)

cds_artifacts
  id                uuid pk
  document_id       uuid fk -> cds_documents
  kind              text          -- raw_docling | cleaned | schema_v1_normalized
  producer          text          -- docling | community-cleaner | ...
  producer_version  text          -- semver of the producing tool
  storage_path      text          -- path in Supabase Storage
  sha256            text
  created_at        timestamptz
  notes             jsonb         -- producer-specific metadata

cleaners
  name             text pk       -- e.g. "community-cleaner"
  repo_url         text
  latest_version   text
  output_kind      text          -- what artifact kind it emits
  registered_at    timestamptz
```

The key property: **raw artifacts are immutable.** When a new Docling version ships, we re-extract and write a new artifact row, but the old blob stays in Storage forever. Same for cleaners. This gives us cheap reproducibility and lets multiple cleaners coexist without one overwriting another.

## Accommodating contributors from day one

The artifact model is designed specifically so that community cleanup tools can plug in without needing write access to production.

A contributor's workflow: clone the repo, `pip install their-cleaner`, point it at a public raw Docling artifact, run it, get back JSON. To get their tool into the pipeline, they PR an entry to `cleaners.yaml` with `(name, repo, version, entrypoint)`. Once merged, a GitHub Actions workflow installs their tool, runs it against all raw artifacts that don't yet have an output from that producer, and writes results back as new rows in `cds_artifacts` + new blobs in Storage. Contributors never touch production credentials.

To make multiple cleaners interoperable (rather than each inventing its own output shape), we'll publish a **target schema** — a JSON Schema / Pydantic model called `cds_schema_v1` that defines what a normalized CDS record looks like. Any cleaner that wants to claim `kind=schema_v1_normalized` must produce output that validates against it. Consumers reading `schema_v1_normalized` artifacts get a stable contract regardless of which cleaner produced them, and cleaners become swappable implementations of the same interface.

If two cleaners produce competing outputs, both get published and the README points at whichever is currently canonical. The loser's artifacts stay available — we never pick winners at the storage layer.

Known extraction issues live in a per-school `known_issues.md` so contributors can prioritize. For example: "HMC 2025-26, C1 table rows shifted by one, values jammed into single cells."

## Milestones

**M0 — Scaffolding (week 1).**
Register `collegedata.fyi` (and optionally `collegedata.live` as a cheap defensive redirect). Supabase project, Postgres schema migration, Storage bucket, edge function stub, GitHub repo with README and LICENSE (MIT or Apache-2.0). Configure Supabase custom domain so `api.collegedata.fyi` routes to the project's PostgREST endpoint — do this before writing any example queries in docs. `cleaners.yaml` empty but committed. Public `cds_manifest` view exposed through PostgREST and confirmed queryable from curl against `api.collegedata.fyi`.

**M1 — CDS Finder V1 (weeks 1-2).**
Scraper edge function that takes a school slug, runs a set of Google dorks / direct URL patterns, and either finds a PDF + upserts a `cds_documents` row or records a failure. `schools.yaml` seeded with 10-20 target institutions (mix of easy wins and hard cases). Cron runs daily. Failure cases are logged with enough detail to hand-debug.

**M2 — Raw Extraction Pipeline (weeks 2-3).**
Local Python worker that polls `extraction_pending`, downloads the PDF from Storage, runs Docling, writes the JSON blob back, flips the status flag. Publishes `raw_docling` artifacts tagged with Docling version. Handles errors by flipping status to `failed` with a reason.

**M3 — Public API and README (week 3).**
PostgREST read-only exposure of `cds_documents` and `cds_artifacts`. Signed Storage URLs (or public if we're comfortable) for direct blob download. README documents: "here's the manifest, here's how to query it, here are the known extraction issues, here's how to contribute a cleaner." First announcement — probably HN Show + a few targeted communities (IR professionals, college admissions data folks).

**M4 — First contributor integration (week 4+).**
Publish `cds_schema_v1` draft. Ship a reference cleaner that handles the easy normalizations (strip running headers, fix kerned numerals, reattach orphan boxed values). Wire the cleaner into GitHub Actions so it runs on every new raw artifact. This becomes the template contributors copy from.

## Target corpus for V1 launch

Start with 20-30 schools across a quality spectrum so we can stress-test the pipeline honestly. Mix of easy cases (schools with clean URL patterns and well-formatted PDFs like Yale), medium cases (HMC-style kerning and layout quirks), and hard cases (schools that gate behind JS-rendered pages or use image-only PDFs). Explicitly include at least a few state schools, a few small liberal arts colleges, and a few tech-focused schools so the long-tail variance shows up early.

## Known risks

The scraper is the thing most likely to hit walls we can't handle in V1. Schools that render their site with JS before exposing the PDF, schools that put the CDS behind a portal login, and schools that only publish image-based PDFs (requiring OCR, not just Docling) will all fail quietly. The mitigation is visibility: every failure writes a row with a reason, and `schools.yaml` accepts per-school overrides so contributors can fix the long tail incrementally.

The extraction quality varies in ways we can't predict without running Docling against each new PDF. HMC's C1 corruption was invisible until we read the PDF page-by-page. The mitigation is the target schema + validator: if a cleaner claims `schema_v1_normalized` and its output fails validation, the artifact is published with a `validation_failed` flag and consumers can filter on it. We do not try to fix extraction bugs at ingestion time.

Supabase free-tier limits could bite if the corpus grows faster than expected. Storage is the only realistic pressure point (Postgres rows are tiny, edge function invocations are rare). Back-of-envelope: 500 schools × 5 years × ~5MB per PDF+JSON = ~12GB, which is above Supabase's free Storage tier but well within any paid plan. This is a "nice problem to have" risk.

## What V1 does not try to be

Not a data product for non-technical users. Not a replacement for IPEDS. Not a CDS authoring tool. Not a ranking or comparison site. Not a clean normalized dataset. All of those are possible V2+ directions, but they all depend on the V1 foundation existing first.

## Open questions

- MIT vs Apache-2.0 for the repo license.
- Do we expose Storage blobs publicly or behind short-lived signed URLs? Public is simpler but commits us to permanent availability of old artifact versions.
- Do we version `cds_schema_v1` from day one or wait until we have a first cleaner shipping? Leaning toward "publish the schema draft at M4, iterate in public."
- Notification mechanism for "new PDFs ready to extract" — email from the edge function, Slack webhook, or just a dashboard badge?
- How aggressively to refresh the corpus — daily discovery cron is cheap, but schools rarely update more than annually. Weekly might be plenty.
- Also grab `collegedata.live` as a defensive $5 registration? 301 to `.fyi` for now; preserves the option to reposition if the corpus ever becomes genuinely real-time.
