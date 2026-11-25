# Copy deck: /data-quality

Persona: researchers and counselors first, parents second. Someone who wants
to know how far a number from this archive can be trusted. Read it aloud: it
should sound like a calm person explaining what was checked and what wasn't.

Mirrors `web/src/components/DataQualityView.tsx`, `web/src/app/data-quality/page.tsx`
and `web/src/lib/data-quality.ts`. Everything is behind the launch gate
(`isDataQualityLaunched()`). Figures in `{braces}` come from the committed
snapshot. Sample results are from the hand checks of 2026-11-25 (PRD 040,
"M0 samples"). Em dashes on the page: 0.

Awaiting Anthony's read.

## Title and lede

**Data quality**

> Snapshot of {November 24, 2026}: {1,163} reports published with numbers
> across {three} years, checked against federal figures and against their own
> printed totals. Data quality here means the quality of what this archive
> publishes, not the quality of any school's own data.

Small normal-case line under it (the PRD wants the run named on the page, so the file name stays):

> Numbers from the archive's scoreboard run of {November 24, 2026}, {12:25 UTC} (file {scoreboard-20261124T122503Z.json}).

## All years at a glance

One row per year, newest first. Rates are shares of that year's published
reports, except the admissions match rate, which is a share of values
compared.

Table: published, set aside, couldn't read, not read yet, admissions match
rate, and the three "adds up" rates. Under it: *Fields stored is left out here
because 2023-24 is counted differently; see Table A.*

## Year picker

2025-26, 2024-25, 2023-24. Controls everything below.

## Notices (only when they apply)

- > {71} of the {404} published 2023-24 reports are numbered by a different
  > year's form. Some question numbers in them point at a different question
  > than the 2023-24 form's.
- > No federal admissions figures for fall 2025 yet.
- > Older form: tables mapped, not every question.

  (No year has this notice today.)

## Table A: Reports and fields stored

> How many {year} reports are published with numbers, set aside, couldn't be
> read or not read yet, and how much of each form we stored.

- > {n} reports counted. Set aside: {n} blank form, {n} too little read, {n}
  > wrong file. Not counted: {n} removed{, {n} with no file}.

  The ", {n} with no file" clause shows only when the year has reports with no
  file to read.
- > Fields stored counts the fields stored for the report as we publish it,
  > including fields recorded as unreadable or "not applicable". It measures
  > how much of the form we reached, not how many usable answers we have. The
  > {year} form has {n} questions. {For years with another form's numbering: The
  > {n} reports numbered by a different year's form have field numbers from that
  > form, whose size differs.}
- **2023-24 only:**
  > 2023-24 is counted differently. From 2024-25 on, fields stored also
  > includes values from a second reading of the same file. This year counts one
  > reading, so it reads lower partly for that reason.

Shown under each table's download button (after launch): *Download {year} table as CSV.* Then, in
small normal-case text (not the uppercase label style): *This table is licensed
CC BY 4.0. Credit collegedata.fyi.* (CC BY 4.0 is a link.)

Wide tables scroll sideways on a phone. Above each table, in small normal-case
text, only while the table is narrower than it needs (CSS only, no script):
*Scroll sideways to see every column.*

## Table B: Admissions against federal figures

> Applicants, admits and enrolled first-year students in each published report
> (CDS C1), compared with the federal figures for the same fall.

**When the year has no federal figures** (2025-26 today): right under the
heading, *No federal admissions figures for fall 2025 yet.* The table shows
dashes, and the notes about "No value", "Differs" and the size of the gap, the
left-out note and the CSV button are hidden.

Table B's two size columns, "Differs by over 2% to 10%" and "Differs by over 10%",
sit after "Differs" and show only for a snapshot in public format 2 (older
snapshots have no size). They are counts, not percentages, so the under-5 rule
has nothing to hide; the size note below shows only with them. The four notes
below show only when the year has federal figures. The
hand-check sentence also needs a covered year, at least one differing value, and
the two covered years together holding 198 to 240 differing values (90% to 110%
of the 219 in the run the sample was drawn from; the snapshot counts values,
not reports).

- > A value is compared only when the federal data has a positive figure for
  > it, and matches means within 2%. Left out: {n} reports we've marked as
  > filed for one campus or unit (federal data reports the whole institution)
  > and {n} whose school has no federal admissions figures.
- > **No value** means no usable CDS number was available to compare. The
  > school may have left it blank. We may have missed it, read it under a
  > different year's numbering, or set it aside because it failed a sanity
  > check. On its own, this table can't say which.
- > **Differs** isn't always ours. Schools sometimes report different figures
  > to the federal government than in their CDS, for example from a different
  > count date. A differing value may be our misreading or a real difference
  > between the two filings.
