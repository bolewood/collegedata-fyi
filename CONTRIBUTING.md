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

Before opening the PR, run the offline identity guard:

```bash
python tools/finder/identity_guard.py
python tools/finder/school_redirect_guard.py
```

The guard checks every curated `name`, `domain`, and `ipeds_id` claim against the checked-in official NCES identity snapshot. If an institution has moved to a new public slug, preserve the old slug in `retired_aliases` so existing links continue to redirect; do not reuse it for another school.
Keep [`web/src/data/school-redirects.json`](web/src/data/school-redirects.json)
in sync with those reviewed aliases. The redirect guard fails when the manifest
is missing an alias, contains an extra alias, or points at a conflicting school.

Open a PR with the new entry and a short note saying how you found the URL. The discovery pipeline will pick it up on the next scheduled run.

Hard schools usually need one of two other files instead of (or as well as) a `schools.yaml` entry:

- [`tools/finder/school_overrides.yaml`](tools/finder/school_overrides.yaml) holds per-school `browse_url`, year-tagged `direct_archive_urls` (Box/Drive/SharePoint listings, and Archive.org snapshots for PDFs a school has taken down), and `hosting_override` blocks. Pin Wayback captures as complete `id_` URLs (toolbar URLs return HTML, and some captures truncate at 1 MB without `%%EOF`).
- [`tools/finder/waf_blocked_urls.yaml`](tools/finder/waf_blocked_urls.yaml) lists listings behind a WAF or JavaScript wall that the scheduled headless-browser archive job crawls.

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
3. Once merged, the CI workflow (coming soon, tracked in M4) will install and run your cleaner against new artifacts and publish results alongside ours. No such workflow exists yet, so registering a cleaner today only records it in `cleaners.yaml`.

Per [ADR 0002](docs/decisions/0002-publish-raw-over-clean.md), we do not pick a winner. Every contributor's artifact is published side by side with the primary, tagged with the `producer` field so consumers can choose.

### 4. Help with extraction quality research

The hardest part of the pipeline is extracting structured data from flattened PDFs. If you have extraction tooling, schema-aware parsers, or ideas for LLM-based fallback, take a look at [`docs/tier4-llm-fallback.md`](docs/tier4-llm-fallback.md) (the shipped fallback; [PRD 006](docs/prd/006-llm-fallback.md) is the design record) and the failure-mode catalog in [`docs/research/tier4-cleaner-learnings-for-llm-fallback.md`](docs/research/tier4-cleaner-learnings-for-llm-fallback.md). PRs welcome.

## Development basics

- Python 3.12 (pinned in [`.python-version`](.python-version); CI uses 3.12), Node 22 (what CI and Vercel run), and Deno 2.x for Supabase Edge Functions.
- Python tooling takes its requirements from each tool's directory. For anything that runs extraction, build the venv from the lock file instead of installing packages by hand:

  ```bash
  cd tools/extraction_worker
  python3.12 -m venv .venv && .venv/bin/pip install -r requirements.lock
  ```

  The worker checks the interpreter and every pinned package at startup and exits on any mismatch (`dependency_check.py`), because different Docling or torch builds write different field values for the same PDF. Pass `--allow-dependency-drift` only for throwaway experiments.
- Architecture overview: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- Schema reference: [`schemas/`](schemas/) (canonical 1,105-field CDS schema, keyed by stable question IDs).
- Frontend: see [`web/README.md`](web/README.md).
- **Visual system** (read before touching any UI): [`web/DESIGN_SYSTEM.md`](web/DESIGN_SYSTEM.md). Canonical tokens in [`web/src/app/tokens.css`](web/src/app/tokens.css); live reference page at [`/design-system/`](https://collegedata.fyi/design-system/); handoff source archive in [`docs/design/`](docs/design/).

## Pull request conventions

- Conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, scoped by area (e.g., `feat(finder):`, `fix(extraction):`).
- One logical change per PR where possible.
- Reference the relevant PRD or ADR in the PR body when applicable.
- If you're changing an extractor, run the regression scorers in [`tools/extraction-validator/`](tools/extraction-validator/) and include the delta.
- User-visible changes bump [`VERSION`](VERSION) (four parts, `MAJOR.MINOR.PATCH.MICRO`) and add a [`CHANGELOG.md`](CHANGELOG.md) entry; recent PR titles carry a `vX.Y.Z.W` prefix. Docs-only and data-only PRs usually skip the bump. If you are not sure, say so in the PR and the maintainer will sort it out.

### Migrations and Edge Functions

- **Migrations reach production only from `main`.** Never run `supabase db push` from a feature branch, even for your own migration: it leaves production ahead of `main` and breaks `supabase db reset` for everyone else. Open the PR with the migration file; a maintainer applies it from a fresh `main` checkout after merge. Test a new migration against a seeded local database (`supabase db reset` on an empty one can fail, because some older migrations assume production data).
- **Edge Functions deploy from `main` too.** The `Deploy Edge Functions` workflow deploys every function in `supabase/functions/` when function code or `supabase/config.toml` changes on `main`. Do not run `supabase functions deploy` from a branch.

### CI checks

Pull requests run [`.github/workflows/ci.yml`](.github/workflows/ci.yml). The checks most likely to catch a contributor:

- **Migration filename hygiene**: `YYYYMMDDHHMMSS_snake_case.sql`, unique timestamps, sorted.
- **Identity and redirect guards**: `tools/finder/identity_guard.py` and `tools/finder/school_redirect_guard.py` (see "Add a school" above).
- **Alias-link guard**: a Vitest test (`web/src/lib/no-alias-school-links.test.ts`) fails if any web source links to `/schools/<alias-slug>` for a renamed school. Link to the canonical slug.
- **No remote fonts**: a Vitest test (`web/src/lib/no-remote-fonts.test.ts`) fails on `next/font/google` or Google Fonts URLs. Add faces as local files.
- **GitHub Actions heredoc lint**: `python tools/ops/lint_gha_heredocs.py` rejects heredoc patterns that break inside workflow `run:` blocks.
- Python unit tests, Deno tests for the Edge Functions, the MCP stdio test, and the web typecheck, Vitest, build, and Playwright smoke tests (`cd web && npm ci && npm run typecheck && npm test`).

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

Briefly: email `contact@bolewood.com` (also shown on the [privacy page](https://collegedata.fyi/privacy)) from a `.edu` address matching your school's domain and specify `school_id`, `cds_year`, and reason. Catalog removal is immediate; bytes removal is available on request. Every takedown is logged in [`docs/takedowns.md`](docs/takedowns.md) as a public transparency measure (no requester PII).

## Questions

Open a GitHub issue with the question label, or email `contact@bolewood.com`. Substantive technical questions and methodology discussions are always welcome.

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [`LICENSE`](LICENSE).

One exception: the curated discovery content under [`data/discovery/`](data/discovery/) is licensed [CC BY-SA 4.0](data/discovery/LICENSE), and outside contributions to that directory are not accepted without a signed contribution agreement. Read [`data/discovery/README.md`](data/discovery/README.md) before opening a PR that touches it. Code contributions everywhere else in the repo are unaffected.
