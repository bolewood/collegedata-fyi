# PRD 040: Archive status — coverage and data quality

**Status:** Draft rev 3 (2026-11-24). Not started.
**Author:** Anthony Showalter (with Claude)
**URLs (planned):** `https://www.collegedata.fyi/coverage` (existing, reworked) and `https://www.collegedata.fyi/data-quality` (new)
**Related:** [scoreboard script](../../tools/extraction-validator/scoreboard.py) (#432, #447, the data source), extraction scoreboard issue #431, [PRD 015](015-institution-directory-and-cds-coverage.md) (institution directory and coverage), [PRD 033](033-public-usage-page.md) (public usage page: the launch-gate pattern), [PRD 030](030-pipeline-observation.md) (pipeline board, which stays), [design system](../../web/DESIGN_SYSTEM.md), [voice](../../web/VOICE.md)

---

## What changed in rev 3

Rev 2 was reviewed by Codex for repo-completeness, against the code and the
2026-11-24 scoreboard JSON. Changes:

- **No privacy suppression.** The owner ruled that there's no privacy concern
  in identifying a school. Every input is a school's own public file, and the
  numbers read from it are already on that school's page. The folding rule,
  the subtraction test and the per-snapshot caveat are gone. Small groups are
  handled for a statistical reason instead (see "Small groups"). The two
  blockers Codex found in folding go with them.
- **One status classifier with a fixed order of precedence,** so a report
  counts in exactly one status. Rev 2's statuses overlapped for the five
  blank-form reports with no extraction.
- **Wording matches what the scoreboard measures.**
  - A "missing" admissions value is no longer called our fault. It means no
    usable value was available.
  - "Adds up" describes the scoreboard's real rule: a table passes when at
    least one of its sums is checked and none fails.
  - "Answers read" is renamed "fields stored", with its limits stated.
- **The question count is per form year** (1,053, 1,083, 1,105), not one
  canonical 1,105.
- **Corrected figures.**
  - 1,163 reports published with numbers, not 1,200.
  - 2025-26 has one report not read yet.
  - Coverage data refreshes hourly.
  - `latest_available_cds_year` is the latest year with numbers read.
  - `?all=1` shows all tracked schools.
- **The shared header carries no data,** so `/data-quality` doesn't need the
  coverage query.
- **One launch gate** covers the header tab, the nav, the footer, the
  sitemap and noindex, on the `/usage` pattern.
- **CSV licensing** keeps federal fields credited to their source.
- **A full test and doc inventory.**

## Problem

The archive publishes numbers read from 1,163 CDS reports across 2023-24 to
2025-26 so far (404, 487 and 272). The newest year is still filling in. The
reports come in six file formats and are read by several readers. A
researcher who wants to use them has four questions and no single place to
answer them:

1. **What do you have?** Which schools, which years, which formats.
2. **What are you probably missing?** Schools that publish a CDS we haven't
   found, years missing for schools we have, files we found but couldn't read.
3. **What do you have trouble reading?** By format, by table, by year.
4. **How far can I trust a number?** Checked against federal figures and
   against the report's own totals.

`/coverage` answers part of 1 and 2, school by school. Nothing public answers
3 or 4. The only measure of reading quality is the scoreboard script's
Markdown, which lives in `scratch/` on one Mac.

An open archive should publish its own error rates. The scoreboard already
computes them.

## Archive status: one header, two tabs

```
Archive status
[ Coverage by school ]  [ Data quality ]
```

- Both `/coverage` and `/data-quality` render a shared
  `<ArchiveStatusHeader active="coverage" | "quality" />` above their own
  content.
  - The tabs are links, not client state.
  - The header is navigation only and carries no counts.
  - Each route shows its own population figures in its own lede: coverage
    from its rows, data quality from its snapshot.
- They stay separate routes because their data differs. Coverage is a live
  query over about 2,900 school rows. Data quality is a reviewed snapshot
  built at deploy time. Neither page loads the other's data.
- Tab names: **Coverage by school** and **Data quality** (owner,
  2026-11-24).
  - "Data quality" means the quality of what this archive publishes, not
    the quality of the school's own data. The lede says so in one sentence.
  - The URL is `/data-quality`.
  - Don't use "scorecard": the site already carries College Scorecard data.
- Nav: the existing "Coverage" item becomes "Archive status", points to
  `/coverage`, and is active on both routes. Today `Nav.tsx` matches only the
  `/coverage` prefix. The footer link is relabeled the same way.

`/pipeline-observation` stays outside this header. It answers "is the pipeline
running?", which is an operator question.

## Glossary: public words

This governs page copy, column heads, and the display labels in the JSON and
the CSVs.

| Internal term | Public word | Note |
|---|---|---|
| extracted, not flagged | **published** | On the site, with numbers read. Includes reports a guard is holding on an earlier reading. |
| flagged (`blank_template`, `low_coverage`, `wrong_file`) | **set aside**, with the reason | Reasons: *blank form*, *too little read*, *wrong file*. |
| failed | **couldn't read** | |
| `extraction_pending`, `discovered` | **not read yet** | The file is archived; its numbers aren't read. |
| fields | **fields stored** | See Table A for what it counts. |
| match / blank / different | **matches** / **no value** / **differs** | |
| pass / fail / nc | **adds up** / **doesn't add up** / **can't check** | |
| B1 / C1 / H1 | **Enrollment (B1)**, **Admissions (C1)**, **Financial aid (H1)** | The code stays in brackets for researchers. |
| schema version | **form year** | Shown only when it differs from the selected year. |
| other schema | **numbered by a different year's form** | |
| full schema / structural + overlay only | (no label) / **older form: tables mapped, not every question** | |
| generated_at | **Snapshot of** *November 24, 2026* | |
| `pdf_flat` | **standard PDF** | |
| `pdf_fillable` | **fillable PDF** | |
| `pdf_scanned` | **scanned PDF** | |
| `xlsx` | **spreadsheet** | |
| `html` | **web page** | |
| `docx` | **Word** | |
| `other`, `unknown`, none | **other or unknown format** | |
| UGDS | **Undergrads** | |
| Title-IV, undergrad-serving | **accept federal aid and enroll undergraduates** | Per `VOICE.md`. |
| In-scope total | **Colleges tracked** | |

**Format labels: one map.** All of them live in one shared map in
`web/src/lib/format-labels.ts`. Both tabs and `/pipeline-observation` use it.
The pipeline board's local `FORMAT_LABEL` (`XLSX`, `DOCX`, `HTML`) is
replaced, so the site uses one vocabulary.

## Tab 1: Coverage by school (`/coverage`, reworked)

The page keeps its live data and its filters. Except where marked, every item
uses fields already selected into the client rows by both query paths in
`web/src/lib/queries.ts`.

1. **Summary strip.**
   - **Colleges tracked**, and the status tiles.
   - **Share of undergraduates at tracked colleges with CDS numbers on file.**
     - Numerator: the summed `undergraduate_enrollment` of rows with a
       `latest_available_cds_year`.
     - Denominator: the summed enrollment of all tracked rows with a known
       enrollment.
     - The note gives the number of rows with no enrollment figure, which are
       left out of both sums.
     - Small colleges publish less often than large ones, so this weighted
       share is the honest headline next to the school count.
2. **Status wording.** Tiles (`LABEL_BY_STATUS` in `CoverageDashboard.tsx`)
   and row badges both use plain words. The badges render the
   server-provided `coverage_label`, so the wording changes in the coverage
   view or in a shared client map that replaces both. For example, "Latest
   extract failed" becomes "Latest report couldn't be read", and "Extract
   failed" becomes "Report couldn't be read".
3. **Latest year with numbers.** A column from `latest_available_cds_year`,
   which is the latest year with numbers read, not the latest file found. Also
   a breakdown: 2025-26, 2024-25, 2023-24, older, none. Showing the latest
   year *found* as well needs `latest_found_cds_year`, which the coverage view
   already has, added to both selects and to `InstitutionCoverage`. That is a
   small query change and is included.
4. **School search** by name or IPEDS ID, over the rows already in the
   browser.
5. **Presets.** The plain URL keeps its default of "missing only", which
   suits people looking for gaps to fill. Add a **"Has a CDS"** preset
   (`?status=cds_available_current,cds_available_stale`). The dashboard
  already accepts a comma-separated `status` list, so the preset is just a
  link. Links from the
   Data quality tab and `/methodology` go to that preset. `?all=1` stays
   and means "all tracked colleges".
6. **CSV download** of the current view or of all rows, with `ipeds_id`,
   `school_id`, state, undergrads, status, latest year with numbers, latest
   year found, and last checked. See "CSV licensing".
7. **Freshness copy.** The page can revalidate every 15 minutes, but the
   coverage table refreshes hourly (cron at minute 17, migration
   `20260612162500_relax_refresh_coverage_cron.sql`). The current page copy
   says "every 15 minutes" and is corrected.

Later, needing new data: formats per school, and years on file per school
with gap years. For example, a school with 2023-24 and 2025-26 on file but
2024-25 missing.

## Tab 2: Data quality (`/data-quality`, new)

### Page order

1. **Title and a two-sentence lede.** What the page measures, the snapshot
   date, and the populations ("1,163 reports published with numbers across
   three years").
2. **All years at a glance.** A compact table, one row per year, newest first:
   - published, set aside, couldn't read, not read yet;
   - the admissions match rate;
   - median fields stored;
   - the three "adds up" rates.

   The trend shows here. In the 2026-11-24 run, couldn't-read falls from 49 in
   2023-24 to 4 in 2025-26. The financial-aid table adds up in 36% of 2023-24
   reports and 85% of 2025-26 reports.
3. **Year picker** (2025-26 | 2024-25 | 2023-24), which controls everything
   below it.
4. **Notices for the year, only when they apply:**
   - "71 of the 404 published 2023-24 reports are numbered by a different
     year's form. Some question numbers in them point at a different question
     than the 2023-24 form's." All 71 are published, unflagged reports.
   - "No federal admissions figures for fall 2025 yet."
   - "Older form: tables mapped, not every question." Only for years without
     a full field schema. None in v1.
5. **Table A, Reports and fields stored,** by format.
6. **Table B, Admissions against federal figures,** by format.
7. **Table C, Do the printed totals add up?,** by format.
8. **How to read this.**
   - What may be our miss and what may be the school's.
   - Why tiny groups show no percentages.
   - How to report a wrong number from a school page.
   - Links to `/methodology`, the API and the Coverage tab's "Has a CDS"
     preset.

Each table has one sentence above it naming what it counts. The explanation of
its weak spots sits next to the table, not in step 8.

### Status classifier

Every document in the run's manifest for a year gets exactly one class,
taken in this order:

1. **Removed** (`removed_at` set): left out of the live count. Shown in the
   note.
2. **No file** (`extraction_status = not_applicable`, used for
   participation states with nothing to read): left out of the live count.
   Shown in the note if it's not zero.
3. **Set aside**: a hidden quality flag (`blank_template`, `low_coverage`,
   `wrong_file`), whatever the extraction status. The reason is kept.
4. **Couldn't read**: `failed`.
5. **Not read yet**: `extraction_pending` or `discovered`, or `extracted`
   with no usable extraction.
6. **Published**: `extracted`, with a served extraction. This includes
   reports a guard is holding on an earlier extraction. The earlier reading is
   still what the site serves, so it is published. The note gives the count
   held.

Live = set aside + couldn't read + not read yet + published.

Recomputed from the 2026-11-24 run (Codex, from the local JSON):

| Year | Published | Set aside | Couldn't read | Not read yet | Live | Removed | Manifest |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-24 | 404 | 21 | 49 | 0 | 474 | 18 | 492 |
| 2024-25 | 487 | 13 | 3 | 0 | 503 | 17 | 520 |
| 2025-26 | 272 | 3 | 4 | 1 | 280 | 19 | 299 |

The five blank-form reports with no extraction are set aside under step 3,
not counted as not read yet. Flags on failed or pending documents aren't
kept in today's run output, which is why the run needs to change (see "Data
path").

### Table A: Reports and fields stored

| Format | Published | Set aside | Couldn't read | Not read yet | Fields stored: median | Lowest 10% |
|---|---:|---:|---:|---:|---:|---:|

- The four statuses follow the classifier. A year's rows sum to its live
  count.
- Under the table, the year's set-aside reasons, the count held by a guard,
  and the removed and no-file counts.
- **Fields stored** is counted over published reports. It is the number of
  fields stored for the served extraction. That includes fields stored as a
  parse error or "not applicable", so it measures how much of the form we
  reached, not how many usable answers we have. The note says so. It also
  gives the year's form size for scale: 1,053 questions on the 2023-24 form,
  1,083 on 2024-25 and 1,105 on 2025-26. The 71 reports numbered by a
  different year's form have field numbers from that form, whose size
  differs from this year's.
- Later work, needing new data: a count of usable answers (by `value_status`),
  and a breakdown by CDS section (A to J).

### Table B: Admissions against federal figures

| Format | Reports checked | Values | Matches | No value | Differs | Match rate |
|---|---:|---:|---:|---:|---:|---:|

- Counts **values, up to three per report**: applicants, admits and enrolled
  first-year students (CDS C1), against IPEDS for the same fall.
  - A value is compared only when IPEDS has a positive figure for it.
  - The head says "values (up to 3 per report)". "Reports checked" sits next
    to it, so no one reads 978 matches as 978 schools.
  - Every report in the 2026-11-24 run contributes 0 or 3 values. The test
    allows fewer.
- **Matches** means within 2%.
- Population: published reports with at least one IPEDS figure to compare.
  - Left out, with counts in the note: reports filed for one campus or unit
    (IPEDS reports the whole institution), and reports whose school has no
    IPEDS admissions figures.
  - In the 2026-11-24 run those are 1 and 17 for 2023-24, and 1 and 19 for
    2024-25.
  - 2025-26 shows a dash, not zeros, and the notice above explains why.
- Copy next to the table:
  - **No value** means no usable CDS number was available to compare. The
    school may have left it blank. We may have missed it, read it under a
    different year's numbering, or set it aside because it failed a sanity
    check. On its own, this table can't say which.
  - **Differs isn't always ours.** Schools sometimes report different figures
    to IPEDS than in their CDS, for example from a different count date. A
    differing value may be our misreading or a real difference between the
    two filings.

### Table C: Do the printed totals add up?

| Format | Reports | Enrollment (B1) | Admissions (C1) | Financial aid (H1) |
|---|---:|---|---|---|

- Each check cell shows *adds up / doesn't add up / can't check*. The three
  are never averaged.
- Population: published reports.
- What each checks:
  - **Enrollment:** undergraduates by sex sum to the total, and undergraduate
    plus graduate sum to the grand total.
  - **Admissions:** applicants, admits and enrolled by sex sum to their totals.
  - **Financial aid:** grant and self-help totals, need-based and
    non-need-based, within $5. Rows we didn't read count as zero once at
    least one row is read.
- How a table is scored, stated on the page:
  - **Adds up** means at least one of the table's sums could be checked and
    none failed. Some of its other sums may not have been checkable.
  - **Doesn't add up** means at least one sum failed.
  - **Can't check** means no sum could be checked: the rows or the total a
    sum needs weren't read, or the printed total is zero beside non-zero rows.
- Copy next to the table:
  - **Doesn't add up isn't always ours.** Some printed totals don't add up in
    the school's own file.
  - **Can't check** can be a blank in the school's file, an unfilled
    automatic total, a miss on our side, or a different year's numbering.
    The 2023-24 financial-aid split comes from the M0 sample and is stated
    with its sample size.
- The numbers are unflattering in places. Publish them, with the explanation
  next to them.

### Small groups

There's no privacy rule. Rows name a format, and a reader may work out which
school a one-report row is. That's fine, because the file and its numbers are
public on the school's page.

The rule is statistical: **a row with fewer than 5 reports in a table shows
its counts but no percentage.** A note says a rate over so few reports isn't
meaningful. Every format appears, under its own label, in every year it
occurs. Year totals are always shown in full.

## Data path

Decided in the 2026-11-24 session (option A of three).

```
Mac: scoreboard.py run (throttled, never two at once)
  -> scratch/extraction-scoreboard/scoreboard-<ts>.json   (full, per document; stays local)
  -> scoreboard.py --public <that json>
  -> web/src/data/data-quality/<YYYY-MM-DD>.json          (aggregates, committed)
  -> PR with the --compare deltas, review, merge -> Vercel build -> /data-quality
```

### Changes to the run (M0)

The run JSON lacks what `--public` needs. The run writes a versioned
`run_format: 2` and adds:

- **`manifest`:** per document, `year`, `source_format`, `extraction_status`,
  `data_quality_flag` and `removed`, for every row the manifest returns. This
  replaces the `"<year> <status>"` counter, which loses format and flag.
- **`federal_left_out`:** the year's counts of single-campus reports and of
  reports with no IPEDS figures, among published reports. These can already
  be rebuilt from `documents[].sub_institutional` and the federal outcomes,
  but should be emitted.
- **`forms`:** per year, the expected form year, whether
  `schemas/cds_schema_<year>.json` exists, and its field count. These come
  from local schema files, read at run time.
- **`held`:** the count per year (already computed; keep it).

Format always comes from `source_format`, never from the reader. For
example, two 2023-24 spreadsheets were read by Tier 4.

### `--public`

- **Reads one run JSON and nothing else.** It doesn't query the database.
  It rejects a run without `run_format: 2` rather than inventing per-format
  zeros. The test runs it with network access blocked.
- **Writes only aggregates and labels.** It never writes per-document rows,
  reader versions, or anything from the local worker summaries. This is to
  keep the file small and stable, not for privacy. The fix-reach columns stay
  internal because they depend on files that exist only on the Mac.
- **Public JSON shape** (one file per snapshot; all counts are integers;
  rates are worked out in the page):

  ```json
  {
    "public_format": 1,
    "snapshot_of": "2026-11-24T12:25:03Z",
    "scoreboard_run": "scoreboard-20261124T122503Z.json",
    "years": [{
      "cds_year": "2023-24",
      "form": {"form_year": "2023-24", "full_field_schema": true, "questions": 1053},
      "federal_fall_loaded": true,
      "other_form_numbering": 71,
      "removed": 18,
      "no_file": 0,
      "held": 6,
      "set_aside_reasons": {"blank_form": 5, "too_little_read": 16, "wrong_file": 0},
      "federal_left_out": {"single_campus": 1, "no_federal_figures": 17},
      "rows": [{
        "format": "pdf_flat",
        "label": "standard PDF",
        "status": {"published": 0, "set_aside": 0, "couldnt_read": 0, "not_read_yet": 0},
        "fields_stored": {"median": 0, "p10": 0},
        "federal": {"reports": 0, "values": 0, "matches": 0, "no_value": 0, "differs": 0},
        "totals": {"reports": 0,
                   "B1": {"adds_up": 0, "doesnt": 0, "cant_check": 0},
                   "C1": {"adds_up": 0, "doesnt": 0, "cant_check": 0},
                   "H1": {"adds_up": 0, "doesnt": 0, "cant_check": 0}}
      }],
      "total": {"...": "same shape as a row"}
    }]
  }
  ```

  The row values are placeholders. The year-level values are from the
  2026-11-24 run.

### Tests (`tools/extraction-validator/test_scoreboard.py`)

- **Classifier,** on synthetic documents covering every
  `extraction_status`:
  - removed;
  - not_applicable;
  - flagged and failed;
  - flagged with no extraction;
  - extracted with no producer;
  - held;
  - published.
- **Shape:** no key outside the allow-list.
- **Sums, for every year:**
  - the rows' statuses sum to the year's live count;
  - live + removed + no file = the manifest count;
  - `federal.reports ≤ status.published`;
  - `matches + no_value + differs = values ≤ 3 × reports`;
  - each table's three outcomes sum to `totals.reports`, which equals
    `status.published`;
  - `total` equals the sum of the rows.
- **Agreement:** fields stored, Table B and Table C equal the run's own
  `aggregate()` output. Table A's statuses are checked by the classifier and
  manifest-sum tests instead. `aggregate()` counts flagged documents only
  among served ones, while the classifier also sets aside a flagged failed
  document.
- **Inputs:** `--public` refuses an old or incomplete run, and makes no
  network call.

### Snapshot selection

The page imports the file in `web/src/data/data-quality/` with the newest
`snapshot_of`.
- Two files with the same date fail the build.
- An empty directory fails the build.
- A file whose `public_format` the page doesn't know fails the build.

### Other rules

- **The page never computes live.** Each run reads large rows from a small
  production host, and back-to-back large reads have taken it down before.
- **Cadence:** after each weekly re-clean pass, in the same PR or one right
  after it.
- **History:** snapshots stay in the directory for the later trend line.

### Rejected

Rejected in session:
- **A Supabase snapshot table.** It puts a run live with no review step, and
  needs a migration and service-key writes from the Mac.
- **A public JSON download under `/snapshots/v1`, for now.** It creates a
  format contract before the shape settles. The page offers CSVs of its
  tables instead.

## CSV licensing

Two browser-built CSVs: coverage rows (M2) and the Data quality tables
(M2).

- **Notice.** A client download can't send the `Link` license header that the
  existing CSV routes use (`DATA_LICENSE_LINK_HEADER`). Each file opens with a
  short comment block instead, built from the constants in
  `web/src/lib/data-license.ts`:
  - **Coverage CSV:** credits federal fields (IPEDS ID, enrollment) to their
    federal source, which the data license excludes from its scope.
    Directory and status columns are licensed as the site's data.
  - **Data quality CSV:** names the snapshot date, the CDS year and the
    table, and is licensed as the site's data.
- **If a `#` comment line breaks a common reader,** switch to a route handler
  that sends the header. Decide this in M2 after trying Excel, pandas and R.

## Years

v1 ships 2023-24, 2024-25 and 2025-26, the years the scoreboard covers today.
Earlier years need many more document reads, done once, throttled and cached
by artifact id. Size the job in M0 from the manifest count. It is a separate
follow-up and doesn't block launch. Years before 2023-24 have only structural
and core-table overlay schemas, so they carry the "older form" notice, and no
admissions match where IPEDS figures are missing.

## Launch gate

One gate, `isDataQualityLaunched()`, on the `isUsageLaunched` pattern
(`web/src/lib/usage.ts`). Before the launch date:

- `/data-quality` has `robots: noindex` and canonical metadata.
- The Data quality tab is left out of the header on `/coverage`.
- Nav and footer keep "Coverage".
- `/methodology` doesn't link to the new page.
- The sitemap leaves it out.

After the date, all of these flip together in one build. Gate tests cover
both states. M2's improvements to `/coverage` don't depend on the gate.

## Milestones

- **M0, measure and script.**
  - Sample 20 of the 215 2023-24 financial-aid "can't check" reports against
    their source files. Record each cause (blank in the school's file,
    unfilled automatic total, our miss, different year's numbering) in this
    PRD. If most are our misses, open a fix issue and decide whether it lands
    before launch.
  - Run changes (`run_format: 2`), `--public`, the tests, and a first
    committed snapshot.
  - Size the earlier-years job.
- **M1, Data quality tab.** `/data-quality` with the page order above, the
  shared format-label map, and `ArchiveStatusHeader`, all behind the gate.
- **M2, Coverage tab.** In order:
  - the header (gated tab);
  - the summary strip with the weighted share;
  - status wording;
  - latest year with numbers, and latest year found;
  - search;
  - the "Has a CDS" preset;
  - both CSVs;
  - the freshness copy fix.
- **M3, launch.**
  - Copy reviewed against `VOICE.md` and the M0 sample.
  - Flip the gate.
  - Update `web/tests/smoke.spec.ts`, which pins the current "Archive
    coverage" heading, and the sitemap and license tests
    (`web/src/lib/sitemap-static.test.ts`, `data-license.test.ts`).
  - Add the route and the snapshot directory to `docs/ARCHITECTURE.md` and to
    the route inventory in `docs/frontend.md`.

UI tests across M1 and M2:
- year selection;
- the empty-federal year;
- under-5 rows with no percentage;
- default, preset and `?all=1` views;
- search;
- back and forward with filters;
- the weighted share with null enrollments;
- CSV contents.

## Later, needs new data

- **Usable answers,** and **fields by CDS section (A to J),** so a researcher
  can see that admissions are read far more completely than, say, faculty.
- **Size of federal differences:** 2 to 10% against over 10%. This separates
  a different count date from a misread column. The run has to keep the
  difference, not only the outcome.
- **More federal checks:** undergraduate enrollment (B1) against IPEDS fall
  enrollment, and tuition (G1) against IPEDS. Each needs a
  definition-alignment note.
- **Click a cell to list its reports,** with links to each school's page.
  There's no privacy bar. It needs per-report rows in the public snapshot.
- **Earlier years,** a **trend line** across snapshots, and **per-school
  formats and gap years** on the Coverage tab.

## Success criteria

- The Data quality numbers equal the scoreboard run named on the page,
  checked by the tests.
- In every year, the format rows' statuses add up to the live count, and live
  plus removed plus no file equals the manifest count.
- No percentage is shown for a group of fewer than 5 reports.
- A researcher can get from either tab to the other in one click, and from
  Data quality to the list of colleges we have a CDS for in one click.
- A new snapshot reaches the site within one PR of a scoreboard run.

## Decisions (owner, 2026-11-24)

- **Tab name: "Data quality".** It reflects the quality of what we publish.
- **Floor of 5 reports** for showing a percentage.
- **One format vocabulary.** The pipeline board takes the shared labels, so
  "XLSX", "DOCX" and "HTML" become "spreadsheet", "Word" and "web page" there
  too.

## Open questions

None at rev 3. The M0 sample may raise copy questions for 2023-24 financial
aid.