- > **Size of the gap** is the difference as a share of the federal figure,
  > counted by value. A gap of 2% or less is a match. "Differs by over 2% to
  > 10%" and "Differs by over 10%" split the rest, and exactly 10% counts in
  > "over 2% to 10%". A gap of over 2% to 10% may come from a different count
  > date. A gap over 10% may be a real difference between the two filings, a
  > scope mismatch such as one campus against the whole institution, a misread
  > column, or our misreading; the size alone can't say which.
- **2023-24 and 2024-25 only (hand check of 10):**
  > In a hand check of 10 differing reports (2023-24 and 2024-25, sampled on
  > November 25, 2026), 8 had the number we compared in the school's file, so
  > the difference came from the federal side or from how the two filings were
  > matched, which can include our matching. 2 were on our side: one misread and
  > one report filed for a different scope than the federal record.

Why the size note says no more: the hand check of 10 reports covers mostly small
gaps. Of its 15 differing values, 5 (in 3 reports) are over 10%: of those 3
reports, 2 (Chatham, Texas A&M-Commerce) had the number we compared in the
school's file and 1 (Fairleigh Dickinson) was our scope error. Three reports
can't say how many large gaps are ours, so the note names the possible causes
and leaves it there.

Why it says no more: the federal side wasn't checked in the sample, only
whether the number we compared is the number in the school's file. The 8 are
unexplained, not cleared.

## Table C: Do the printed totals add up?

> Whether the totals printed in each published report equal the sum of their
> own rows. The three tables are never averaged together.

- > **Enrollment** checks that undergraduates by sex sum to the total, and that
  > undergraduate plus graduate sum to the grand total. **Admissions** checks
  > that applicants, admits and enrolled by sex sum to their totals.
  > **Financial aid** checks grant and self-help totals, and need-based and
  > non-need-based, within $5; rows we didn't read count as zero once at least
  > one row is read.
- > **Adds up** means at least one of the table's sums could be checked and
  > none failed. **Off by under 2%** (enrollment, admissions) means at least
  > one sum missed, but every miss was under 2% of its printed total. **Off by
  > more**, or **doesn't add up** for financial aid, means at least one sum
  > missed by more. **Can't check** means no sum could be checked: the rows or
  > the total a sum needs weren't read, or the printed total is zero beside
  > non-zero rows.
- > Off by under 2% is usually the school's file: it mostly means a small cell,
  > such as students of unknown sex, left out of the rows while the total
  > includes it. Off by more isn't always ours either, because some printed
  > totals don't add up in the school's own file, but it is where our reading
  > errors show. Can't check can be a blank in the school's file, an unfilled
  > automatic total, a miss on our side, or a different year's numbering.
- **2023-24 only (hand check of 20):**
  > For financial aid in 2023-24: in a hand check of 20 of the reports we
  > couldn't check, sampled on November 25, 2026, 19 had the financial aid table
  > filled in and we hadn't stored it in full.

  The sample was drawn from the 217 can't-check reports in the 2026-11-25 run.
  The sentence shows only while the snapshot's 2023-24 count is within 90% to
  110% of 217 (196 to 238), so it disappears once a fix shrinks the pool, or a
  regression grows it, instead of going false.
  There is no sentence about a fix: none is merged.

## How to read this

> Some of what looks like an error is the school's. A school may leave a cell
> blank, print a total that doesn't add up, or report different figures to the
> federal government. Some is ours: we may misread a cell or map it under the
> wrong year's numbering. These tables can't always tell which, so each one
> says what its weak spots are.

> Some school files disagree with themselves, for example a residency table
> whose totals differ from the table by sex. For admissions counts we use the
> rows by sex when both men and women were read, and the printed total
> otherwise.

> A format with fewer than 5 reports in a table shows its counts but no
> percentage, because a rate over so few reports isn't meaningful. Year totals
> always show in full.

> If a number on a school's page looks wrong, open that school's page and tell
> us.

> Related: methodology, the API, and the colleges we have a CDS for.

## /coverage strings added by PRD 040

- Tile: **This year's reports on file**, "Of the {n} schools with a {previous}
  report on file, {n} also have a {current} report on file. Snapshot of {date}."
- Tile: **Colleges tracked**: "Accept federal aid and enroll undergraduates".
- Tile: **Undergrads with CDS numbers**: "Share of undergraduates at tracked
  colleges with CDS numbers on file. {n} colleges have no enrollment figure and
  are left out of both sums."
- Columns: With numbers, Found. Empty cells show an en dash (they showed em
  dashes before this review, one per row).
- After launch, beside the CSV buttons: the federal-columns note, the licensed
  columns sentence with the CC BY 4.0 link, and what the two year columns mean.
