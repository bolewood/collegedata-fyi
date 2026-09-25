# Changelog

All notable changes to this project will be documented in this file.

This project uses four-part semantic versioning.

## [Unreleased]

## [0.6.14.0] - 2026-09-25

### Added

- Harvard, Princeton, and Stanford now have a GPA page at
  `/schools/{id}/gpa` from CDS C11 (enrolled first-years who reported a
  GPA) and C12 (average, when printed). Yale left C11 blank. Dartmouth,
  Vanderbilt, Cornell, Duke, and Brown do not yet have three usable
  years.

## [0.6.13.0] - 2026-09-24

### Added

- Bowdoin, Rice, and Lafayette now have an early-decision page at
  `/schools/{id}/early-decision`. Dartmouth, Vanderbilt, and Cornell
  do not yet have three usable C21 years plus a school-written details
  note. Harvard, Princeton, Yale, and Stanford are REA/SCEA and are
  not on this list.

## [0.6.12.0] - 2026-09-24

### Added

- Five more schools now have an acceptance-rate page: Davidson,
  Skidmore, Boston College, Alabama, and Howard. Elon, CU Boulder, and
  Stony Brook did not yet have three usable years. Barnard's 2022-23
  extract doubles the printed count. Penn State's file is not
  University Park.

## [0.6.11.0] - 2026-09-24

### Added

- Six more schools now have an acceptance-rate page: Georgia Tech,
  Caltech, UChicago, Rutgers, Texas A&M, and Yale. UVA did not yet have
  three usable years. Tulane waits until the hub and the stat page
  name the same latest year.


## [0.6.10.0] - 2026-09-24

### Added

- Ten more schools now have an acceptance-rate page: Wisconsin–Madison,
  Florida, UCSB, Stanford, UCLA, UNC, USC, UT Austin, Wellesley, and
  Lafayette. WashU, UW, and Michigan did not yet have three usable years.


## [0.6.9.0] - 2026-09-24

### Added

- Acceptance-rate pages now show early decision beside the first-year
  rate when the school’s Common Data Set includes C21 counts: a second
  bar on the chart, a second line in the Rate cell, and a sentence in
  the lead. Years without those counts stay a dash. Early action is not
  shown — the CDS does not print EA applicant or admit counts.

## [0.6.8.0] - 2026-09-23

### Changed

- School pages use the name people search as the public URL. Virginia Tech
  is `/schools/virginia-tech`, Caltech is `/schools/caltech`, and Tulane is
  `/schools/tulane-university`. The legal federal names still work and
  redirect. Brand colors stay with the school.
- The twenty acceptance-rate pages are in the sitemap and can be indexed.

## [0.6.7.0] - 2026-09-23

### Added

- Twenty schools now have an acceptance-rate page with the school's own
  first-year counts by entering class, a chart when four or more years
  are available, and a link to each original file. The pages are not
  indexed yet.

### Changed

- School and year pages use the count printed in the Common Data Set
  when it is clearer than the projected row, and they hide a figure
  that does not match federal admissions data or belongs to a system
  office rather than a college.

## [0.6.6.1] - 2026-09-23

### Fixed

- School and year pages skip the waitlist sentence when the reported
  counts contradict each other (more admitted from the waitlist than
  offered a spot, or than accepted one). Two schools were showing one.

### Changed

- PRD 031 rev 2: stat pages now start with a measured history backfill
  (no pre-2024-25 numbers are in the tables a stat page would read), a
  canonical-slug freeze, and a single acceptance-rate pilot capped by an
  allowlist sitemap.

## [0.6.6.0] - 2026-09-23

### Fixed

- Virginia Tech 2025-26 and twelve other school years load again. Since
  2026-08-25 their old slugs redirected to a school page that didn't have
  those years, so they returned 404. School and year pages now include
  years that were archived under a school's other slug (Virginia Tech,
  Rutgers, Texas A&M, UVA, Georgia Tech).
- The sitemap and the Schools list only show URLs that load, list each
  school once, and carry last-modified dates.
