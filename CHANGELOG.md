# Changelog

All notable changes to this project will be documented in this file.

This project uses four-part semantic versioning.

History before 0.1.0.0 (2026-08-03), including the June and July 2026 work, is not summarized here; it is in git (`git log`) and the merged pull requests.

## [Unreleased]

### Added

- **Daily renewal alarm** (`Ops discovery renewal`, 13:41 UTC; #460).
  - **What it checks:** of the schools with last year's Common Data Set on file, how many also have this year's. A two-year check also keeps in view schools that already missed a year, and a next-year check runs from March.
  - **Floor:** each number is compared with a floor read off how fast schools usually post, scaled by how much of a year's schools mature renewal reaches (the median of the last five mature year-pairs, measured on every run). The unscaled curve counts only schools that post, so a fully caught-up year sat under it and a healthy year would have opened an issue every month (#508).
  - **Below the floor:** it opens one issue per CDS year, assigned to the owner, and posts to Discord #alerts. It updates the issue without commenting, replaces it with a new issue every 30 days (or at once on a 5-point worsening) while still below, closes it when that year recovers, and retires years that are two cycles old.
  - **A standing alarm doesn't go quiet:** while a year stays below its floor, it is superseded by a new assigned issue every 30 days, and at once when the gap widens by 5 points.
  - **Arrivals check:** a separate per-year check opens its own issue when almost nothing new arrived for a CDS year, judged every day over both 30 and 60 days, against how fast schools usually post. That catches most total stops within about a month; a stop starting in late November can take up to about six weeks (#506).
  - **Fails loudly:** a short or empty read, too few schools in the denominator, or a floor that disagrees with the database fails the job; it never reports zero.
  - **First run:** on 2026-11-25 renewal was 373 of 498 (75%). Against the unscaled floor of 82.5% a manual run opened #507, before the scaled floor (about 71–73%, depending on the measured ratio) merged; the first scheduled run is on 2026-11-25 at 13:41 UTC.
- **Watching the alarm:**
  - The hourly Discord poll alerts when the renewal workflow hasn't run on schedule for 36 hours.
  - A run that fails day after day says so, and posts every seventh day.
  - An optional outside check-in (`RENEWAL_DEADMAN_URL`) catches GitHub pausing scheduled workflows.
- **Pipeline board:**
  - A new first tile, Renewal. It goes red below a floor, on a missed daily run, while an earlier year's alarm is still open, or when almost nothing new arrived, naming the year. Its registry row and a 400-day history of finished runs (`pipeline_heartbeat_history`) came with migration #469, applied to production on 2026-11-25.
  - The Stuck PDFs tile reflects its result: red at 90% or more still stuck, amber above 50%.
- **The renewal report and the board now also count:**
  - schools with two live documents in one filed year, classified (#467);
  - seeds that haven't produced a new year this cycle (#462);
  - schools whose listing is known but whose current-year file couldn't be fetched, by cause (#468).
- **A monthly hand check:** on the 3rd, an issue lists 20 random schools with links, to record whether each has posted a newer CDS than ours, or whether our newest file isn't a full CDS. The next month's issue reports the miss rate (#461).
- **`/data-quality`**, behind a launch gate (PRD 040 M1). The scoreboard's run files were made `run_format: 2` (superseded by `run_format: 3`, below), and `--public` writes the page's snapshot (M0).
- **`/coverage`** gains a renewal tile (live since the first snapshot was committed, #524), the share of undergraduates with CDS numbers, search, a "Has a CDS" preset and the latest-year columns (M2). CSV downloads wait for the launch gate.
- **Data quality page and snapshot (PRD 040), run of 2026-11-25.** The `/data-quality` page, its CSV downloads and the `/coverage` CSV downloads (with the notes beside them) are behind the launch gate and are not public yet. Public on `/coverage`: the renewal tile (#524); two small text fixes (#517); the tile's new label and note (#542); the tiles' alignment, the on-file note moved under the tiles and a zero-count sentence hidden (#544); the corrected on-file note (#546); and dates and numbers that no longer depend on the browser's language or time zone (#547). Also public: numbers on the school browser and the endowment draw-rate recipe are always written in US format (#547).
  - **First snapshot (#524):** the first Data quality snapshot (the 2026-11-25 14:09 UTC run) is committed. The `/coverage` renewal tile now shows 373 of 498 schools (75%).
  - **Copy and hand checks (#517):** hand-check results for 2023-24 financial aid and for differing admissions values, a note on files that disagree with themselves, a license line beside the CSV downloads, and plainer wording throughout, all behind the gate. Public on `/coverage`: empty table cells now use an en dash, and the missing space after "Not checked yet" in the methodology paragraph is fixed.
  - **Snapshot checks and phone tables (#520):** a snapshot whose counts don't add up, or that carries years the page can't show yet, now fails the build. Tables on phones scroll in whole columns.
  - **CSV downloads (#512):** every file opens with its column names and has no comment lines. Data quality tables are served from their own links with the license in an HTTP `Link` header. The coverage file includes the school name, and a note beside its buttons (behind the gate) says which of its columns are federal figures.
  - **Size of federal differences (#528):** the admissions-against-federal table splits "Differs" into gaps of over 2% to 10% and over 10%, with a note on what the size can and can't say. The federal CSV has matching columns.
  - **Fields and usable answers by section (#530):** a table below the main completeness table (reports and fields stored, by format) shows, for each part of the CDS form, how many questions it has and how many fields and usable answers a typical report has, with a CSV download.
  - **Enrollment and tuition against federal figures (#532):** two more federal checks compare each report's total undergraduates and its tuition with the federal figures, with a note on what can differ and a CSV for each.
  - **Reports behind each count (#535):** each count in the tables is a button that lists the reports behind it, with a link to each school's page for that year.
  - **Trend across snapshots (#537):** an "Over time" section shows the page's main numbers for each snapshot of the archive, with a small line per measure once there are two snapshots. With one snapshot it shows that snapshot's numbers and says a trend appears with the second. Current-year renewal has its own small table.
  - **Launch fixes from the final review (#542):** a file filed under more than one federal record (Fairleigh Dickinson's two campuses, 2024-25) is left out of the federal comparisons, and a file a school holds twice in one year counts once (eight schools), so the published counts are now 430, 487 and 421 for 2023-24, 2024-25 and 2025-26. Notes are plainer and more specific: near misses, the match rate, financial aid, tuition years, the admissions rows by sex, section E for 2023-24, the IPEDS sources, and what "on file" counts for renewal. The snapshot format is now 5. Public on `/coverage`: the renewal tile is labelled with the year it counts ("2025-26 reports on file", not "This year's reports on file") and its note says what is counted: the earlier-year count takes any report we hold, including ones we set aside or couldn't read, and a school counts as renewed only if its current-year report is one we have not set aside.
  - **Final polish (#544):** on `/coverage` (public), the summary tiles now line up along their top edge, the definition of "on file" moved from the renewal tile to a short note under the tiles, and the "0 colleges have no enrollment figure" sentence is hidden when that count is zero. Behind the gate: table row labels wrap on phones instead of running over the numbers (the by-section table's section names), the note on fields stored per report says how the median is taken (the middle report by rank; for an even count, the lower of the two middle values, with no averaging), and the "Left out" sentences no longer end in a stray comma when a clause is left out.
  - **On-file note and year links (#546 to #548):** Public: on `/coverage`, the on-file note now says the earlier-year count leaves out filings made for a single campus or unit (#546), and the last-checked dates and counts in the table are written the same way in every browser, whatever its language or time zone (#547); on the school browser and the endowment draw-rate recipe, numbers are always written in US format (#547). Behind the gate: the year links on `/data-quality` no longer cause a page error that dropped the first click, a direct link to another year shows a "Loading" line until the page is ready, and a change of year is announced to screen readers (#547); the year buttons now work on phones, including while a list of reports is open (#548).
- **Extraction scoreboard (tooling).**
  - **Run format 3 (#510):** keeps, per document, the federal figures beside ours (with the IPEDS year each came from), field-status counts by CDS section, raw B1 and G1 candidates against IPEDS (tuition against the following academic year), and the IPEDS id and file hash. Public output is unchanged.
  - **Earlier years (#514):** it can be run for years before 2023-24 (`--years`). Those years record status counts and fields stored but no sum checks and no IPEDS comparison; `--public` marks them (`sum_checks_unavailable`, `federal_left_out.not_compared`). The command that runs it against production is staged and has not been run.

### Fixed

- When a school's CDS page disappears, the archive now marks the newest dated
  year as gone, not an undated file that happened to sort first.
- The resolver now logs and reports how many subpage links it skipped past its
  25-page cap.
- **The monthly stuck-seed sweep:**
  - It now accounts for every school (flagged + fresh + skipped = total, with a reason per skip), and stops with an error if the numbers don't add up (#464).
  - It counts a school as fixed only when the new seed reaches a newer CDS year at or past the current one, or is a listing page whose newest year matches ours (#463).
  - It no longer posts to a standing issue each month.
- **The monthly finder probe:**
  - It no longer marks a school "not found" when its search never ran. A budget, 402 or 429 response, unreadable reply or timeout now means "not searched", with no 30-day cooldown.
  - A run in which nothing was searched fails.
  - It counts the schools cut by its caps.
- **The headless archive:**
  - It reports the years and schools it skipped.
  - It fails when nothing was attempted or nothing was committed.
  - It reads known years by canonical year.
- **Years:** the directory repair tool, the top-100 coverage check and the published-years readers take the year from the freshness floor or the canonical year, never a hardcoded or text-sorted value.
- **Renewal counting:** documents with any data-quality flag (today: the wrong file, a blank template or low coverage) don't count as a school having filed the current year, and sub-program files no longer hide a missing main-campus file.
- **Text spacing (#519):** words no longer run together, and a stray "&apos;" no longer shows, on several pages (for example the "aren't on the page yet" note on a school's report page, the API docs and the usage page).
- **Financial aid read by column (#533, cleaner 0.3.44):** the financial aid (H1) dollar amounts are read from the PDF text layer by column. It was built for 2023-24 reports, where an estimated 156 of the 224 reports that can't be checked today become checkable once their documents are re-read. The reader is not limited to that year: on the staged re-clean, 2024-25 and 2025-26 also change (10 and 1 "can't check" reports become "adds up"), and some wrong H1 values are corrected in all three years, including a row's amount in a neighboring row or column (for example Princeton, UT Dallas and UC Davis in 2024-25 and Vermont in 2025-26). The production re-clean is staged and has not been run, so served values change only when it is.

### Docs

- A prevention ledger for the stale-seeds postmortem, and the postmortem's action table with each action's status.
- PRD 040 records the M0 hand samples.
- `tools/ops/README.md` and `tools/finder/README.md` describe the renewal alarm, the monthly hand check and the seed-sweep tools; `docs/ARCHITECTURE.md` and `docs/ops-discord.md` describe the scaled floor.
- The finder now points 38 more schools whose newest archived CDS was 2022-23 or older at their CDS listing page (#465).

## [0.6.24.0] - 2026-11-18

Covers #317 to #346: the named scholarship directory grows to its planned size
and PRD 036 closes, and the site stops overloading its database each morning.

### Added

- The scholarship directory now lists 95 programs at 74 schools, up from 23 at
  20. 79 are verified against the school's own pages, or those of a foundation
  the school ties to the program, and 16 are published as conflicting because
  those pages disagree. Browse them at
  `/scholarships` or on each school's page (#321 to #326, #328, #329, #344).
- "Other info" on scholarship cards: a sourced fact that fits no structured
  field, such as "awarded for the fall semester only", shown as one sentence
  with a link to the school's page. In the record format it is
  `versions[].other_info`; in the API it is the `other_info` column of
  `scholarship_directory`; the CSV download gains an `other_info_json` column
  (#342, #343).
- A size floor: a program is listed only when its top tier is worth at least
  $10,000 a year (or $40,000 over four years), covers full tuition, or waives
  the out-of-state tuition differential (#317).
- The scholarship fetcher and monitor can fall back to a headless browser for
  school sites that refuse a plain HTTP client. It loads only the one public
  page and never passes a login, CAPTCHA or robots.txt block (#318, #319).
- `tools/ops/revalidate_pages.py` and a daily "Page refresh sweep" workflow
  (13:35 UTC) refresh the cached pages of schools whose data changed in the
  last 26 hours. Run `python tools/ops/revalidate_pages.py --all` after a
  federal data load or a school identity change (#336).
- University of Cincinnati and University of Minnesota Twin Cities are back in
  the discovery school list. Five more schools lost the same way are tracked in
  #345 (#344).
- PRD 039, a plan to make school pages cheaper to render. Work starts no
  earlier than 2026-11-24 (#339, #341).

### Changed

- Coverage follows the school's promise. Full tuition stated for a standard
  full-time credit load counts as full, and a full waiver of tuition itself
  counts as full tuition; "up to" before a dollar amount is still partial
  (#330, #332).
- Scholarship benefit lines say "Duration: Four years." where they said "For
  Four years." (#343).
- School pages are cached for 7 days, not 24 hours, and are refreshed when
  their data changes. A daily crawl had been making several hundred pages
  rebuild in the same minute. In the API gateway logs for the same window,
  the busiest minute was about 2,100 requests with 557 errors on 2026-11-16
  and about 540 requests with one error on 2026-11-18, the first morning after
  the change. One day is not proof (#336).
- The public API key is read-only at the grant level, and can no longer call
  the cache-refresh and other maintenance functions (#337).
- CI builds and smoke-tests the web app only when `web/` or the workflow
  changed (#338).

### Fixed

- Every published scholarship record was audited, first a sample of 20 and
  then the other 73. 38 records got a corrected version and three more lost a
  campus restriction the school's page does not state. Five more corrections
  followed from re-checking what the monitor flagged, among them SMU's
  admission deadline for President's Scholars, which is November 1. Published
  versions are never edited: each correction is a new version (#330, #331,
  #346).
- A school URL containing non-ASCII characters returned a 500. It now returns
  a 404 (#333, #335).
- Every build read about 700 documents at once for the sitemap, which timed
  out the database. It now reads three schools at a time (#334).
- The scholarship loader finished green without refreshing the site, because
  its refresh step used a `jq` function the runner lacks (#327).

### Known limits

- 10 of the 95 scholarship records have had an owner spot-check; the rest were
  drafted and reviewed by agents against the school's pages.
- The change monitor cannot read six script-rendered source pages (Duke's
  scholarship office, Clemson, UT Dallas McDermott, Morehead-Cain, Indiana
  Wells) and cannot reach Tulane's admission page or Prairie View's scholarship
  page. Those are checked by hand in the annual review.
- The monitor flags a record only when a change moves an amount, a date, a
  year or a selection word. A rewording that moves none of those is caught
  only by the annual review.
- With 7-day page caching, a change that the sweep does not see can take up to
  a week to appear: coverage wording that changes with no document change,
  and federal data loads or identity changes when `--all` is not run.
- Requests made straight to the data API are not rate-limited.

## [0.6.23.0] - 2026-11-14

Named scholarship directory (PRD 036), merged as #310 to #315.

### Added

- `/scholarships`: a directory of named merit scholarships, each linked to the
  school's own page and dated. Launches with 23 programs at 20 schools.
  Filters cover coverage, selection, National Merit status, separate
  application, deadline month and residency. School pages show a scholarship card when the school has a
  record; schools without one show nothing (#315).
- `/methodology/scholarships`: how records are made and checked, what each
  freshness label means, how to cite and reuse the data, and a correction
  issue template (#315).
- Public API view `scholarship_directory`: the newest publishable version of
  each program per school, with sources, evidence locators, a
  `freshness_status` and the cycle basis. Joint programs appear once per
  participating school. Documented on `/api` (#312, #315).
- Record format for programs under `data/scholarships/programs/`: one YAML
  file per program, a JSON Schema, a field guide, a CC BY-SA 4.0 licence with
  attribution text, and `tools/scholarships/validate.py`, which CI runs on
  every PR. Verified versions are immutable; a correction is a new version
  (#311).
- The first 23 records, drafted from official pages fetched on 2026-11-14 and
  checked field by field in a second pass. 19 are verified; 4 are published as
  conflicting because the school's own pages disagree (#313).
- Loader and downloads: `scholarships-load.yml` validates and loads records on
  merge to `main`, then revalidates the web pages. The full set is downloadable
  as `/data/scholarships-v1.json` and `/data/scholarships-v1.csv.zip`; a test
  fails when the committed snapshot is stale (#312, #315).
- Change monitor (`tools/scholarships/monitor.py`, `scholarships-monitor.yml`):
  re-fetches each program's source pages and flags a record for review only
  when a term it records has changed. Unreachable pages and stale-cycle signals
  open an issue without changing the record. Runbook:
  `docs/runbooks/scholarships-annual-review.md` (#314).
- `tools/common/polite_fetch.py`: a shared fetcher that obeys robots.txt and
  crawl delays, sends conditional requests, and reports login or CAPTCHA walls
  as their own result (#310).

### Known limits

- Texas A&M's pages return 404 to a plain fetch and were read in a headless
  browser. The monitor cannot reach them and reports them as unreachable.
- The 12 records corrected during checking did not get a second independent
  pass.
- Capped housing or meal allowances are recorded as partial coverage.

## [0.6.22.0] - 2026-11-14

Covers the 21 pull requests merged on 2026-11-13 and 2026-11-14 (#269 to #308)
that did not bump the version at the time.

### Added

- Share button on school pages, year pages, `/coverage` and `/match` (PRD 024
  M1). Desktop opens a popover with Copy link and, where supported, Share with
  device; phones open the native share sheet. `/match` adds Copy summary: fit
  bucket counts with no GPA, test scores or code. `/match` link previews use
  generic Open Graph text (#308).
- Corpus audit (`tools/data_quality/corpus_audit.py`): a read-only check for
  one file published under several schools, different schools with identical
  admissions counts, CDS applicants more than 1.5x away from the IPEDS count,
  and a file whose A1 names a different school. Explained findings live in
  `corpus_audit_accepted.yaml` with a reason each. `ops-corpus-audit.yml` runs
  it daily at 13:40 UTC and posts the findings issue on Mondays (#293, #299,
  #301).
- "Data audit" station on `/pipeline-observation`, fed by the audit's
  heartbeats. The lamp means the audit ran, not that the data is clean (#301).
- Campus notes. A branch campus whose main campus files a CDS that does not
  include it says so and links to the main campus; Fairleigh Dickinson's pages
  say its one CDS covers both campuses. The list is
  `web/src/lib/campus-filings.ts` (#295).
- Projection sanity rules (`tools/browser_backend/sanity_rules.py`). A value
  that cannot be true is published as `parse_error` with no number: Early
  Decision admitted above applicants, a graduating class size that is a
  calendar year or smaller than its borrowers, a full-time first-year count
  above all full-time undergraduates, and a per-student average award above
  $150,000 (#277, #291).
- `/api/schools/search?ipeds_id=<six digits>` looks a school up by IPEDS unit
  id; a malformed id returns `400 invalid_ipeds_id` (#289).
- `cds_documents.source_gone_at`, also on `cds_manifest`: the school's CDS page
  is gone. `removed_at` now means only that an operator hid the document
  (#273).
- `/api` explains that `field_id` numbers change between form years and that
  `canonical_field_id` or `canonical_metric` follows one question across
  years, lists the `value_status` values, points to admission factors on
  `school_browser_rows`, and separates the MIT-licensed code and dataset from
  the school-owned documents (#288).

### Changed

- A school taking its file down no longer removes our archived copy from the
  site: the archive re-check writes `source_gone_at`, not `removed_at`. 18
  documents from 17 schools hidden this way were restored (#273, #274).
- Coverage status ignores hidden documents. A school with no visible document
  no longer reads "CDS available" in search or on `/coverage` (#294, #297).
- `school_browser_rows.ed_applicants` and `ed_admitted` are null when the
  `ed_math_inconsistent` flag is set (#277).
- On `/match`, Share replaces "Copy code". Copying the link on desktop is now
  two clicks. `match_share_copied` still fires, alongside the new `share_*`
  events (#308).
- CI runs the Tier 2 suite only when its inputs change, and in parallel
  (#275).
- 77 documents hidden on 2026-11-14: 22 that belonged to another school or
  were not a CDS, and 55 main-campus or system-office copies on branch campus
  pages.
- Spoke-ops: operator note on when to use the residential runner; the
  registration-token request retries with backoff (#272).

### Fixed

- Match share codes (`code`) and search text (`q`) are dropped from the URLs
  sent to Vercel Analytics on every page. A code decodes back to GPA and test
  scores, and page views on `/match?code=...` were sending it (#308).
- Dollar and percent answers under the `Nearest $1` and `Nearest 1%` format
  hints are stored as numbers, with percents on one 0 to 1 scale. About 33,900
  values that were text with no number gain one; template text in those cells
  becomes `parse_error` (#290).
- Tier 4 no longer reads Early Decision counts from later sections or from
  written-out dates such as "12 months 15 days". Producer version 0.3.19
  (#286).
- The projection uses the sum of the reported components when a C1 total is
  smaller than one of them (#271).
- D5 transfer-credit labels follow the printed column headers: `TFER_RFS` is
  "Recommended of Some" and `TFER_ROS` is "Required of Some". The 2023-24 to
  2025-26 schemas are regenerated (#269).
- Finder: UW Tacoma, UW Bothell and Wright State no longer inherit another
  campus's files from a shared listing; WPI and Winona State seeds point at
  listing pages instead of a single old PDF (#287, #298).

## [0.6.21.0] - 2026-11-12

### Added

- Template overlay values are served (PRD 038 A15). The school page, the
  browser projection and `cds_selected_extraction_result` merge text-layer
  numbers and dropdowns, boxed checkboxes, and OCR numbers from vector-rendered
  pages onto a matching Tier 4 extraction. Checkboxes without a printed box,
  free text and OCR from raster pages are stored but not served.
- `school_browser_rows.overlay_producer_version` records the overlay version
  and served classes for merged rows; change intelligence compares it so an
  overlay-only difference between years is an extraction change.
- `OVERLAY_SERVE_CLASSES=none` turns the merge off for the web and the
  projection; `cds_overlay_serve_classes()` controls the SQL view.

### Changed

- An overlay value of zero never replaces a non-zero value from Tier 4.
- `/api` notes that `kind=cleaned` rows from `tier2_template_overlay` include
  unserved classes and that the selected-result view is the served data.

## [0.6.20.0] - 2026-11-12

### Added

- Template overlay extraction (PRD 038) for flattened prints of the official
  2024-25 and 2025-26 CDS templates. It matches each page against the blank
  template and reads every field at its known position: text-layer values,
  checkbox marks, and OCR for pages whose text is drawn as outlines. On the
  95-document cohort it emits a median of 432 text and checkbox values per
  document, against 282 fields from Tier 4.
- `tools/extraction_worker/overlay_entry.py`: a dry-run-by-default CLI that
  writes one `kind='cleaned'`, `producer='tier2_template_overlay'` artifact per
  document, with `--rehold` to re-decide the Tier 4 disagreement hold without
  re-extracting. `tools/tier2_extractor/shadow_report.py` reports per-class
  counts and disagreement with Tier 4.
- Overlay merge in the browser projection and the school-page query, and a
  pending (unapplied) SQL view in `supabase/pending/`. All three are off by
  default: with `OVERLAY_SERVE_CLASSES` unset no overlay value is served and
  output is identical to the previous release.
- Field maps and blank templates for 2024-25 and 2025-26 under `schemas/`.

### Changed

- Change intelligence classifies a difference in overlay version or served
  classes between two years as an extraction change, not a school-side change.
- Three audit scripts ignore a `+overlay.<version>` suffix when comparing
  producer versions.

## [0.6.19.16] - 2026-11-09

### Changed

- Sentry events, transactions, and breadcrumbs now have `code` (Match share
  codes) and `q` (search text) query values replaced with `[Filtered]` before
  sending.
- Privacy page now discloses Sentry error reports and sampled performance
  traces, per-request friendly-API usage rows (kept 400 days), and the TLS
  fingerprint used in the hashed client code.
- Snapshot copy and `/api/snapshots` no longer present dated URLs as frozen:
  they serve live data, usually regenerated within the hour. The manifest carries the generation
  date and a note, and the unavailable `collegedata.duckdb` link is gone.
- Methodology: class rank is C.10 (was C.11); C.1 supplies applicant, admit, and
  enrolled counts. The merit-profile page no longer hard-codes a school count.
- `/api` marks `GET /api/facts/{school_id}` deprecated, documents 308 canonical-slug redirects,
  400/404 errors, the 25-school compare cap, all six CLI subcommands, the
  directory, coverage, change-event, and FSA views, and the
  `canonical_field_id`, `equivalence_kind`, and `source_producer` columns.
- `openapi.json` (now 0.2.0) lists the deprecated `/api/facts/{school_id}`, error and redirect
  responses, and the `X-CollegeData-Client` header. `llms.txt` lists the missing
  endpoints and pages.

## [0.6.19.15] - 2026-11-09

### Changed

- School pages (hub, year, acceptance-rate, early-decision, gpa, layout, OG
  images) and school-scoped cached queries now revalidate every 24 h instead of
  hourly. Hourly regeneration let crawler sweeps of stale pages trigger hundreds
  of concurrent ISR re-renders that saturated PostgREST and tripped the 4 s
  query timeout (Sentry COLLEGEDATA-FYI-1A/1E/19). Cached school queries now
  carry a `school:<school_id>` tag in addition to `school-data`.

### Added

- `POST /api/revalidate` (bearer `REVALIDATE_SECRET`; 503 if unset) expires
  per-school tags and pages for `{"school_ids": [...]}` (max 100) or everything
  for `{"all": true}`.
- The extraction worker notifies it for schools whose data changed when
  `COLLEGEDATA_REVALIDATE_URL` and `REVALIDATE_SECRET` are set (best effort,
  never fails the run); `ops-extraction-worker.yml` passes both through.

## [0.6.19.14] - 2026-11-09

### Fixed

- Checked-in recipe datasets (`waitlist-recipe-data.ts`,
  `pricing-power-recipe-data.ts`, `alignment-gap-recipe-data.ts`, and
  `endowment-draw-rate-recipe-data.ts`) and the College Transitions mirror
  (`tools/mirrors/college_transitions/`) now use the searchable canonical slugs
  introduced in PR #187 (`caltech`, `georgia-tech`, `tulane-university`, `uw`,
  `rutgers`, `virginia-tech`, `texas-am`, `uchicago`, `uva`) instead of their
  308-redirecting federal alias slugs. Recipe generators
  (`tools/ipeds/build_pricing_power_recipe.py`,
  `tools/scorecard/build_alignment_gap_recipe.py`,
  `tools/ipeds/build_endowment_draw_rate_recipe.py`) and mirror catalog/ingest
  scripts resolve every school through shared helpers in
  `tools/finder/identity_guard.py` (`resolve_canonical_school_id`,
  `validated_canonical_alias_slug_map`, `canonicalize_school_url`).

### Added

- `tools/ops/duplicate_slug_audit.py` (read-only) audits active `cds_documents`
  against `institution_slug_crosswalk`, classifying any document filed under a
  non-canonical alias slug by whether the canonical `school_id` already has an
  active document for the same year and/or the same `source_sha256`, and exits
  non-zero when any are found.
- `web/src/lib/no-alias-school-links.test.ts` and
  `web/src/data/searchable-slug-aliases.json` fail Vitest and `identity_guard`
  if any `web/src` file links to `/schools/<alias-slug>` or emits an alias
  `schoolId` for the nine renamed schools.

## [0.6.19.13] - 2026-11-09

### Fixed

- Schools that republish a fillable AcroForm CDS PDF as a flattened copy no
  longer drop from exact Tier 2 extraction to Tier 4 Docling when the data is
  unchanged. Before routing a fieldless PDF, the extraction worker checks prior
  `cds_artifacts(kind='source')` rows for the document; when an earlier source
  is a fillable PDF with at least 50 filled fields and a page count within
  ±10%, it compares the fillable's numeric form values (4+ digits, normalizing
  `$` and commas) against the newest file's page text (`PdfPageTexts`):
  - `>= 90%` present (`flattened_reprint_same_data`): extracts with Tier 2 from
    the fillable source (Valparaiso 2025-26: 86/87 = 98.85% match, keeps 621
    Tier 2 fields instead of falling to 313 in Tier 4).
  - Substantial text layer (`>= 100` chars) and `<= 10%` present
    (`print_to_pdf_values_missing_from_text`): extracts with Tier 2 from the
    fillable source and marks the result for operator review via
    `notes.quality_warnings`, `extracted_needs_review`, and `review_docs` in
    the run summary (University of Miami 2025-26 "Microsoft: Print To PDF"
    reprint draws form values as vector paths: 2/204 = 0.98% in text, keeps
    758 Tier 2 fields instead of 137–156 in Tier 4).
  - Meaningful disagreement between 10% and 90% (`edition_values_changed`):
    keeps the new flattened file so revised editions are not overwritten by
    stale fillable values (Barnard 2025-26: 79/97 = 81.44% match).
  - Every evaluated decision is recorded in `notes.source_selection` on the
    canonical artifact (`chosen_sha256`, `candidate_sha256`, `latest_sha256`,
    `match_ratio`, `matched_values`, `total_values`, `reason`, `needs_review`).

## [0.6.19.12] - 2026-11-09

### Fixed

- `/feedback` now submits `FormData` directly from the browser to Formspree
  (reading `NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT` with fallback to
  `NEXT_PUBLIC_FORMSPREE_ENDPOINT`), matching `SubmissionForm.tsx`. Removed the
  server-side `/api/feedback` route, database queue tests, and hourly
  `notify_feedback.py` cron workflow.

## [0.6.19.11] - 2026-11-09

### Fixed

- The archiver no longer lets a section file replace a complete CDS. A
  refresh now holds back (and logs `refresh_held_shrinking`) when the new
  PDF has under 40% of the pages of a current PDF that has 10 or more pages.
  Utah's discovery seed pointed at `CDS_2022-2023-D.pdf`, and refreshes
  swapped a complete 29-page 2022-23 CDS for 2-page Section A and D files,
  dropping that year from 552 to 26 fields. Held refreshes leave the
  document and its `source_url` untouched. Operator uploads through
  `archive-upload` still replace on purpose.
## [0.6.19.10] - 2026-11-09

### Fixed

- PDFs with a good text layer are no longer treated as scans when pypdf
  cannot parse their fonts. pypdf 6.2x and 7.0 raise "More than one
  /FontFile found" on some font descriptors. The format sniff caught that,
  counted zero text, labeled the file `pdf_scanned`, and the worker OCR'd
  every page instead of reading the text layer: Grinnell 2023-24 fell from
  411 to 122 fields, and the regression guard held it back. Page text now
  goes through `pdf_text.PdfPageTexts`, which keeps pypdf as the reader and
  falls back to pdfium for any page pypdf fails on. A sample neither library
  can read is "unknown", not "scanned". The same fallback covers the
  layout-text supplement (empty for these PDFs before), the visual-OCR page
  picker and year detection. Grinnell now extracts 382 fields without OCR.
- `pypdfium2==5.15.1` is now an explicit requirement (it was already in the
  lock via Docling) and is installed for CI's Python tests.
- Tier 4 producer version 0.3.18.
## [0.6.19.9] - 2026-11-09

### Added

- A test fails CI if anything loads fonts from Google again: a
  `next/font/google` import or a `fonts.googleapis.com` / `fonts.gstatic.com`
  reference in `web/src` or `next.config.ts`. `web/DESIGN_SYSTEM.md` and
  `web/AGENTS.md` now say fonts are self-hosted in `src/app/fonts/` and point
  to its README for adding a face.

## [0.6.19.8] - 2026-11-09

### Fixed

- Builds no longer fail when Google Fonts is slow or unreachable. The site's
  three typefaces (Newsreader, Geist, JetBrains Mono) were loaded with
  `next/font/google`, which downloads them on every build, and a failed
  download failed the whole Vercel build (`next/font/google ... Turbopack
  build failed`), several times recently. The variable-weight Latin files are
  now committed under `web/src/app/fonts/` with their SIL Open Font License
  texts and loaded with `next/font/local`, using the same CSS variables, so
  pages render the same and the build makes no font requests.
## [0.6.19.7] - 2026-11-08

### Fixed

- The extraction workflow's `requeue_document_ids` input now re-extracts in
  place, as #246 made the worker do. The workflow still flipped every listed
  document to `extraction_pending` up front, which hides their admissions
  figures on the site until each finishes, and it never passed
  `--requeue-document-ids` or `--force-reextract` to the worker. A document
  whose producer version and source had not changed would therefore be
  reconciled straight back to `extracted` without a new extraction. The
  workflow now passes both flags and leaves status alone.

## [0.6.19.6] - 2026-11-08

### Fixed

- The school-page merit profile no longer says "Academic merit aid checked"
  when a school only uses academics for need-based aid.
  `school_merit_profile.institutional_aid_academics` combined CDS H.1401
  (academics as a criterion for non-need aid) with H.1411 (academics for
  need-based aid). The view now also serves `merit_criteria_academics`
  (H.1401) and `need_criteria_academics` (H.1411), the card uses the
  non-need flag, and the methodology page describes H14 correctly. The old
  column keeps its meaning for API compatibility and is marked deprecated.
  2 of 518 schools change.
## [0.6.19.5] - 2026-11-08

### Fixed

- Tier 4 no longer drops whole tables from PDFs that print every filled-in
  value twice. Some flattened-form PDFs keep each typed value as page text
  and as a form appearance, so Docling read cells as "113 113" and the
  cleaner rejected them. When doubled numeric cells outnumber single ones
  across a document, each doubled cell is collapsed to one value before
  parsing. This restores B2, B4, C9, H and J tables for TCU 2022-23, RIT
  2025-26 and Houston Christian 2025-26, and puts RIT and HCU's C1
  residency rows back in the right columns. Only these three documents in
  the corpus have the pattern.
- 2025-26 C1 "total first-years enrolled" by sex (C.107-C.109) no longer
  takes the full-time count. The 2025-26 schema tags the full-time rows
  (C.110) with the same unit load as the totals, so the full-time count was
  landing in the total. When a file prints only full-time and part-time
  rows, the total is now their sum, as the compact-table path already did
  (Alabama: 3,344 rather than 3,318). A replay over all 532 current
  2024-26 Tier 4 documents changed only these fields outside the three
  doubled-text files, and every change was a correction.
- Tier 4 producer version 0.3.17.

## [0.6.19.4] - 2026-11-08

### Fixed

- Re-extracting documents no longer blanks their pages while the run works
  through the list. `--requeue-document-ids` used to flip every listed
  document to `extraction_pending` up front, and the site hides admissions
  figures for pending documents, so a 538-document re-extraction would have
  blanked 509 year pages for hours. Requeued documents are now selected by
  id whatever their status; each keeps its status and served data until its
  own re-extraction finishes, and a run stopped partway leaves the rest as
  they were.
- The pending-status repair pass only considers documents that are actually
  pending.
- The extraction pipeline doc now runs redrains with the locked worker venv
  instead of a separate `docling-eval` environment.

## [0.6.19.3] - 2026-11-08

### Fixed

- The extraction worker now refuses to run on an environment that doesn't
  match its lock. `tools/extraction_worker/requirements.lock` pins all 149
  packages (Docling, torch, EasyOCR, pypdf, parsers and their dependencies)
  for Python 3.12, and `.python-version` pins the interpreter. The worker
  checks both at startup and exits on drift unless given
  `--allow-dependency-drift`. A stale local venv (Python 3.9, Docling 2.69.1)
  is what dropped Sacramento State 2023-24 from 274 to 108 fields.
- The daily extraction job installs from the lock and reads the Python
  version from `.python-version`.

### Changed

- The extraction worker README says to run large re-extractions in CI rather
  than on a laptop, since the same pins can still produce slightly different
  model output on macOS.

## [0.6.19.2] - 2026-11-07

### Fixed

- Tier 4 extraction now runs one known Docling build everywhere. The
  requirements said `docling>=2.0`, so the daily CI job pulled the newest
  release (2.148.0) while a local operator venv sat on 2.69.1; re-extracting
  Sacramento State 2023-24 locally dropped it from 274 to 108 fields.
  Docling and its three companion packages are now pinned exactly, and the
  Tier 4 producer version is 0.3.16.
- A Tier 4 re-extraction of the same source PDF that keeps under 60% of
  the previous artifact's fields (when it had 100 or more) is now held back
  and reported as `tier4_field_regression` instead of replacing the good
  artifact.

### Added

- Every Tier 4 artifact records the installed Docling package versions in
  `docling_config.package_versions`.

## [0.6.19.1] - 2026-11-07

### Fixed

- Full CDS documents are no longer hidden because one free-text answer
  ran long. When the H15 financial-aid policy answer ran into Sections I
  and J (up to ~44k characters), the document was marked low coverage even
  with 500-600 good fields, which hid Penn State and Pitt 2025-26 among
  others. That check now hides a document only below 300 fields.
- The H15 answer now stops where Section I begins even when the PDF breaks
  the heading apart (`INST RUCT IONAL FACULT Y`, `Section I:`, `FACU LTY`),
  and drops page footers and the COVID follow-up question. Of 140 polluted
  answers in production, 107 were all spill and become empty; 33 keep the
  school's real answer. Tier 4 producer version is now 0.3.15.

## [0.6.19.0] - 2026-11-07

### Fixed

- Schools that publish their CDS one section per file get the whole CDS,
  not Section A alone. Filenames like `Regent_CDS_A_2012-2013.pdf`,
  `Regent CDS_2015-2016_A.pdf`, and William & Mary's
  `cds_2025-26_a1.pdf` were not recognized as section files, so the
  archive kept one section and called it the year's CDS. A lone
  letter-suffixed file with no sibling sections (Ferrum's
  `CDS_2020-2021F.pdf`) is still kept as the full document.
- Wiki "export this page" links (BookStack `/export/pdf`) are no longer
  archived as CDS files. Arkansas State's 2024-25 and 2025-26 entries were
  one-line PDFs of the wiki page. The resolver now follows the page's
  attachment links instead, which finds 17 years of Arkansas State CDS
  files.
- XLSX and fillable-PDF extractions now get the same low-coverage checks
  as flat PDFs, and the pending-extraction repair pass no longer clears
  those flags. A document drawn from a single CDS section without
  Section C is flagged low coverage. Section C alone stays visible.

### Added

- The monthly stuck-seed report also lists schools whose discovery seed
  is a single section PDF, so the finder looks for their real CDS page.
- `tools/extraction_worker/backfill_quality_flags.py` adds missing
  low-field and single-section flags to existing documents. It only
  adds flags, never clears them, and dry-runs by default.

## [0.6.18.5] - 2026-11-07

### Fixed

- The hourly coverage refresh runs again. Since 2026-10-30 every run had
  failed with "DELETE requires a WHERE clause": the non-blocking rebuild
  emptied the coverage table with a bare DELETE, which Supabase's
  safeupdate guard rejects when the call comes through the API. The
  coverage ledger stayed frozen at its 2026-10-30 snapshot. The DELETE
  now carries `where true`; nothing else changes.

## [0.6.18.4] - 2026-10-07

### Fixed

- The D2 transfer admissions table on 2024-25 year pages now reads the
  2024-25 layout's five cells per row (men, women, another gender, unknown,
  total). It read four, so from the second row on every cell came from the
  wrong row: "Admitted men" showed the applicant total. Tier 4 extracts that
  still store D2 in the 2025-26 numbering keep the old table.

### Added

- The official 2021-22 and 2022-23 CDS templates (fillable PDF and XLSX),
  recovered from the Internet Archive, are archived in `schemas/templates/`
  with source URLs, Wayback snapshots, and SHA-256 hashes. A synthesized
  canonical schema for those years was evaluated and not adopted: it matched
  IPEDS admissions counts less often than the current 2025-26 fallback.

## [0.6.18.3] - 2026-10-06

### Fixed

- Admissions headlines are corrected for 26 spreadsheet-sourced CDS
  documents, including Wabash College 2025-26 (issue #159). Their stored
  extractions predated the 0.2.3 XLSX extractor fix and still used the
  in-state row as the total. Wabash showed 911 applicants instead of 2,496,
  and Vanderbilt showed 2,885 instead of 48,196. The documents were
  re-extracted and their browser rows refreshed.
- The year page's field list now labels the C1 residency rows (in-state,
  out-of-state, nonresident, unknown) instead of repeating "Total
  first-time, first-year who applied" for each one, which made the in-state
  count read as a second total.

## [0.6.18.2] - 2026-10-05

### Added

- A `Deploy Edge Functions` GitHub workflow deploys every Supabase Edge
  Function after its tests and type-check pass, whenever function code lands
  on `main`. It can also be run by hand. Deployed functions had drifted up
  to two months behind `main`, which is how the section-package churn fixed
  in 0.6.18.1 went unnoticed.

## [0.6.18.1] - 2026-10-05

### Fixed

- The archiver no longer re-extracts multi-PDF (section package) CDS
  documents every night. A package now counts as unchanged when the school
  serves the same section files in the same order, even if the merged
  bundle's bytes differ. Previously, a stale `archive-process` deploy wrote
  build timestamps into every bundle, so documents like Samford 2024-25
  were refreshed, stored again, and re-queued for extraction on each run.

## [0.6.18.0] - 2026-10-04

### Changed

- Overhauled the Alignment Gap recipe (/recipes/alignment-gap) per PRD 034:
  sharpened narrative lede, demystified the metric, added base shelf for
  below-median burden schools to expand vertical resolution by 2.2x, smoothed
  the parity diagonal boundary, and synchronized cross-chart school selection.

### Added

- Interactive worked examples table with synchronized chart highlight and standardized
  6-column metrics across both merit-aid groups.

## [0.6.17.1] - 2026-10-03

### Changed

- Launched the public usage page at `/usage`: it is now indexed and linked
  from the footer, sitemap, `/api`, and `/about`. Launched ahead of the
  planned November 1 date, leading with September 2026.

### Fixed

- The usage publish step now works in 7-day batches so each call stays under
  the database's 8-second statement timeout.

## [0.6.17.0] - 2026-10-02

### Added

- Public usage page at `/usage` and open data at `/usage.json` (PRD 033 M1
  and M2). It shows daily unique downloads split into browser, machine, and
  bots and crawlers; downloads by kind; use of the open API by others; how
  demand is spread across schools, with a school lookup; our own serving
  load; and a worked example of how one request is counted. Every chart has
  a table alternative. Until November 1, 2026 the page is `noindex` and not
  linked from the site.
- A publish step in the API usage ingest workflow. It copies ready days and
  complete months into three public tables, `usage_public_daily`,
  `usage_public_school_months`, and `usage_public_months`, applying the
  privacy rules in Postgres: one number per school per month, rounded to the
  nearest 10, schools under 10 not listed (only counted in the monthly
  summary), no client names or per-client rows. A scan of everything
  published runs after each publish and opens an alert issue if any rule is
  broken, and days that stay unpublishable open their own alert.

### Security

- Revoked the anon and authenticated grants on `api_usage_events`. Row-level
  security already blocked reads; the table is written only with the service
  role.

## [0.6.16.0] - 2026-10-02

### Added

- Daily unique archive downloads (PRD 033 M0). The API usage ingest now
  counts, for each closed UTC day, one download per visitor per file per
  day, split into browser, machine, bots and crawlers, and our own
  pipeline. It is stored privately in `api_usage_downloads_daily`. Visitors
  are matched by IP address and user agent inside the log query; neither is
  stored. A new `daily` workflow mode recounts downloads without
  reprocessing the hourly tables.

### Changed

- AI clients are split into AI agents fetching for a person (ChatGPT-User,
  Claude-User) and AI crawlers (GPTBot, ClaudeBot). Crawlers from the
  COUNTER-Robots list that appear in our traffic without a "bot" name are
  now bots, and headless browsers, Google Apps Script, and a bare
  `Mozilla/5.0` no longer count as browsers.
- Every tool that reads public Storage or uses the anon key identifies
  itself as `collegedata-pipeline`, so its traffic is excluded from usage
  counts. A test enforces it.
- The privacy page describes the usage counting and its retention.

## [0.6.15.2] - 2026-10-01

### Changed

- The API usage ingest is scheduled twice an hour, and the operator health
  check now flags it after 8 hours without a run instead of 3. GitHub has
  been starting this repo's scheduled jobs hours late. The health check
  also reads more recent runs so the busier schedule doesn't push other
  workflows out of its 24-hour window.

## [0.6.15.1] - 2026-10-01

### Changed

- API usage capture now uses strict attribution from 2026-10-01 20:00 UTC,
  the first full hour after the site started tagging its own requests.
  Earlier hours keep the pre-tagging inference rules.

## [0.6.15.0] - 2026-10-01

### Added

- Hourly API usage capture for all gateway traffic (PRD 032): PostgREST,
  archive-file downloads, and Edge Functions, not just the friendly API.
  A GitHub Actions job reads Supabase gateway logs and writes private
  hourly aggregates by surface, route, and who sent the request (our
  pipeline, our site, the friendly API, unattributed browsers, or third
  parties). No IP addresses, full user agents, or query strings are
  stored; third-party clients get a hash that changes daily.
- The site and friendly API now identify themselves to Supabase with
  `X-Client-Info`, and pipeline tools send a `collegedata-pipeline`
  User-Agent. The API page asks bulk users to send a descriptive
  User-Agent.

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
