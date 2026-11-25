# PRD 040: Archive status — coverage and data quality

**Status:** Final draft rev 4 (2026-11-24), amended the same day for the [stale-seeds postmortem](../postmortems/2026-11-24-stale-discovery-seeds.md) (see [Amendment](#amendment-2026-11-24-current-year-renewal)). **Build status (2026-11-25):** M0 (#492, #510: `run_format` 3, `--public`, the `renewal` block, the near-miss split; hand samples #485; the first committed snapshot, #524), M1 (#487: `/data-quality`) and M2 (#487: `/coverage` rework) are merged. M3 is done except the owner's launch date: copy and sample results (#517), CSVs (#512), snapshot arithmetic checks, phone tables, the copy-deck drift test, docs and the success-criteria test map (the M3 PR). The flip PR (#529) sets `DATA_QUALITY_LAUNCH_DATE` to the owner's date, 2026-11-27 (00:00 UTC; one line in `web/src/lib/data-quality.ts`) and decides the gate once per build: `next.config.ts` evaluates the date when the build starts and inlines the result, so every surface (server pages, the sitemap, client components) reads one value. The first production build on or after the date launches everything together; a build before it stays closed, whatever the clock says later. Launch is the owner's call.
**Author:** Anthony Showalter (with Claude)
**URLs (planned):** `https://www.collegedata.fyi/coverage` (existing, reworked) and `https://www.collegedata.fyi/data-quality` (new)
**Related:** [scoreboard script](../../tools/extraction-validator/scoreboard.py) (#432, #447, the data source), extraction scoreboard issue #431, [PRD 015](015-institution-directory-and-cds-coverage.md) (institution directory and coverage), [PRD 033](033-public-usage-page.md) (public usage page: the launch-gate pattern), [PRD 030](030-pipeline-observation.md) (pipeline board, which stays), [design system](../../web/DESIGN_SYSTEM.md), [voice](../../web/VOICE.md)

---

## What changed in rev 4

Rev 3 was reviewed by Fable against `scoreboard.py`, a later run and the
database. Changes:

- **Near misses are split out in Table C.** About two thirds of failing
  enrollment and admissions sums are off by under 2% (356 of 538 in the 12:25
  UTC run). The typical case is a school leaving out a small cell. For
  example, Vassar prints 2,462 against 2,456 for men plus women, with
  "unknown" at 0. Enrollment and admissions now show *adds up*, *off by
  under 2%*, *off by more* and *can't check*.
- **Fields stored is two measures.** 2024-25 on counts rows in the published
  projection, which includes template-overlay values. 2023-24 counts one base
  extraction, because years before 2024-25 aren't projected
  (`MIN_YEAR_START = 2024`). The page says so, and fields stored leaves the
  all-years table.
- **The held count is out of the public file.** It comes only from the Mac's
  local worker summaries (`load_holds()`), which the public file must not
  depend on.
- **The figures are illustrative.**
  - Three 2023-24 documents are both failed and flagged as blank forms, so
    under the classifier 2023-24 reads 24 set aside and 46 couldn't read,
    not 21 and 49.
  - Today's re-clean pass also moved the published counts.
  - Every figure in this PRD is from the 12:25 UTC run of 2026-11-24, and M0
    regenerates them.
- **Problem question 2 is reworded** to what the archive can answer: where
  the gaps are. A count of schools known to publish but not on file is later
  work.

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

The archive publishes numbers read from about 1,160 CDS reports across
2023-24 to 2025-26 so far (404, 487 and 272 in the 12:25 UTC run of
2026-11-24; every figure in this PRD is from that run and is illustrative). The newest year is still filling in. The
reports come in six file formats and are read by several readers. A
researcher who wants to use them has four questions and no single place to
answer them:

1. **What do you have?** Which schools, which years, which formats.
2. **Where are the gaps?** These are the schools where:
   - we found a source but couldn't reach it automatically;
   - we checked and found no public CDS;
   - we haven't checked yet;
   - the latest CDS is old;
   - the report couldn't be read.
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
   - **{year} reports on file** (added by the amendment), first in the
     strip: current-year renewal, as defined in the
     [amendment](#amendment-2026-11-24-current-year-renewal). For example,
     "Of the 479 schools with a 2024-25 report on file, 364 also have a
     2025-26 report on file." It counts what we hold, not what schools have
     posted. The client rows can't compute it (they carry only the latest
     year with numbers), so it reads the committed Data quality snapshot's
     `renewal` block and names the snapshot's date. This is the strip's one
     exception to live data.
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
   `school_id`, `school_name`, state, undergrads, status, latest year with
   numbers, latest year found, and last checked. See "CSV licensing".
7. **Freshness copy.** The page can revalidate every 15 minutes, but the
   coverage table refreshes hourly (cron at minute 17, migration
   `20260612162500_relax_refresh_coverage_cron.sql`). The current page copy
   says "every 15 minutes" and is corrected.

The status tiles and the latest-year breakdown answer the Problem's
question 2: each kind of gap is one tile or one bucket. The page doesn't
claim to count schools that publish a CDS we haven't found.

Later, needing new data:

- **Known to publish, not on file.** Join the discovery seed lists to
  coverage.
- **Formats per school.**
- **Years on file per school,** with gap years. For example, a school with 2023-24 and 2025-26 on file but
2024-25 missing.

## Tab 2: Data quality (`/data-quality`, new)

### Page order

1. **Title and a two-sentence lede.** What the page measures, the snapshot
   date, and the populations ("1,163 reports published with numbers across
   three years").
2. **All years at a glance.** A compact table, one row per year, newest first:
   - published, set aside, couldn't read, not read yet;
   - the admissions match rate;
   - the three "adds up" rates.

   Fields stored is left out here, because 2023-24 is counted differently
   (see Table A). The trend shows here. In the 12:25 UTC run, couldn't-read
   falls from 46 in 2023-24 to 4 in 2025-26, under the classifier. The financial-aid table adds up in 36% of 2023-24
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
5. **Over time,** under the notices (built after the first tables; it follows
   the year picker): the page's main numbers by committed snapshot, and
   current-year renewal in its own small table (see History, below).
6. **Table A, Reports and fields stored,** by format.
7. **Table B, Admissions against federal figures,** by format.
8. **Table C, Do the printed totals add up?,** by format.
9. **How to read this.**
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
   still what the site serves, so it is published. The public page doesn't
   count holds, because the count comes only from the Mac's local worker
   summaries.

Live = set aside + couldn't read + not read yet + published.

Illustrative, from the 12:25 UTC run of 2026-11-24. The 2023-24 row includes
the three failed documents that are also flagged as blank forms (Fable, from
the database). M0 regenerates every figure.

| Year | Published | Set aside | Couldn't read | Not read yet | Live | Removed | Manifest |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023-24 | 404 | 24 | 46 | 0 | 474 | 18 | 492 |
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
- Under the table, the year's set-aside reasons and the removed and no-file
  counts.
- **Fields stored** is counted over published reports. It is the number of
  fields stored for the served extraction. That includes fields stored as a
  parse error or "not applicable", so it measures how much of the form we
  reached, not how many usable answers we have. The note says so. It also
  gives the year's form size for scale: 1,053 questions on the 2023-24 form,
  1,083 on 2024-25 and 1,105 on 2025-26. The 71 reports numbered by a
  different year's form have field numbers from that form, whose size
  differs from this year's.
- **2023-24 is counted differently.** For 2024-25 on, fields stored counts
  rows in the published projection, which includes template-overlay values.
  2023-24 isn't projected (`MIN_YEAR_START = 2024` in
  `project_browser_data.py`). Its count is the values in one base extraction,
  and it reads lower partly for that reason. The 2023-24 table carries that
  note, and the all-years table leaves fields stored out.
- **By section** (`public_format` 3): under Table A, one row per CDS section (A
  to J) for the year: questions on the form, median fields stored, median
  usable answers, and usable as a share of questions. Per year, not per
  format: per format and section would be 10 times the rows for a question a
  researcher asks of the whole year.
  - A **usable answer** is a stored field whose `value_status` is `reported`.
    Parse errors and empty cells are never usable. "Not applicable" is a school
    saying a question doesn't apply to it, so a reader has nothing to use and
    it is not counted. It is 0.6% of stored fields overall but 6% to 9% of
    section D's, so counting it would raise D's usable median (25 to 27 in
    2024-25); the deck says so.
  - Medians are over published reports numbered by the year's own form, so no
    median can exceed the section's question count. Reports numbered by
    another year's form (`other_form_numbering`) are left out and named in a
    note. The share is blank under 5 reports. The 2023-24 counting note
    applies.
  - The snapshot checks: the sections' questions add up to the form's;
    reports = published minus other numbering; 0 <= usable <= stored <=
    questions in every row. Medians do not sum, so no sum check applies.

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
- **Differs by size** (`public_format` 2): two more columns after "Differs",
  "Differs by over 2% to 10%" and "Differs by over 10%", counted by value.
  - The gap is the absolute difference as a share of the IPEDS figure, worked
    out from the run's `federal_values` with the same rule that decides
    "differs". Exactly 2% is a match. Exactly 10% is in the "over 2% to 10%" column.
  - Counts only, no percentages, so the under-5 rule has nothing to hide.
  - The note says a gap of over 2% to 10% may come from a different count
    date, and that a gap over 10% may be a real difference between the two
    filings, a scope mismatch, a misread column or our misreading; the size
    alone can't say which. It does not lean on the M0 sample: of that sample's
    15 differing values, 5 (in 3 reports) are over 10%, and of those 3
    reports 2 had the number we compared in the school's file and 1
    (Fairleigh Dickinson) was a university-wide file filed under two campus records, which the page now leaves out (`shared_file`).
- **Table B, more checks** (`public_format` 4): under Table B, two tables with
  Table B's columns minus "Values" (one value per report). Same classes (match
  within 2%, no value, differs split over 2% to 10% and over 10%), same
  population rule (a value counts only when IPEDS has a positive figure; one
  campus or unit left out).
  - **Enrollment:** our B1 "Total all undergraduates" against IPEDS `EFUG`
    (DRVEF, fall of the CDS year). Both count degree-seeking and
    non-degree-seeking, full-time and part-time undergraduates on a fall census
    date. Expected differences: the census date, and a school counting a
    different group. In the 2026-11-25 run 90% of the reports that have both a B1
    total and a federal figure are within 2% (the table's match rate, 74% and
    77%, also counts the reports with no usable B1 total).
  - **Tuition:** one figure per report, the all-undergraduates in-state figure
    (G.108) when filled, else the private single figure (G.102), a 0 counting
    as no value, against IPEDS `TUITION2` (in-state average tuition for
    full-time undergraduates, table COST1_<year> from IPEDS data year 2024 on
    and IC<year>_AY before, academic year starting the fall after the CDS year,
    because the form asks for the following year's price). Neither includes
    required fees (IPEDS FEE2, CDS G.111). Out-of-state (G.109/TUITION3) and
    first-year rows are not compared: one figure per report keeps a school that
    fills several rows from counting several times, and the first-year rows
    match the all-undergraduates rows closely. G.108 comes first because a public
    school that fills G.102 too has put another rate there (West Chester). Not aligned: per-credit or
    program-specific pricing, several rates, a different year.
  - Whether IPEDS figures are loaded is per check and per year: the CDS 2024-25
    and 2025-26 tuition (IPEDS 2025 and 2026) and 2025-26 enrollment (fall
    2025) are not loaded, so those cells are dashes with a notice.
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

- Enrollment and admissions cells show *adds up / off by under 2% / off by
  more / can't check*. Financial aid shows *adds up / doesn't add up / can't
  check*; it already allows $5. The three tables are never averaged.
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
  - **Off by under 2%** (enrollment, admissions) means at least one sum
    missed, but every miss was under 2% of its printed total.
  - **Off by more** (enrollment, admissions), or **doesn't add up**
    (financial aid), means at least one sum missed by more.
  - **Can't check** means no sum could be checked: the rows or the total a
    sum needs weren't read, or the printed total is zero beside non-zero rows.
- Copy next to the table:
  - **Off by under 2%** is usually the school's file. It mostly means a small
    cell left out of the rows, such as students of unknown sex, while the
    total includes it. In the 12:25 UTC run, about two thirds of failing
    enrollment and admissions sums were this kind.
  - **Off by more isn't always ours** either. Some printed totals don't add up
    in the school's own file. It is where our reading errors show, though, and
    the M0 sample checks some.
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
  but should be emitted. The run JSON does not carry `shared_file` (reports
  whose file is filed under more than one federal record, public format 5): it
  needs every school's hashes at once, so `prepare_run` computes it for the
  public snapshot.
- **`forms`:** per year, the expected form year, whether
  `schemas/cds_schema_<year>.json` exists, and its field count. These come
  from local schema files, read at run time.
- **Near misses:** the table checks record a failing sum's gap as a share of
  its printed total, so enrollment and admissions can be split at 2%.
  - This changes the scoreboard's own Table C metric. The run records
    `sum_check_version: 2`.
  - `--compare` notes the switch instead of reporting it as a change in
    quality.

Format always comes from `source_format`, never from the reader. For
example, two 2023-24 spreadsheets were read by Tier 4.

### `--public`

- **Reads one run JSON and nothing else.** It doesn't query the database.
  It rejects a run without `run_format: 3` (2 before the size of federal
  differences) rather than inventing per-format
  zeros. The test runs it with network access blocked.
- **Writes only aggregates and labels.** (Except the reports file, see "Click a cell
  to list its reports", which lists the reports behind each count and nothing else,
  and which reads the school list `tools/finder/schools.yaml` for display names as
  well as the run JSON: a file in the repo, not the database.) It never writes per-document rows,
  reader versions, or anything from the local worker summaries. This is to
  keep the file small and stable, not for privacy. The fix-reach columns stay
  internal because they depend on files that exist only on the Mac.
- **Public JSON shape** (one file per snapshot; all counts are integers;
  rates are worked out in the page):

  ```json
  {
    "public_format": 5,
    "snapshot_of": "2026-11-24T12:25:03Z",
    "scoreboard_run": "scoreboard-20261124T122503Z.json",
    "years": [{
      "cds_year": "2023-24",
      "form": {"form_year": "2023-24", "full_field_schema": true, "questions": 1053},
      "federal_fall_loaded": true,
      "other_form_numbering": 71,
      "removed": 18,
      "no_file": 0,
      "duplicate_file": 0,
      "set_aside_reasons": {"blank_form": 8, "too_little_read": 16, "wrong_file": 0},
      "federal_left_out": {"single_campus": 1, "shared_file": 0, "no_federal_figures": 17},
      "sections": {"reports": 0,
                   "rows": [{"section": "A", "questions": 0, "stored_median": 0, "usable_median": 0}]},
      "rows": [{
        "format": "pdf_flat",
        "label": "standard PDF",
        "status": {"published": 0, "set_aside": 0, "couldnt_read": 0, "not_read_yet": 0},
        "fields_stored": {"median": 0, "p10": 0},
        "federal": {"reports": 0, "values": 0, "matches": 0, "no_value": 0, "differs": 0,
                     "differs_2_to_10pct": 0, "differs_over_10pct": 0},
        "totals": {"reports": 0,
                   "B1": {"adds_up": 0, "under_2pct": 0, "off_more": 0, "cant_check": 0},
                   "C1": {"adds_up": 0, "under_2pct": 0, "off_more": 0, "cant_check": 0},
                   "H1": {"adds_up": 0, "doesnt": 0, "cant_check": 0}}
      }],
      "total": {"...": "same shape as a row"}
    }]
  }
  ```

  `public_format` 2 adds `differs_2_to_10pct` and `differs_over_10pct` under
  `federal`: each differing value's gap as a share of the federal figure,
  over 2% up to and including 10%, and over 10%. They add up to `differs` in
  every row and total, and `--public` refuses otherwise. Format 1 files have
  neither key, stay readable, and the page refuses either key on a format 1
  file. A run without `federal_values` (`run_format` 2) cannot make format 2,
  and `--public` refuses it instead of writing format 1: a snapshot quietly
  missing the split would look like one that has it.

  `public_format` 3 adds, per year, `"sections": {"reports": 0, "rows":
  [{"section": "A", "questions": 0, "stored_median": 0, "usable_median": 0}]}`
  (rows empty for a year whose form has no full field schema). Required on 3,
  refused on 1 and 2.

  `public_format` 4 adds `checks` to every row and total
  (`{"enrollment": C, "tuition": C}`, where `C` is `{reports, matches,
  no_value, differs, differs_2_to_10pct, differs_over_10pct}`, one value per
  report so `matches + no_value + differs = reports`) and `federal_checks` to
  every year (`{"enrollment": I, "tuition": I}`, where `I` is `{loaded,
  data_year, single_campus, no_federal_figures}`). Required on 4, refused on 1
  to 3.

  `public_format` 5 (the launch review) changes what is counted and adds three
  keys: `duplicate_file` per year, `federal_left_out.shared_file` and, in each
  `federal_checks` entry, `shared_file`. Required on 5, refused on 1 to 4, and
  read as 0 there. Two rules apply to every consumer (`prepare_run`):
  **(1) a file held twice by one school in one year counts once:** documents of
  one school and year with the same `source_sha256` are one report; the kept
  one is the published one, then the one read most recently (`newest_at`), then
  the lowest document id; the others and their manifest entries are dropped and
  counted in `duplicate_file`. A document with no hash is never grouped.
  **(2) one file under more than one federal record is left out of every
  federal comparison** (Table B, enrollment and tuition): a report whose
  `source_sha256` another school's report of the same year also holds, with a
  different IPEDS id on each, is `shared_file`. The left-out groups are
  disjoint, in the order single campus, shared file, no federal figures.

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
  - each table's outcomes sum to `totals.reports`, which equals
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
- **History:** snapshots stay in the directory and feed "Over time": the page
  reads every committed snapshot (each against its own `public_format`; two on
  one date still fail the build) and shows, for the selected year, reports
  published, reports we couldn't read, the admissions match rate, the three
  adds-up rates, one column per snapshot, oldest first, each labelled with its
  date and run name, with a small line per row from the second snapshot on,
  spaced by snapshot date; renewal (both over previous, as /coverage shows it)
  is archive-wide, not per year, so it has its own table with the school years
  each snapshot compares, and a new series starts where those years change.
  A line breaks at a missing value. Every value is that snapshot's own number. With one snapshot the page shows it as
  "first snapshot" and says a trend appears with the second; it draws no line
  or axis for one point. A series starts at the first snapshot that has it and
  the page says so. The table is the accessible form of every point.

### Rejected

Rejected in session:
- **A Supabase snapshot table.** It puts a run live with no review step, and
  needs a migration and service-key writes from the Mac.
- **A public JSON download under `/snapshots/v1`, for now.** It creates a
  format contract before the shape settles. The page offers CSVs of its
  tables instead.

## CSV licensing

Two CSVs: coverage rows (M2) and the Data quality tables (M2). Both have
the real header on row 1 and start with a UTF-8 BOM, like
`app/schools/[school_id]/[year]/cds.csv`. Neither has comment lines.

- **Decision trail.** The first design put a `#` comment block at the top of
  each browser-built file, because a client download can't send a header.
  D11 tested that file in pandas, R `read.csv` and `readr`, Python
  `csv.reader` and `DictReader`, and LibreOffice standing in for Excel
  (Excel was not run). No reader handled it with default options. pandas and
  `read.csv` raised errors. `readr`, `DictReader` and LibreOffice returned
  wrong tables (for `readr` and `DictReader`, the comment text as column
  names). `csv.reader` returned ragged rows. Only readers with a comment
  option recovered, and only if the user knew to pass it. The block was
  dropped.
- **Data quality** is served by a static route,
  `/data-quality/csv/[table]/[year]` (`reports`, `sections`, `federal`,
  `enrollment`, `tuition`, `totals`), built
  from the committed snapshot with the `Link: <license>; rel="license"`
  header (`DATA_LICENSE_LINK_HEADER`). The route sets
  `dynamicParams = false`, so an unknown table or year is a 404, and the gate
  closed means no pages are built, so every request is a 404. Launched with no
  snapshot committed, the build fails, as the page's does. The snapshot date,
  year and table name are in the filename, not in the file.
- **Coverage** stays a browser download. The dashboard saves the rows the
  table shows, filtered and sorted with the shared `coverageViewRows`, or all
  tracked colleges. No server route: a route would re-read the rows from the
  database for every filter and sort combination, and the file could differ
  from the screen. A browser download can't send the `Link` header, and a saved
  file wouldn't keep it, so this file carries no license marking. The file has
  a `school_name` column after `school_id`.
- **Credit.** Next to the coverage download buttons the page says that IPEDS
  ID, school name, state and undergraduate enrollment come from the federal
  College Scorecard and IPEDS, which our license doesn't cover; that the
  school ID, status, year and last-checked columns are licensed CC BY 4.0
  (linked); and what `latest_year_with_numbers` and `latest_year_found` mean.
  Column names are unchanged.

## Years

v1 ships 2023-24, 2024-25 and 2025-26, the years the scoreboard covers today.
Earlier years need many more document reads, done once, throttled and cached
by artifact id. Size the job in M0 from the manifest count. It is a separate
follow-up and doesn't block launch. Years before 2023-24 have only structural
and core-table overlay schemas, so they carry the "older form" notice, and no
admissions match where IPEDS figures are missing.

## Launch gate

One gate, `dataQualityLaunched()` (decided once per build), on the `isUsageLaunched` pattern
(`web/src/lib/usage.ts`). Before the launch date:

- `/data-quality` has `robots: noindex` and canonical metadata.
- The Data quality tab is left out of the header on `/coverage`.
- Nav and footer keep "Coverage".
- `/methodology` doesn't link to the new page.
- The sitemap leaves it out.

After the date, all of these flip together in the first build made on or after
it: the gate is decided once per build (`next.config.ts` inlines it as
`DATA_QUALITY_LAUNCHED`) and no surface reads the clock itself. Gate tests cover
both states through that same value. M2's improvements to `/coverage` don't depend on the gate.

## Milestones

- **M0, measure and script.**
  - Measure the near-miss split for enrollment and admissions from the run's
    `check_numbers`. No database reads are needed.
  - Sample 10 admissions "off by more" reports against their source files, to
    see how many are our reading errors.
  - Sample 20 of the 215 (217 in the 2026-11-25 runs) 2023-24 financial-aid "can't check" reports against
    their source files. Record each cause (blank in the school's file,
    unfilled automatic total, our miss, different year's numbering) in this
    PRD. If most are our misses, open a fix issue and decide whether it lands
    before launch.
  - Run changes (`run_format: 2`), `--public`, the tests, and a first
    committed snapshot.
  - Size the earlier-years job.
  - **Current-year renewal** (amendment). Add a `renewal` block to the run
    and to the public snapshot: the current CDS year (`cds_freshness_floor()`
    on the run date), the previous year, the number of schools with a live
    document filed under each (`canonical_year`), and the number with both.
    `unknown` is not a year. Every snapshot records it, so later snapshots
    give a curve by date.
- **M1, Data quality tab.** `/data-quality` with the page order above, the
  shared format-label map, and `ArchiveStatusHeader`, all behind the gate.
- **M2, Coverage tab.** In order:
  - the header (gated tab);
  - the "{year} reports on file" tile from the snapshot's `renewal`
    block;
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
- the renewal tile matches the snapshot's `renewal` block;
- CSV contents.

## Later, needs new data

- **Usable answers,** and **fields by CDS section (A to J):** built
  (`public_format` 3; see "By section" under Table A).
- **Size of federal differences:** built (`public_format` 2). Table B splits
  "Differs" into over 2% up to 10% and over 10%, as counts. It may separate
  a different count date from a misread column or a scope mismatch, but size
  alone does not say which. The hand check holds only 3 reports with a gap
  over 10%, too few to say how many large gaps are ours.
- **More federal checks:** built (`public_format` 4; see "Table B, more
  checks"): undergraduate enrollment (B1) against IPEDS fall undergraduate
  enrollment, and tuition (G1) against IPEDS in-state tuition, each with a
  definition-alignment note.
- **Click a cell to list its reports:** built. Every count above zero in
  Tables A, B, B2 and C is a button that opens the list of the reports it
  counts, each linked to the school's page for that year (`/schools/<id>/<year>`).
  There's no privacy bar. The rows are in a separate file written with the
  snapshot (`reports/<date>.json`, about 320 KB, 60 KB gzipped), so the aggregate
  snapshot stays small, and the page fetches it on the first click from a static
  route (`/data-quality/reports/<date>`, gated like the page), never in its own
  bundle. Rows hold only what a count needs: document id, school, format,
  status, the outcome in each table (no values), and `nopage` when the school's
  page for that year would not exist. The build fails if any
  count in the snapshot differs from the number of rows it lists. Federal
  counts count values, so a report can hold up to three: the list says so.
  A report whose school the run did not record, or whose school has no page for
  that year (only a blank template that year), is listed without a link.
- **Earlier years** and **per-school formats and gap years** on the Coverage
  tab. (The **trend across snapshots** is built: "Over time" on the page; see
  History under "Other rules".)

## Success criteria

- The Data quality numbers equal the scoreboard run named on the page,
  checked by the tests.
- In every year, the format rows' statuses add up to the live count, and live
  plus removed plus no file plus `duplicate_file` (the same file held twice by
  one school, dropped in `prepare_run`) equals the manifest count.
- No percentage is shown for a group of fewer than 5 reports.
- A researcher can get from either tab to the other in one click, and from
  Data quality to the list of colleges we have a CDS for in one click.
- A new snapshot reaches the site within one PR of a scoreboard run.
- The Coverage tab's first number is current-year renewal and equals the
  snapshot's `renewal.both` over `renewal.previous`, checked by a test.

## Decisions (owner, 2026-11-24)

- **Rev 4 is the final edit** before building. It takes Fable's five
  findings as recommended.

- **Tab name: "Data quality".** It reflects the quality of what we publish.
- **Floor of 5 reports** for showing a percentage.
- **One format vocabulary.** The pipeline board takes the shared labels, so
  "XLSX", "DOCX" and "HTML" become "spreadsheet", "Word" and "web page" there
  too.

## Amendment (2026-11-24): current-year renewal

The [stale-seeds postmortem](../postmortems/2026-11-24-stale-discovery-seeds.md)
found that the archive had stopped collecting new years for about 150
schools, and that no page or alarm showed it. The coverage page labeled each
school "Older CDS available" but never added the labels up.

This PRD is the public view of the archive's health, so it takes the
postmortem's headline number. "Freshness" already means refresh timing here
(Coverage item 7), so the number is called renewal:

> **Current-year renewal:** of the schools with a live document whose filed
> year (`canonical_year`) is the previous CDS year, the share that also have
> one for the current CDS year. The current CDS year is
> `cds_freshness_floor()` on the snapshot date. `unknown` years don't count.

The rule is asymmetric (`scoreboard.py` calls the alarm's `school_years`
twice). The previous-year count (`renewal.previous`) takes any live report for
that year except one filed for a single campus or unit (`school_years` in
`tools/ops/discovery_renewal.py` skips `sub_institutional` rows), including ones
we set aside (flagged) or couldn't read. The
renewed count (`renewal.both`, and `two_year_both`) excludes a school whose
current-year report is flagged (wrong file, blank template, low coverage): a
flagged report is not a renewal. A report we couldn't read still counts.
`renewal.current` (436 in the 2026-11-25 snapshot, after the 2023-24 financial aid re-clean) counts every school with a
current-year report, set-aside ones included, and is not shown on any page.
The page's wording says this ("on file" in the earlier-year count; a school
renews only if its current-year report is one we have not set aside).

On 2026-11-24 it was 236 of 476 (50%) in the morning and 364 of 479 (76%)
after the fixes.

- **Coverage tab:** the "{year} reports on file" tile, first in the
  summary strip, read from the snapshot.
- **M0:** a `renewal` block in the run and the public snapshot.
- **M2:** the tile and its test.
- **Success criteria:** one line for it.

The alarm itself is not part of this PRD. It is postmortem action 1 (#460):
a scheduled workflow that opens a new issue when renewal falls below a
monthly floor, because a page nobody is prompted to open doesn't warn anyone.

`discovered_at` can't give last year's curve, because the archive began in
April 2026 (348 of the 471 live 2024-25 documents were first seen that
month). The files' own production dates give an approximate one: of 2024-25
files with a usable date, 18% were produced by February 2025, 46% by April,
68% by June, 81% by August and 88% by November. #460 reads its floor off
that curve by months since the CDS year's fall (so 81% or more once the
current year switches in September) until a year of snapshots exists.

## Open questions

Five copy questions came out of the M0 samples; see "Copy questions for the owner" at the end of "M0 samples (2026-11-25)". None is decided.

## M0 samples (2026-11-25)

Two hand samples against the school's own files, taken from the saved run
`scoreboard-20261125T011508Z.json`. Selection: each population sorted by
`document_id`, then `random.Random(40).sample(...)`. Files came from the
public `sources` bucket (one manifest request and one file request per
document, 5 s apart; 30 of each). No `cds_artifacts` reads. Page numbers are
PDF page numbers, not the printed ones. No copy is decided here; the
questions that depend on the results are at the end.

### Sample 1: admissions "differs" (Table B), 10 reports

Population: published reports, not filed for one unit, with at least one of
the three admissions values marked "differs" against IPEDS. That is 140
reports, pooling 2023-24 and 2024-25 (2025-26 has no federal comparison).
"Off by more" in the brief was read as Table B's "Differs", which is a 2%
test per value. So this sample says nothing per year.

The unit is a report, not a value: a report can differ on one, two or three
metrics, listed in the "Differs on" column. I did not fetch the IPEDS figures
or check the join to the federal record (to stay inside the request budget).
The question answered is narrower: is the number we compared the number in the
school's file? Where it is, a CDS extraction error is ruled out for that
report. That is all. It does not show that the two filings differ, because the
federal side, the join and the scope (campus or whole institution) were not
checked.

| School | Year | What we read (applied / admitted / enrolled) | What the file says | Verdict | Evidence | Differs on | Document |
|---|---|---|---|---|---|---|---|
| Chatham University | 2023-24 | 3,611 / 2,923 / 332 | Same. Rows by sex sum to the same totals. | File matches our reading | p. 11 | applied | `d8993473-97fa-4589-870b-2356a7ff004e` |
| Southeast Missouri State University | 2024-25 | 11,262 / 7,767 / 1,381 | Same. The 2024-25 form has no printed total; the rows by sex sum to ours. | File matches our reading | p. 9 | applied | `f47fea08-1c6b-4b99-83dd-19341912ec38` |
| Virginia Commonwealth University | 2024-25 | 21,201 / 19,572 / 4,275 | The rows by sex sum to ours. The residency table in the same file prints 24,804 / 20,769 / 4,449 for the same cohort. | File matches our reading; the file disagrees with itself | p. 11 (by sex), p. 12 (residency totals) | enrolled | `12bd5c43-e83c-42e5-bf3f-e72a5f17111c` |
| Louisiana Tech University | 2024-25 | 8,242 / 7,478 / 2,453 | Same printed totals (workbook, sheet CDS-C, rows C117 to C119). The residency rows beside them do not add to them (in-state 7,062, out-of-state blank, nonresident 1,464). | File matches our reading | Sheet CDS-C, rows C101 to C131 | applied | `70e42e60-ac4f-4fb6-82c0-afab9863b447` |
| Arkansas State University | 2024-25 | 11,568 / 9,207 / 1,977 | Same. Rows by sex sum to ours. | File matches our reading | p. 13 | applied, admitted | `7c31617c-ef1b-4c4a-bc3b-d8c3458b0212` |
| Albion College | 2023-24 | 5,438 / 4,522 / 353 | Applied and admitted the same. Enrolled is 363: men 173, women 180, another gender 10. The run stored the total (363) but not the third row (10); `printed_admissions` prefers the rows by sex over the total, so it gave 353. | Our error (enrolled; the by-sex rows are preferred over the stored total, and the another-gender row was not read; related to #435, which covers another-gender cells not read from 2024-25 fillable PDFs) | p. 13 | enrolled | `564d6790-a3b8-4e3b-90c1-662d9eaa0278` |
| University of Northern Colorado | 2023-24 | 9,479 / 8,880 / 1,229 | Same. Rows by sex sum to ours. | File matches our reading | p. 11 | applied | `2ecd118f-d64d-43af-bb26-973e6c19b6fc` |
| Fairleigh Dickinson University, Metropolitan Campus | 2024-25 | 11,478 / 10,665 / 1,188 | Same. The file carries a residency total that is also the same. | File matches our reading. The file is university-wide, filed under two campus records (Florham and Metropolitan carry the same file; IPEDS reports the two campuses on their own at 5,652 and 5,826 applicants respectively), so neither record can be compared to it alone. We did not know this at the time of the sample; since the launch review the page leaves such files out (`shared_file`). The 2023-24 Metropolitan filing is the same kind of file but stays in Table B: Florham has no 2023-24 document, so the rule has no second record to see (#543). | p. 8 | applied, admitted, enrolled | `9ece97f5-8807-4579-8f33-234648ee1c95` |
| Texas A&M University-Commerce | 2023-24 | 8,856 / 6,865 / 1,294 | Rows by sex sum to ours. The residency table's printed "Total" column reads 1,282 / 992 / 48, which is the total with the in-state column left out. | File matches our reading; the school's printed totals are wrong | p. 7 | applied, admitted, enrolled | `7b54793e-2ad7-4fee-a95a-86371a65cad2` |
| University of Scranton | 2023-24 | 9,866 / 8,011 / 1,037 | Same. Rows by sex sum to ours. | File matches our reading | p. 19 | applied | `d1661d03-dc18-4cef-9249-7c84303f71bd` |

Totals, 10 reports:

| Result | Reports |
|---|---:|
| File matches our reading (CDS extraction error ruled out) | 8 |
| Our reading error (Albion) | 1 |
| Our scope or metadata gap (Fairleigh Dickinson, Metropolitan Campus: one university-wide file filed under two campus records; file matches our reading) | 1 |

So 2 of 10 are on our side (Albion's reading, Fairleigh Dickinson's scope), and
for the other 8 the sample rules out a CDS extraction error but does not
explain the difference. With so few, the plausible range for the share on our
side is roughly 6% to 51%. Three reports have conflicts inside the school's own
file, each different, and are described one by one under question 3. We take
the rows by sex when both men and women were read, else the printed total
(`printed_admissions`).

### Sample 2: 2023-24 financial aid "can't check" (Table C, H1), 20 reports

Population: published 2023-24 reports whose H1 result is "can't check". That
is 217 in this run (the PRD text says 215; the 2 extra are in the saved run,
not a different filter). Of the 217, 201 have no H1 dollar value stored at
all, and 16 have some.

Cause categories as defined in the milestone: blank in the school's file,
unfilled automatic total, our miss, different year's numbering. For each file
I read the H1 page and checked whether the dollar rows and the total rows
were filled. Two files (UT Tyler, Cal Poly) have no text on the H1 table, so
I rendered the page and read it as an image.

| School | Year | What we read | What the file says | Cause | Evidence | Document |
|---|---|---|---|---|---|---|
| Stanford University | 2023-24 | Nothing for H1 (164 fields in all; stored under the 2025-26 form) | Filled; total grants $247,998,976 need-based, $7,400,358 non-need-based; the form states 2022-2023 final figures | Our miss. The 2025-26 label may also play a part. | p. 30 | `83ff8a43-8291-4f57-822a-6a9b1c70a9e4` |
| UC Santa Barbara | 2023-24 | Nothing for H1 | Filled; total grants $250,339,948 / $16,299,808; total self-help $20,739,207 / $15,650,948 | Our miss | p. 23 | `b0f62a00-b542-4645-8167-a63fe90007a4` |
| New Mexico Institute of Mining and Technology | 2023-24 | Nothing for H1 | Cells empty. The page says "2023-2024 Financial Aid Data not available at this time"; the document is stamped "DRAFT - incomplete". | Blank in the school's file | p. 17 | `9c03102c-d57e-4ca6-ab8a-6f2a3c7a3b91` |
| Bucknell University | 2023-24 | Nothing for H1 | Filled; total grants $65,991,532 / $8,410,335; total self-help $8,681,074 / $6,866,527 | Our miss | p. 25 | `0ae27762-7353-44d9-9ff9-6f126d93a2e1` |
| University of Iowa | 2023-24 | Nothing for H1 | Filled; total grants $83,780,996 / $48,007,220; total self-help $63,628,162 / $64,291,063. The table runs across a page break. | Our miss | pp. 20 to 21 | `476f9765-d9f8-4fff-a284-4a5f5f54a581` |
| University of Wisconsin-Green Bay | 2023-24 | 4 of the H1 values (federal and state rows only) | Filled on two pages; total grants $61,867,041 / $13,994,769. The table is split between the pages. | Our miss (the second page's rows not read) | pp. 39 to 40 | `51a07dd2-ab50-4e05-b55c-f4ba48577ac1` |
| Virginia Commonwealth University | 2023-24 | Nothing for H1 | Filled; total grants $127,424,448 / $34,294,341; total self-help $2,082,634 / $0 | Our miss | p. 32 | `cf82d031-4076-4eb4-ae37-494ddb194a26` |
| Bentley University | 2023-24 | Nothing for H1 | Filled; total grants $71,079,573 / $29,286,995 | Our miss | p. 19 | `c955dda0-174a-47c7-9d5c-d71f1219ad69` |
| Tulane University | 2023-24 | Nothing for H1 | Filled; total grants $98,726,078 / $56,763,488; total self-help $14,906,734 / $18,193,003 | Our miss | p. 25 | `3cc47c6c-a829-41d3-b702-e71c4b4bbf7d` |
| College of Coastal Georgia | 2023-24 | Nothing for H1 | Filled; total grants $6,576,435 / $2,161,845; total self-help $5,617,884 / $635,520 | Our miss | p. 24 | `21802c5c-b095-450c-a3a8-201fe17220a2` |
| Xavier University | 2023-24 | Nothing for H1 | Filled; total grants $39,860,858 / $75,031,663; total self-help $18,983,977 / $16,155,600 | Our miss | p. 24 | `e8f650d6-7d9e-41d9-97ba-9deb4654f7fe` |
| Samford University | 2023-24 | Nothing for H1 | Filled; total grants $27,105,079 / $39,112,091; total self-help $7,633,487 / $9,547,203 | Our miss | p. 47 | `64ffa98e-3dd9-4763-a04f-e58830c8b39e` |
| University of Texas at Tyler | 2023-24 | Nothing for H1 | Filled (e.g. total grants $31,178,810 / $2,275,443). The PDF has no form fields (0 widgets); the values are flattened drawings missing from the page's text layer, so a text read sees an empty table. Read from the rendered page. | Our miss (values not in the text layer; needs the page-image path) | p. 32 | `510d4578-7b0a-42f0-a7e6-b36466f53026` |
| Beloit College | 2023-24 | Nothing for H1 | Filled; total grants $27,579,901 / $12,181,462; total self-help $4,671,771 / $3,160,616 | Our miss | p. 24 | `e21918e3-c8be-453c-9441-3cd526715d25` |
| Illinois Wesleyan University | 2023-24 | Nothing for H1 | Filled; total grants $43,035,172 / $15,977,251; total self-help $5,431,748 / $7,099,457 | Our miss | p. 45 | `803c606c-383b-44ca-ba9e-f391da00545d` |
| Gettysburg College | 2023-24 | Nothing for H1 | Filled; total grants $96,243,345 / $6,540,297; total self-help $9,102,792 / $4,728,131 | Our miss | p. 24 | `f5902dae-11e6-4763-9107-f0592fbc10b3` |
| California Polytechnic State University, San Luis Obispo | 2023-24 | Nothing for H1 | Filled (e.g. total grants $94,032,998 / $15,113,702). 0 widgets; same flattened-drawing text-layer problem as UT Tyler. | Our miss (values not in the text layer; needs the page-image path) | p. 32 | `0a0772f2-eaeb-4119-b94e-67b8853f70f2` |
| Macalester College | 2023-24 | Nothing for H1 | Filled; total grants $69,834,505 / $11,145,250; total self-help $10,313,347 / $809,152 | Our miss | p. 45 | `9c7c73f8-a46c-4cf6-9124-eff4ae67c127` |
| Oakland University | 2023-24 | Nothing for H1 | Filled; total grants $35,666,720 / $28,281,145; total self-help $15,745,449 / $17,822,383 | Our miss | p. 20 | `dfd83b3d-b055-4cc7-91a6-173c3d52d49e` |
| Northern Kentucky University | 2023-24 | Nothing for H1 | Filled; total grants $23,806,065 / $40,639,987; total self-help $16,589,935 / $29,055,105 | Our miss | p. 20 | `226e7cce-6e94-4599-92ea-ae36ffde383c` |

Totals, 20 reports:

| Cause | Reports |
|---|---:|
| Blank in the school's file | 1 |
| Unfilled automatic total | 0 |
| Our miss | 19 |
| Different year's numbering | 0 |

So 19 of 20 (95%) are our misses; the plausible range for the 217 is roughly
76% to 99%. In every one of the 19, the total rows were filled as well, so no
unfilled automatic total turned up. Stanford is stored under the 2025-26
schema label and might count as a numbering case; it would not change the
conclusion, because its H1 values were filled and unread either way. Of the
217, 201 (93%) have no H1 dollar value stored. Of the 217, 34 are served
from tier4_docling 0.3.0 (125 from 0.3.40), so part of "our miss" may be stale
extractions; the fix should split by producer version. The fix issue is #486.

### Copy questions for the owner

These depend on the results. None is decided here.

1. **Table C, financial aid "can't check" copy.** The PRD says "can't check"
   can be a blank in the school's file, an unfilled automatic total, a miss on
   our side, or a different year's numbering. The sample says 19 of 20 are our
   misses, and the three other causes together are 1 of 20. Does 2023-24
   financial aid keep the neutral four-cause sentence, say that most are our
   misses, or stay off the page for 2023-24 until the fix lands (see fix
   issue #486)?
2. **Table B, "Differs" copy.** In 8 of 10 reports the file matched our
   reading, in 1 our reading was wrong and in 1 our scope was wrong. The
   sample rules out an extraction error for those 8 but does not show why
   they differ from IPEDS (the federal side and the join were not checked). Is
   the note under Table B's "Differs" still "may be our misreading or a real
   difference", with this sample's size, or does it say more?
3. **Files that disagree with themselves.** Three reports, three different
   conflicts:
   - Virginia Commonwealth (2024-25): the by-sex table (p. 11) sums to
     21,201 / 19,572 / 4,275, which is what we used. The residency table
     (p. 12) prints 24,804 / 20,769 / 4,449 for the same cohort.
   - Texas A&M-Commerce (2023-24): the by-sex rows sum to
     8,856 / 6,865 / 1,294, which is what we used. The residency table's
     printed "Total" column reads 1,282 / 992 / 48, which leaves out the
     in-state column.
   - Louisiana Tech (2024-25, workbook): the printed totals (C117 to C119,
     8,242 / 7,478 / 2,453) are what we used. The residency rows beside them
     do not add to those totals.
   Should the page say anything about files like these, and should they be
   counted separately from "differs"?
4. **One-unit filings not marked as such.** (Answered by the launch review:
   Fairleigh Dickinson's file is university-wide and filed under two campus
   records, which is now the `shared_file` rule. The question below was asked
   before that was known.) Fairleigh Dickinson, Metropolitan Campus was read
   as one campus filed on its own; it is not in the sub-institutional list, so
   it sat in Table B. Is that a
   data question to fix before launch, and does Table B's note about left-out
   one-unit reports need to say the list may be incomplete?
5. **2023-24 financial aid count.** The text says 215; the run has 217. Use
   the run's number on the page?