- Lists built from the full archive no longer drop or repeat rows where
  a school's reports cross a page boundary. The sitemap was missing
  Louisiana Tech, Eastern Connecticut, and Susquehanna years, and the
  public `sources.jsonl` snapshot had six duplicate rows.

### Added

- School and year pages open with the school's own numbers in plain
  English: applicants, admits, acceptance rate, yield, test scores,
  early decision, waitlist, and a comparison with the year before.
  Search descriptions carry the same numbers, and year pages include
  both "2025-26" and "2025-2026".
- Every school page links all of its years, not just the latest three.
- Draft PRD 031 for per-school stat pages (acceptance rate, early
  decision, test scores, waitlist), for review.

## [0.6.5.0] - 2026-09-21

### Changed

- The Extract clock says Daily Cap Reached on a light green tile when
  the daily drain stops on purpose and files are still waiting. A missed
  run stays red, and a run that extracts nothing stays yellow.

## [0.6.4.0] - 2026-09-18

### Fixed

- Archive Oklahoma State University's Common Data Set PDFs from the
  IRA listing at ira.okstate.edu. Cloudflare was blocking the normal
  downloader; the daily Playwright job now crawls that page so new
  years keep landing.

## [0.6.3.0] - 2026-09-17

### Added

- Load Federal Student Aid institutional nonpayment rates as a Title IV
  companion (not a fourth named homepage source). School pages show a
  Nonpayment KPI with the FSA as-of date and an explicit "not the official
  cohort default rate" hint. The public view is `fsa_nonpayment_current`.

## [0.6.2.1] - 2026-09-14

### Fixed

- Keep archived Common Data Set files attached to the official school
  name and IPEDS UNITID, including 1990s filenames such as UF's
  `cds1997-98.pdf`. The public slug stays `uf`; the file no longer
  publishes as a nameless `unknown` year.

## [0.6.2.0] - 2026-09-12

### Added

- Show the last 14 days of extraction finishes (up to 50 files) on
  `/pipeline-observation`, backed by a private append-only run/item ledger
  so operators can see what drained without exposing document IDs, hashes,
  or raw worker errors.
- Keep University of Colorado Boulder on the headless-archive worklist with
  the public Data & Analytics listing as the crawl seed. IR confirmed the
  SharePoint folder is downloadable; the SharePoint host itself stays
  uncrawled.

## [0.6.1.1] - 2026-08-31

### Changed

- Exclude entering classes under 100 students from the College Pricing Power
  recipe (Panel A 1,744 → 1,417 schools; Panel B 1,557 → 1,386). In IPEDS
  filings from very small direct-matriculation institutions the admitted count
  often equals the enrolled count, which reads as 100% yield but reflects
  record-keeping rather than a market signal; the near-100% yield band drops
  from 80 schools to 2. Methodology copy, docs, and the XLSX starter now state
  the filter and its tally.

## [0.6.1.0] - 2026-08-31

### Changed

- Rebuild the Acceptance × Yield recipe as College Pricing Power: two IPEDS-backed
  scatter panels (acceptance vs. yield for 1,744 schools; yield vs. debt burden for
  1,557 schools with College Scorecard debt, earnings, and net price), a Syracuse
  University worked example motivated by fall 2026 reporting, quadrant reading
  guides, an adversarially reviewed methodology section, and a regenerated
  downloadable starter workbook.

### Added

- Reproducible pricing-power data pipeline (`tools/ipeds/build_pricing_power_recipe.py`)
  that emits the checked-in recipe dataset with build invariants for anchor schools,
  axis windows, panel counts, and rate granularity, plus regen-drift tests that pin
  the page's prose claims to the data.

### Added

- Keep Syracuse University's 2017-18 through 2021-22 Common Data Set files in the archive after the school took the live PDFs down, using complete Archive.org snapshots.

### Changed

- Fetch Wayback Machine CDS links as the original file instead of the HTML toolbar page, and refuse truncated Archive.org PDFs that look complete but have no trailer.

## [0.6.0.2] - 2026-08-30

### Added

- Keep an operator 100-school coverage cohort current by scoring listing seeds and archived source bytes each night, then fetching JavaScript, Cloudflare, and Drive gaps with hosted Chromium.
- Fetch NYU Common Data Set files from the house Mac only when that school is on a sticky residential allowlist, with a hard five-school cap and no secrets on the Mac.

