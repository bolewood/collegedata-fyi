# Changelog

All notable changes to this project will be documented in this file.

This project uses four-part semantic versioning.

## [Unreleased]

### Added

- Show a data-generated Common Data Set archive lead on school hubs and year pages, including an official IR link when we have a usable HTML URL, and gated-request copy only for schools we have actually read (Virginia Tech).
- Publish three source-literacy pages under `/about` (Common Data Set, College Scorecard, IPEDS) and link them from About, the footer, and `/llms.txt`.
- Record the August 2026 Search Console CDS-query export next to PRD 028, including URL inspection of the Virginia Tech and Harvey Mudd canaries.
- Record school-direct Common Data Set insert and refresh events in an append-only log, expose a per-school RSS feed of those events, show which freshness signal a school or year page is using, and daily-probe the top 50 schools by public C1 applicant volume once they are nine months past that file date.

### Changed

- Replace the About page’s three-paragraph source gloss with a short hub that points at the longer CDS, Scorecard, and IPEDS notes.
- Add R (`httr2`) copy-paste examples on `/api` and the acceptance-vs-yield recipe, and round recipe-page percents to whole numbers except below 10% and for endowment draw rates.

### Fixed

- Rank Jump-to-school exact slugs and nicknames (MIT, Penn) ahead of accidental name substrings, and prefer schools that already have a CDS year.
- Point Oklahoma's archive seed at the IRR listing (`/irr/other-reports`) instead of a single 2023-24 DAM PDF, and prefer Brave HTML listings over year-specific PDFs so sibling years are not frozen out.

## [0.5.1.0] - 2026-08-10

### Added

- Verify in CI that every reviewed retired school slug has one unambiguous, non-conflicting permanent redirect to its canonical school.

### Changed

- Treat the checked-in retired-alias corpus as the shared redirect authority for school pages, metadata, APIs, and downloads, while still resolving ordinary search aliases from the live crosswalk.

### Fixed

- Preserve scalar, repeated, and empty query parameters when retired school and school-year links redirect to their canonical pages.
- Prevent annual Scorecard refreshes from assigning a retired slug as another school's primary or non-primary alias.

## [0.5.0.0] - 2026-08-10

### Added

- Validate every curated school-to-IPEDS mapping against a checked-in official NCES identity snapshot in CI and before directory or recipe generation can write data.
- Follow retired school links safely across pages, metadata, Open Graph images, APIs, CSV exports, and Excel downloads with permanent redirects to the canonical school.

### Changed

- Preserve reviewed school slugs and retired aliases across annual finder and College Scorecard refreshes, while refusing missing, empty, malformed, ambiguous, or identity-mismatched inputs before any database client is created.
- Keep the waitlist and endowment recipes tied to canonical document and IPEDS provenance, including corrected Tufts data and refreshed endowment coverage.

### Fixed

- Restore Tufts University to IPEDS `168148` and UMass Dartmouth to IPEDS `167987`, with an atomic migration that repairs the directory, documents, projections, discovery history, coverage, search, federal facts, and serving caches without transferring one institution's data to the other.
- Prevent a later Scorecard refresh or stale retired-slug payload from reintroducing the Tufts identity split.

## [0.4.0.0] - 2026-08-06

### Added

- Review the [reproducible 24-check data-integrity audit](docs/plans/audit-2026-08-06-final/README.md) with full-universe pagination evidence, query and result checksums, source-byte probes, a deterministic resolver cohort, and an explicit record of executed, partial, deferred, and rejected checks.
- Follow the [recommended audit cadence](docs/plans/audit-2026-08-06-final/RECOMMENDED-CADENCE.md), backed by daily, weekly, monthly, quarterly, release-triggered, and change-triggered controls, with the remaining manual ground-truth and concurrency work called out separately.

### Changed

- Keep the [annual College Scorecard directory refresh](tools/scorecard/README.md) aligned with the current complete vintage by comparing the prior release, stabilizing one-release degree-classification regressions, hiding institutions missing from the new vintage, and refreshing public coverage immediately.

### Fixed

- Accept valid empty PostgREST result sets in the audit paginators and keep the regression checks running in CI.

## [0.3.0.0] - 2026-08-05

### Added

- Open any endowment draw-rate threshold count to inspect its complete ranked school list, including current-directory links, archived-school context, and small-endowment volatility markers.
- Read the same qualified interpretation disclaimer above the threshold table and inside every expanded list, with documented eligibility and cumulative-bucket semantics.

## [0.2.1.0] - 2026-08-03

### Changed

- Read the endowment draw-rate recipe in plainer language, with clearer descriptions of coverage, thresholds, school comparisons, and the federal accounting check.

## [0.2.0.0] - 2026-08-03

### Added

- Explore five years of private nonprofit college endowment draw rates at `/recipes/endowment-draw-rate`, including sector distributions, threshold shares, and selection-neutral school histories.
- Rebuild the versioned recipe dataset from public IPEDS Finance Part H facts with a read-only, paginated generator and documented source-release provenance.

### Changed

- Expand the recipes index and methodology documentation to cover reproducible federal-data analyses alongside CDS recipes.

### Fixed

- Calculate percentile and strict threshold statistics from exact values before display rounding, keep documentation tied to the generated dataset version, and display each institution under its latest reported identity.

## [0.1.0.0] - 2026-08-03

### Added

- Load and analyze IPEDS endowment values, gifts, investment returns, spending distributions, and other changes from official Finance releases.
- Request endowment facts from the per-school public API with the `finance` category.

### Changed

- Resolve Finance table names by fiscal year and preserve manifest-declared release provenance throughout downloads, analysis, and loads.
- Make release reruns revision-safe by rejecting downgrades and rollbacks, pruning stale rows and facts, and superseding older public facts.

### Fixed

- Route revised-final Finance data through the official Access database, reject zero-fact endowment runs, and prevent stale sibling artifacts from being loaded.
- Bound and stream Access archive downloads, and reject unsupported Finance comparison filters instead of returning unrelated default columns.
