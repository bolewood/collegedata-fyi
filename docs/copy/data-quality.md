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

## Table A, by section: Fields stored and usable answers by section

Under Table A, only for a snapshot in public format 3 and a year whose form has
a full field schema. One row per CDS section (A General information, B
Enrollment and persistence, C First-time, first-year admission, D Transfer
admission, E Academic offerings and policies, F Student life, G Annual
expenses, H Financial aid, I Instructional faculty and class size, J
Disciplinary areas of degrees conferred). Columns: questions on the form,
fields stored (median), usable answers (median), usable as a share of
questions. The share is blank (a dash) under 5 reports; a year with no reports
shows dashes for the medians.

> For each part of the {year's} form, how many questions it has and how many
> fields and usable answers a typical report has, counting the {n} published
> {year} reports numbered by that form.

("1 report" when there is one.) Under 5 reports no share is shown, and a line
says so: *Fewer than 5 reports, so no share is shown.*

- > A usable answer is a value a reader can use. Fields recorded as unreadable
  > or as "not applicable" are stored but not counted as usable; counting "not
  > applicable" would raise some sections, transfer admission especially. The
  > medians are per report and per section, so they don't add up to a report's total,
  > and not every question applies to every school, so a share of 100% isn't
  > the goal. A low number can mean the school left a section blank, that we
  > didn't reach it, or both; this table can't say which.
- {Only when some reports are numbered by another year's form:} 
  > Left out: {n} reports numbered by a different year's form, whose field
  > numbers belong to that form.
- **2023-24 only:**
  > 2023-24 is counted differently. From 2024-25 on, fields stored also
  > includes values from a second reading of the same file. This year counts one
  > reading, so it reads lower partly for that reason.

"Usable" means `value_status` `reported` and nothing else. In the 2026-11-25
run, over the 1,280 published reports numbered by their year's own form, the
stored fields were 641,995 reported, 6,594 parse errors and 3,776 "not
applicable" (0.6% of fields). "Not applicable" is a school saying a question
doesn't apply to it. It is left out because that is not an answer a reader can
use, but it is not negligible in one section: counting it would raise transfer
admission (D)'s usable median from 14 to 15 (2023-24), 25 to 27 (2024-25) and 23
to 26 (2025-26), because "not applicable" is 6% to 9% of that section's stored
fields (schools without transfer admission often mark it). It would also move
financial aid (H) by 1 in 2024-25 and 2025-26 and first-time admission (C) by 1
in 2025-26. No `missing` (empty) status is stored in the run.
Medians are over reports numbered by the year's own form, so a section's median
can never exceed its question count.

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

## Table B, more checks: Enrollment and tuition against federal figures

Under Table B, only for a snapshot in public format 4. A section head, then two
small tables with the same columns as Table B except "Values" (one value per
report): format, reports checked, matches, no value, differs, differs by over 2%
to 10%, differs by over 10%, match rate. The rate is a dash under 5 reports, in
the All formats row too.

> Two more checks of what a published report says: its total undergraduates
> (CDS B1) and its tuition (CDS G1), each compared with the federal figure.

**Undergraduate enrollment (CDS B1)**

- When the year has no federal figures for it: *No federal fall {year}
  undergraduate enrollment figures yet.* The table shows dashes and its notes
  and CSV button are hidden.
- > **Undergraduate enrollment** compares the total of all undergraduates in the
  > report (CDS B1: degree-seeking and not, full-time and part-time) with the
  > federal fall undergraduate enrollment (IPEDS table DRVEF{year}, variable
  > EFUG, fall {year}). Both count undergraduates on a fall census date, and the
  > dates can differ. A school may also count a different group of students in
  > each. {Only when some reports are numbered by another year's form:} Many of
  > the reports with no value are among the {n} numbered by a different year's
  > form, where the B1 total is harder for us to find.
- > Left out: {n} {report or reports} we've marked as filed for one campus or
  > unit and {n} whose school has no federal undergraduate enrollment figure.
  > **No value** means no usable CDS number was available to compare: the
  > school may have left it blank, or we may have missed it or set it aside.
  > **Differs** isn't always ours.

**Tuition (CDS G1)**

- When the year has none: *No federal tuition figures for the {academic year}
  academic year yet.* (2024-25 and 2025-26 today: the federal tuition for
  academic years 2025-26 and 2026-27 is not loaded.)
- > **Tuition** compares the report's tuition for all undergraduates (CDS G1:
  > the in-state figure when the school gives one, else the single private
  > figure) with the federal in-state average tuition for full-time
  > undergraduates (IPEDS table IC{year}_AY, which our federal
  > facts label COST1_{year}, variable TUITION2, academic year {academic
  > year}). The CDS form for {cds year} asks for that following year's tuition.
  > Neither includes required fees, which each lists separately. A report can
  > differ for reasons that aren't errors: per-credit or program-specific
  > pricing, a figure for a different year or group of students, or a school
  > with several rates reporting one of them. Out-of-state and first-year
  > tuition aren't compared.
- The left-out note is the same as for enrollment, ending "…no federal tuition
  figure."

A tuition of 0 is treated as no value and the other row is used (Rollins
College 2023-24: in-state 0, private 60,580, which matches). The in-state row is
preferred because a public school that fills both has put another rate in the
private row (West Chester 2023-24: private 19,290 is the out-of-state figure,
in-state 7,716). Likewise a B1 total of 0 is no value.

**Once, under both tables** (when either table has figures):

> A value is compared only when the federal data has a positive figure for it.
> Matches means within 2%; differs by over 2% to 10% and differs by over 10%
> split the rest, and exactly 10% counts in the first. This snapshot doesn't
> record which IPEDS release (final or provisional), release date or imputation
> flag each figure came from. Where a final and a provisional release both have
> a figure, the final one is used. A school's page shows the release and
> imputation for its latest federal figures, which can be a later year than the
> one compared here.

Why these two pairings: enrollment lines up well. Of the reports with both a B1
total and a federal figure (so leaving out "no value"), 90% in 2023-24 and 2024-25 are
within 2%, with a median ratio of 1.00; the table's own match rate is lower
(74% in 2023-24, 77% in 2024-25) because it counts "no value" reports too.
Tuition is noisier: 68% of the reports with both numbers match in 2023-24
(212 of 313), with differences on both sides, and the table's match rate is 49%
with "no value" counted. So the page says what can differ and does not call a
difference an error.

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