### Changed

- Point Notre Dame and Williams discovery seeds at HTML listings instead of a single old PDF, and run the residential job after the hosted archive so it can use the same morning's result.

## [0.6.0.1] - 2026-08-25

### Added

- Show Goshen College's official purple in its school glyph, backed by the college athletics communications palette.

## [0.6.0.0] - 2026-08-25

### Added

- Show researched brand colors for 204 more public schools, with source and confidence evidence for every reviewed school and explicit null results where no defensible digital value was found; see the [coverage-gap implementation record](docs/plans/brand-colors-coverage-gap-plan.md).
- Theme school records with a two-plate riso ink pair derived from each school's brand hexes, seeded for the 19 brief schools that exist in the Scorecard directory, and keep house forest/ochre when no usable colour is on file.
- Show a two-dot school glyph beside school names in search, directory, coverage, browse, match, breadcrumbs, and the latest-drain feed, using grey plus a hollow B when colours are not on file.
- Show a data-generated Common Data Set archive lead on school hubs and year pages, including an official IR link when we have a usable HTML URL, and gated-request copy only for schools we have actually read (Virginia Tech).
- Publish three source-literacy pages under `/about` (Common Data Set, College Scorecard, IPEDS) and link them from About, the footer, and `/llms.txt`.
- Record the August 2026 Search Console CDS-query export next to PRD 028, including URL inspection of the Virginia Tech and Harvey Mudd canaries.
- Record school-direct Common Data Set insert and refresh events in an append-only log, expose a per-school RSS feed of those events, show which freshness signal a school or year page is using, and daily-probe the top 50 schools by public C1 applicant volume once they are nine months past that file date.
- Run the CDS URL finder monthly via GitHub Actions against the Brave Search API, re-probe stale one-file PDF seeds, flag that coverage class on a GitHub issue, and open a seed-update PR.

### Changed

- Replace the About page’s three-paragraph source gloss with a short hub that points at the longer CDS, Scorecard, and IPEDS notes.
- Add R (`httr2`) copy-paste examples on `/api` and the acceptance-vs-yield recipe, and round recipe-page percents to whole numbers except below 10% and for endowment draw rates.

### Fixed

- Resolve school glyph colors through reviewed aliases while preserving direct school identities and refusing incomplete or ambiguous crosswalk matches.
- Rank Jump-to-school exact slugs and nicknames (MIT, Penn) ahead of accidental name substrings, and prefer schools that already have a CDS year.
- Ignore sentinel CDS years such as `unknown` when choosing a school's latest coverage year, so search no longer labels a current extract (Michigan 2025-26) as "Older CDS available".
- Point Oklahoma's archive seed at the IRR listing (`/irr/other-reports`) instead of a single 2023-24 DAM PDF, and prefer Brave HTML listings over year-specific PDFs so sibling years are not frozen out.
- Stop copying Ohio University's main-campus CDS URL onto the five regional UNITIDs that share ohio.edu.
- Mark coverage `cds_available_stale` when the latest extracted year is older than the finder freshness floor, even if weekly archive re-verified the same file.
- Point Ohio University's main-campus seed at the IEA university-data listing instead of a 404 `/instres` PDF.
- Keep monthly finder seed PRs based on current `main` and artifact `schools.yaml`, so a mid-run workflow edit cannot reject the push and eat a 2h45m Brave run.
- Restore finder checkpoint saves (`_save_yaml`) that the pipeline-board heartbeat patch accidentally deleted.
- Let landing-hint promotion read `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` from the Actions environment instead of requiring a `.env` file on the runner.
- Recover 216 listing/seed replacements from the 2026-08-21 Brave run logs (the seed PR never left the runner) and skip search-junk URLs so news pages and non-CDS PDFs do not become seeds.
- Publish finder seed PRs even when a later probe step fails, keep a mid-run listing fix on `main` when the probe only stamped `probe_state`, and auto-enqueue changed seeds on merge after a `school_ids` canary so a rolled-back filter cannot re-queue the corpus.

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
