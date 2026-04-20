# Contributing to collegedata.fyi

Thanks for thinking about contributing. This project is designed around community help from day one, and there are a few specific ways you can make a real difference.

## Ways to contribute

### 1. Add a school we don't yet track

If `collegedata.fyi` doesn't know about a school's CDS, it's almost always because the school's website doesn't match our default URL patterns. The fix is usually one entry in [`tools/finder/schools.yaml`](tools/finder/schools.yaml).

Minimum entry:

```yaml
- id: your-school-slug
  name: Your School Name
  domain: yourschool.edu
  ipeds_id: '123456'
  discovery_seed_url: https://yourschool.edu/institutional-research/common-data-set
  scrape_policy: active
```

Use the existing entries (Carnegie Mellon, Columbia, Harvard, and so on) as reference for edge cases, such as schools that publish separate CDS files per sub-institution.

Open a PR with the new entry and a short note saying how you found the URL. The discovery pipeline will pick it up on the next scheduled run.

### 2. Fix your own school's data

If you work in institutional research at a school we index and our extraction got something wrong, you have three options, in increasing order of effort:

- **Open an issue** describing what's wrong. Include the school ID, CDS year, the specific field IDs (e.g., C1.01), and what the correct value is. We'll investigate and either fix the cleaner or add a per-school override.
- **Submit ground-truth data** for a specific year. We use hand-verified ground-truth YAMLs to score extraction accuracy. Files live in [`tools/extraction-validator/ground_truth/`](tools/extraction-validator/ground_truth/). Contributing ground truth for your school lets us detect regressions for it specifically, which is the most durable way to keep your numbers right.
- **Write a cleaner** that normalizes your school's CDS format (see below).

### 3. Write a cleanup tool

Our in-tree cleaner handles a useful subset of fields well, but Docling markdown has a long tail of format variants our cleaner does not cover (community college templates, pre-2020 terminology, wrapped cells, and so on). See [`docs/extraction-quality.md`](docs/extraction-quality.md) for current coverage by section and [`docs/known-issues/`](docs/known-issues/) for per-school notes.

Raw Docling markdown lives at `cds_artifacts.notes.markdown` on every Tier 4 artifact, keyed by document. A cleanup tool reads the markdown, normalizes its target fields, and publishes the result as a new artifact with its own `producer` tag.

To register a cleaner:

1. Build and publish your cleaner as a Python package in a public repo.
2. Open a PR appending an entry to [`cleaners.yaml`](cleaners.yaml). See the commented example in that file for schema.
3. Once merged, the CI workflow (coming soon, tracked in M4) will install and run your cleaner against new artifacts and publish results alongside ours.

Per [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md), we do not pick a winner. Every contributor's artifact is published side by side with the primary, tagged with the `producer` field so consumers can choose.

### 4. Help with extraction quality research

The hardest part of the pipeline is extracting structured data from flattened PDFs. If you have extraction tooling, schema-aware parsers, or ideas for LLM-based fallback, take a look at [`docs/prd/006-llm-fallback.md`](docs/prd/006-llm-fallback.md) and the failure-mode catalog in [`docs/research/tier4-cleaner-learnings-for-llm-fallback.md`](docs/research/tier4-cleaner-learnings-for-llm-fallback.md). PRs welcome.

## Development basics

- Python 3.11+, Node 20+, Deno for Supabase Edge Functions.
- `.venv` in repo root for Python tooling. Requirements in each tool's directory.
- Architecture overview: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- Schema reference: [`schemas/`](schemas/) (canonical 1,105-field CDS schema, keyed by stable question IDs).
- Frontend: see [`web/README.md`](web/README.md).

## Pull request conventions

- Conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, scoped by area (e.g., `feat(finder):`, `fix(extraction):`).
- One logical change per PR where possible.
- Reference the relevant PRD or ADR in the PR body when applicable.
- If you're changing an extractor, run the regression scorers in [`tools/extraction-validator/`](tools/extraction-validator/) and include the delta.

## Project governance

The project is currently maintained by [Anthony S.](https://bolewood.com) at Bolewood Group, LLC, which funds infrastructure (Supabase, Vercel, domains). That's a single-maintainer bus factor today, and we're open about it.

**We actively want co-maintainers.** If you've contributed a meaningful cleaner, a schema extension, a substantial documentation improvement, or a new extraction tier — or if you just care about this data being good and want to take shared ownership of a surface (discovery pipeline, Tier 4 cleaner, schema, frontend, docs) — open an issue or reach out directly. Co-maintainer conversations are welcome at any contribution level; there's no minimum tenure gate.

Architectural decisions are recorded as ADRs in [`docs/decisions/`](docs/decisions/). Substantive proposals should start as an ADR draft in a PR so the discussion is durable and the reasoning is preserved. Smaller changes can go through a regular issue or PR with a clear description.

### Succession and continuity

The project is designed so that the corpus cannot be stranded if Bolewood Group is ever unable to continue funding infrastructure:

- The code is MIT-licensed with no proprietary dependencies. Any fork can run the full pipeline.
- All archived source documents live in an S3-compatible object store and can be mirrored by any third party. The full archive is the long-term public-good asset; keeping it independently replicable is a first-class design goal, not an afterthought.
- The canonical schema is extracted programmatically from the CDS Initiative's own XLSX template, so there is no private schema definition to lose.
- The extraction pipeline, the discovery crawler, and the frontend are all reproducible from the repository alone.

A dedicated succession ADR will be written if the project grows to a scale where it's warranted, or if a second maintainer or sponsoring organization steps in. Until then, the fork-friendly posture above is the practical guarantee.

## If you represent a school and need a document removed

The archive preserves publicly-published CDS documents on the presumption that they are public-accountability records. If your school's IR office needs a document removed (accidental publish, FERPA-adjacent content, version dispute, etc.), the protocol is documented in [ADR 0008](docs/decisions/0008-takedown-process.md).

Briefly: email the contact on [collegedata.fyi](https://collegedata.fyi) from a `.edu` address matching your school's domain and specify `school_id`, `cds_year`, and reason. Catalog removal is immediate; bytes removal is available on request. Every takedown is logged in [`docs/takedowns.md`](docs/takedowns.md) as a public transparency measure (no requester PII).

## Questions

Open a GitHub issue with the question label, or reach out via the contact on [collegedata.fyi](https://collegedata.fyi). Substantive technical questions and methodology discussions are always welcome.

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [`LICENSE`](LICENSE).
